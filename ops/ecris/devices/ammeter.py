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
    def __init__(self, read_frequency_per_min: float,
                 ip: str | None = None, 
                 port: int | None = None,
                 prompt: str = 'B2900A>'):
        super().__init__(ip, port, prompt)
        
        if not 1 <= read_frequency_per_min <= 2000:
            raise ValueError(f'Bad value of read frequency {read_frequency_per_min} (must be 1-2000)')

        self.nplc_setting = 1 / read_frequency_per_min * 60.0

    @property
    def readable_keys(self) -> Set[DataKeys]:
        """Returns the set of keys that can be read from the device."""
        return {Ammeter.DataKeys.CURRENT}

    @property
    def writable_keys(self) -> Set[DataKeys]:
        """Returns the set of keys that can be written to the device."""
        return {Ammeter.DataKeys.NPLC_SETTING}

    async def read_data(self, data_key: DataKeys) -> float:
        match data_key:
            case Ammeter.DataKeys.CURRENT:
                await self._write('meas:curr?')
                response = await self._read_until()
                return float(response)
        raise KeyError(f'Read operation for data_key {data_key.name} not implemented.')

    async def write_data(self, data_key: DataKeys, value: float) -> None:
        match data_key:
            case Ammeter.DataKeys.NPLC_SETTING:
                await self._write(f':sens:curr:nplc {value}')
                return 
        
        raise KeyError(f'Write operation for data_key {data_key.name} not implemented.')

    async def setup(self) -> None:
        await self.reset()
        await asyncio.sleep(2)
        for command in [
            ':sens:func "curr"',
            ':sens:curr:rang:auto on',
            ':sens:curr:nplc:auto off',
            f':sens:curr:nplc {self.nplc_setting}',
            ':inp on'
        ]:
            await self._write(command)
    
    async def reset(self) -> None:
        _log.info(f'Resetting Ammeter at {self._host}...')
        await self._write("*rst")
        _log.info('Ammeter reset.')