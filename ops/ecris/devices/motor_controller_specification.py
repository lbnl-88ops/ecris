from enum import Enum, auto, StrEnum

class Axis(Enum):
    X = auto()
    Y = auto()
    Z = auto()
    A = auto()

PERPENDICULAR_AXIS = {
    Axis.X: Axis.Y,
    Axis.Y: Axis.X,
    Axis.Z: Axis.A,
    Axis.A: Axis.Z
}

class Commands(StrEnum):
    OPEN_PROGRAM0 = 'PROG0'
    SET_RAMPING = "ACC 5 DEC 5 VEL 15 STP 100"