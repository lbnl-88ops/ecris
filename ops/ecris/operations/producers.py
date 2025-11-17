import asyncio
import time
from typing import Dict

from ops.ecris.devices.ammeter import Ammeter
from ops.ecris.drivers.measurement import AverageMeasurement

import numpy as np

def time_average_current(loop, ammeter: Ammeter, average_seconds: float) -> AverageMeasurement:
    time_start = time.time()
    current_readings = []

    while time.time() - time_start < average_seconds:
        coroutine = ammeter.read_current()
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        data = future.result()
        current_readings.append(data)
    average = float(np.average(current_readings))
    if abs(average) < 1E-16:
        standard_deviation = -2
    else:
        standard_deviation = float(np.std(current_readings))/average * 100
    return AverageMeasurement(source=ammeter.name, 
                              timestamp=time.time(),
                              average=average, 
                              standard_deviation=standard_deviation)

