import logging
import asyncio
import qasync
import json
import websockets
from collections import deque
import pyqtgraph as pg
from PySide6 import QtWidgets

import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
_log = logging.getLogger(__name__)

HISTORY_SIZE = 200
MEAN_WINDOW_SIZE = 10
PLOT_UPDATE_RATE_HZ = 60
PLOT_UPDATE_INTERVAL_S = 1.0/PLOT_UPDATE_RATE_HZ




async def websocket_consumer(queue: asyncio.Queue):
    uri = "ws://localhost:8765"
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                _log.info(f"Connected to {uri}")
                async for message in websocket:
                    await queue.put(json.loads(message))
        except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError):
            _log.warning("Connection lost. Reconnecting in 2 seconds...")
            await asyncio.sleep(2)

async def plot_updater(queue: asyncio.Queue, data_line, mean_line):
    x_data = deque(maxlen=HISTORY_SIZE)
    y_data = deque(maxlen=HISTORY_SIZE)
    mean_plot_y = deque(maxlen=HISTORY_SIZE)
    mean_plot_x = deque(maxlen=HISTORY_SIZE)

    while True:
        points_processed = 0
        while not queue.empty():
            data = queue.get_nowait()
            points_processed += 1
            if 'time' in data and 'value' in data:
                x_data.append(data['time'])
                y_data.append(data['value'])

        if points_processed > 0:
            if len(y_data) >= MEAN_WINDOW_SIZE:
                last_n_values = list(y_data)[-MEAN_WINDOW_SIZE:]
                mean_plot_y.append(np.mean(last_n_values))
                mean_plot_x.append(x_data[-1])
                mean_line.setData(mean_plot_x, mean_plot_y)
            data_line.setData(x_data, y_data)

        await asyncio.sleep(PLOT_UPDATE_INTERVAL_S)
            

async def main():
    plot = pg.plot(title='Real time data')
    plot.showGrid(x=True, y=True)
    data_line = plot.plot(pen=None, symbol='o', symbolSize=5, name="Data")
    mean_line = plot.plot(pen='r', name=f"Moving average (N={MEAN_WINDOW_SIZE})")
    plot.addLegend()
    plot.show()

    data_queue = asyncio.Queue()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(websocket_consumer(data_queue))
        tg.create_task(plot_updater(data_queue, data_line, mean_line))

if __name__ == "__main__":
    try:
        qasync.run(main())
    except (KeyboardInterrupt, RuntimeError, websockets.exceptions.ConnectionClosedError):
        _log.info("Shutting down plotter client.")

