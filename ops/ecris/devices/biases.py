from typing import TypeAlias, Callable

BiasFunction: TypeAlias = Callable[[float], float]


def POSITIVE_VALUES_ONLY(current: float) -> float:
    return max(0, current)


def INVERT_VALUES(current: float) -> float:
    return -current


def POSITIVE_VALUES_ONLY_AFTER_INVERSION(current: float) -> float:
    return POSITIVE_VALUES_ONLY(INVERT_VALUES(current))
