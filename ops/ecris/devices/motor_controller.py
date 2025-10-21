import asyncio
from enum import StrEnum, Enum, auto
from logging import getLogger
from typing import Any

from ops.ecris.model.device import TelnetDevice

_log = getLogger(__name__)

class MotorController(TelnetDevice):

    class Commands(StrEnum):
        OPEN_PROGRAM0 = 'PROG0'
        SET_RAMPING = "ACC 5 DEC 5 VEL 15 STP 100"

    class Axis(Enum):
        X = auto()
        Y = auto()
        Z = auto()
        A = auto()

    PERPENDICULAR_AXIS = {
        Axis.X: Axis.Y,
        Axis.Y: Axis.X,
        Axis.Z: Axis.A,
        Axis.A: Axis.Z
    }

    def __init__(self, id: str = 'ACR74C', 
                 ip: str | None = None, 
                 port: int | None = None, 
                 prompt: str = 'SYS>',
                 encoding: str = 'ascii'):
        super().__init__(id, ip, port, prompt, encoding)

    async def read_data(self, data_key: Any) -> float:
        raise NotImplementedError

    async def write_data(self, data_key: Any, value: float) -> None:
        raise NotImplementedError

    async def connect(self) -> None:
        _log.debug(f'Connecting Motor Controller at {self._host}')
        await super().connect()
        await self._setup()

    async def send_command(self, command: str):
        await self._write(command)
        raw_response = await self._read_until(self._prompt if self._prompt is not None else '\n')
        response_lines = [l.strip() for l in raw_response.split()]
        response = [l for l in response_lines if l != self._prompt and l != command]
        if len(response) == 1:
            return response[0]
        return response

    async def _setup(self) -> None:
        self._prompt = 'P00>'
        await self.send_command(MotorController.Commands.OPEN_PROGRAM0)
        await self.send_command(MotorController.Commands.SET_RAMPING)