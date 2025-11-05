from logging import getLogger

from ops.ecris.drivers.device import Device

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