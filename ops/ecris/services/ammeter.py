import asyncio
from logging import getLogger
import time
from ops.ecris.devices import Ammeter
from ops.ecris.drivers.device import TelnetDevice
from ops.ecris.drivers.measurement import ValueMeasurement
from .base_acquisition import TelnetDataAcquisitionService
from .distributor import DataDistributor
from .processors import AveragingProcessor

_log = getLogger(__name__)

class CurrentAcquisitionService(TelnetDataAcquisitionService):
    def __init__(self, ammeter: Ammeter):
        if not isinstance(ammeter._connection, TelnetDevice):
            raise ValueError('Ammeter must use telnet device connection')
        super().__init__(ammeter._connection)
        # Distributer for current data
        self._distributor = DataDistributor(self._data_queue)
        self._distributor_task: asyncio.Task | None = None
        self._ammeter = ammeter

    async def start(self) -> None:
        await super().start()
        self._distributor_task = asyncio.create_task(self._distributor.run())

    def subscribe(self) -> asyncio.Queue:
        queue = self._distributor.subscribe()
        _log.debug(f'New subscriber to {self.__class__.__name__}, total subscribers {self._distributor.n_subscribers}')
        return queue

    async def stop(self):
        if self._distributor_task and not self._distributor_task.done():
            self._distributor_task.cancel()
            await asyncio.gather(self._distributor_task, return_exceptions=True)
        await super().stop()

    def _acquire_data(self) -> ValueMeasurement:
        coroutine = self._ammeter.read_current()
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        data = future.result()
        return ValueMeasurement(
            source=self.device.id,
            timestamp=time.time(),
            value=data
        )

class AverageCurrentService:
    def __init__(self, raw_data_source: CurrentAcquisitionService, average_rate: float = 0.33):
        input_queue = raw_data_source._distributor.subscribe()
        self._processor = AveragingProcessor(input_queue, average_rate)
        self.data_queue = self._processor.data_queue

    async def start(self):
        await self._processor.run()
