from ops.ecris.legacy.emittance_scan import Motor
from tests.fakes import FakeMotorController

from unittest.mock import patch, call

import pytest

MODULE = 'ops.ecris.legacy.emittance_scan.'

def test_motor_init():
    expected_ip = '10.10.100.60'
    port = 5002
    commands = ["PROG0", "ACC 5 DEC 5 VEL 15 STP 100"]
    fake_controller = FakeMotorController()

    with patch(MODULE + 'telnetlib') as mock_telnet, \
        patch(MODULE + 'time.sleep') as mock_sleep:
        mock_connection = mock_telnet.Telnet.return_value
        mock_connection.write = fake_controller.handle_command
        mock_connection.read_very_eager = fake_controller.read_buffer
        motor = Motor(beam_line=0)

    mock_telnet.Telnet.assert_called_once_with(expected_ip, port, timeout=3)
    assert fake_controller.decoded_log == commands
    assert fake_controller.buffer_clear
        
    mock_sleep.assert_has_calls([call(0.07)]*2)
    assert mock_sleep.call_count == len(commands)
