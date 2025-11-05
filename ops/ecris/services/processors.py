import asyncio
import time
import statistics
import logging
from ops.ecris.drivers.measurement import ValueMeasurement, AverageMeasurement

_log = logging.getLogger(__name__)

class AveragingProcessor:
    """Subscribes to a raw ValueMeasurement stream and emits AverageMeasurements."""

    def __init__(self, input_queue: asyncio.Queue, interval_seconds: float):
        self._input_queue = input_queue
        self._interval = interval_seconds
        self.data_queue  = asyncio.Queue()
        
    async def run(self):
        """The main processing loop. Run this as a task."""
        _log.debug(f"AveragingProcessor is running with a {self._interval}s window.")
        buffer = []
        start_time = time.monotonic()
        
        while True:
            measurement: ValueMeasurement = await self._input_queue.get()
            buffer.append(measurement.value)
            
            if time.monotonic() - start_time >= self._interval:
                if buffer:
                    avg = statistics.mean(buffer)
                    # Calculate standard deviation as a percentage of the mean
                    std_dev_percent = (statistics.stdev(buffer) / avg) * 100 if len(buffer) > 1 and avg != 0 else 0
                    
                    avg_measurement = AverageMeasurement(
                        source=measurement.source,
                        timestamp=time.time(),
                        average=avg,
                        standard_deviation=std_dev_percent
                    )
                    await self.data_queue.put(avg_measurement)
                
                # Reset for the next window
                buffer = []
                start_time = time.monotonic()
            
            self._input_queue.task_done()
