from ops.ecris.legacy.emittance_scan import FatalError, Motor
from ops.ecris.legacy.mappings import LEGACY_AXIS_MAPPING
from .fakes import FakeMotorController
from .fakes.fake_motor_controller import set_up_test, FakeState
from ops.ecris.devices.motor_controller_specification import (
    Axis, Commands, PERPENDICULAR_AXIS, Bit,
    MID_POINT_OFFSETS)

from unittest.mock import MagicMock, patch, call

import pytest

MODULE = 'ops.ecris.legacy.emittance_scan.'

ALL_AXES = [Axis.X, Axis.Y, Axis.Z, Axis.A]

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

class MoveSequences:
    @staticmethod
    def _drive_sequence(axis: Axis, position: float, move_steps: int, relative=False) -> list[str]:
        """
        Generates the commands for a DRIVEN move.
        STARTS with DRIVE ON, ENDS when the polling for that move is complete.
        Does NOT include the initial axis clear check or the final DRIVE OFF.
        """
        move_cmd = Commands.RELATIVE_MOVE(axis, position) if relative else Commands.MOVE(axis, position)
        return (
            [Commands.DRIVE_ON(axis), move_cmd] 
            + [Commands.CHECK_IN_MOTION()] * (move_steps + 1))
    
    @staticmethod
    def _in_motion_check(coastdown_steps: int) -> list[str]:
        """
        Generates the commands for a COASTING stop.
        STARTS with DRIVE OFF, ENDS when the polling for that coast is complete.
        """
        return ([Commands.CHECK_IN_MOTION()] * (coastdown_steps + 1))

    @staticmethod
    def _move_to(axis: Axis, 
                 position_to_move: float, 
                 move_steps: int, 
                 relative=False, 
                 coastdown_steps: int = 0):
        expected_commands = ([
            Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis), 
            Commands.DRIVE_ON(axis), 
            Commands.RELATIVE_MOVE(axis, position_to_move) if relative else Commands.MOVE(axis, position_to_move)]
            + [Commands.CHECK_IN_MOTION()] * (move_steps + 1)
            + [Commands.DRIVE_OFF(axis)])
        return expected_commands

    @staticmethod
    def _move_out_sequence(axis: Axis, move_steps: int):
        return (MoveSequences._move_to(axis, 200, move_steps) + [
            Commands.CLEAR_BIT(Bit.KILL_ALL_MOVES(axis)),
            Commands.DRIVE_OFF(axis)] )

    @staticmethod
    def _cleanup_after_limit_sequence(axis: Axis,
                                      coastdown_steps: int = 0):
        return (
            [Commands.CLEAR_BIT(Bit.KILL_ALL_MOVES(axis)), Commands.DRIVE_OFF(axis)]
            + [Commands.CHECK_IN_MOTION()] * (coastdown_steps + 1)
            + [Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis)])

@pytest.mark.parametrize("axis", ALL_AXES)
class TestAllAxes(MoveSequences):
    @pytest.mark.parametrize("expected_state", [True, False])
    def test_axis_clear_calculates_correct_bit_and_calls_send_command( 
        self, mock_motor_controller, axis, expected_state):
        perpendicular_axis = PERPENDICULAR_AXIS[axis]

        motor, _, _ , _ = mock_motor_controller
        commands = [Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis)]

        if not expected_state:
            test = set_up_test(mock_motor_controller, 
                                    {FakeState.AxisNotClear: perpendicular_axis},
                                    commands)
        else:
            test = set_up_test(mock_motor_controller, {}, commands)

        state = motor.axis_clear(LEGACY_AXIS_MAPPING[axis])
        assert state == expected_state
        test.assert_passed()

    def test_move_out(self, mock_motor_controller, axis):
        motor, _, _, _ = mock_motor_controller
        move_steps = 3
        expected_commands = self._move_out_sequence(axis, move_steps)
        test = set_up_test(mock_motor_controller, {
            FakeState.MotionSteps: move_steps,
            FakeState.DecrementMotionOnCheck: True,}, expected_commands)

        motor.move_out(LEGACY_AXIS_MAPPING[axis])

        test.assert_passed()

    def test_centering(self, mock_motor_controller, axis):
        motor, _, _, _ = mock_motor_controller
        move_steps = [3, 4]
        coastdown = [1, 2]

        expected_commands = (
            [Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis)] 
            + self._move_to(axis, -200, move_steps[0])
            + self._in_motion_check(coastdown[0])
            + self._move_to(axis, MID_POINT_OFFSETS[axis], move_steps[1], relative=True)
            + self._in_motion_check(coastdown[1])
            + [Commands.RESET_AXIS(axis),
               Commands.DRIVE_OFF(axis)])

        test = set_up_test(mock_motor_controller, {
            FakeState.DecrementMotionOnCheck: True,
            FakeState.MotionSteps: move_steps,
            FakeState.CoastDownSteps: coastdown,
            }, expected_commands)

        motor.centering(LEGACY_AXIS_MAPPING[axis])
        test.assert_passed()
        for i, centered in enumerate(motor.centered):
            if i == LEGACY_AXIS_MAPPING[axis]:
                assert centered
            else:
                assert not centered

    def test_centering_already_centered(self, mock_motor_controller, axis):
        motor, _, _, _ = mock_motor_controller
        move_steps = [3]
        motor.centered[LEGACY_AXIS_MAPPING[axis]] = True

        expected_commands = (
            [Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis)]
            + self._move_to(axis, 0, move_steps[0])
        )

        test = set_up_test(mock_motor_controller, {
            FakeState.DecrementMotionOnCheck: True,
            FakeState.MotionSteps: move_steps,
            }, expected_commands)

        motor.centering(LEGACY_AXIS_MAPPING[axis])
        test.assert_passed()

    def test_centering_axis_not_clear(self, mock_motor_controller, axis):
        motor, _, _, _ = mock_motor_controller
        perpendicular_axis = PERPENDICULAR_AXIS[axis]
        
        # Define the physics for this specific test run
        move_steps = [4, 5, 6]
        coastdown_steps = [1, 2, 3]

        # The test now reads like a story, composing physical primitives.
        expected_commands = (
            [Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis)]
            + self._move_out_sequence(perpendicular_axis, move_steps[0])
            + self._in_motion_check(coastdown_steps[0])
            + [Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis)] # The final safety check
            + self._move_to(axis, -200, move_steps[1])
            + self._in_motion_check(coastdown_steps[1])
            + self._move_to(axis, MID_POINT_OFFSETS[axis], move_steps[2], relative=True)
            + self._in_motion_check(coastdown_steps[2])
            + [Commands.RESET_AXIS(axis), 
               Commands.DRIVE_OFF(axis)]
        )

        # The setup is identical.
        test = set_up_test(mock_motor_controller, {
            FakeState.DecrementMotionOnCheck: True,
            FakeState.MotionSteps: move_steps,
            FakeState.AxisNotClear: perpendicular_axis,
            FakeState.ClearAxisOnStop: perpendicular_axis,
            FakeState.CoastDownSteps: coastdown_steps
            }, expected_commands)

        # The action is identical.
        motor.centering(LEGACY_AXIS_MAPPING[axis])
        test.assert_passed()

    def test_centering_axis_cant_clear(self, mock_motor_controller, axis):
        motor, _, _, _ = mock_motor_controller
        move_steps = [2, 3, 4]
        perpendicular_axis = PERPENDICULAR_AXIS[axis]

        expected_commands = (
            [Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis)]
            + self._move_out_sequence(PERPENDICULAR_AXIS[axis], move_steps[0])
            + [Commands.CHECK_IN_MOTION(),
               Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis),
               Commands.DRIVE_OFF(axis)])

        test = set_up_test(mock_motor_controller, {
            FakeState.DecrementMotionOnCheck: True,
            FakeState.MotionSteps: move_steps,
            FakeState.AxisNotClear: perpendicular_axis,
            }, expected_commands)
        with pytest.raises(FatalError):
            motor.centering(LEGACY_AXIS_MAPPING[axis])
        test.assert_passed()
        
