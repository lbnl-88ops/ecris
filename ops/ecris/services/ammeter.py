from ops.ecris.devices import Ammeter
from ops.ecris.model.measurement import Measurement
from .base_acquisition import TelnetDataAcquisitionService
from ops.ecris.operations.producers import time_average_current

class AverageCurrentAcquisitionService(TelnetDataAcquisitionService):
    def __init__(self, ammeter: Ammeter, average_rate: float = 0.33) -> None:
        self.device: Ammeter
        self.average_rate = average_rate
        super().__init__(ammeter)

    def _acquire_data(self) -> Measurement:
        return time_average_current(self._loop, self.device, average_seconds=self.average_rate)
