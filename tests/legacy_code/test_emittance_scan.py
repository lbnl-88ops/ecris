from ops.ecris.legacy.emittance_scan import Motor
from tests.fakes import FakeMotorController
from tests.fakes.fake_motor_controller import set_up_test, FakeState
from ops.ecris.devices.motor_controller_specification import (
    Axis, Commands, PERPENDICULAR_AXIS)

from unittest.mock import MagicMock, patch, call

import pytest

MODULE = 'ops.ecris.legacy.emittance_scan.'
LEGACY_AXIS_MAPPING = {
    Axis.X: 0,
    Axis.Y: 1,
    Axis.Z: 2,
    Axis.A: 3
}

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
    commands = [Commands.OPEN_PROGRAM0, Commands.SET_RAMPING]

    mock_telnet.Telnet.assert_called_once_with(expected_ip, port, timeout=3)
    assert fake_controller.decoded_log == commands
    assert fake_controller.buffer_clear
        
    mock_sleep.assert_has_calls([call(0.07)]*2)
    assert mock_sleep.call_count == len(commands)
 
@pytest.mark.parametrize("input_axis", [Axis.X, Axis.Y, Axis.Z, Axis.Z])
@pytest.mark.parametrize("expected_state", [True, False])
def test_axis_clear_calculates_correct_bit_and_calls_send_command( 
    mock_motor_controller, input_axis, expected_state):
    perpendicular_axis = PERPENDICULAR_AXIS[input_axis]

    motor, fake_controller, _ , mock_sleep = mock_motor_controller
    expected_bit = 16128 + LEGACY_AXIS_MAPPING[perpendicular_axis] * 32
    commands = [f"?BIT({expected_bit})"]

    if not expected_state:
        test = set_up_test(mock_motor_controller, 
                                 {FakeState.AxisNotClear: perpendicular_axis},
                                 commands)
    else:
        test = set_up_test(mock_motor_controller, {}, commands)

    state = motor.axis_clear(LEGACY_AXIS_MAPPING[input_axis])
    assert state == expected_state
    test.assert_passed()

# def test_move_to(mock_motor_controller):
#     motor, fake_controller, _, mock_sleep = mock_motor_controller
#     # fake_controller.axis_clear_states = [True, True, True, True]
#     position_to_move = 15.5
#     axis_to_move = 0 # X
#     fake_controller.set_motion_steps(2)

#     motor.move_to(position_to_move, axis_to_move)
#     expected_bit = 16128 + 32

#     expected_commands = [
#         f"?BIT({expected_bit})",
#         "DRIVE ON X",
#         f"X{position_to_move}",
#         "?BIT(516)", # First check, returns 1 (in motion)
#         "?BIT(516)", # Second check, returns 1 (in motion)
#         "?BIT(516)", # Third check, returns 0 (motion complete)
#         "DRIVE OFF X"
#     ]
    
#     assert fake_controller.decoded_log == expected_commands
#     assert fake_controller.buffer_clear
