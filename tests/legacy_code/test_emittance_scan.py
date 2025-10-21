from ops.ecris.legacy.emittance_scan import Motor
from tests.fakes import FakeMotorController, fake_motor_controller

from unittest.mock import MagicMock, patch, call

import pytest

MODULE = 'ops.ecris.legacy.emittance_scan.'

@pytest.fixture
def mock_motor_controller_no_reset():
    fake_controller = FakeMotorController()
    with patch(MODULE + 'telnetlib') as mock_telnet, \
        patch(MODULE + 'time.sleep') as mock_sleep:
        mock_connection = mock_telnet.Telnet.return_value
        mock_connection.write = fake_controller.handle_command
        mock_connection.read_very_eager = fake_controller.read_buffer
        initialized_motor = Motor(beam_line=0)
        yield initialized_motor, fake_controller, mock_telnet, mock_sleep

@pytest.fixture
def mock_motor_controller(mock_motor_controller_no_reset):
    initialized_motor, fake_controller, mock_telnet, mock_sleep = mock_motor_controller_no_reset
    mock_sleep.reset_mock()
    fake_controller.post_init_reset()
    
    yield initialized_motor, fake_controller, mock_telnet, mock_sleep

def test_motor_init(mock_motor_controller_no_reset):
    _, fake_controller, mock_telnet, mock_sleep = mock_motor_controller_no_reset
    expected_ip = '10.10.100.60'
    port = 5002
    commands = ["PROG0", "ACC 5 DEC 5 VEL 15 STP 100"]

    mock_telnet.Telnet.assert_called_once_with(expected_ip, port, timeout=3)
    assert fake_controller.decoded_log == commands
    assert fake_controller.buffer_clear
        
    mock_sleep.assert_has_calls([call(0.07)]*2)
    assert mock_sleep.call_count == len(commands)
 
@pytest.mark.parametrize("input_axis, expected_other_axis",
                         [(0, 1), (1, 0), (2, 3), (3, 2),])
@pytest.mark.parametrize("expected_state", [True, False])
def test_axis_clear_calculates_correct_bit_and_calls_send_command( 
    mock_motor_controller, 
    input_axis, 
    expected_other_axis,
    expected_state):

    motor, fake_controller, _ , mock_sleep = mock_motor_controller
    fake_controller.axis_clear_states[expected_other_axis] = expected_state

    expected_bit = 16128 + expected_other_axis * 32
    commands = [f"?BIT({expected_bit})"]

    state = motor.axis_clear(input_axis)

    assert fake_controller.decoded_log == commands
    assert fake_controller.buffer_clear
        
    mock_sleep.assert_has_calls([call(0.07)]*len(commands))
    assert mock_sleep.call_count == len(commands)
    assert state == expected_state

def test_move_to(mock_motor_controller):
    motor, fake_controller, _, mock_sleep = mock_motor_controller
    fake_controller.axis_clear_states = [True, True, True, True]
    position_to_move = 15.5
    axis_to_move = 0 # X
    fake_controller.set_motion_steps(2)

    motor.move_to(position_to_move, axis_to_move)
    expected_bit = 16128 + 32

    expected_commands = [
        f"?BIT({expected_bit})",
        "DRIVE ON X",
        f"X{position_to_move}",
        "?BIT(516)", # First check, returns 1 (in motion)
        "?BIT(516)", # Second check, returns 1 (in motion)
        "?BIT(516)", # Third check, returns 0 (motion complete)
        "DRIVE OFF X"
    ]
    
    assert fake_controller.decoded_log == expected_commands
    assert fake_controller.buffer_clear
