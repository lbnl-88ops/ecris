import time
import numpy as np
from typing import Tuple

from ops.ecris.model import Ammeter

async def time_average_current(ammeter: Ammeter,
                               average_seconds: float) -> Tuple[float, float]:
    time_start = time.time()
    current_readings = []

    while time.time() - time_start < average_seconds:
        data = await ammeter.get_data()
        current_readings.append(data['current'])
    average = float(np.average(current_readings))
    if abs(average) < 1E-16:
        standard_deviation = -2
    else:
        standard_deviation = float(np.std(current_readings))/average * 100
    return average, standard_deviation

