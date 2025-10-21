from ops.ecris.legacy.emittance_scan import FatalError, Motor
from tests.fakes import FakeMotorController
from tests.fakes.fake_motor_controller import set_up_test, FakeState
from ops.ecris.devices.motor_controller_specification import (
    Axis, Commands, PERPENDICULAR_AXIS, Bit)

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
    commands = [Commands.QUERY_BIT(Bit.AXIS_CLEAR(input_axis))]

    if not expected_state:
        test = set_up_test(mock_motor_controller, 
                                 {FakeState.AxisNotClear: perpendicular_axis},
                                 commands)
    else:
        test = set_up_test(mock_motor_controller, {}, commands)

    state = motor.axis_clear(LEGACY_AXIS_MAPPING[input_axis])
    assert state == expected_state
    test.assert_passed()

def _full_move_sequence(axis: Axis, position_to_move: float, move_steps: int):
    expected_commands = ([
        Commands.QUERY_BIT(Bit.AXIS_CLEAR(axis)), 
        Commands.DRIVE_ON(axis), 
        Commands.MOVE(axis, position_to_move)] 
        + [Commands.QUERY_BIT(Bit.IN_MOTION)] * (move_steps + 1)
        + [Commands.DRIVE_OFF(axis)])
    return expected_commands

def _cleanup_after_limit_sequence(axis: Axis):
    return [Commands.CLEAR_BIT(Bit.KILL_ALL_MOVES(axis)), 
           Commands.DRIVE_OFF(axis),
           Commands.QUERY_BIT(Bit.IN_MOTION), 
           Commands.QUERY_BIT(Bit.AXIS_CLEAR(axis))]

@pytest.mark.parametrize("axis", [Axis.X, Axis.Y, Axis.Z, Axis.A])
def test_move_to(mock_motor_controller, axis):
    motor, _, _, _ = mock_motor_controller
    position_to_move = 15.5
    move_steps: int = 2
    expected_commands = _full_move_sequence(axis, position_to_move, move_steps)
    
    test = set_up_test(mock_motor_controller, {
        FakeState.MotionSteps: move_steps,
        FakeState.DecrementMotionOnCheck: True}, expected_commands)

    motor.move_to(position_to_move, LEGACY_AXIS_MAPPING[axis])
    test.assert_passed()
    
@pytest.mark.parametrize("axis", [Axis.X, Axis.Y, Axis.Z, Axis.A])
def test_move_to_axis_not_clear(mock_motor_controller, axis):
    motor, _, _, _ = mock_motor_controller
    position_to_move = 15.5
    perpendicular_axis = PERPENDICULAR_AXIS[axis]
    move_steps = [2, 3]
    clearing_move = _full_move_sequence(perpendicular_axis, 200, move_steps[0])
    cleanup = _cleanup_after_limit_sequence(axis)
    primary_move = _full_move_sequence(axis, position_to_move, move_steps[1])

    expected_commands = (
        [primary_move[0]] 
        + clearing_move 
        + cleanup 
        + primary_move[1:])
    
    test = set_up_test(mock_motor_controller, {
        FakeState.AxisNotClear: perpendicular_axis,
        FakeState.MotionSteps: move_steps,
        FakeState.DecrementMotionOnCheck: True,
        FakeState.ClearAxisOnStop: perpendicular_axis},
        expected_commands)

    motor.move_to(position_to_move, LEGACY_AXIS_MAPPING[axis])
    test.assert_passed()
    
@pytest.mark.parametrize("axis", [Axis.X, Axis.Y, Axis.Z, Axis.A])
def test_move_to_axis_cannot_clear(mock_motor_controller, axis):
    motor, _, _, _ = mock_motor_controller
    position_to_move = 15.5
    perpendicular_axis = PERPENDICULAR_AXIS[axis]
    move_steps = [4, 3]

    clearing_move = _full_move_sequence(perpendicular_axis, 200, move_steps[0])
    cleanup = _cleanup_after_limit_sequence(axis)
    primary_move = _full_move_sequence(axis, position_to_move, move_steps[1])

    expected_commands = (
        [primary_move[0]]
        + clearing_move
        + cleanup
        + [Commands.DRIVE_OFF(axis)]) # Drive off due to error
    
    test = set_up_test(mock_motor_controller, {
        FakeState.AxisNotClear: perpendicular_axis,
        FakeState.MotionSteps: move_steps,
        FakeState.DecrementMotionOnCheck: True,
        FakeState.ClearAxisOnStop: None},
        expected_commands)

    with pytest.raises(FatalError):
        motor.move_to(position_to_move, LEGACY_AXIS_MAPPING[axis])
    test.assert_passed()
    
@pytest.mark.parametrize("axis", [Axis.X, Axis.Y, Axis.Z, Axis.A])
def test_move_to_axis_keyboard_interrupt(mock_motor_controller, axis):
    motor, _, _, _ = mock_motor_controller
    position_to_move = 15.5
    move_steps = [4, 3]

    primary_move = _full_move_sequence(axis, position_to_move, move_steps[1])
    step_to_interrupt = 5

    expected_commands = (
        primary_move[:step_to_interrupt]
        + [
            Commands.SET_BIT(Bit.KILL_ALL_MOVES(axis)),
            Commands.CLEAR_BIT(Bit.KILL_ALL_MOVES(axis)),
            Commands.DRIVE_OFF(axis)
        ])
    
    test = set_up_test(mock_motor_controller, {
        FakeState.MotionSteps: move_steps,
        FakeState.DecrementMotionOnCheck: True,
        FakeState.InterruptAfterCommands: (step_to_interrupt, KeyboardInterrupt),
        },
        expected_commands)

    with pytest.raises(KeyboardInterrupt):
        motor.move_to(position_to_move, LEGACY_AXIS_MAPPING[axis])
    test.assert_passed()
    
