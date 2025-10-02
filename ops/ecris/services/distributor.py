import asyncio
import logging
from typing import List
from ops.ecris.model.measurement import Measurement

_log = logging.getLogger(__name__)

class DataDistributor:
    def __init__(self, input_queue):
        self._input_queue = input_queue
        self._subscriber_queues: List[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        self._subscriber_queues.append(queue)
        _log.debug(f"New subscriber. Total: {len(self._subscriber_queues)}")
        return queue

    async def run(self): 
        _log.info("DataDistributor is running...")
        while True:
            measurement: Measurement = await self._input_queue.get()
            for q in self._subscriber_queues:
                q.put_nowait(measurement)
            self._input_queue.task_done()
