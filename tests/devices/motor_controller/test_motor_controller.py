from unittest.mock import MagicMock, mock_open, patch, AsyncMock, call

import pytest

from ops.ecris.devices.motor_controller import MotorController
from ops.ecris.devices.motor_controller_specification import Axis, Commands
from .helpers import FakeMotorController


ALL_AXES = [Axis.X, Axis.Y, Axis.Z, Axis.A]


@pytest.fixture
def mock_motor_controller_connection():
    fake_controller = FakeMotorController()
    with patch("ops.ecris.model.device.open_connection") as mock_open_conn:
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock(side_effect=fake_controller.handle_command)
        mock_reader.readuntil = AsyncMock(side_effect=fake_controller.read_buffer)
        mock_writer.is_closing = MagicMock(return_value=False)
        mock_open_conn.return_value = (mock_reader, mock_writer)
        controller = MotorController(ip="127.0.0.1", port=9999)
        yield controller, fake_controller, mock_open_conn


@pytest.mark.asyncio
async def test_connect_sends_correct_commands(mock_motor_controller_connection):
    controller, fake_controller, mock_open_conn = mock_motor_controller_connection

    # 1. Test values
    commands = [Commands.OPEN_PROGRAM0, Commands.SET_RAMPING]

    await controller.connect()

    mock_open_conn.assert_awaited_once_with("127.0.0.1", 9999, encoding=False)
    assert fake_controller.decoded_log == commands
    assert fake_controller.buffer_clear
