from logging import getLogger
import asyncio
import json
import websockets
import matplotlib.pyplot as plt
from collections import deque

import numpy as np

_log = getLogger(__name__)

HISTORY_SIZE = 50
MEAN_WINDOW_SIZE = 10

plt.ion()
fig, ax = plt.subplots()
x_data = deque(maxlen=HISTORY_SIZE)
y_data = deque(maxlen=HISTORY_SIZE)
mean_plot_y = deque(maxlen=HISTORY_SIZE)
mean_plot_x = deque(maxlen=HISTORY_SIZE)

line, = ax.plot([], [], 'k.', label='Raw data')
mean_line, = ax.plot([], [], '--', label=f'{MEAN_WINDOW_SIZE}-pt moving avg')
ax.legend()
ax.set_xlabel("Time (s)")
ax.set_ylabel("Value")
ax.set_title("Real-Time Data from WebSocket")
ax.grid(True)

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
                    mean_line.set_xdata(mean_plot_x)
                    mean_line.set_ydata(mean_plot_y)

                line.set_xdata(x_data)
                line.set_ydata(y_data)
                
                ax.relim()
                ax.autoscale_view()
                
                plt.pause(0.001)

if __name__ == "__main__":
    try:
        asyncio.run(listen_and_plot())
    except (KeyboardInterrupt, websockets.exceptions.ConnectionClosedError):
        _log.info("Shutting down plotter client.")
