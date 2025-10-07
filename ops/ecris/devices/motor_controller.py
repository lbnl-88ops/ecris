import asyncio
from logging import getLogger
from typing import Any

from ops.ecris.model.device import TelnetDevice

_log = getLogger(__name__)

class MotorController(TelnetDevice):
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