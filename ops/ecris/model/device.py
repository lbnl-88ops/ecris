from abc import ABC, abstractmethod
import asyncio
from logging import getLogger
from typing import Dict, List, Type
from ipaddress import IPv6Address, ip_address, IPv4Address
from telnetlib3 import open_connection, TelnetReader, TelnetWriter

_log = getLogger(__name__)

class DataDevice(ABC):
    @abstractmethod
    async def get_data() -> Dict:
        pass

    @property
    def data_types(self) -> Dict[str, Type]:
        raise NotImplementedError

    @property
    def data_keys(self) -> List[str]:
        raise NotImplementedError

class TelnetDevice(DataDevice):
    def __init__(self, ip: str | None = None, port: int | None = None):
        self._ip: IPv4Address | IPv6Address | None = None
        self._port: int | None = None
        self._reader: TelnetReader | None = None
        self._writer: TelnetWriter | None = None
        self._connection_lock = asyncio.Lock()

        if ip:
            self.ip = ip
        if port:
            self.port = port

    @property
    def is_connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    @property
    def ip(self) -> IPv6Address | IPv4Address | None:
        return self._ip

    @ip.setter
    def ip(self, to_set: str | IPv4Address) -> None:
        if isinstance(to_set, IPv4Address):
            self._ip = to_set
        else:
            self._ip = ip_address(to_set)

    @property
    def port(self) -> int | None:
        return self._port

    @port.setter
    def port(self, to_set: int) -> None:
        if to_set < 0:
            raise ValueError(f"Bad port value: {to_set} (must be >=0)")
        self._port = to_set

    @property
    def _host(self) -> str:
        return f'{self._ip}:{self._port}'


    async def connect(self) -> None:
        async with self._connection_lock:
            host = f'{self._ip}:{self._port}'
            if self.is_connected:
                _log.debug(f'Already connected to {host}.')
                return

            self._check_configured()
            _log.info(f'Attempting to connect to {host}...')

            try:
                self._reader, self._writer = await asyncio.wait_for(
                    open_connection(self._ip, self._port), timeout=3.0)
                _log.info(f'Successfully connected to {host}.')
            except (ConnectionRefusedError, OSError, asyncio.TimeoutError) as e:
                _log.error(f'Failed to connect to {host}: {e}')
                self._reader = None
                self._writer = None
                raise

    async def disconnect(self) -> None:
        if not self.is_connected:
            return
        
        _log.info(f"Disconnecting from {self._host}...")
        self._writer.close()
        await self._writer.wait_closed()
        self._reader = None
        self._writer = None
        _log.info("Disconnected successfully.")

    async def _write(self, command: str):
        if not self.is_connected:
            raise ConnectionError("Device is not connected. Cannot write.")
        
        self._writer.write(command + '\n')
        await self._writer.drain()

    async def _read_until(self, separator: str = '\n') -> str:
        if not self.is_connected:
            raise ConnectionError("Device is not connected. Cannot read.")
        
        try:
            response = await self._reader.readuntil(separator.encode('ascii'))
            return response.strip()
        except asyncio.IncompleteReadError:
            _log.error("Connection closed while waiting for response.")
            await self.disconnect()
            raise ConnectionError("Connection lost while reading.")

    def _check_configured(self) -> None | RuntimeError:
        if self._ip is None:
            raise RuntimeError('Cannot connect, no IP set.')
        if self._port is None:
            raise RuntimeError('Cannot connect, no port set.')
        