import asyncio
from enum import StrEnum, Enum, auto
from logging import getLogger
from typing import Any, List
import asyncio

from ops.ecris.model.device import TelnetDevice
from .motor_controller_specification import Commands, Axis, PERPENDICULAR_AXIS

_log = getLogger(__name__)


class MotorController(TelnetDevice):
    def __init__(
        self,
        id: str = "ACR74C",
        ip: str | None = None,
        port: int | None = None,
        prompt: str = "SYS> ",
        encoding: str = "ascii",
    ):
        super().__init__(id, ip, port, prompt, encoding)
        self._move_lock = asyncio.Lock()

    async def read_data(self, data_key: Any) -> float:
        raise NotImplementedError

    async def write_data(self, data_key: Any, value: float) -> None:
        raise NotImplementedError

    async def connect(self) -> None:
        _log.debug(f"Connecting Motor Controller at {self._host}")
        await super().connect()
        await self._setup()

    async def send_command(self, command: str) -> bool | float | str:
        await self._write(command)
        await asyncio.sleep(0.07)
        raw_response = await self._read_until(self._prompt)
        print(f"{raw_response=}")
        response_lines = [l.strip() for l in raw_response.split("\r\n")]
        response = [l for l in response_lines if l != self._prompt.strip() and l != command]
        if len(response) == 1:
            try:
                return bool(int(response[0]))
            except ValueError:
                try:
                    return float(response[0])
                except ValueError:
                    return response[0]

    async def _setup(self) -> None:
        self._prompt = "P00> "
        await self.send_command(Commands.OPEN_PROGRAM0)
        await self.send_command(Commands.SET_RAMPING)

    async def _is_moving(self):
        is_moving = True
        while is_moving:
            is_moving = await self.send_command(Commands.CHECK_IN_MOTION())

    async def is_axis_clear_to_move(self, axis: Axis):
        response = await self.send_command(Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis))
        try:
            return bool(int(response))
        except ValueError:
            raise ValueError(f"Bad response from motor controller: {response}")

    async def move_to_position(self, axis: Axis, position: float, *, relative=False):
        async with self._move_lock:
            if not await self.is_axis_clear_to_move(axis):
                pass
            await self.send_command(Commands.DRIVE_ON(axis))
            await self.send_command(
                Commands.MOVE(axis, position)
                if not relative
                else Commands.RELATIVE_MOVE(axis, position)
            )
            await self._is_moving()
            await self.send_command(Commands.DRIVE_OFF(axis))
        return
