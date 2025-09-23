import asyncio
from logging import getLogger
from ipaddress import ip_address, IPv4Address
from typing import Dict, Type, List
import time

from .device import TelnetDevice

_log = getLogger(__name__)

class Ammeter(TelnetDevice):
    def __init__(self, read_frequency: float,
                 ip: str | None = None, port: int | None = None):
        super().__init__(ip, port)
        self.read_frequency = read_frequency
        if not 1 <= self.read_frequency <= 2000:
            raise ValueError(f'Bad value of read frequency {self.read_frequency} (must be 1-2000)')
        self.read_hz = 1/self.read_frequency * 60.0

    async def get_data(self) -> Dict:
        await self._write('meas:curr?')
        response = await self._read_until()
        current = float(response)
        return {
            "time": time.time(),
            "current": current,
        }

    async def setup(self) -> None:
        await self.reset()
        await asyncio.sleep(2)
        for command in [
            ':sens:func "curr"',
            ':sens:curr:rang:auto on',
            ':sens:curr:nplc:auto off',
            f':sens:curr:nplc {self.read_hz}',
            ':inp on'
        ]:
            await self._write(command)
    
    async def reset(self) -> None:
        _log.info(f'Resetting Ammeter at {self._host}...')
        await self._write("*rst")
        _log.info('Ammeter reset.')

    @property
    def data_types(self) -> Dict[str, Type]:
        return {"time": float, "current": float}

    @property
    def data_keys(self) -> List[str]:
        return ["time", "current"]