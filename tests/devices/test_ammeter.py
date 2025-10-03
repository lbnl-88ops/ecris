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
async def test_setup_sends_correct_commands(mock_ammeter_connection):
    ammeter, mock_reader, mock_writer, _ = mock_ammeter_connection
    ammeter._writer = mock_writer
    ammeter._reader = mock_reader
    expected_nplc = 1.0

    commands = [ ("*rst"),
        (':sens:func "curr"'),
        (':sens:curr:rang:auto on'),
        (':sens:curr:nplc:auto off'),
        (f':sens:curr:nplc {expected_nplc}'),
        (':inp on')
    ]

    mock_reader.readuntil.return_value = b'B2900A>\r\n'

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

    mock_writer.write.assert_called_once_with(b'meas:curr?\r\n')

    assert mock_reader.readuntil.call_count == 2
    
    expected_data = 1.2345e-05
    assert data == pytest.approx(expected_data)
