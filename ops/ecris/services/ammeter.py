import asyncio
import time
from ops.ecris.devices import Ammeter
from ops.ecris.model.measurement import AverageMeasurement, ValueMeasurement
from .base_acquisition import TelnetDataAcquisitionService
from ops.ecris.operations.producers import time_average_current

class _AmmeterService(TelnetDataAcquisitionService):
    def __init__(self, ammeter: Ammeter) -> None:
        self.device: Ammeter
        super().__init__(device=ammeter)

class AverageCurrentAcquisitionService(_AmmeterService):
    def __init__(self, ammeter: Ammeter, average_rate: float = 0.33) -> None:
        self.average_rate = average_rate
        super().__init__(ammeter)

    def _acquire_data(self) -> AverageMeasurement:
        return time_average_current(self._loop, self.device, average_seconds=self.average_rate)

class CurrentAquisitionService(_AmmeterService):
    def __init__(self, ammeter: Ammeter) -> None:
        super().__init__(ammeter)

    def _acquire_data(self) -> ValueMeasurement:
        coroutine = self.device.read_data(Ammeter.DataKeys.CURRENT)
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        return ValueMeasurement(
            source=self.device.id,
            timestamp=time.time(),
            value=future.result())
