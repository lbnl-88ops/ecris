from dataclasses import dataclass

from ops.ecris.devices.motor_controller_specification import Axis

CAPACITOR_PLATE_DISTANCE_IN_M = 0.0189992
CAPACITOR_LENGTH_IN_M = 0.1199896


@dataclass
class LinearScanParameters:
    axis: Axis
    position_min: float
    position_max: float
    position_step: float

    divergence_min: float
    divergence_max: float
    divergence_step: float

    samples_per_point: int = 2000
    d = CAPACITOR_PLATE_DISTANCE_IN_M
    L = CAPACITOR_LENGTH_IN_M
