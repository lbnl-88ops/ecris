from logging import getLogger
import asyncio
from typing import Dict, Callable, Any, Awaitable

_log = getLogger(__name__)

async def consumer(data_queue, 
                   data_broadcasters: Dict[str, Callable[[str], Awaitable[None]]]):
    while True:
        data = await data_queue.get()
        tasks = [broadcaster(data[key]) for key, broadcaster in data_broadcasters.items()]
        await asyncio.gather(*tasks)
        data_queue.task_done()

async def log_message(message: str) -> None:
    _log.info(f'{message=}')
    