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

MID_POINT_OFFSETS = {Axis.X: 30.18, 
                     Axis.Y: 36.50, 
                     Axis.Z: 31.75, 
                     Axis.A: 31.75} 

class Bit:
    IN_MOTION: int = 516

    @staticmethod
    def AXIS_CLEAR(axis: Axis) -> int:
        return 16128 + axis.value * 32

    @staticmethod
    def KILL_ALL_MOVES(axis: Axis) -> int:
        return 8467 + axis.value * 32

class Commands(StrEnum):
    OPEN_PROGRAM0 = 'PROG0'
    SET_RAMPING = "ACC 5 DEC 5 VEL 15 STP 100"

    @staticmethod
    def QUERY_BIT(bit: int) -> str:
        return f"?BIT({bit})"

    @staticmethod
    def CLEAR_BIT(bit: int) -> str:
        return f"CLR BIT({bit})"
    
    @staticmethod
    def SET_BIT(bit: int) -> str:
        return f"SET BIT({bit})"

    @staticmethod
    def DRIVE_ON(axis: Axis):
        return f"DRIVE ON {str(axis.name)}"

    @staticmethod
    def DRIVE_OFF(axis: Axis):
        return f"DRIVE OFF {str(axis.name)}"

    @staticmethod
    def MOVE(axis: Axis, value: float):
        return f"{str(axis.name)}{value}"

    @staticmethod
    def RELATIVE_MOVE(axis: Axis, value: float):
        return f"{str(axis.name)}/{value}"

    @staticmethod
    def RESET_AXIS(axis: Axis):
        return f"RES AXIS{str(axis.value)}"

    @staticmethod
    def CHECK_IN_MOTION() -> str:
        return Commands.QUERY_BIT(Bit.IN_MOTION)

    @staticmethod
    def CHECK_PERPENDICULAR_AXIS_CLEAR(axis: Axis) -> str:
        return Commands.QUERY_BIT(Bit.AXIS_CLEAR(PERPENDICULAR_AXIS[axis]))
