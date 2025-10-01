from abc import ABC, abstractmethod
from enum import StrEnum
import asyncio
from logging import getLogger
from typing import Dict, List, Type, Any
from ipaddress import IPv6Address, ip_address, IPv4Address
from telnetlib3 import open_connection, TelnetReader, TelnetWriter

_log = getLogger(__name__)

class Device(ABC):
    """
    An abstract base class for a controllable device.
    """
    @abstractmethod
    async def read_data(self, data_key: Any) -> float:
        """
        Fetches a single data point from the device.
        Raises:
            KeyError: If the data_key is not supported for reading.
        """
        pass

    @abstractmethod
    async def write_data(self, data_key: Any, value: float) -> None:
        """
        Writes a single data value to the device.
        Raises:
            KeyError: If the data_key is not supported for writing.
        """
        pass

class TelnetDevice(Device):
    def __init__(self, ip: str | None = None, port: int | None = None,
                 prompt: str | None = None, encoding: str = 'ascii'):
        self._ip: IPv4Address | IPv6Address | None = None
        self._port: int | None = None
        self._prompt = prompt
        self._reader: TelnetReader | None = None
        self._writer: TelnetWriter | None = None
        self._connection_lock = asyncio.Lock()
        self.encoding = encoding

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
            host = self._host
            if self.is_connected:
                _log.debug(f'Already connected to {host}.')
                return

            self._check_configured()
            _log.info(f'Attempting to connect to {host} with {self.encoding} encoding...')

            try:
                ip_str = str(self._ip)
                self._reader, self._writer = await asyncio.wait_for(
                    open_connection(ip_str, self._port, encoding=False), timeout=3.0)
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
        encoded_command = (command + '\r\n').encode(self.encoding) 
        self._writer.write(encoded_command)
        await self._writer.drain()

    async def _read_until(self, separator: bytes = b'\n') -> str:
        if not self.is_connected:
            raise ConnectionError("Device is not connected. Cannot read.")
        
        try:
            raw_bytes = await self._reader.readuntil(separator)
            response = raw_bytes.decode(self.encoding)
            if self._prompt is not None and response.startswith(self._prompt):
                response = response.removeprefix(self._prompt)
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
        