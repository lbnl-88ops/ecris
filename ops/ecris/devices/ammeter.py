import asyncio
from logging import getLogger
from typing import Set
from enum import Enum, auto, StrEnum

from ops.ecris.model.device import TelnetDevice, Device

_log = getLogger(__name__)

class Ammeter(TelnetDevice, Device):
    class DataKeys(Enum):
        """Defines the valid data keys for the Ammeter."""
        CURRENT = auto()
        NPLC_SETTING = auto()

    class Commands(StrEnum):
        MEASURE_CURRENT = 'meas:curr?'
        RESET = '*rst'
        SET_NPLC = ':sens:curr:nplc {}'
        CURRENT_FUNCTION = ':sens:func "curr"'
        CURRENT_AUTO_RANGE = ':sens:curr:rang:auto on'
        CURRENT_NPLC_AUTO_OFF = ':sens:curr:nplc:auto off'
        INPUT_ON = ':inp on'
    
    def __init__(self, read_frequency_per_min: float,
                 ip: str | None = None, 
                 port: int | None = None,
                 prompt: str = 'B2900A>',
                 id: str = 'KeySight B2900A'):
        super().__init__(id, ip, port, prompt)
        
        if not 1 <= read_frequency_per_min <= 2000:
            raise ValueError(f'Bad value of read frequency {read_frequency_per_min} (must be 1-2000)')

        self.nplc_setting = 1 / read_frequency_per_min * 60.0
        self.id = id

    @property
    def readable_keys(self) -> Set[DataKeys]:
        """Returns the set of keys that can be read from the device."""
        return {Ammeter.DataKeys.CURRENT}

    @property
    def writable_keys(self) -> Set[DataKeys]:
        """Returns the set of keys that can be written to the device."""
        return set()

    async def send_command(self, command: str) -> str | None:
        """Send command to Ammeter, consume echo and parse for any response"""
        await self._write(command)
        terminator = self._prompt if self._prompt is not None else '\n'
        raw_response = await self._read_until(terminator)
        response_lines = raw_response.split()
        return None

    async def read_data(self, data_key: DataKeys) -> float:
        match data_key:
            case Ammeter.DataKeys.CURRENT:
                await self.send_command(Ammeter.Commands.MEASURE_CURRENT)                                
                try:
                    async with asyncio.timeout(2.0): # Overall timeout for the read operation
                        while True:
                            response = await self.send_command(Ammeter.Commands.MEASURE_CURRENT)
                            try:
                                assert response is not None
                                return float(response)
                            except ValueError or AssertionError:
                                    _log.debug(f"Error in current measurement, non-float response: {response!r}")
                except TimeoutError:
                    _log.error("Timeout occurred while waiting for a valid numeric response from the ammeter.")
                    raise ConnectionAbortedError("Ammeter timed out.")
        raise KeyError(f'Read operation for data_key {data_key.name} not implemented.')

    async def write_data(self, data_key: DataKeys, value: float) -> None:
        raise KeyError(f'Write operation for data_key {data_key.name} not implemented.')

    async def connect(self) -> None:
        _log.debug(f'Connecting Ammeter at {self._host}...')
        await super().connect()
        await self._setup()

    async def _setup(self) -> None:
        await self.reset()
        _log.debug(f'Setting up Ammeter at {self._host}...')
        await asyncio.sleep(2)
        setup_commands = [Ammeter.Commands.CURRENT_FUNCTION, 
                          Ammeter.Commands.CURRENT_AUTO_RANGE, 
                          Ammeter.Commands.CURRENT_NPLC_AUTO_OFF, 
                          Ammeter.Commands.SET_NPLC.format(self.nplc_setting),
                          Ammeter.Commands.INPUT_ON]
        for command in setup_commands:
            await self._write(command)
    
    async def reset(self) -> None:
        _log.debug(f'Resetting Ammeter at {self._host}...')
        await self.send_command(Ammeter.Commands.RESET)
        _log.debug('Ammeter reset.')