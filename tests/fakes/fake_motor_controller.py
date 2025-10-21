from imaplib import Commands
from typing import List, Dict, Any
from enum import Enum, auto

from unittest.mock import call

from ops.ecris.devices.motor_controller_specification import Axis

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

        self.axis_clear_states = {Axis.X: True, 
                                  Axis.Y: True, 
                                  Axis.Z: True, 
                                  Axis.A: True} # Default to clear

        self._prompt = "SYS> "
        self._buffer = []
        self._to_buffer('Unkown banner.')
        self.command_log = []
        self._motion_steps_remaining: int = 0

    def post_init_reset(self):
        self.command_log = []
        self._buffer = []
        self._prompt = "SYS> "

    @property
    def buffer_clear(self) -> bool:
        return len(self._buffer) == 0

    def _to_buffer(self, unencoded_command) -> None:
        self._buffer.append(f"{unencoded_command}\r\n{self._prompt}".encode('ascii'))

    @property
    def decoded_log(self) -> List[str]:
        return [s.decode('ascii').strip() for s in self.command_log]

    def set_motion_steps(self, steps: int):
        self._motion_steps_remaining = steps


    def read_buffer(self, prompt = None) -> bytes:
        end = len(self._buffer)
        if prompt is not None:
            for i, line in enumerate(self._buffer):
                if line.decode('ascii').endswith(prompt):
                    end = i
                    break
        read_buffer = b''.join(self._buffer[0:end + 1])
        del self._buffer[0:end + 1]
        return read_buffer

    def handle_command(self, raw_command):
        self.command_log.append(raw_command)
        command = raw_command.decode('ascii').strip()
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
                    command_return = int(self._motion_steps_remaining > 0)
                    self._motion_steps_remaining -= 1

        self._to_buffer(command + '\r\n' + str(command_return))

class FakeState(Enum):
    AxisNotClear = auto()

class CheckTestPassed:
    def __init__(self, fake: FakeMotorController, mock_sleep, commands):
        self._mock_sleep = mock_sleep
        self._fake = fake
        self._commands = commands

    def assert_passed(self):
        assert self._fake.decoded_log == self._commands
        assert self._fake.buffer_clear
        self._mock_sleep.assert_has_calls([call(0.07)]*len(self._commands))
        assert self._mock_sleep.call_count == len(self._commands)

        

def set_up_test(setup_classes,
               states: Dict[FakeState, Any],
               commands):
    motor, fake, mock_connection, mock_sleep = setup_classes
    for state, value in states.items():
        match state:
            case FakeState.AxisNotClear:
                fake.axis_clear_states[value] = False
    return CheckTestPassed(fake, mock_sleep, commands)
    