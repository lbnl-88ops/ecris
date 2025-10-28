from unittest.mock import MagicMock, mock_open, patch, AsyncMock, call

import pytest

from ops.ecris.devices.motor_controller import MotorController
from ops.ecris.devices.motor_controller_specification import Axis, Commands, PERPENDICULAR_AXIS
from tests.devices.motor_controller.helpers import set_up_test, MoveSequences, FakeState
from .helpers import FakeMotorController


ALL_AXES = [Axis.X, Axis.Y, Axis.Z, Axis.A]

DEVICE_MODULE = "ops.ecris.model.device."
MODULE = "ops.ecris.devices.motor_controller."


@pytest.fixture
def mock_motor_controller_not_connected():
    fake_controller = FakeMotorController()
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

    commands = [Commands.OPEN_PROGRAM0, Commands.SET_RAMPING]

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
