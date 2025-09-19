import asyncio
import random
import threading
import logging
import time

from ops.ecris.data.producer_thread import producer_thread
from ops.ecris.data.consumer import consumer, log_message

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
        consumer(queue, {'value': log_message, 'time': log_message}))
    await consumer_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Shutting down')