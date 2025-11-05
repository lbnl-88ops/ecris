from logging import getLogger
from typing import Any

from ops.ecris.drivers.device import Device
from .connected_device import _ConnectedDevice

class Ammeter(_ConnectedDevice):
    def __init__(self, connection: Device, read_key: Any,
                 name: str = 'Ammeter'):
        super().__init__(connection)
        self._read_key = read_key
        self.name = name

    async def read_current(self) -> float:
        return await self._connection.read_data(self._read_key)
