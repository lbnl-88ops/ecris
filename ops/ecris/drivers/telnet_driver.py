import asyncio
from logging import getLogger
from ipaddress import IPv6Address, ip_address, IPv4Address
from typing import Any
from telnetlib3 import open_connection, TelnetReader, TelnetWriter

from .base import SessionDriver

_log = getLogger(__name__)


class TelnetDriver(SessionDriver):
    def __init__(
        self,
        id: str = "TelnetDevice",
        ip: str | None = None,
        port: int | None = None,
        prompt: str | None = None,
        encoding: str = "ascii",
        command_terminator: str = "\r\n",
    ):
        self.id = id
        self._ip: IPv4Address | IPv6Address | None = None
        self._port: int | None = None
        self._prompt = prompt if prompt is not None else "\n"
        self._reader: TelnetReader | None = None
        self._writer: TelnetWriter | None = None
        self._connection_lock = asyncio.Lock()
        self.encoding = encoding
        self._command_terminator = command_terminator

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
        return f"{self._ip}:{self._port}"

    async def read_data(self, data_key: Any) -> float:
        raise NotImplementedError("Subclasses must implement read_data")

    async def write_data(self, data_key: Any, value: float) -> None:
        raise NotImplementedError("Subclasses must implement write_data")

    async def connect(self) -> None:
        async with self._connection_lock:
            host = self._host
            if self.is_connected:
                _log.debug(f"Already connected to {host}.")
                return

            self._check_configured()
            _log.info(f"Attempting to connect to {host} with {self.encoding} encoding...")

            try:
                ip_str = str(self._ip)
                self._reader, self._writer = await asyncio.wait_for(
                    open_connection(ip_str, self._port, encoding=False), timeout=3.0
                )
                _log.debug("Connected, performing handshake...")
                await self._handshake()
                _log.debug("Handshake complete, performing setup...")
                # TODO: Move this out of connect
                await self._setup()
                # _log.debug(f"Awaiting initial response, expected prompt = {self._prompt}")
                # response = await asyncio.wait_for(self._read_until(self._prompt), 1.0)
                # _log.info(f"Successfully connected to {host}, response: {response}.")
            except (ConnectionRefusedError, OSError, asyncio.TimeoutError) as e:
                _log.error(f"Failed to connect to {host}: {e}")
                self._reader = None
                self._writer = None
                raise

    async def _handshake(self) -> None:
        pass

    async def _setup(self) -> None:
        pass

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
        encoded_command = (command + self._command_terminator).encode(self.encoding)
        _log.debug(f"Writing command {encoded_command!r}")
        self._writer.write(encoded_command)
        _log.debug(f"Draining buffer")
        await self._writer.drain()
        _log.debug(f"Buffer drained")

    async def _read_until(self, separator: str = "\n") -> str:
        if not self.is_connected:
            raise ConnectionError("Device is not connected. Cannot read.")
        try:
            _log.debug(f"Awaiting read to terminator {separator.encode(self.encoding)!r}")
            raw_bytes = await self._reader.readuntil(separator.encode(self.encoding))
            _log.debug(f"Raw response {raw_bytes[:20]!r}" + "..." if len(raw_bytes) > 20 else "")
            response = raw_bytes.decode(self.encoding)
            if self._prompt is not None:
                response = response.removeprefix(self._prompt)
            return response.strip()
        except asyncio.IncompleteReadError:
            _log.error("Connection closed while waiting for response.")
            await self.disconnect()
            raise ConnectionError("Connection lost while reading.")

    def _check_configured(self) -> None | RuntimeError:
        if self._ip is None:
            raise RuntimeError("Cannot connect, no IP set.")
        if self._port is None:
            raise RuntimeError("Cannot connect, no port set.")
