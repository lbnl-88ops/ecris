import asyncio
from functools import partial
import threading
from typing import Callable
from logging import getLogger

from ops.ecris.data.producer_thread import producer_thread
from ops.ecris.model.device import TelnetDevice
from ops.ecris.model.measurement import Measurement

_log = getLogger(__name__)

class TelnetDataAquisitionService:
    def __init__(self, device: TelnetDevice) -> None:
        self.device = device
        self._loop: asyncio.AbstractEventLoop | None = None
        self._data_queue: asyncio.Queue | None = None

    def _aquire_data(self) -> Measurement:
        raise NotImplementedError

    async def start(self, aquisition_rate: float) -> None:
        _log.info(f'Starting data acquisition service for "{self.device.id}"...')
        self._loop = asyncio.get_running_loop()
        self._data_queue = asyncio.Queue()
        await self.device.connect()
        self._producer_thread = threading.Thread(
            target=producer_thread,
            args=(self._loop, self._data_queue, self._aquire_data, aquisition_rate),
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
