from enum import Enum, auto, StrEnum

class Axis(Enum):
    X = 0
    Y = 1
    Z = 2
    A = 3

PERPENDICULAR_AXIS = {
    Axis.X: Axis.Y,
    Axis.Y: Axis.X,
    Axis.Z: Axis.A,
    Axis.A: Axis.Z
}

class Commands(StrEnum):
    OPEN_PROGRAM0 = 'PROG0'
    SET_RAMPING = "ACC 5 DEC 5 VEL 15 STP 100"

    @staticmethod
    def QUERY_BIT(bit: int) -> str:
        return f"?BIT({bit})"

    @staticmethod
    def DRIVE_ON(axis: Axis):
        return f"DRIVE ON {str(axis.name)}"

    @staticmethod
    def DRIVE_OFF(axis: Axis):
        return f"DRIVE OFF {str(axis.name)}"

    @staticmethod
    def MOVE(axis: Axis, value: float):
        return f"{str(axis.name)}{value}"

class Bit:
    IN_MOTION: int = 516

    @staticmethod
    def axis_clear(axis: Axis) -> int:
        return 16128 + axis.value * 32
