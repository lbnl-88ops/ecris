import asyncio
from logging import getLogger
import time
from ops.ecris.data.producer_thread import producer_thread
from .base_acquisition import BaseAquisitionService
from ops.ecris.drivers.venus_plc import VenusPLC
from ops.ecris.drivers.measurement import MultiValueMeasurement
import threading

_log = getLogger(__name__)


class PLCDataAquisitionService(BaseAquisitionService):
    def __init__(self, venus_plc: VenusPLC, update_interval: float = 1.0):
        super().__init__()
        self.venus_plc: VenusPLC = venus_plc
        self.update_interval = update_interval

    async def start(self) -> None:
        _log.info(f"Starting {self.__class__.__name__}...")

        self._loop = asyncio.get_running_loop()
        self._producer_thread = threading.Thread(
            target=producer_thread,
            args=(self._loop, self._data_queue, self._acquire_data),
            daemon=True,
            name=f"VENUSPLCData_Producer",
        )
        self._producer_thread.start()
        self._is_running = True
        _log.debug(f"{self.__class__.__name__} started successfully.")

    async def stop(self):
        if not self._is_running:
            return
        _log.info(f"Stopping {self.__class__.__name__} for ...")
        self._is_running = False

    def _acquire_data(self) -> MultiValueMeasurement:
        coroutine = self.venus_plc.get_all_data()
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        data = future.result()
        data_time = time.time()
        time.sleep(self.update_interval)
        return MultiValueMeasurement(
            source="VENUS PLC", timestamp=data_time, values={v[0]: v[1] for v in data.values()}
        )
