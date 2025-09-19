import asyncio
import random
import threading
import logging
import time
from functools import partial

from ops.ecris.data.producer_thread import producer_thread
from ops.ecris.data.consumer import consumer
from ops.ecris.data.broadcasters import log_data

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    def random_data():
        return {'time': time.time(), 'value': 50 + random.uniform(-10, 10)}
    thread = threading.Thread(target=producer_thread, args=(loop, queue, random_data, 1),
                              daemon=True)
    thread.start()
    consumer_task = asyncio.create_task(
        consumer(queue, [partial(log_data, value='time'),
                         partial(log_data, value='value')]))
    await consumer_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Shutting down')