@pytest.mark.parametrize("axis", ALL_AXES)
@pytest.mark.parametrize("relative", [False, True])
class TestMoveSequencesWithRelative(MoveSequences):
    def test_move_to(self, mock_motor_controller, axis, relative):
        motor, _, _, _ = mock_motor_controller
        position_to_move = 15.5
        move_steps: int = 2
        expected_commands = self._move_to(axis, position_to_move, move_steps, relative)
        
        test = set_up_test(mock_motor_controller, {
            FakeState.MotionSteps: move_steps,
            FakeState.DecrementMotionOnCheck: True}, expected_commands)

        action_to_perform = motor.relative_move if relative else motor.move_to
        action_to_perform(position_to_move, LEGACY_AXIS_MAPPING[axis])
        test.assert_passed()
        
    def test_move_to_axis_not_clear(self, mock_motor_controller, axis, relative):
        motor, _, _, _ = mock_motor_controller
        position_to_move = 15.5
        perpendicular_axis = PERPENDICULAR_AXIS[axis]
        move_steps = [2, 3]
        coastdown_steps = [1]
        clearing_move = self._move_to(perpendicular_axis, 200, move_steps[0])
        cleanup = self._cleanup_after_limit_sequence(axis, coastdown_steps=coastdown_steps[0])
        primary_move = self._move_to(axis, position_to_move, move_steps[1], relative)

        expected_commands = (
            [primary_move[0]] 
            + clearing_move 
            + cleanup 
            + primary_move[1:])
        
        test = set_up_test(mock_motor_controller, {
            FakeState.AxisNotClear: perpendicular_axis,
            FakeState.MotionSteps: move_steps,
            FakeState.DecrementMotionOnCheck: True,
            FakeState.ClearAxisOnStop: perpendicular_axis,
            FakeState.CoastDownSteps: coastdown_steps},
            expected_commands)

        action_to_perform = motor.relative_move if relative else motor.move_to
        action_to_perform(position_to_move, LEGACY_AXIS_MAPPING[axis])
        test.assert_passed()
        
    def test_move_to_axis_cannot_clear(self, mock_motor_controller, axis, relative):
        motor, _, _, _ = mock_motor_controller
        position_to_move = 15.5
        perpendicular_axis = PERPENDICULAR_AXIS[axis]
        move_steps = [4, 3]

        clearing_move = self._move_to(perpendicular_axis, 200, move_steps[0])
        cleanup = self._cleanup_after_limit_sequence(axis)
        primary_move = self._move_to(axis, position_to_move, move_steps[1], relative)

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
            action_to_perform = motor.relative_move if relative else motor.move_to
            action_to_perform(position_to_move, LEGACY_AXIS_MAPPING[axis])
        test.assert_passed()
        
    def test_move_to_axis_keyboard_interrupt(self, mock_motor_controller, axis, relative):
        motor, _, _, _ = mock_motor_controller
        position_to_move = 15.5
        move_steps = [4, 3]

        primary_move = self._move_to(axis, position_to_move, move_steps[1], relative)
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
            action_to_perform = motor.relative_move if relative else motor.move_to
            action_to_perform(position_to_move, LEGACY_AXIS_MAPPING[axis])
        test.assert_passed()
        
