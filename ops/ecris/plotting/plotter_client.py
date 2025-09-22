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

HISTORY_SIZE = 50
MEAN_WINDOW_SIZE = 10


x_data = deque(maxlen=HISTORY_SIZE)
y_data = deque(maxlen=HISTORY_SIZE)
mean_plot_y = deque(maxlen=HISTORY_SIZE)
mean_plot_x = deque(maxlen=HISTORY_SIZE)

async def listen_and_plot(data_line, mean_line):
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        _log.info(f"Connected to {uri}")
        async for message in websocket:
            data = json.loads(message)
            
            if 'time' in data and 'value' in data:
                x_data.append(data['time'])
                y_data.append(data['value'])

                if len(y_data) >= MEAN_WINDOW_SIZE:
                    last_n_values = list(y_data)[-MEAN_WINDOW_SIZE:]
                    mean_plot_y.append(np.mean(last_n_values))
                    mean_plot_x.append(data['time'])
                    mean_line.setData(mean_plot_x, mean_plot_y)

                data_line.setData(x_data, y_data)
                await asyncio.sleep(0)
                

def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication()
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    plot = pg.plot(title='Real time data')
    plot.showGrid(x=True, y=True)
    data_line = plot.plot(pen=None, symbol='o', symbolSize=5, name="Data")
    mean_line = plot.plot(pen='r', name=f"Moving average (N={MEAN_WINDOW_SIZE})")
    plot.addLegend()
    with loop:
        task = loop.create_task(listen_and_plot(data_line, mean_line))
        loop.run_forever()

if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, websockets.exceptions.ConnectionClosedError):
        _log.info("Shutting down plotter client.")
    finally:
        if 'loop' in locals() and loop.is_running():
            loop.close()

