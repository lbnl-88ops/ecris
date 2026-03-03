from logging import getLogger

from ops.ecris.drivers.base import Connectable, DataSource

_log = getLogger(__name__)


class _LogicalDeviceBase:
    def __init__(self, connection: DataSource):
        self._connection = connection

    @property
    def is_connected(self) -> bool:
        """
        Checks if the underlying driver is connectable and connected.
        Returns True for static (non-connectable) sources.
        """
        if isinstance(self._connection, Connectable):
            return self._connection.is_connected
        return True  # Static sources are always "connected"

    async def connect(self) -> None:
        """Connects the underlying driver, if it is connectable."""
        if isinstance(self._connection, Connectable):
            await self._connection.connect()

    async def disconnect(self) -> None:
        """Disconnects the underlying driver, if it is connectable."""
        if isinstance(self._connection, Connectable):
            await self._connection.disconnect()

