import asyncio
import time
from ops.ecris.devices import Ammeter
from ops.ecris.model.measurement import ValueMeasurement
from .base_acquisition import TelnetDataAcquisitionService
from .distributor import DataDistributor
from .processors import AveragingProcessor

class CurrentAcquisitionService(TelnetDataAcquisitionService):
    def __init__(self, ammeter: Ammeter):
        super().__init__(ammeter)
        # It creates and owns the distributor. The distributor is fed by the base class's _data_queue.
        self.distributor = DataDistributor(self._data_queue)

    async def start(self) -> None:
        await super().start()

    def _acquire_data(self) -> ValueMeasurement:
        coroutine = self.device.read_data(Ammeter.DataKeys.CURRENT)
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        return ValueMeasurement(
            source=self.device.id,
            timestamp=time.time(),
            value=future.result()
        )

class AverageCurrentService:
    def __init__(self, raw_data_source: CurrentAcquisitionService, average_rate: float = 0.33):
        input_queue = raw_data_source.distributor.subscribe()
        self._processor = AveragingProcessor(input_queue, average_rate)
        self.data_queue = self._processor.data_queue

    async def start(self):
        await self._processor.run()
