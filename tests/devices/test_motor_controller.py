from unittest.mock import MagicMock, mock_open, patch, AsyncMock, call

import pytest

from ops.ecris.devices.motor_controller import MotorController

@pytest.fixture
def mock_motor_controller_connection():
    with patch('ops.ecris.model.device.open_connection') as mock_open_conn:
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.is_closing = MagicMock(return_value=False)
        mock_open_conn.return_value = (mock_reader, mock_writer)
        
        controller = MotorController(ip='127.0.0.1', port=9999)
        
        yield controller, mock_reader, mock_writer, mock_open_conn

@pytest.mark.asyncio
async def test_connect_sends_correct_commands(mock_motor_controller_connection):
    controller, mock_reader, mock_writer, mock_open_conn = mock_motor_controller_connection
    banner = 'Unknown values.\r\nSYS>'

    side_effects = [banner.encode('ascii')]
    mock_reader.readuntil.side_effect = side_effects

    await controller.connect()

    mock_open_conn.assert_awaited_once_with('127.0.0.1', 9999, encoding=False)
    mock_reader.readuntil.assert_called_once_with('SYS>'.encode('ascii'))
    assert mock_reader.readuntil.call_count == len(side_effects)
