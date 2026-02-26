import pytest
from unittest.mock import MagicMock, patch, AsyncMock, call

from ops.ecris.drivers.keithley import Keithley


@pytest.fixture
def mock_keithley_connection():
    with patch("ops.ecris.drivers.telnet_driver.open_connection") as mock_open_conn:
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.is_closing = MagicMock(return_value=False)
        mock_open_conn.return_value = (mock_reader, mock_writer)

        keithley = Keithley(sample_frequency_hz=60, ip="127.0.0.1", port=9999)

        yield keithley, mock_reader, mock_writer, mock_open_conn


@pytest.mark.asyncio
async def test_connect_sends_correct_commands(mock_keithley_connection):
    keithley, mock_reader, mock_writer, mock_open_conn = mock_keithley_connection
    expected_nplc = 100.0
    handshake_commands = [
        "*lang scpi",
        ":trace:clear",
        "*tst?",
        "*idn?",
    ]

    handshake_return_values = ["0\r\n", "KEITHLEY INSTRUMENTS,MODEL DMM7512,04684146,1.7.16a\r\n"]
    reset_command = ["*rst"]

    setup_commands = [
        ':sens:func "curr"',
        ":sens:curr:rang:auto on",
        ":sens:curr:delay:auto off",
        f":sens:curr:nplc {expected_nplc}",
    ]
    read_until_effects = [v.encode("ascii") for v in handshake_return_values]

    mock_reader.readuntil.side_effect = read_until_effects

    with patch("asyncio.sleep") as mock_sleep:
        await keithley.connect()
        assert mock_sleep.await_count == 2
        mock_sleep.assert_has_awaits([call(2.0), call(5.0)])

    mock_open_conn.assert_awaited_once_with("127.0.0.1", 9999, encoding=False)
    all_commands = handshake_commands + reset_command + setup_commands

    expected_write_calls = [call(f"{c}\r\n".encode("ascii")) for c in all_commands]
    expected_readuntil_calls = [call("\n".encode("ascii")) for _ in read_until_effects]

    mock_writer.write.assert_has_calls(expected_write_calls)
    mock_reader.readuntil.assert_has_calls(expected_readuntil_calls)
    assert mock_writer.write.call_count == len(expected_write_calls)
    assert mock_reader.readuntil.call_count == len(read_until_effects)


@pytest.mark.asyncio
async def test_read_data_sends_command_and_parses_response(mock_keithley_connection):
    keithley, mock_reader, mock_writer, _ = mock_keithley_connection
    keithley._backend._reader = mock_reader
    keithley._backend._writer = mock_writer
    command = "meas:curr?"

    mock_reader.readuntil.return_value = "1.2345E-05\r\n".encode("ascii")

    data = await keithley.read_data(keithley.DataKeys.CURRENT)

    mock_writer.write.assert_called_once_with(f"{command}\r\n".encode("ascii"))
    mock_reader.readuntil.assert_awaited_once_with("\n".encode("ascii"))

    expected_data = 1.2345e-05
    assert data == pytest.approx(expected_data)
