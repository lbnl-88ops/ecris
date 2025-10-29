import asyncio
from enum import StrEnum, Enum, auto
from logging import getLogger
from typing import Any, List, Type, TypeVar, overload
import asyncio

from ops.ecris.utilities.decorators import with_lock_named
from ops.ecris.model.device import TelnetDevice
from .motor_controller_specification import Commands, Axis, PERPENDICULAR_AXIS

_log = getLogger(__name__)

_T = TypeVar("_T")


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

    @overload
    async def send_command(self, command: str, return_type: Type[_T]) -> _T: ...

    @overload
    async def send_command(self, command: str, return_type: None = None) -> None: ...

    async def send_command(self, command: str, return_type: Type[_T] | None = None) -> _T | None:
        await self._write(command)
        await asyncio.sleep(0.07)
        raw_response = await self._read_until(self._prompt)
        if return_type is not None:
            response_lines = [ln.strip() for ln in raw_response.split("\r\n")]
            print(f"{response_lines=}")
            response = [
                ln for ln in response_lines if ln != self._prompt.strip() and ln != command
            ]
            if len(response) != 1:
                raise RuntimeError(f"Unexpected response from Motor Controller: {response}")
            try:
                value = response[0]
                if return_type is bool and value.isdigit:
                    return bool(int(value))
                return return_type(response[0])
            except ValueError:
                raise RuntimeError(f"Could not convert {response=} to type {return_type}")

    async def _setup(self) -> None:
        self._prompt = "P00> "
        await self.send_command(Commands.OPEN_PROGRAM0)
        await self.send_command(Commands.SET_RAMPING)

    async def _movement_stopped(self):
        is_moving = True
        while is_moving:
            is_moving = await self.send_command(Commands.CHECK_IN_MOTION(), bool)

    async def is_axis_clear_to_move(self, axis: Axis) -> bool:
        return await self.send_command(Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis), bool)

    @with_lock_named("_move_lock")
    async def move_to_position(self, axis: Axis, position: float, *, relative=False):
        if not await self.is_axis_clear_to_move(axis):
            pass
        move_command = Commands.RELATIVE_MOVE if relative else Commands.MOVE
        await self.send_command(Commands.DRIVE_ON(axis))
        await self.send_command(move_command(axis, position))
        await self._movement_stopped()
        await self.send_command(Commands.DRIVE_OFF(axis))
        return
