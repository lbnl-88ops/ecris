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
        pass

    @property
    def momentum_array(self) -> np.ndarray:
        pass

    async def run(self) -> np.ndarray:
        pass
