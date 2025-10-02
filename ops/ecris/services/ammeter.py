import asyncio
from logging import getLogger
import time
from ops.ecris.devices import Ammeter
from ops.ecris.model.measurement import ValueMeasurement
from .base_acquisition import TelnetDataAcquisitionService
from .distributor import DataDistributor
from .processors import AveragingProcessor

_log = getLogger(__name__)

class CurrentAcquisitionService(TelnetDataAcquisitionService):
    def __init__(self, ammeter: Ammeter):
        super().__init__(ammeter)
        # Distributer for current data
        self.distributor = DataDistributor(self._data_queue)
        self._distributor_task: asyncio.Task | None = None

    async def start(self) -> None:
        await super().start()
        self._distributor_task = asyncio.create_task(self.distributor.run())

    async def stop(self):
        if self._distributor_task and not self._distributor_task.done():
            self._distributor_task.cancel()
            await asyncio.gather(self._distributor_task, return_exceptions=True)
        await super().stop()

    def _acquire_data(self) -> ValueMeasurement:
        coroutine = self.device.read_data(Ammeter.DataKeys.CURRENT)
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        data = future.result()
        return ValueMeasurement(
            source=self.device.id,
            timestamp=time.time(),
            value=data
        )

class AverageCurrentService:
    def __init__(self, raw_data_source: CurrentAcquisitionService, average_rate: float = 0.33):
        input_queue = raw_data_source.distributor.subscribe()
        self._processor = AveragingProcessor(input_queue, average_rate)
        self.data_queue = self._processor.data_queue

    async def start(self):
        await self._processor.run()
