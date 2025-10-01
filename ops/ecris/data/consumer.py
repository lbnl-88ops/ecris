from logging import getLogger
import asyncio
from typing import Dict, Callable, Any, Awaitable, List

from ops.ecris.model.measurement import Measurement

async def consumer(data_queue, 
                   data_broadcasters: List[Callable[[Measurement], Awaitable[None]]]):
    while True:
        data = await data_queue.get()
        tasks = [broadcaster(data) for broadcaster in data_broadcasters]
        await asyncio.gather(*tasks)
        data_queue.task_done()

