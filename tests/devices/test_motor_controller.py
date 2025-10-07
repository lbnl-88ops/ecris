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

    # 1. Test values
    banner = 'Unknown values.\r\nSYS>'
    commands = ["PROG0", "ACC 5 DEC 5 VEL 15 STP 100"]
    side_effects = [banner.encode('ascii')] + [f'{s}\r\nP00>'.encode('ascii') for s in commands]
    expected_write_calls = [call(f'{s}\r\n'.encode('ascii')) for s in commands]
    expected_readuntil_calls = [call(s.encode('ascii')) 
                                for s in ['SYS>'] + ['P00>'] * len(commands)]

    # 2. Set up mocks
    mock_reader.readuntil.side_effect = side_effects

    # 3. Run command
    await controller.connect()

    # 4. Test assertions
    mock_open_conn.assert_awaited_once_with('127.0.0.1', 9999, encoding=False)
    mock_reader.readuntil.assert_has_calls(expected_readuntil_calls)
    mock_writer.write.assert_has_calls(expected_write_calls)
    assert mock_reader.readuntil.call_count == len(expected_readuntil_calls)
    assert mock_writer.write.call_count == len(expected_write_calls)
