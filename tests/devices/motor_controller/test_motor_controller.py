from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ops.ecris.devices import DeviceMalfunctionError
from ops.ecris.devices.motor_controller import MotorController
from ops.ecris.devices.motor_controller_specification import (
    MID_POINT_OFFSETS,
    PERPENDICULAR_AXIS,
    Axis,
    Bit,
    Commands,
)
from tests.devices.motor_controller.helpers import FakeState, MoveSequences, set_up_test

from .helpers import FakeMotorController

ALL_AXES = [Axis.VenusX, Axis.VenusY, Axis.AcerX, Axis.AcerY]

DEVICE_MODULE = "ops.ecris.drivers.telnet_driver."
MODULE = "ops.ecris.devices.motor_controller."


@pytest.fixture
def mock_motor_controller_not_connected():
    fake_controller = FakeMotorController(include_sleep=False)
    with (
        patch(DEVICE_MODULE + "open_connection") as mock_open_conn,
        patch(MODULE + "asyncio.sleep") as mock_sleep,
    ):
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock(side_effect=fake_controller.handle_command)
        mock_reader.readuntil = AsyncMock(side_effect=fake_controller.read_buffer)
        mock_writer.is_closing = MagicMock(return_value=False)
        mock_open_conn.return_value = (mock_reader, mock_writer)
        controller = MotorController(ip="127.0.0.1", port=9999)
        yield controller, fake_controller, mock_open_conn, mock_sleep


@pytest.fixture
def mock_motor_controller(mock_motor_controller_not_connected):
    controller, fake_controller, mock_open_conn, mock_sleep = mock_motor_controller_not_connected
    mock_reader, mock_writer = mock_open_conn.return_value
    controller._reader = mock_reader
    controller._writer = mock_writer
    fake_controller.post_init_reset()
    fake_controller._prompt = "P00> "
    controller._prompt = "P00> "
    yield controller, fake_controller, mock_open_conn, mock_sleep


@pytest.mark.asyncio
async def test_connect_sends_correct_commands(mock_motor_controller_not_connected):
    motor_controller, fake_controller, mock_open_conn, _ = mock_motor_controller_not_connected

    commands = [
        "",  # Wake up
        Commands.GET_FIRMWARE_VERSION,
        Commands.GET_ATTACHMENTS,
        Commands.OPEN_PROGRAM0,
        Commands.SET_RAMPING,
    ]

    test = set_up_test(mock_motor_controller_not_connected, {}, commands)

    await motor_controller.connect()

    mock_open_conn.assert_awaited_once_with("127.0.0.1", 9999, encoding=False)
    test.assert_passed()


