import abc
import asyncio
import threading
from logging import getLogger
from typing import Any

from ops.ecris.data.producer_thread import producer_thread
from ops.ecris.drivers.device import TelnetDevice
from ops.ecris.drivers.measurement import Measurement

_log = getLogger(__name__)

class BaseAquisitionService(abc.ABC):
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._data_queue = asyncio.Queue()
    
    @abc.abstractmethod
    def _acquire_data(self) -> Any:
        raise NotImplementedError

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()

    @property
    def data_queue(self) -> asyncio.Queue:
        return self._data_queue

class TelnetDataAcquisitionService(BaseAquisitionService):
    def __init__(self, device: TelnetDevice) -> None:
        self.device = device
        super().__init__()

    @abc.abstractmethod
    def _acquire_data(self) -> Measurement:
        raise NotImplementedError

    async def start(self) -> None:
        _log.info(f'Starting {self.__class__.__name__} for "{self.device.id}"...')
        
        self._loop = asyncio.get_running_loop()
        await self.device.connect()
        self._producer_thread = threading.Thread(
            target=producer_thread,
            args=(self._loop, self._data_queue, self._acquire_data),
            daemon=True,
            name=f"{self.device.id}_Producer"
        )
        self._producer_thread.start()
        self._is_running = True
        _log.debug(f'{self.__class__.__name__} started successfully.')

    async def stop(self):
        if not self._is_running:
            return
        _log.info(f'Stopping {self.__class__.__name__} for "{self.device.id}"...')
        if self.device.is_connected:
            _log.debug(f'Disconnecting device "{self.device.id}"')
            await self.device.disconnect()
        self._is_running = False
