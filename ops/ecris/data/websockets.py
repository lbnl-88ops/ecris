from logging import getLogger
from websockets import ServerConnection

_log = getLogger(__name__)

CONNECTED_CLIENTS = set()

async def client_handler(websocket: ServerConnection):
    _log.info(f"Client connected: {websocket.remote_address}")
    CONNECTED_CLIENTS.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        _log.info(f"Client disconnected: {websocket.remote_address}")
        CONNECTED_CLIENTS.remove(websocket)
