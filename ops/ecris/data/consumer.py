from logging import getLogger
import asyncio
from typing import Dict, Callable, Any, Awaitable, List

_log = getLogger(__name__)

async def consumer(data_queue, 
                   data_broadcasters: List[Callable[[Dict], Awaitable[None]]]):
    while True:
        data = await data_queue.get()
        tasks = [broadcaster(data) for broadcaster in data_broadcasters]
        await asyncio.gather(*tasks)
        data_queue.task_done()

