import asyncio
from logging import getLogger
from typing import Set, List
from enum import Enum, auto, StrEnum

from .telnet_driver import TelnetDriver

_log = getLogger(__name__)


class SCPIDriver(TelnetDriver):
    class DataKeys(Enum):
        CURRENT = auto()
        NPLC_SETTING = auto()

    class Commands(StrEnum):
        MEASURE_CURRENT = "meas:curr?"
        RESET = "*rst"
        SET_NPLC = ":sens:curr:nplc {}"
        CURRENT_FUNCTION = ':sens:func "curr"'
        CURRENT_AUTO_RANGE = ":sens:curr:rang:auto on"
        CURRENT_NPLC_AUTO_OFF = ":sens:curr:nplc:auto off"
        INPUT_ON = ":inp on"
        TEST = "*tst?"  # returns 0, generally for handshake
        IDENTITY = "*idn?"  # Returns identity
        CLEAR_BUFFER = ":trace:clear"
        SET_LANG = "*lang scpi"

    def __init__(
        self,
        read_frequency_per_min: float,
        ip: str | None = None,
        port: int | None = None,
        prompt: str | None = None,
        id: str = "SCPI Device",
        command_echo: bool = False,
    ):
        super().__init__(id, ip, port, prompt)

        if not 1 <= read_frequency_per_min <= 2000:
            raise ValueError(
                f"Bad value of read frequency {read_frequency_per_min} (must be 1-2000)"
            )

        self.nplc_setting = 1 / read_frequency_per_min * 60.0
        self.id = id
        self.command_echo = command_echo

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
        await asyncio.sleep(0.1)

    async def send_command(self, command: str) -> List[str] | str | None:
        await self._write(command)
        terminator = self._prompt if self._prompt is not None else "\n"
        raw_response = await self._read_until(terminator)
        response = [l.strip() for l in raw_response.split()]

        if self._prompt is not None:
            response = [l for l in response if l != self._prompt]
        if self.command_echo is not None:
            response = [l for l in response if l != command]

        if len(response) == 1:
            return response[0]
        return response

    async def read_data(self, data_key: DataKeys) -> float:
        match data_key:
            case SCPIDriver.DataKeys.CURRENT:
                try:
                    async with asyncio.timeout(2.0):  # Overall timeout for the read operation
                        while True:
                            _log.debug("Reading current")
                            response = await self.send_command(SCPIDriver.Commands.MEASURE_CURRENT)
                            _log.debug(f"Raw response {response!r}")
                            try:
                                return float(response)
                            except ValueError or AssertionError:
                                _log.debug(
                                    f"Error in current measurement, non-float response: {response!r}"
                                )
                except TimeoutError:
                    _log.error(
                        f"Timeout occurred while waiting for a valid numeric response from {self.id}."
                    )
                    raise ConnectionAbortedError(f"Connection to {self.id} timed out.")
        raise KeyError(f"Read operation for data_key {data_key.name} not implemented.")

    async def write_data(self, data_key: DataKeys, value: float) -> None:
        raise KeyError(f"Write operation for data_key {data_key.name} not implemented.")

    async def connect(self) -> None:
        _log.debug(f"Connecting to {self.id} at {self._host}...")
        await super().connect()

    async def reset(self) -> None:
        _log.debug(f"Resetting {self.id} at {self._host}...")
        if self.command_echo:
            await self.send_command(SCPIDriver.Commands.RESET)
        else:
            await self.send_silent_command(SCPIDriver.Commands.RESET)
        _log.debug(f"{self.id} reset.")
