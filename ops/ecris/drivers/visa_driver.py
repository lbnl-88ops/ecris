import asyncio
from logging import getLogger
from typing import Any

import pyvisa
from pyvisa.resources import MessageBasedResource

from .base import SessionDriver

_log = getLogger(__name__)


class VISADriver(SessionDriver):
    def __init__(self, resource_name: str, id: str = "VISADevice", **kwargs):
        self.resource_name = resource_name
        self.id = id
        self._rm: pyvisa.ResourceManager | None = None
        self._instrument: MessageBasedResource | None = None
        self._visa_kwargs = kwargs
        self._connection_lock = asyncio.Lock()
        self._io_lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return self._instrument is not None

    async def connect(self) -> None:
        async with self._connection_lock:
            if self.is_connected:
                return

            def _connect():
                _log.info(f"Connecting to VISA resource: {self.resource_name}")
                self._rm = pyvisa.ResourceManager("@py")
                self._instrument = self._rm.open_resource(self.resource_name, **self._visa_kwargs)
                _log.info(f"Connected to {self.resource_name}")

            try:
                await asyncio.to_thread(_connect)
                if not isinstance(self._instrument, MessageBasedResource):
                    self._instrument.close()
                    self._instrument = None
                    raise TypeError(
                        f"Resource '{self.resource_name}' is not a MessageBasedResource "
                        f"(got {type(self._instrument).__name__!r}). "
                        "Only message-based VISA resources are supported."
                    )
                await self._handshake()
                await self._setup()
            except Exception as e:
                _log.error(f"Failed to connect to {self.resource_name}: {e}")
                self._instrument = None
                if self._rm:
                    self._rm.close()
                    self._rm = None
                raise

    async def _handshake(self) -> None:
        pass

    async def _setup(self) -> None:
        pass

    async def disconnect(self) -> None:
        async with self._connection_lock:
            if not self.is_connected:
                return

            def _disconnect():
                _log.info(f"Disconnecting from VISA resource: {self.resource_name}")
                self._instrument.close()
                self._rm.close()
                self._instrument = None
                self._rm = None

            await asyncio.to_thread(_disconnect)

    async def _write(self, command: str) -> None:
        if not self.is_connected:
            raise ConnectionError("Device is not connected. Cannot write.")

        async with self._io_lock:
            _log.debug(f"Writing VISA command: {command!r}")
            await asyncio.to_thread(self._instrument.write, command)

    async def _read_until(self, separator: str = "\n") -> str:
        if not self.is_connected:
            raise ConnectionError("Device is not connected. Cannot read.")

        async with self._io_lock:
            # VISA normally reads until the terminator configured on the instrument.
            # We ignore the separator for now and just use the instrument's default read.
            response = await asyncio.to_thread(self._instrument.read)
            _log.debug(f"Read VISA response: {response!r}")
            return response.strip()

    async def _query(self, command: str) -> str:
        if not self.is_connected:
            raise ConnectionError("Device is not connected. Cannot query.")

        async with self._io_lock:
            _log.debug(f"Querying VISA command: {command!r}")
            response = await asyncio.to_thread(self._instrument.query, command)
            _log.debug(f"VISA query response: {response!r}")
            return response.strip()

    async def query_ascii_values(self, command: str) -> list[float]:
        if not self.is_connected:
            raise ConnectionError("Device is not connected. Cannot query.")

        async with self._io_lock:
            _log.debug(f"Querying ASCII values VISA command: {command!r}")
            response = await asyncio.to_thread(self._instrument.query_ascii_values, command)
            _log.debug(f"VISA query_ascii_values response: {response!r}")
            return response

    async def read_data(self, data_key: Any) -> float:
        raise NotImplementedError("Subclasses must implement read_data")

    async def write_data(self, data_key: Any, value: float) -> None:
        raise NotImplementedError("Subclasses must implement write_data")
