import asyncio
from logging import getLogger
from typing import Set, List, Tuple, Any
from enum import Enum, auto, StrEnum
from time import perf_counter

import numpy as np
from .base import SessionDriver
from .telnet_driver import TelnetDriver
from .visa_driver import VISADriver

_log = getLogger(__name__)


class SCPIDriver(SessionDriver):
    class DataKeys(Enum):
        CURRENT = auto()
        VOLTAGE = auto()
        NPLC_SETTING = auto()

    class Commands(StrEnum):
        MEASURE_CURRENT = "meas:curr?"
        MEASURE_VOLTAGE = "meas:volt?"
        RESET = "*rst"
        SET_NPLC = ":sens:curr:nplc {}"
        CURRENT_FUNCTION = ':sens:func "curr"'
        CURRENT_AUTO_RANGE = ":sens:curr:rang:auto on"
        CURRENT_NPLC_AUTO_OFF = ":sens:curr:nplc:auto off"
        CURRENT_SET_APERATURE = ":sens:curr:aper {}"
        CURRENT_GET_APERATURE = ":sens:curr:aper?"
        CURRENT_MIN_RANGE = ":sens:curr:range min"
        SET_COUNT = ":sens:count {}"
        GET_COUNT = ":sens:count?"
        CURRENT_DELAY_DISABLE = ":sens:curr:delay:auto off"
        INPUT_ON = ":inp on"
        TEST = "*tst?"  # returns 0, generally for handshake
        IDENTITY = "*idn?"  # Returns identity
        CLEAR_BUFFER = ":trace:clear"
        SET_LANG = "*lang scpi"
        READ = ":read?"
        READ_DIGITIZE = ":read:dig?"
        SIMPLE_LOOP = 'TRIG:LOAD "SimpleLoop", {}'
        LOOP_INIT = "INIT"
        WAIT = "*WAI"
        LOOP_EXEC = "INIT; *WAI"
        AUTOZERO_OFF = ":sens:curr:azer off"
        AUTOZERO_ONCE = ":sens:azer:once"

        @staticmethod
        def set_range(value_to_measure: float):
            return f":sens:curr:rang {value_to_measure:.2e}"

        @staticmethod
        def get_trace_data(start: int, end: int, buffer_name: str) -> str:
            return f':trace:data? {start}, {end}, "{buffer_name}", READ'

        @staticmethod
        def get_trace_time(start: int, end: int, buffer_name: str) -> str:
            return f':trace:data? {start}, {end}, "{buffer_name}", TST'

    def __init__(
        self,
        sample_frequency_hz: float,
        ip: str | None = None,
        port: int | None = None,
        resource_name: str | None = None,
        prompt: str | None = None,
        id: str = "SCPI Device",
        command_echo: bool = False,
    ):
        self.id = id
        self.command_echo = command_echo
        self.nplc_setting = 6000 / sample_frequency_hz
        self._prompt = prompt

        if resource_name:
            self._backend = VISADriver(resource_name, id=id)
        else:
            self._backend = TelnetDriver(id=id, ip=ip, port=port, prompt=prompt)

    @property
    def _host(self) -> str:
        if isinstance(self._backend, VISADriver):
            return self._backend.resource_name
        elif isinstance(self._backend, TelnetDriver):
            return self._backend._host
        return "Unknown"

    @property
    def is_connected(self) -> bool:
        return self._backend.is_connected

    async def connect(self) -> None:
        _log.debug(f"Connecting to {self.id} at {self._host}...")
        await self._backend.connect()
        # Handshake and setup are done by the transport's connect, but we might want 
        # to ensure they are called on this object if not already called.
        # Actually TelnetDriver.connect calls self._handshake() and self._setup().
        # Since self._backend is a TelnetDriver/VISADriver, it calls its own handshake/setup.
        # We still need to call our device-specific handshake and setup.
        await self._handshake()
        await self._setup()

    async def disconnect(self) -> None:
        await self._backend.disconnect()

    async def _handshake(self) -> None:
        pass

    async def _setup(self) -> None:
        pass

    async def _write(self, command: str) -> None:
        await self._backend._write(command)

    async def _read_until(self, separator: str = "\n") -> str:
        return await self._backend._read_until(separator)

    @property
    def readable_keys(self) -> Set[DataKeys]:
        """Returns the set of keys that can be read from the device."""
        return {SCPIDriver.DataKeys.CURRENT}

    @property
    def writable_keys(self) -> Set[DataKeys]:
        """Returns the set of keys that can be written to the device."""
        return set()

    async def send_silent_command(self, command: str) -> None:
        """Send a command with no expected response"""
        await self._write(command)

    async def send_command(self, command: str) -> List[str] | str | None:
        await self._write(command)
        if isinstance(self._backend, VISADriver):
            # For VISA, we can use _query or just read. 
            # If we already wrote, we should read.
            raw_response = await self._backend._read_until()
        else:
            terminator = self._prompt if self._prompt is not None else "\n"
            raw_response = await self._read_until(terminator)
        
        if "\n" in raw_response:
            response = [l.strip() for l in raw_response.split("\n")]
        else:
            response = [raw_response.strip()]

        if self._prompt is not None:
            response = [l for l in response if l != self._prompt]
        if self.command_echo is not None:
            response = [l for l in response if l != command]

        if len(response) == 1:
            return response[0]
        elif len(response) == 0:
            return None
        return response

    async def read_loop(self, n_points: int) -> Tuple[np.ndarray, np.ndarray]:
        await self.send_silent_command(SCPIDriver.Commands.LOOP_INIT)
        await self.send_silent_command(SCPIDriver.Commands.WAIT)
        data_response = await self.send_command(
            SCPIDriver.Commands.get_trace_data(1, n_points, "defbuffer1")
        )
        time_response = await self.send_command(
            SCPIDriver.Commands.get_trace_time(1, n_points, "defbuffer1")
        )
        _log.debug("Clearing buffer")
        await self.send_silent_command(SCPIDriver.Commands.CLEAR_BUFFER)
        assert isinstance(data_response, str)
        assert isinstance(time_response, str)
        data = np.array([float(v) for v in data_response.split(",")])
        time = np.array([str(v) for v in time_response.split(",")])
        return data, time

    async def read_data_points(
        self, data_key: DataKeys, n_points: int, timing: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        times = [perf_counter()]
        match data_key:
            case SCPIDriver.DataKeys.CURRENT:
                pass
            case _:
                raise KeyError(f"Read operation for data_key {data_key.name} not implemented.")
        try:
            total_time = n_points * timing + 60
            async with asyncio.timeout(total_time):  # Overall timeout for the read operation
                while True:
                    times.append(perf_counter())
                    _log.debug(f"Clearing buffer, {times[-1] - times[-2]}")
                    await self.send_silent_command(SCPIDriver.Commands.CLEAR_BUFFER)
                    # _log.debug("Setting count")
                    # await self.send_silent_command(SCPIDriver.Commands.SET_COUNT.format(n_points))
                    times.append(perf_counter())
                    _log.debug(f"Setting aperature {times[-1] - times[-2]}")
                    await self.send_silent_command(
                        SCPIDriver.Commands.CURRENT_SET_APERATURE.format(timing)
                    )
                    times.append(perf_counter())
                    _log.debug(f"Zeroing and setting range {times[-1] - times[-2]}")
                    await self.send_silent_command(SCPIDriver.Commands.AUTOZERO_ONCE)
                    await self.send_silent_command(SCPIDriver.Commands.AUTOZERO_OFF)
                    # await self.send_silent_command(SCPIDriver.Commands.CURRENT_MIN_RANGE)
                    times.append(perf_counter())
                    _log.debug(f"Reading data {times[-1] - times[-2]}")
                    await self.send_silent_command(
                        SCPIDriver.Commands.SIMPLE_LOOP.format(n_points)
                    )
                    await self.send_silent_command(SCPIDriver.Commands.LOOP_INIT)
                    await self.send_silent_command(SCPIDriver.Commands.WAIT)
                    times.append(perf_counter())
                    _log.debug(f"Retrieving data {times[-1] - times[-2]}")
                    data_response = await self.send_command(
                        SCPIDriver.Commands.get_trace_data(1, n_points, "defbuffer1")
                    )
                    times.append(perf_counter())
                    _log.debug(f"Retrieving time {times[-1] - times[-2]}")
                    time_response = await self.send_command(
                        SCPIDriver.Commands.get_trace_time(1, n_points, "defbuffer1")
                    )
                    times.append(perf_counter())
                    _log.debug(f"Clearing buffer {times[-1] - times[-2]}")
                    try:
                        assert isinstance(data_response, str)
                        assert isinstance(time_response, str)
                        data = np.array([float(v) for v in data_response.split(",")])
                        time = np.array([str(v) for v in time_response.split(",")])
                        return data, time
                    except (ValueError, AssertionError) as exc:
                        _log.error(f"Error in current measurement, non-float response: {exc}")
                        raise RuntimeError(f"Measurement failed: {exc}") from exc
        except TimeoutError:
            _log.error(
                f"Timeout occurred while waiting for a valid numeric response from {self.id}."
            )
            raise ConnectionAbortedError(f"Connection to {self.id} timed out.")

    async def read_data(self, data_key: DataKeys) -> float:
        match data_key:
            case SCPIDriver.DataKeys.CURRENT:
                command = SCPIDriver.Commands.MEASURE_CURRENT
            case SCPIDriver.DataKeys.VOLTAGE:
                command = SCPIDriver.Commands.MEASURE_VOLTAGE
            case _:
                raise KeyError(f"Read operation for data_key {data_key.name} not implemented.")
        try:
            async with asyncio.timeout(10.0):  # Overall timeout for the read operation
                while True:
                    _log.debug(f"Reading {data_key.name}")
                    if isinstance(self._backend, VISADriver):
                        try:
                            values = await self._backend.query_ascii_values(command)
                            if values:
                                return values[0]
                        except Exception as exc:
                            _log.debug(f"Error in VISA measurement: {exc}")
                    else:
                        response = await self.send_command(command)
                        _log.debug(f"Raw response {response!r}")
                        try:
                            if isinstance(response, str):
                                return float(response)
                            elif isinstance(response, list) and len(response) > 0:
                                return float(response[0])
                            _log.debug(f"Error in current measurement, non-float response: {response!r}")
                        except (ValueError, TypeError):
                            _log.debug(
                                f"Error in current measurement, non-float response: {response!r}"
                            )
        except TimeoutError:
            _log.error(
                f"Timeout occurred while waiting for a valid numeric response from {self.id}."
            )
            raise ConnectionAbortedError(f"Connection to {self.id} timed out.")

    async def write_data(self, data_key: DataKeys, value: float) -> None:
        raise KeyError(f"Write operation for data_key {data_key.name} not implemented.")

    async def reset(self) -> None:
        _log.debug(f"Resetting {self.id} at {self._host}...")
        if self.command_echo:
            await self.send_command(SCPIDriver.Commands.RESET)
        else:
            await self.send_silent_command(SCPIDriver.Commands.RESET)
        _log.debug(f"{self.id} reset.")
