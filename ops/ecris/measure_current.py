import time
import numpy as np
from typing import Tuple

from ops.ecris.devices import VenusPLC, Ammeter

async def time_average_current(ammeter: Ammeter,
                               average_seconds: float) -> Tuple[float, float]:
    time_start = time.time()
    current_readings = []

    while time.time() - time_start < average_seconds:
        data = await ammeter.get_data(Ammeter.DataKeys.CURRENT)
        current_readings.append(data)
    average = float(np.average(current_readings))
    if abs(average) < 1E-16:
        standard_deviation = -2
    else:
        standard_deviation = float(np.std(current_readings))/average * 100
    return average, standard_deviation


async def update_plc_average_current(ammeter: Ammeter, venus_plc: VenusPLC, 
                                     average_seconds: float = 0.33) -> None:
    average, stdev = await time_average_current(ammeter, average_seconds)
    await venus_plc.write_data(VenusPLC.DataKeys.AVERAGE_CURRENT, average)
    await venus_plc.write_data(VenusPLC.DataKeys.CURRENT_STDEV, stdev)