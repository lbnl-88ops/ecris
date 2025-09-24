# test_ammeter_pytest.py

import pytest
from unittest.mock import MagicMock, patch, AsyncMock, call
import time

from ops.ecris.model.ammeter import Ammeter

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
async def test_setup_sends_correct_commands(mock_ammeter_connection):
    ammeter, _, mock_writer, mock_open_conn = mock_ammeter_connection
    expected_nplc = 1.0

    await ammeter.connect()
    with patch('asyncio.sleep') as mock_sleep:
        await ammeter.setup()
        mock_sleep.assert_awaited_once_with(2.0)
    
    mock_open_conn.assert_awaited_once_with('127.0.0.1', 9999)

    expected_calls = [call(f"{c}\n".encode('ascii')) for c in [
        ("*rst"),
        (':sens:func "curr"'),
        (':sens:curr:rang:auto on'),
        (':sens:curr:nplc:auto off'),
        (f':sens:curr:nplc {expected_nplc}'),
        (':inp on')
    ]]

    mock_writer.write.assert_has_calls(expected_calls)
    assert mock_writer.write.call_count == 6

@pytest.mark.asyncio
async def test_get_data_sends_command_and_parses_response(mock_ammeter_connection):
    ammeter, mock_reader, mock_writer, _ = mock_ammeter_connection
    current_time = time.time() 
    mock_reader.readuntil.return_value = b'B2900A>      1.2345E-05\r\n'

    await ammeter.connect()
    mock_reader.reset_mock()
    mock_writer.reset_mock()

    with patch('time.time', return_value=current_time):
        data = await ammeter.get_data()

    mock_reader.readuntil.assert_awaited_once_with('\n'.encode('ascii'))
    mock_writer.write.assert_called_once_with("meas:curr?\n".encode('ascii'))
    mock_writer.drain.assert_awaited_once()

    expected_data = {
        "time": current_time,
        "current": 1.2345e-05
    }
    assert data == expected_data