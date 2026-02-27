import asyncio
import time
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path

import numpy as np

from ops.ecris.devices.ammeter import Ammeter
from ops.ecris.devices.dipole import Dipole
from ops.ecris.drivers.scpi_driver import SCPIDriver
from ops.ecris.drivers.venus_plc import VenusPLC
from ops.ecris.services.averaging import AveragingService

from .parameters import CSDParameters

_log = getLogger(__name__)


@dataclass
class CSDResult:
    """
    Data container for the results of a Charge State Distribution (CSD) sweep.
    """

    timestamps: np.ndarray
    dipole_currents: np.ndarray
    magnetic_fields: np.ndarray
    faraday_cup_currents: np.ndarray
    extraction_voltage: float
    start_time: float
    duration: float

    def save(self, directory: Path) -> Path:
        """
        Saves the results to a file in the legacy space-delimited format.

        Args:
            directory: The directory to save the file in.

        Returns:
            The path to the saved file.
        """
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)

        t_str = str(int(self.start_time))
        file_path = directory / f"csd_{t_str}"

        with open(file_path, "w") as f:
            for i in range(len(self.timestamps)):
                # Match legacy format: "%.3f %.3f %.8f %.5e\n"
                f.write(
                    "%.3f %.3f %.8f %.5e\n"
                    % (
                        self.timestamps[i],
                        self.dipole_currents[i],
                        self.magnetic_fields[i],
                        self.faraday_cup_currents[i],
                    )
                )

        _log.info(f"CSD data saved to {file_path}")
        return file_path


