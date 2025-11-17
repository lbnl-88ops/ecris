from logging import getLogger
from typing import Any, Callable

from ops.ecris.drivers import DataSource
from .base import _LogicalDeviceBase


def POSITIVE_VALUES_ONLY(current: float) -> float:
    return max(0, current)


def INVERT_VALUES(current: float) -> float:
    return -current


def POSITIVE_VALUES_ONLY_AFTER_INVERSION(current: float) -> float:
    return POSITIVE_VALUES_ONLY(INVERT_VALUES(current))


class Ammeter(_LogicalDeviceBase):
    def __init__(self, connection: DataSource, read_key: Any, name: str = "Ammeter"):
        super().__init__(connection)
        self._read_key = read_key
        self.name = name

    async def read_current(self) -> float:
        return await self._connection.read_data(self._read_key)


class BiasedAmmeter(Ammeter):
    def __init__(
        self, connection: DataSource, read_key: Any, bias_function: Callable[[float], float]
    ):
        super().__init__(connection, read_key)
        self._bias_function = bias_function

    async def read_current(self) -> float:
        raw_current = await super().read_current()
        return self._bias_function(raw_current)
