import asyncio
import time
from logging import getLogger
from typing import Any, List, Type, TypeVar, get_args, get_origin, overload

from ops.ecris.drivers.telnet_driver import TelnetDriver
from ops.ecris.utilities.decorators import with_lock_named

from .exceptions import DeviceMalfunctionError
from .motor_controller_specification import (
    MID_POINT_OFFSETS,
    PERPENDICULAR_AXIS,
    Axis,
    Bit,
    Commands,
)

_log = getLogger(__name__)


_T = TypeVar("_T")


class MotorController(TelnetDriver):
    def __init__(
        self,
        id: str = "ACR74C",
        ip: str | None = None,
        port: int | None = None,
        prompt: str = "SYS>",
        encoding: str = "ascii",
        fast_ramp: bool = False
    ):
        super().__init__(id, ip, port, prompt, encoding, command_terminator="\r")
        self._move_lock = asyncio.Lock()
        self._centered = {a: False for a in Axis}
        self._motor_on = {a: False for a in Axis}
        self._fast_ramp = fast_ramp

    def is_centered(self, axis: Axis) -> bool:
        return self._centered[axis]

    async def read_data(self, data_key: Any) -> float:
        raise NotImplementedError

    async def write_data(self, data_key: Any, value: float) -> None:
        raise NotImplementedError

    async def connect(self, wakeup_required=True) -> None:
        _log.debug(f"Connecting Motor Controller at {self._host}")
        await super().connect()
        await self._setup()

    async def _clear_buffer(self):
        await self._read_until(self._prompt)

    @overload
    async def send_command(self, command: str, return_type: Type[_T]) -> _T: ...

    @overload
    async def send_command(self, command: str, return_type: None = None) -> None: ...

    async def send_command(self, command: str, return_type: Type[_T] | None = None) -> _T | None:
        _log.debug(f"Sending command {command}")
        await self._write(command)
        raw_response = await self._read_until(self._prompt)
        _log.debug(f"Raw response {raw_response}")

        if return_type is not None:
            response_lines = [ln.strip() for ln in raw_response.split("\r\n")]
            data_lines = [
                ln for ln in response_lines if ln and ln != self._prompt.strip() and ln != command
            ]

            if get_origin(return_type) is list:
                line_type_args = get_args(return_type)

                if not line_type_args:
                    raise TypeError("List return type must be subscripted, e.g., List[str]")

                line_type = line_type_args[0]
                return [line_type(line) for line in data_lines]

            elif len(data_lines) == 1:
                value = data_lines[0]
                try:
                    _log.debug(f"Processing return value {value}")
                    if return_type is bool:
                        match value.lower():
                            case "-1" | "1" | "yes" | "true" | "on":
                                return return_type(1)  # Use 1 for True to satisfy TypeVar
                            case "0" | "no" | "off" | "false":
                                return return_type(0)  # Use 0 for False to satisfy TypeVar
                            case _:
                                raise ValueError(f"Unrecognized boolean value {value}")
                    return return_type(value)
                except (ValueError, TypeError) as e:
                    raise RuntimeError(
                        f"Could not convert response '{value}' to type {return_type.__name__}"
                    ) from e

            else:
                raise RuntimeError(
                    f"Expected a single-line response for type '{return_type.__name__}' "
                    f"but received {len(data_lines)} lines: {data_lines}"
                )

        return None  # No return_type was specified

    async def _handshake(self):
        """Sends commands to verify connection and logs device info."""
        try:
            await asyncio.wait_for(self.send_command(""), timeout=3.0)
        except TimeoutError:
            _log.debug("Wakeup timed out, controller may already be in program mode, reattempting")
            self._prompt = "P00>"
            await self._clear_buffer()
            await asyncio.wait_for(self.send_command(""), timeout=3.0)
        try:
            firmware_version = await self.send_command(Commands.GET_FIRMWARE_VERSION, List[str])
            attachment_list = await self.send_command(Commands.GET_ATTACHMENTS, List[str])
            attachments_str = "\n".join(attachment_list)
            _log.info(f"Connection to {self.id} verified, firmware version {firmware_version}")
            _log.info(f"Configured attachments:\n{attachments_str}")

        except (RuntimeError, ConnectionError) as e:
            _log.error("Handshake with motor controller failed.", exc_info=True)
            raise ConnectionError("Handshake not verified, check driver configuration.") from e

    async def _setup(self) -> None:
        self._prompt = "P00>"
        await self.send_command(Commands.OPEN_PROGRAM0)
        if self._fast_ramp:
            await self.send_command(Commands.SET_FAST_RAMPING)
        else:
            await self.send_command(Commands.SET_RAMPING)

    async def _movement_stopped(self, axis: Axis | None = None, initial_wait: float = 0):
        is_moving = True
        try:
            start = time.perf_counter()
            calls = 0
            await asyncio.sleep(initial_wait)
            while is_moving:
                calls += 1
                is_moving = await self.send_command(Commands.CHECK_IN_MOTION(), bool)
                # Prevent busy-wait condition (constantly pinging the controller)
                # await asyncio.sleep(0.01)
            total_time = time.perf_counter() - start
            _log.info(f"Time waiting for movement to stop: {total_time}, {calls=}, {total_time/calls} per call")
        except KeyboardInterrupt:
            if axis is not None:
                await self.send_command(Commands.SET_BIT(Bit.KILL_ALL_MOVES(axis)))
                await self.send_command(Commands.CLEAR_BIT(Bit.KILL_ALL_MOVES(axis)))
                # await self.send_command(Commands.DRIVE_OFF(axis))
                raise
            else:
                raise

    async def get_position(self, axis: Axis) -> float:
        return await self.send_command(Commands.GET_POSITION(axis), float)

    async def get_scale(self) -> float:
        return await self.send_command(Commands.GET_SCALE, float)

    @with_lock_named("_move_lock")
    async def is_axis_clear_to_move(self, axis: Axis) -> bool:
        return await self._is_axis_clear_to_move_unsafe(axis)

    async def _is_axis_clear_to_move_unsafe(self, axis: Axis) -> bool:
        return await self.send_command(Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis), bool)

    @with_lock_named("_move_lock")
    async def move_to_position(self, axis: Axis, position: float, *, relative=False):
        return await self._move_to_position_unsafe(axis, position, relative=relative)

    async def _move_to_position_unsafe(self, axis: Axis, position: float, *, relative=False):
        if not await self._is_axis_clear_to_move_unsafe(axis):
            perpendicular_axis = PERPENDICULAR_AXIS[axis]
            await self._move_to_position_unsafe(perpendicular_axis, 200)
            await self.send_command(Commands.CLEAR_BIT(Bit.KILL_ALL_MOVES(axis)))
            # await self.send_command(Commands.DRIVE_OFF(axis))
            await self._movement_stopped(perpendicular_axis)
            if not await self._is_axis_clear_to_move_unsafe(axis):
                await self.send_command(Commands.DRIVE_OFF(axis))
                raise DeviceMalfunctionError(f"Axis {perpendicular_axis} cannot be cleared")
        move_command = Commands.RELATIVE_MOVE if relative else Commands.MOVE
        if self._motor_on[axis]:
            _log.info('Motor already on.')
        else:
            _log.info('Starting motor.')
            await self.send_command(Commands.DRIVE_ON(axis))
            self._motor_on[axis] = True
        await self.send_command(move_command(axis, position) + " : " + Commands.WAIT_UNTIL_STOP)
        # await self._movement_stopped(axis)
        # await self.send_command(Commands.DRIVE_OFF(axis))
        return

    @with_lock_named("_move_lock")
    async def move_axis_to_positive_eof(self, axis):
        await self._move_axis_to_positive_eof_unsafe(axis)

    async def _move_axis_to_positive_eof_unsafe(self, axis):
        await self._move_to_position_unsafe(axis, 200)
        await self.send_command(Commands.CLEAR_BIT(Bit.KILL_ALL_MOVES(axis)))
        await self.send_command(Commands.DRIVE_OFF(axis))
        self._motor_on[axis] = False

    @with_lock_named("_move_lock")
    async def center_axis(self, axis):
        if not await self._is_axis_clear_to_move_unsafe(axis):
            perpendicular_axis = PERPENDICULAR_AXIS[axis]
            await self._move_axis_to_positive_eof_unsafe(perpendicular_axis)
            await self._movement_stopped(perpendicular_axis)
            if not await self._is_axis_clear_to_move_unsafe(axis):
                await self.send_command(Commands.DRIVE_OFF(axis))
                raise DeviceMalfunctionError(f"Axis {axis} cannot be cleared")
        if self.is_centered(axis):
            _log.info("Device already centered")
            # await self._move_to_position_unsafe(axis, 0)
            return
        _log.info("Centering device...")
        await self._move_to_position_unsafe(axis, -200)
        await self.send_command(Commands.CLEAR_BIT(Bit.KILL_ALL_MOVES(axis)))
        self._motor_on[axis] = False
        # await self._movement_stopped(axis)
        await self._move_to_position_unsafe(axis, MID_POINT_OFFSETS[axis], relative=True)
        # await self._movement_stopped(axis)
        await self.send_command(Commands.RESET_AXIS(axis))
        # await self.send_command(Commands.DRIVE_OFF(axis))
        self._centered[axis] = True
        _log.info(f"Axis {axis} centered.")