class CSDOperation:
    """
    Operation that performs a Charge State Distribution (CSD) sweep.

    This operation coordinates the dipole magnet (via LabJack) and the ammeter
    (via Keithley) to sweep through a range of M/Q values, recording the
    resulting beam current. It faithfully replicates the logic of the legacy
    00_operationFastCSD.py script.
    """

    def __init__(
        self,
        ammeter: Ammeter,
        dipole: Dipole,
        plc: VenusPLC,
        averaging_service: AveragingService,
        params: CSDParameters = CSDParameters(),
        batman_scale: float = 131.0,
    ):
        """
        Initializes the CSDOperation.

        Args:
            ammeter: The ammeter device for reading beam current.
            dipole: The dipole magnet device for setting magnetic field.
            plc: The PLC for reading parameters and setting status.
            averaging_service: The service to pause during the sweep.
            params: Configuration parameters for the sweep.
            batman_scale: Scaling factor for the batman_i_set PLC variable.
        """
        self._ammeter = ammeter
        self._dipole = dipole
        self._plc = plc
        self._averaging_service = averaging_service
        self._params = params
        self._batman_scale = batman_scale

    async def run(self) -> CSDResult:
        """
        Executes the CSD sweep operation.

        Returns:
            A CSDResult object containing the collected data.
        """
        t_all_start = time.time()
        _log.info("Starting Fast CSD operation.")

        # 1. Pre-flight checks and preparation
        was_in = await self._plc.read_data(VenusPLC.DataKeys.FARADAY_CUP_IN)
        if not was_in:
            _log.info("Faraday cup is out; inserting for CSD.")
            await self._plc.write_data(VenusPLC.DataKeys.FARADAY_CUP_IN, 1.0)

        # Save datasheet (legacy requirement)
        await self._save_datasheet(str(int(t_all_start)))

        v_ext = await self._plc.read_data(VenusPLC.DataKeys.EXTRACTION_VOLTAGE)
        b_start = await self._dipole.read_field()

        # Read current setpoint and scale to Amps
        raw_i_start = await self._plc.read_data(VenusPLC.DataKeys.BATMAN_I_SET)
        i_start = raw_i_start / self._batman_scale

        # Calculate sweep bounds in Amps
        i_low = (self._params.dipole_alpha / self._params.dipole_slope) * np.sqrt(
            self._params.mq_min * v_ext
        )
        i_high = (self._params.dipole_alpha / self._params.dipole_slope) * np.sqrt(
            self._params.mq_max * v_ext
        )

        # Clamp to safety limits
        i_low = min(i_low, self._params.i_max_clamp)
        i_high = min(i_high, self._params.i_max_clamp)

        # 2. Pause the background averaging service
        await self._averaging_service.pause()

        try:
            # 3. Perform a single auto-zero before the sweep
            await self._perform_autozero()

            # 4. Slow ramp to the starting current
            _log.info(f"Ramping magnet from {i_start:.3f}A to {i_low:.3f}A.")
            await self._changeslow(i_start, i_low, wait_time=1.0)

            # 5. Wait for Faraday cup to settle if it was just inserted
            if not was_in:
                elapsed = time.time() - t_all_start
                wait_needed = self._params.settle_time - elapsed
                if wait_needed > 0:
                    _log.debug(f"Waiting {wait_needed:.2f}s for Faraday cup settle.")
                    await asyncio.sleep(wait_needed)

            # 6. Perform the Square-Root Sweep
            _log.info(f"Performing √I sweep from {i_low:.3f}A to {i_high:.3f}A.")
            n = self._params.n_steps
            # ipoints = np.sqrt(np.linspace(Ilow*Ilow,Ihigh*Ihigh,npoints))
            i_points = np.sqrt(np.linspace(i_low**2, i_high**2, n))

            timestamps = np.zeros(n)
            dipole_currents = i_points
            magnetic_fields = np.zeros(n)
            faraday_cup_currents = np.zeros(n)

            for i in range(n):
                ireq = i_points[i]
                await self._dipole.set_current(ireq)

                # High-speed sequential reads
                faraday_cup_currents[i] = await self._ammeter.read_current()
                magnetic_fields[i] = await self._dipole.read_field()
                timestamps[i] = time.time()

            _log.info("Sweep complete. Returning to original state.")

            # 7. Retract Faraday cup if it was out originally
            if not was_in:
                _log.info("Retracting Faraday cup.")
                await self._plc.write_data(VenusPLC.DataKeys.FARADAY_CUP_IN, 0.0)

            # 8. Slow ramp back to the original setpoint
            await self._changeslow(i_points[-1], i_start, wait_time=0.0)

            # 9. Closed-loop field reset
            _log.info(f"Restoring magnetic field to {b_start:.5f}T.")
            await self._resetbatman(b_start, i_start)

        finally:
            # 10. Resume background averaging
            await self._averaging_service.resume()

        duration = time.time() - t_all_start
        _log.info(f"Fast CSD operation completed in {duration:.1f}s.")

        return CSDResult(
            timestamps=timestamps,
            dipole_currents=dipole_currents,
            magnetic_fields=magnetic_fields,
            faraday_cup_currents=faraday_cup_currents,
            extraction_voltage=v_ext,
            start_time=t_all_start,
            duration=duration,
        )

    async def _changeslow(self, i_start: float, i_end: float, wait_time: float = 1.0):
        """
        Ramps the magnet current slowly between two points.
        """
        # ipts = np.linspace(istart,iend,int(np.ceil(np.abs(istart-iend)))*3)
        diff = abs(i_start - i_end)
        n_steps = int(np.ceil(diff)) * self._params.slow_ramp_density

        if n_steps < 2:
            await self._dipole.set_current(i_end)
        else:
            steps = np.linspace(i_start, i_end, n_steps)
            for i_req in steps:
                await self._dipole.set_current(i_req)
                # Reads are used to pace the ramp in legacy code
                await self._ammeter.read_current()
                await self._dipole.read_field()

        if wait_time > 0:
            await asyncio.sleep(wait_time)

    async def _resetbatman(self, b_goal: float, i_start: float):
        """
        Performs a closed-loop reset of the magnet field.
        """
        t_start = time.time()
        i_next = i_start
        while time.time() < t_start + self._params.field_reset_timeout:
            b_now = await self._dipole.read_field()
            if b_now < b_goal:
                i_next += self._params.field_reset_step
            elif b_now > b_goal:
                i_next -= self._params.field_reset_step
            else:
                break
            await self._dipole.set_current(i_next)
            # Yield to allow other tasks to run during the timeout loop
            await asyncio.sleep(0.01)

    async def _perform_autozero(self) -> None:
        """Sends a single auto-zero command to the ammeter."""
        connection = self._ammeter._connection
        if hasattr(connection, "send_silent_command"):
            await connection.send_silent_command(SCPIDriver.Commands.AUTOZERO_ONCE)

    async def _save_datasheet(self, t_str: str):
        """
        Saves a snapshot of all PLC variables to a datasheet file.
        """
        try:
            # We need a directory. I'll use a default or pass it in.
            # For now, let's assume we use /data/csds as in legacy.
            directory = Path("/data/csds/")
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)

            file_path = directory / f"dsht_{t_str}"
            _log.info(f"Saving datasheet to {file_path}")

            all_data = await self._plc.get_all_data()
            with open(file_path, "w") as f:
                for idx, (name, value) in all_data.items():
                    # Legacy format: "%4i %.5e %s\n"
                    f.write("%4i %.5e %s\n" % (idx, value, name))
        except Exception as e:
            _log.error(f"Failed to save datasheet: {e}")
