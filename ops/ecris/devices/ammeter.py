import asyncio
from logging import getLogger
from typing import Set
from enum import Enum, auto

from ops.ecris.model.device import TelnetDevice, Device

_log = getLogger(__name__)

class Ammeter(TelnetDevice, Device):
    class DataKeys(Enum):
        """Defines the valid data keys for the Ammeter."""
        CURRENT = auto()
        NPLC_SETTING = auto()
    class Commands(str, Enum):
        MEASURE_CURRENT = 'meas:curr?'
        RESET = '*rst'

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
        return {Ammeter.DataKeys.NPLC_SETTING}

    async def send_command(self, command):
        await self._write(command)
        response = await self._read_until('\n')
        if command not in response:
            _log.warning(f'Recieved unexpected response: {response} expected command echo {command}')

    async def read_data(self, data_key: DataKeys) -> float:
        match data_key:
            case Ammeter.DataKeys.CURRENT:
                await self.send_command(Ammeter.Commands.MEASURE_CURRENT)                                
                try:
                    async with asyncio.timeout(2.0): # Overall timeout for the read operation
                        while True:
                            response = await self._read_until('\n')
                            if not response:
                                continue
                            try:
                                return float(response)
                            except ValueError:
                                if Ammeter.Commands.MEASURE_CURRENT in response:
                                    _log.debug("Command echo recieved and discarded")
                                else:
                                    _log.debug(f"Discarding non-numeric line: {response!r}")
                                continue
                except TimeoutError:
                    _log.error("Timeout occurred while waiting for a valid numeric response from the ammeter.")
                    raise ConnectionAbortedError("Ammeter timed out.")
        raise KeyError(f'Read operation for data_key {data_key.name} not implemented.')

    async def write_data(self, data_key: DataKeys, value: float) -> None:
        match data_key:
            case Ammeter.DataKeys.NPLC_SETTING:
                await self._write(f':sens:curr:nplc {value}')
                return 
        
        raise KeyError(f'Write operation for data_key {data_key.name} not implemented.')

    async def connect(self) -> None:
        _log.debug(f'Connecting Ammeter at {self._host}...')
        await super().connect()
        await self._setup()

    async def _setup(self) -> None:
        await self.reset()
        _log.debug(f'Setting up Ammeter at {self._host}...')
        await asyncio.sleep(2)
        for command in [
            ':sens:func "curr"',
            ':sens:curr:rang:auto on',
            ':sens:curr:nplc:auto off',
            f':sens:curr:nplc {self.nplc_setting}',
            ':inp on'
        ]:
            await self.send_command(command)
    
    async def reset(self) -> None:
        _log.debug(f'Resetting Ammeter at {self._host}...')
        await self.send_command(Ammeter.Commands.RESET)
        _log.debug('Ammeter reset.')