from ops.ecris.devices import Ammeter
from ops.ecris.model.measurement import Measurement
from .base_aquisition import TelnetDataAcquisitionService
from ops.ecris.operations.producers import time_average_current

class AverageCurrentAquisitionService(TelnetDataAcquisitionService):
    def __init__(self, ammeter: Ammeter) -> None:
        self.device: Ammeter
        super().__init__(ammeter)

    def _aquire_data(self) -> Measurement:
        return time_average_current(self._loop, self.device, 0.33)
