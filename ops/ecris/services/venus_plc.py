import asyncio
from logging import getLogger
import time
from ops.ecris.data.producer_thread import producer_thread
from .base_acquisition import BaseAquisitionService
from ops.ecris.devices.venus_plc import VenusPLC
from ops.ecris.model.measurement import MultiValueMeasurement
import threading

_log = getLogger(__name__)

class PLCDataAquisitionService(BaseAquisitionService):
    def __init__(self, venus_plc: VenusPLC):
        super().__init__()
        self.venus_plc: VenusPLC = venus_plc

    async def start(self) -> None:
        _log.info(f'Starting {self.__class__.__name__}...')
        
        self._loop = asyncio.get_running_loop()
        self._producer_thread = threading.Thread(
            target=producer_thread,
            args=(self._loop, self._data_queue, self._acquire_data),
            daemon=True,
            name=f"VENUSPLCData_Producer"
        )
        self._producer_thread.start()
        self._is_running = True
        _log.debug(f'{self.__class__.__name__} started successfully.')


    async def stop(self):
        if not self._is_running:
            return
        _log.info(f'Stopping {self.__class__.__name__} for ...')
        self._is_running = False

    def _acquire_data(self) -> MultiValueMeasurement:
        coroutine = self.venus_plc.get_all_data()
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        data = future.result()
        return MultiValueMeasurement(
            source='VENUS PLC',
            timestamp=time.time(),
            values={v[0]: v[1] for v in data.values()})
