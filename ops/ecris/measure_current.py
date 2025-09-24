import time
import numpy as np

from ops.ecris.model import Ammeter

async def time_average_current(ammeter: Ammeter,
                               average_seconds: float) -> float:
    time_start = time.time()
    current_readings = []

    while time.time() - time_start < average_seconds:
        data = await ammeter.get_data()
        current_readings.append(data['current'])
    
    return float(np.average(current_readings))

