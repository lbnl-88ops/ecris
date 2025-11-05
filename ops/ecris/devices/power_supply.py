from logging import getLogger
from typing import Any

from ops.ecris.model.device import Device

_log = getLogger(__name__)

class _ConnectedDevice:
    def __init__(self, connection: Device):
        self._connection = connection

    @property
    def is_connected(self) -> bool:

        return self._connection.is_connected

    async def connect(self) -> None:
        if self.is_connected:
            _log.debug(f"Device using {self._connection.__class__.__name__} is already connected.")
            return
        _log.info(f"Connecting device via {self._connection.__class__.__name__}...")
        await self._connection.connect()

    async def disconnect(self) -> None:
        await self._connection.disconnect()

class Voltmeter(_ConnectedDevice):
    def __init__(self, connection: Device, read_key: Any):
        super().__init__(connection)
        self._read_key = read_key

    async def read_voltage(self) -> float:
        return await self._connection.read_data(self._read_key)

class VoltageSource(_ConnectedDevice):
    def __init__(self, connection: Device, set_key: Any):
        super().__init__(connection)
        self._set_key = set_key

    async def set_voltage(self, voltage: float) -> None:
        await self._connection.write_data(self._set_key, voltage)

class PowerSupply(Voltmeter, VoltageSource):
    def __init__(self, connection: Device, read_key: Any, set_key: Any):
        Voltmeter.__init__(self, connection, read_key)
        VoltageSource.__init__(self, connection, set_key)