@pytest.mark.asyncio
@pytest.mark.parametrize("axis", ALL_AXES)
class TestAllAxes(MoveSequences):
    @pytest.mark.parametrize("expected_state", [True, False])
    async def test_axis_clear_calculates_correct_bit_and_calls_send_command(
        self, mock_motor_controller, axis, expected_state
    ):
        perpendicular_axis = PERPENDICULAR_AXIS[axis]
        motor: MotorController
        motor, _, _, _ = mock_motor_controller
        commands = [Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis)]

        if not expected_state:
            test = set_up_test(
                mock_motor_controller,
                {FakeState.AxisNotClear: perpendicular_axis},
                commands,
            )
        else:
            test = set_up_test(mock_motor_controller, {}, commands)

        state = await motor.is_axis_clear_to_move(axis)
        test.assert_passed()
        assert state == expected_state

    async def test_move_to_positive_eof(self, mock_motor_controller, axis):
        motor: MotorController
        motor, _, _, _ = mock_motor_controller
        move_steps = 3
        expected_commands = self._move_out_sequence(axis, move_steps)
        test = set_up_test(
            mock_motor_controller,
            {
                FakeState.MotionSteps: move_steps,
                FakeState.DecrementMotionOnCheck: True,
            },
            expected_commands,
        )

        await motor.move_axis_to_positive_eof(axis)

        test.assert_passed()

    async def test_centering(self, mock_motor_controller, axis):
        motor: MotorController
        motor, _, _, _ = mock_motor_controller
        move_steps = [3, 4]
        coastdown = [1, 2]

        expected_commands = (
            [Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis)]
            + self._move_to(axis, -200, move_steps[0])
            + self._in_motion_check(coastdown[0])
            + self._move_to(axis, MID_POINT_OFFSETS[axis], move_steps[1], relative=True)
            + self._in_motion_check(coastdown[1])
            + [Commands.RESET_AXIS(axis), Commands.DRIVE_OFF(axis)]
        )

        test = set_up_test(
            mock_motor_controller,
            {
                FakeState.DecrementMotionOnCheck: True,
                FakeState.MotionSteps: move_steps,
                FakeState.CoastDownSteps: coastdown,
            },
            expected_commands,
        )

        await motor.center_axis(axis)
        test.assert_passed()
        for a in Axis:
            assert motor.is_centered(a) == (a == axis)

    async def test_centering_already_centered(self, mock_motor_controller, axis):
        motor: MotorController
        motor, _, _, _ = mock_motor_controller
        move_steps = [3]
        motor._centered[axis] = True

        expected_commands = [Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis)] + self._move_to(
            axis, 0, move_steps[0]
        )

        test = set_up_test(
            mock_motor_controller,
            {
                FakeState.DecrementMotionOnCheck: True,
                FakeState.MotionSteps: move_steps,
            },
            expected_commands,
        )

        await motor.center_axis(axis)
        test.assert_passed()

    async def test_centering_axis_not_clear(self, mock_motor_controller, axis):
        motor: MotorController
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
            + [Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis)]  # The final safety check
            + self._move_to(axis, -200, move_steps[1])
            + self._in_motion_check(coastdown_steps[1])
            + self._move_to(axis, MID_POINT_OFFSETS[axis], move_steps[2], relative=True)
            + self._in_motion_check(coastdown_steps[2])
            + [Commands.RESET_AXIS(axis), Commands.DRIVE_OFF(axis)]
        )

        # The setup is identical.
        test = set_up_test(
            mock_motor_controller,
            {
                FakeState.DecrementMotionOnCheck: True,
                FakeState.MotionSteps: move_steps,
                FakeState.AxisNotClear: perpendicular_axis,
                FakeState.ClearAxisOnStop: perpendicular_axis,
                FakeState.CoastDownSteps: coastdown_steps,
            },
            expected_commands,
        )

        # The action is identical.
        await motor.center_axis(axis)
        test.assert_passed()

    async def test_centering_axis_cant_clear(self, mock_motor_controller, axis):
        motor: MotorController
        motor, _, _, _ = mock_motor_controller
        move_steps = [2, 3, 4]
        perpendicular_axis = PERPENDICULAR_AXIS[axis]

        expected_commands = (
            [Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis)]
            + self._move_out_sequence(PERPENDICULAR_AXIS[axis], move_steps[0])
            + [
                Commands.CHECK_IN_MOTION(),
                Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis),
                Commands.DRIVE_OFF(axis),
            ]
        )

        test = set_up_test(
            mock_motor_controller,
            {
                FakeState.DecrementMotionOnCheck: True,
                FakeState.MotionSteps: move_steps,
                FakeState.AxisNotClear: perpendicular_axis,
            },
            expected_commands,
        )
        with pytest.raises(DeviceMalfunctionError):
            await motor.center_axis(axis)
        test.assert_passed()


