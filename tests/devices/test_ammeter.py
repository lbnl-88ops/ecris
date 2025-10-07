# test_ammeter_pytest.py

import pytest
from unittest.mock import MagicMock, patch, AsyncMock, call

from ops.ecris.devices.ammeter import Ammeter

@pytest.fixture
def mock_ammeter_connection():
    with patch('ops.ecris.model.device.open_connection') as mock_open_conn:
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.is_closing = MagicMock(return_value=False)
        mock_open_conn.return_value = (mock_reader, mock_writer)
        
        ammeter = Ammeter(read_frequency_per_min=60, ip='127.0.0.1', port=9999)
        
        yield ammeter, mock_reader, mock_writer, mock_open_conn

@pytest.mark.asyncio
async def test_connect_sends_correct_commands(mock_ammeter_connection):
    ammeter, mock_reader, mock_writer, mock_open_conn = mock_ammeter_connection
    expected_nplc = 1.0
    setup_commands = [
        "*rst",
        ':sens:func "curr"',
        ':sens:curr:rang:auto on',
        ':sens:curr:nplc:auto off',
        f':sens:curr:nplc {expected_nplc}',
        ':inp on'
    ]
    banner = 'Welcome to Keysight B2900A Series.\r\nB2900A> '
    read_until_effects = [f'{s}\r\nB2900A> '.encode('ascii') for s in [banner] + setup_commands]

    mock_reader.readuntil.side_effect = read_until_effects

    with patch('asyncio.sleep') as mock_sleep:
        await ammeter.connect()
        mock_sleep.assert_awaited_once_with(2.0)
    
    mock_open_conn.assert_awaited_once_with('127.0.0.1', 9999, encoding=False)

    expected_calls = [call(f"{c}\r\n".encode('ascii')) for c in setup_commands]

    mock_writer.write.assert_has_calls(expected_calls)
    assert mock_writer.write.call_count == len(expected_calls)
    assert mock_writer.readuntil.call_count == len(read_until_effects)

@pytest.mark.asyncio
async def test_read_data_sends_command_and_parses_response(mock_ammeter_connection):
    ammeter, mock_reader, mock_writer, _ = mock_ammeter_connection
    command = "meas:curr?"

    mock_reader.readuntil.return_value = 'meas:curr?\r\n  1.2345E-05\r\nB2900A> '.encode('ascii')

    with patch('asyncio.sleep') as mock_sleep:
        await ammeter.setup()
        mock_sleep.assert_awaited_once_with(2.0)

    mock_reader.readuntil.side_effect = [
        f'{ammeter._prompt} {c}'.encode('ascii') for c in commands
    ]
    expected_calls = [call(f"{c}\r\n".encode('ascii')) for c in commands]
    
    mock_writer.write.assert_has_calls(expected_calls)
    assert mock_writer.write.call_count == len(commands)
    assert mock_reader.readuntil.call_count == len(commands)

@pytest.mark.asyncio
async def test_read_data_parses_response_correctly(mock_ammeter_connection):
    ammeter, mock_reader, mock_writer, _ = mock_ammeter_connection
    ammeter._writer = mock_writer
    ammeter._reader = mock_reader

    mock_reader.readuntil.side_effect = [
        f'{ammeter._prompt} meas:curr?\r\n'.encode('ascii'),    # First read gets the echo
        b'+1.2345E-05\r\n'   # Second read gets the data
    ]

    data = await ammeter.read_data(Ammeter.DataKeys.CURRENT)

    mock_reader.readuntil.assert_awaited_once_with('B2900A>'.encode('ascii'))
    mock_writer.write.assert_called_once_with("meas:curr?\r\n".encode('ascii'))
    mock_writer.drain.assert_awaited_once()

    assert mock_reader.readuntil.call_count == 2
    
    expected_data = 1.2345e-05
    assert data == pytest.approx(expected_data)
