import asyncio
from abc import ABC
from logging import getLogger
import numpy as np

from .parameters import LinearScanParameters
from ops.ecris.devices.motor_controller import MotorController
from ops.ecris.devices.ammeter import Ammeter
from ops.ecris.devices.deflection_plate_controller import DeflectionPlateController

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
        self._results = []

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

    async def run(self) -> np.ndarray:
        positions = self.position_array
        divergences = self.divergence_array

        m = len(divergences)
        n = len(positions)
        beam_trace = np.zeros((m, n))

        for i, position in enumerate(positions):
            await self._motor.move_to_position(self.params.axis, position)
            position_trace = np.zeros((m,))
            for j, divergence in enumerate(divergences):
                await self._deflection_plate_controller.set_divergence(divergence)
                total_current = []
                for _ in range(self.params.samples_per_point):
                    total_current.append(await self._ammeter.read_current())
                position_trace[j] = np.mean(total_current)
            beam_trace[:, i] = position_trace
        return beam_trace
