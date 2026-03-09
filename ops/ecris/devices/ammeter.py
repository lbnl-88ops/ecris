from typing import Any

from ops.ecris.drivers import DataSource

from .base import _LogicalDeviceBase
from .biases import BiasFunction


class Ammeter(_LogicalDeviceBase):
    def __init__(self, connection: DataSource, read_key: Any, name: str = "Ammeter"):
        super().__init__(connection)
        self._read_key = read_key
        self.name = name

    async def read_current(self) -> float:
        return await self._connection.read_data(self._read_key)


class BiasedAmmeter(Ammeter):
    """An ammeter that applies a bias function to each raw reading.

    Commonly used with ``DataKeys.VOLTAGE`` (e.g. from an SCPI driver) when the
    physical current signal is represented as a voltage on the instrument.  In
    that case supply a ``bias_function`` such as ``SCALE_VALUE(factor)`` from
    ``ops.ecris.devices.biases`` to convert the raw voltage reading into the
    desired engineering units before the value is returned by ``read_current``.
    """

    def __init__(self, connection: DataSource, read_key: Any, bias_function: BiasFunction):
        super().__init__(connection, read_key)
        self._bias_function = bias_function

    async def read_current(self) -> float:
        raw_current = await super().read_current()
        return self._bias_function(raw_current)
