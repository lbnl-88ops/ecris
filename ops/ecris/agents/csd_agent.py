import asyncio
import time
from logging import getLogger
from pathlib import Path

import numpy as np

from ops.ecris.devices.ammeter import Ammeter
from ops.ecris.devices.dipole import Dipole
from ops.ecris.drivers.venus_plc import VenusPLC
from ops.ecris.operations.csd.csd_operation import CSDOperation
from ops.ecris.operations.csd.parameters import CSDParameters
from ops.ecris.services.averaging import AveragingService

_log = getLogger(__name__)


class CSDAgent:
    """
    Coordinator agent for CSD and Averaging operations.

    This agent runs as a long-lived process (suitable for systemd) that:
    1. Manages the background AveragingService.
    2. Polls the PLC for CSD and Peaking requests.
    3. Triggers CSDOperations when requested, handling the pausing of averaging.
    4. Tracks manual setpoint changes for the dipole magnet.
    """

    def __init__(
        self,
        ammeter: Ammeter,
        dipole: Dipole,
        plc: VenusPLC,
        averaging_service: AveragingService,
        csd_directory: Path = Path("/data/csds/"),
        batman_scale: float = 131.0,
        params: CSDParameters = CSDParameters(),
    ):
        """
        Initializes the CSDAgent.

        Args:
            ammeter: The ammeter device.
            dipole: The dipole magnet device.
            plc: The VenusPLC instance.
            averaging_service: The pausable averaging service.
            csd_directory: Directory where CSD results are saved.
            batman_scale: Scaling factor for the PLC batman_i_set variable.
            params: Default CSD parameters.
        """
        self._ammeter = ammeter
        self._dipole = dipole
        self._plc = plc
        self._averaging_service = averaging_service
        self._csd_directory = csd_directory
        self._batman_scale = batman_scale
        self._params = params

        self._last_batman_i = 0.0
        self._is_running = False

    async def run(self) -> None:
        """
        The main event loop of the CSDAgent.
        """
        _log.info("CSDAgent starting.")
        self._is_running = True

        # Ensure directory exists
        if not self._csd_directory.exists():
            self._csd_directory.mkdir(parents=True, exist_ok=True)

        # Initialize background averaging
        await self._averaging_service.start()

        # Initialize tracking of batman current
        try:
            raw_i = await self._plc.read_data(VenusPLC.DataKeys.BATMAN_I_SET)
            self._last_batman_i = raw_i / self._batman_scale
        except Exception as e:
            _log.error(f"Failed to initialize batman setpoint tracking: {e}")

        while self._is_running:
            try:
                # 1. Poll for CSD requests
                request_type = await self._check_csd_requests()
                if request_type == 1:
                    await self._handle_csd_request()
                elif request_type == 2:
                    await self._handle_custom_csd_request()

                # 2. Poll for Batman setpoint changes
                await self._handle_batman_changes()

                # 3. Poll for Peaking requests (placeholder)
                await self._check_peaking_requests()

                # Polling interval
                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                _log.error(f"Error in CSDAgent main loop: {e}", exc_info=True)
                await asyncio.sleep(1)

        await self._averaging_service.stop()
        _log.info("CSDAgent stopped.")

    async def _check_csd_requests(self) -> int:
        """Checks PLC for standard or custom CSD requests."""
        if await self._plc.read_data(VenusPLC.DataKeys.CSD_REQUEST):
            return 1
        if await self._plc.read_data(VenusPLC.DataKeys.CSD_CUSTOM_REQUEST):
            return 2
        return 0

    async def _handle_csd_request(self) -> None:
        _log.info("Handling standard CSD request.")
        await self._plc.write_data(VenusPLC.DataKeys.CSD_IN_PROGRESS, 1.0)
        try:
            op = CSDOperation(
                self._ammeter,
                self._dipole,
                self._plc,
                self._averaging_service,
                params=self._params,
                batman_scale=self._batman_scale,
            )
            result = await op.run()
            result.save(self._csd_directory)
        finally:
            await self._plc.write_data(VenusPLC.DataKeys.CSD_IN_PROGRESS, 0.0)

    async def _handle_custom_csd_request(self) -> None:
        _log.info("Handling custom CSD request.")
        await self._plc.write_data(VenusPLC.DataKeys.CSD_CUSTOM_IN_PROGRESS, 1.0)
        try:
            mq_min = await self._plc.read_data(VenusPLC.DataKeys.CSD_MQ_MIN)
            mq_max = await self._plc.read_data(VenusPLC.DataKeys.CSD_MQ_MAX)
            n_steps = int(await self._plc.read_data(VenusPLC.DataKeys.CSD_NUM_POINTS))

            custom_params = CSDParameters(mq_min=mq_min, mq_max=mq_max, n_steps=n_steps)
            op = CSDOperation(
                self._ammeter,
                self._dipole,
                self._plc,
                self._averaging_service,
                params=custom_params,
                batman_scale=self._batman_scale,
            )
            result = await op.run()
            result.save(self._csd_directory)
        finally:
            await self._plc.write_data(VenusPLC.DataKeys.CSD_CUSTOM_IN_PROGRESS, 0.0)

    async def _handle_batman_changes(self) -> None:
        """Detects changes in the PLC setpoint and ramps the magnet."""
        raw_req = await self._plc.read_data(VenusPLC.DataKeys.BATMAN_I_SET)
        i_req = raw_req / self._batman_scale

        if abs(i_req - self._last_batman_i) > 0.001:  # Threshold for change
            _log.info(f"Batman setpoint change: {self._last_batman_i:.3f}A -> {i_req:.3f}A")

            # Replicate legacy logic for ramping
            if abs(i_req - self._last_batman_i) > 1.0:
                await self._ramp_slowly(self._last_batman_i, i_req)
            else:
                await self._dipole.set_current(i_req)

            self._last_batman_i = i_req

    async def _ramp_slowly(self, i_start: float, i_end: float) -> None:
        """Internal helper for slow manual ramping."""
        diff = abs(i_start - i_end)
        n_steps = int(np.ceil(diff)) * self._params.slow_ramp_density
        if n_steps < 2:
            await self._dipole.set_current(i_end)
            return

        steps = np.linspace(i_start, i_end, n_steps)
        for i_req in steps:
            await self._dipole.set_current(i_req)
            # Match legacy 'pacing' reads
            await self._ammeter.read_current()
            await self._dipole.read_field()

    async def _check_peaking_requests(self) -> None:
        """Polls for peaking requests (placeholder)."""
        if await self._plc.read_data(VenusPLC.DataKeys.PEAKING_REQUEST):
            _log.warning("Peaking request detected but feature is not yet implemented.")
            # Clear request to avoid repeated warnings
            # await self._plc.write_data(VenusPLC.DataKeys.PEAKING_REQUEST, 0.0)
