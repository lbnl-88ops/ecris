from imaplib import Commands
from typing import List, Dict, Any, Tuple
from enum import Enum, auto

from unittest.mock import call, MagicMock
import pytest

from ops.ecris.devices.motor_controller_specification import Axis
from ops.ecris.legacy.mappings import LEGACY_AXIS_MAPPING


class FakeMotorController:
    def __init__(self, unit_mode="mm", initial_positions=None):
        # --- CONFIGURATION ---
        self.unit_mode = unit_mode
        self._positions = initial_positions or [100.0, 100.0, 100.0, 100.0]

        if self.unit_mode == "mm":
            self._unit_distance = 19685
        elif self.unit_mode == "steps":
            self._unit_distance = 1
        elif self.unit_mode == "inch":
            self._unit_distance = 500000
        else:
            self._unit_distance = -1

        self.axis_clear_states = {
            Axis.X: True,
            Axis.Y: True,
            Axis.Z: True,
            Axis.A: True,
        }  # Default to clear

        self._prompt = "SYS> "
        self._buffer = []
        self._to_buffer("Unkown banner.")
        self.command_log = []
        self._current_motion_steps: int = 0

        # Test parameters
        self.motion_steps_remaining: List[int] = [0]
        self.coastdown_steps_remaining: List[int] = []
        self.decrement_motion_on_check: bool = False
        self.axis_clear_after_stop: Axis | None = None
        self.exception_timer: Tuple[int, Exception] | None = None
        self.coasting_down = False

    def post_init_reset(self):
        self.command_log = []
        self._buffer = []
        self._prompt = "SYS> "

    @property
    def buffer_clear(self) -> bool:
        return len(self._buffer) == 0

    def _to_buffer(self, unencoded_command) -> None:
        self._buffer.append(f"{unencoded_command}\r\n{self._prompt}".encode("ascii"))

    @property
    def decoded_log(self) -> List[str]:
        return [s.decode("ascii").strip() for s in self.command_log]

    def set_motion_steps(self, steps: List[int]):
        self.motion_steps_remaining = steps

    def read_buffer(self, prompt: bytes | None = None) -> bytes:
        end = len(self._buffer)
        if prompt is not None:
            for i, line in enumerate(self._buffer):
                if line.decode("ascii").endswith(prompt.decode("ascii")):
                    end = i
                    break
        read_buffer = b"".join(self._buffer[0 : end + 1])
        del self._buffer[0 : end + 1]
        return read_buffer

    def _move(self) -> None:
        if self.decrement_motion_on_check and self._current_motion_steps > 0:
            self._current_motion_steps -= 1
            if self._current_motion_steps == 0:
                if self.coasting_down:
                    self.coasting_down = False
                if self.axis_clear_after_stop is not None:
                    self.axis_clear_states[self.axis_clear_after_stop] = True

    def _put_in_motion(self) -> None:
        if self._current_motion_steps == 0:
            if self.motion_steps_remaining:
                self._current_motion_steps = self.motion_steps_remaining.pop(0)
                self.in_normal_motion = True
            else:
                raise RuntimeError
        else:
            raise RuntimeError

    def handle_command(self, raw_command):
        if self.exception_timer is not None:
            value, exception = self.exception_timer
            if value == 0:
                self.exception_timer = None
                raise exception
            else:
                self.exception_timer = (value - 1, exception)
        self.command_log.append(raw_command)
        command = raw_command.decode("ascii").strip()
        command_return = ""

        if command == "PROG0":
            self._prompt = "POO> "
        elif command.startswith("?BIT("):
            queried_bit = int(command.removeprefix("?BIT(")[:-1])
            match queried_bit:
                case 16128:
                    command_return = int(self.axis_clear_states[Axis.X])
                case 16160:
                    command_return = int(self.axis_clear_states[Axis.Y])
                case 16192:
                    command_return = int(self.axis_clear_states[Axis.Z])
                case 16224:
                    command_return = int(self.axis_clear_states[Axis.A])
                case 516:
                    command_return = int(self._current_motion_steps > 0)
                    self._move()
        elif (
            command.startswith("X")
            or command.startswith("Y")
            or command.startswith("Z")
            or command.startswith("A")
        ):  # move command
            self._put_in_motion()
        elif command.startswith("DRIVE OFF"):
            if self.coastdown_steps_remaining and not self.coasting_down:
                self.coasting_down = True
                self._current_motion_steps = self.coastdown_steps_remaining.pop(0)

        self._to_buffer(command + "\r\n" + str(command_return))


class FakeState(Enum):
    AxisNotClear = auto()
    AxisCentered = auto()
    MotionSteps = auto()
    CoastDownSteps = auto()
    DecrementMotionOnCheck = auto()
    ClearAxisOnStop = auto()
    InterruptAfterCommands = auto()


class CheckTestPassed:
    def __init__(self, fake: FakeMotorController, mock_sleep, commands):
        self._mock_sleep = mock_sleep
        self._fake = fake
        self._commands = commands

    def assert_passed(self):
        assert self._fake.decoded_log == self._commands, (
            f"{self._fake.decoded_log} != {self._commands}"
        )
        assert self._fake.buffer_clear
        self._mock_sleep.assert_has_calls([call(0.07)] * len(self._commands))
        assert self._mock_sleep.call_count == len(self._commands)


def set_up_test(setup_classes, states: Dict[FakeState, Any], commands):
    fake: FakeMotorController
    motor, fake, mock_connection, mock_sleep = setup_classes
    for state, value in states.items():
        match state:
            case FakeState.AxisNotClear:
                fake.axis_clear_states[value] = False
            case FakeState.MotionSteps:
                if isinstance(value, int):
                    fake.set_motion_steps([value])
                else:
                    fake.set_motion_steps(value)
            case FakeState.DecrementMotionOnCheck:
                fake.decrement_motion_on_check = value
            case FakeState.ClearAxisOnStop:
                fake.axis_clear_after_stop = value
            case FakeState.InterruptAfterCommands:
                fake.exception_timer = value
            case FakeState.AxisCentered:
                motor.centered[LEGACY_AXIS_MAPPING[value]] = True
            case FakeState.CoastDownSteps:
                fake.coastdown_steps_remaining = value
    return CheckTestPassed(fake, mock_sleep, commands)

