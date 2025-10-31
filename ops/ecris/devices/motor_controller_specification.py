from enum import Enum, auto, StrEnum


class Axis(Enum):
    VenusX = "X"
    VenusY = "Y"
    AcerX = "Z"
    AcerY = "A"


PERPENDICULAR_AXIS = {
    Axis.VenusX: Axis.VenusY,
    Axis.VenusY: Axis.VenusX,
    Axis.AcerX: Axis.AcerY,
    Axis.AcerY: Axis.AcerX,
}

_AXIS_BIT_MAP = {
    Axis.VenusX: 0,
    Axis.VenusY: 1,
    Axis.AcerX: 2,
    Axis.AcerY: 3,
}

MID_POINT_OFFSETS = {Axis.VenusX: 30.18, Axis.VenusY: 36.50, Axis.AcerX: 31.75, Axis.AcerY: 31.75}


class Bit:
    IN_MOTION: int = 516

    @staticmethod
    def AXIS_CLEAR(axis: Axis) -> int:
        return 16128 + _AXIS_BIT_MAP[axis] * 32

    @staticmethod
    def KILL_ALL_MOVES(axis: Axis) -> int:
        return 8467 + _AXIS_BIT_MAP[axis] * 32

    @staticmethod
    def POSITION_BIT(axis: Axis) -> int:
        return 12288 + _AXIS_BIT_MAP[axis] * 256


class Commands(StrEnum):
    GET_FIRMWARE_VERSION = "VER"
    GET_ATTACHMENTS = "ATTACH"
    OPEN_PROGRAM0 = "PROG0"
    SET_RAMPING = "ACC 5 DEC 5 VEL 15 STP 100"
    GET_SCALE = "SCALE"

    @staticmethod
    def GET_POSITION(axis: Axis) -> str:
        return f"?P({Bit.POSITION_BIT(axis)})"

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
        return f"DRIVE ON {str(axis.value)}"

    @staticmethod
    def DRIVE_OFF(axis: Axis):
        return f"DRIVE OFF {str(axis.value)}"

    @staticmethod
    def MOVE(axis: Axis, value: float):
        return f"{str(axis.value)}{value}"

    @staticmethod
    def RELATIVE_MOVE(axis: Axis, value: float):
        return f"{str(axis.value)}/{value}"

    @staticmethod
    def RESET_AXIS(axis: Axis):
        return f"RES AXIS{str(_AXIS_BIT_MAP[axis])}"

    @staticmethod
    def CHECK_IN_MOTION() -> str:
        return Commands.QUERY_BIT(Bit.IN_MOTION)

    @staticmethod
    def CHECK_PERPENDICULAR_AXIS_CLEAR(axis: Axis) -> str:
        return Commands.QUERY_BIT(Bit.AXIS_CLEAR(PERPENDICULAR_AXIS[axis]))
