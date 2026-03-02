import asyncio
import time
from abc import ABC
from logging import getLogger

import numpy as np

from ops.ecris.devices.ammeter import Ammeter
from ops.ecris.devices.deflection_plate_controller import DeflectionPlateController
from ops.ecris.devices.motor_controller import MotorController

from .parameters import LinearScanParameters

_log = getLogger(__name__)


class LinearEmittanceScan(ABC):
    _scan_lock = asyncio.Lock()

    def __init__(
        self,
        motor: MotorController,
        ammeter: Ammeter,
        deflection_plate_controller: DeflectionPlateController,
        scan_params: LinearScanParameters,
    ):
        self._motor = motor
        self._ammeter = ammeter
        self._deflection_plate_controller = deflection_plate_controller
        self.params = scan_params

    @property
    def position_array(self) -> np.ndarray:
        return np.arange(
            self.params.position_min,
            self.params.position_max + self.params.position_step,
            self.params.position_step,
        )

    @property
    def divergence_array(self) -> np.ndarray:
        return np.arange(
            self.params.divergence_min,
            self.params.divergence_max + self.params.divergence_step,
            self.params.divergence_step,
        )

    async def _connect_all_devices(self) -> None:
        _log.info("Connecting devices...")
        await asyncio.gather(
            self._motor.connect(),
            self._ammeter.connect(),
            self._deflection_plate_controller.connect(),
        )
        _log.info("All devices connected.")

    async def _disconnect_all_devices(self) -> None:
        _log.info("Disconnecting all devices...")
        await asyncio.gather(
            self._motor.disconnect(),
            self._ammeter.disconnect(),
            self._deflection_plate_controller.disconnect(),
        )
        _log.info("All devices disconnected.")

    async def _scan_divergences(self, divergences: np.ndarray) -> np.ndarray:

        divergence_trace = np.zeros_like(divergences)
        for j, divergence in enumerate(divergences):
            _log.debug(f"  Setting divergence to {divergence:.4f} rad")
            start = time.perf_counter()
            await self._deflection_plate_controller.set_divergence(divergence)

            _log.info(f"Divergence set in {start - time.perf_counter()}")

            total_current = []
            start = time.perf_counter()
            for _ in range(self.params.samples_per_point):
                current_reading = await self._ammeter.read_current()
                total_current.append(current_reading)
            _log.info(f"Samples taken in {start - time.perf_counter()}")
            mean_current = np.mean(total_current)
            divergence_trace[j] = mean_current
            _log.debug(
                f"  -> Collected {self.params.samples_per_point} samples. "
                f"Averaged current: {mean_current:.4e} A"
            )
        return divergence_trace

    async def run(self) -> np.ndarray:
        """
        Executes the emittance scan, collecting data and returning it as a 2D numpy array.
        """
        async with self._scan_lock:
            start_time = time.monotonic()

            n_positions = len(self.position_array)
            n_divergences = len(self.divergence_array)
            beam_trace = np.zeros((n_divergences, n_positions))

            _log.info(
                f"Starting emittance scan for axis {self.params.axis.name}: "
                f"{n_positions} positions x {n_divergences} divergences "
                f"({n_positions * n_divergences} total points)."
            )
            _log.info(f"Sampling {self.params.samples_per_point} points per measurement.")

            try:
                await self._connect_all_devices()
                await self._motor.center_axis(self.params.axis)

                for i, position in enumerate(self.position_array):
                    _log.info(f"Processing position {i + 1}/{n_positions}: {position:.3f} mm")
                    _log.debug(
                        f"Moving to position {position:.3f} on axis {self.params.axis.name}"
                    )
                    await self._motor.move_to_position(self.params.axis, position)
                    beam_trace[:, i] = await self._scan_divergences(self.divergence_array)
                await self._motor.move_axis_to_positive_eof(self.params.axis)
                await self._deflection_plate_controller.set_divergence(0)
                duration = time.monotonic() - start_time
                _log.info(f"Emittance scan finished successfully in {duration:.2f} seconds.")
                return beam_trace

            finally:
                # --- Ensure devices are always disconnected, even if an error occurs ---
                await self._disconnect_all_devices()
