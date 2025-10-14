import asyncio
from typing import Callable
from logging import getLogger

from .exceptions import ECRISDataFailure
from ops.ecris.model.measurement import Measurement

_log = getLogger(__name__)

def producer_thread(loop: asyncio.AbstractEventLoop, 
                    data_queue: asyncio.Queue, 
                    producer: Callable[[],Measurement]):
    _log.info("Producer thread started")
    while True:
        try:
            data = producer()
        except Exception as exc:
            raise ECRISDataFailure(exc)
        loop.call_soon_threadsafe(data_queue.put_nowait, data)