@pytest.mark.asyncio
@pytest.mark.parametrize("axis", ALL_AXES)
@pytest.mark.parametrize("relative", [False, True])
class TestMoveSequencesWithRelative(MoveSequences):
    async def test_move_to(self, mock_motor_controller, axis, relative):
        motor, _, _, _ = mock_motor_controller
        position_to_move = 15.5
        move_steps: int = 2
        expected_commands = self._move_to(axis, position_to_move, move_steps, relative)

        test = set_up_test(
            mock_motor_controller,
            {FakeState.MotionSteps: move_steps, FakeState.DecrementMotionOnCheck: True},
            expected_commands,
        )

        await motor.move_to_position(axis, position_to_move, relative=relative)
        test.assert_passed()

    async def test_move_to_axis_not_clear(self, mock_motor_controller, axis, relative):
        motor, _, _, _ = mock_motor_controller
        position_to_move = 15.5
        perpendicular_axis = PERPENDICULAR_AXIS[axis]
        move_steps = [2, 3]
        coastdown_steps = [1]
        clearing_move = self._move_to(perpendicular_axis, 200, move_steps[0])
        cleanup = self._cleanup_after_limit_sequence(axis, coastdown_steps=coastdown_steps[0])
        primary_move = self._move_to(axis, position_to_move, move_steps[1], relative)

        expected_commands = [primary_move[0]] + clearing_move + cleanup + primary_move[1:]

        test = set_up_test(
            mock_motor_controller,
            {
                FakeState.AxisNotClear: perpendicular_axis,
                FakeState.MotionSteps: move_steps,
                FakeState.DecrementMotionOnCheck: True,
                FakeState.ClearAxisOnStop: perpendicular_axis,
                FakeState.CoastDownSteps: coastdown_steps,
            },
            expected_commands,
        )

        await motor.move_to_position(axis, position_to_move, relative=relative)
        test.assert_passed()

    async def test_move_to_axis_cannot_clear(self, mock_motor_controller, axis, relative):
        motor: MotorController
        motor, _, _, _ = mock_motor_controller
        position_to_move = 15.5
        perpendicular_axis = PERPENDICULAR_AXIS[axis]
        move_steps = [4, 3]

        clearing_move = self._move_to(perpendicular_axis, 200, move_steps[0])
        cleanup = self._cleanup_after_limit_sequence(axis)
        primary_move = self._move_to(axis, position_to_move, move_steps[1], relative)

        expected_commands = (
            [primary_move[0]] + clearing_move + cleanup + [Commands.DRIVE_OFF(axis)]
        )  # Drive off due to error

        test = set_up_test(
            mock_motor_controller,
            {
                FakeState.AxisNotClear: perpendicular_axis,
                FakeState.MotionSteps: move_steps,
                FakeState.DecrementMotionOnCheck: True,
                FakeState.ClearAxisOnStop: None,
            },
            expected_commands,
        )

        with pytest.raises(DeviceMalfunctionError):
            await motor.move_to_position(axis, position_to_move, relative=relative)
        test.assert_passed()

    async def test_move_to_axis_keyboard_interrupt(self, mock_motor_controller, axis, relative):
        motor: MotorController
        motor, _, _, _ = mock_motor_controller
        position_to_move = 15.5
        move_steps = [4, 3]

        primary_move = self._move_to(axis, position_to_move, move_steps[1], relative)
        step_to_interrupt = 5

        expected_commands = primary_move[:step_to_interrupt] + [
            Commands.SET_BIT(Bit.KILL_ALL_MOVES(axis)),
            Commands.CLEAR_BIT(Bit.KILL_ALL_MOVES(axis)),
            Commands.DRIVE_OFF(axis),
        ]

        test = set_up_test(
            mock_motor_controller,
            {
                FakeState.MotionSteps: move_steps,
                FakeState.DecrementMotionOnCheck: True,
                FakeState.InterruptAfterCommands: (
                    step_to_interrupt,
                    KeyboardInterrupt,
                ),
            },
            expected_commands,
        )

        with pytest.raises(KeyboardInterrupt):
            await motor.move_to_position(axis, position_to_move, relative=relative)
        test.assert_passed()
