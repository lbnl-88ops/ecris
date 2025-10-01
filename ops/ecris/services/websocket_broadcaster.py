import asyncio
import json
import logging
from dataclasses import asdict, is_dataclass
from typing import Set, Any
from ipaddress import IPv4Address, IPv6Address, ip_address

from websockets.asyncio.server import serve, ServerConnection, Server

_log = logging.getLogger(__name__)

class WebSocketBroadcaster:
    """
    A class that runs a WebSocket server to broadcast data to all connected clients.
    """
    def __init__(self, ip: str, port: int) -> None:
        self._ip: IPv4Address | IPv6Address = ip_address(ip)
        if port < 0:
            raise ValueError(f"Bad port value: {port} (must be >=0)")
        self._port = port
        self._connected_clients: Set[ServerConnection] = set()
        self._server: Server | None = None

    async def _connection_handler(self, websocket: ServerConnection):
        _log.info(f"New client connected: {websocket.remote_address}")
        self._connected_clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            _log.info(f"Client disconnected: {websocket.remote_address}")
            self._connected_clients.remove(websocket)

    @property
    def ip(self) -> IPv4Address | IPv6Address:
        return self._ip

    @property
    def port(self) -> int:
        return self._port
    
    @property
    def _host(self) -> str:
        return f'{self._ip}:{self._port}'

    async def start(self):
        if self._server:
            _log.warning("Server is already running.")
            return
        
        _log.debug(f"Starting WebSocket broadcaster on ws://{self._host}")
        self._server = await serve(self._connection_handler, str(self._ip), self._port)

    async def stop(self):
        """Stops the WebSocket server gracefully."""
        if not self._server:
            return
        
        _log.debug("Stopping WebSocket broadcaster...")
        self._server.close()
        await self._server.wait_closed()
        _log.debug("WebSocket broadcaster stopped.")
        self._server = None

    async def broadcast(self, message_data: Any):
        """
        Encodes a message to JSON and sends it to all connected clients.
        
        """
        if not self._connected_clients:
            return

        # Convert dataclasses to dicts for JSON serialization
        if is_dataclass(message_data):
            payload = asdict(message_data)
        else:
            payload = message_data
            
        json_message = json.dumps(payload)

        # Use asyncio.gather to send messages to all clients concurrently
        tasks = [client.send(json_message) for client in self._connected_clients]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Optionally, log any errors that occurred during the broadcast
        for result in results:
            if isinstance(result, Exception):
                _log.warning(f"Failed to send message to a client: {result}")