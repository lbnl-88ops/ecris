from typing import List

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

        self._is_moving = False
        self._axis_clear_states = [True, True, True, True] # Default to clear

        self._prompt = "SYS> "
        self._buffer = []
        self._to_buffer('Unkown banner.')
        self.command_log = []

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
                    command_return = int(self._axis_clear_states[0])
                case 16160:
                    command_return = int(self._axis_clear_states[1])
                case 16192:
                    command_return = int(self._axis_clear_states[2])
                case 16224:
                    command_return = int(self._axis_clear_states[3])

        self._to_buffer(command + '\r\n' + str(command_return))