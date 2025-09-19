from logging import getLogger
from typing import Dict, Set
import json
import websockets

from .websockets import CONNECTED_CLIENTS

_log = getLogger(__name__)

async def log_data(data, value) -> None:
    _log.info(f'{value}={data[value]}')

async def broadcast_to_clients(data: Dict):
    if not CONNECTED_CLIENTS:
        return
    message = json.dumps(data)
    websockets.broadcast(CONNECTED_CLIENTS, message)
