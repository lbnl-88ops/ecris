import asyncio
import random
import threading
import logging
import time
from functools import partial

import websockets

from ops.ecris.data.producer_thread import producer_thread
from ops.ecris.data.consumer import consumer
from ops.ecris.data.broadcasters import log_data, broadcast_to_clients
from ops.ecris.data.websockets import client_handler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

_log = logging.getLogger(__name__)

async def main():
    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def random_data():
        return {'time': time.time(), 'value': 50 + random.uniform(-10, 10)}

    thread = threading.Thread(target=producer_thread, args=(loop, queue, random_data, 1/3),
                              daemon=True)
    thread.start()


    broadcasters = [
            partial(log_data, value='time'), 
            partial(log_data, value='value'),
            broadcast_to_clients,
    ]

    consumer_task = asyncio.create_task(consumer(queue, broadcasters))
    server = await websockets.serve(client_handler, "localhost", 8765)
    _log.info('Websocket server started on ws://localhost:8765')
    await consumer_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Shutting down')