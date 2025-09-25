import asyncio
from logging import getLogger
from typing import Any

from labjack import ljm

from ops.ecris.model.device import Device

_log = getLogger(__name__)

class LabJack(Device):
    def __init__(self) -> None:
        self._connection_lock = asyncio.Lock()
        self._handle: int | None = None
        super().__init__()

    async def connect(self) -> None:
        async with self._connection_lock:
            if self.is_connected:
                _log.debug('LabJack is already connected')
                return
            self._handle = await asyncio.to_thread(ljm.openS, "T8", "usb", "ANY")
            return

    async def get_data(self, data_key: Any) -> float:
        return await super().get_data(data_key)

    async def write_data(self, data_key: Any, value: float) -> None:
        return await super().write_data(data_key, value)


    @property
    def is_connected(self) -> bool:
        return self._handle is not None
