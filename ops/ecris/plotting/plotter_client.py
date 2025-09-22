from logging import getLogger
import asyncio
import json
import websockets
from collections import deque
import pyqtgraph as pg
from PySide6 import QtWidgets

import numpy as np

_log = getLogger(__name__)

HISTORY_SIZE = 50
MEAN_WINDOW_SIZE = 10

app = QtWidgets.QApplication()
plot = pg.plot(title='Real time data')
plot.showGrid(x=True, y=True)
data_line = plot.plot(pen=None, symbol='o', symbolSize=5)
mean_line = plot.plot(pen='r')

x_data = deque(maxlen=HISTORY_SIZE)
y_data = deque(maxlen=HISTORY_SIZE)
mean_plot_y = deque(maxlen=HISTORY_SIZE)
mean_plot_x = deque(maxlen=HISTORY_SIZE)

async def listen_and_plot():
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
                app.processEvents()


if __name__ == "__main__":
    try:
        asyncio.run(listen_and_plot())
    except (KeyboardInterrupt, websockets.exceptions.ConnectionClosedError):
        _log.info("Shutting down plotter client.")
