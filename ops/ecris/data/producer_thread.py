import asyncio
import time
from typing import Callable, Dict
from logging import getLogger

from .exceptions import ECRISDataFailure

_log = getLogger(__name__)

def producer_thread(loop, data_queue, 
                    producer: Callable[[],Dict],
                    poll_interval: float):
    _log.info("Producer thread started")
    while True:
        start = time.monotonic()
        try:
            data = producer()
        except Exception as exc:
            raise ECRISDataFailure(exc)
        loop.call_soon_threadsafe(data_queue.put_nowait, data)
        wait_time = poll_interval - (time.monotonic() - start)
        if wait_time > 0:
            time.sleep(wait_time)
