import asyncio
from functools import partial
import threading
from typing import Callable
from logging import getLogger

from ops.ecris.data.producer_thread import producer_thread
from ops.ecris.model.device import TelnetDevice
from ops.ecris.model.measurement import Measurement

_log = getLogger(__name__)

class TelnetDataAquisition:
    def __init__(self, device: TelnetDevice) -> None:
        self.device = device
        self._loop: asyncio.AbstractEventLoop | None = None
        self._data_queue: asyncio.Queue | None = None

    async def start(self,
                    aquisition_function: Callable[[asyncio.AbstractEventLoop,
                                                   TelnetDevice], 
                                                  Measurement],
                    aquisition_rate: float) -> None:
        _log.info(f'Starting data acquisition service for "{self.device.id}"...')
        self._loop = asyncio.get_running_loop()
        self._data_queue = asyncio.Queue()
        await self.device.connect()
        aquisition_thread = partial(
            aquisition_function, self._loop, self.device)
        self._producer_thread = threading.Thread(
            target=producer_thread,
            args=(self._loop, self._data_queue, aquisition_thread, aquisition_rate),
            daemon=True)
        self._producer_thread.start()
        self._is_running = True
        _log.debug('Data aquisition service started.')

    @property
    def data_queue(self) -> asyncio.Queue | None:
        return self._data_queue

    async def stop(self):
        """Stops the service and disconnects from the device."""
        if not self._is_running:
            return
        _log.info(f'Stopping data aquisition for "{self.device.id}"...')
        
        if self.device.is_connected:
            _log.debug(f'Disconnecting device "{self.device.id}"')
            await self.device.disconnect()
        
        self._is_running = False
