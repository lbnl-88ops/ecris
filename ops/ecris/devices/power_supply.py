from logging import getLogger
from typing import Any, Callable

from ops.ecris.drivers import DataSource
from .base import _LogicalDeviceBase

_log = getLogger(__name__)


class Voltmeter(_LogicalDeviceBase):
    def __init__(self, connection: DataSource, read_key: Any):
        super().__init__(connection)
        self._read_key = read_key

    async def read_voltage(self) -> float:
        return await self._connection.read_data(self._read_key)


class VoltageSource(_LogicalDeviceBase):
    def __init__(self, connection: DataSource, set_key: Any):
        super().__init__(connection)
        self._set_key = set_key

    async def set_voltage(self, voltage: float) -> None:
        await self._connection.write_data(self._set_key, voltage)


class PowerSupply(Voltmeter, VoltageSource):
    def __init__(self, connection: DataSource, read_key: Any, set_key: Any):
        Voltmeter.__init__(self, connection, read_key)
        VoltageSource.__init__(self, connection, set_key)


class BiasedVoltageSource(VoltageSource):
    def __init__(
        self, connection: DataSource, set_key: Any, bias_function: Callable[[float], float]
    ):
        super().__init__(connection, set_key)
        self._bias_function = bias_function

    async def set_voltage(self, voltage: float) -> None:
        return await super().set_voltage(self._bias_function(voltage))
