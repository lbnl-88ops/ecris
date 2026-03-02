# test_keysight_pytest.py

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from ops.ecris.drivers.keysight import Keysight


@pytest.fixture
def mock_keysight_connection():
    with patch("ops.ecris.drivers.telnet_driver.open_connection") as mock_open_conn:
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.is_closing = MagicMock(return_value=False)
        mock_open_conn.return_value = (mock_reader, mock_writer)

        keysight = Keysight.connect_at_ip(ip="127.0.0.1", port=9999, aperture_time=0.0166)

        yield keysight, mock_reader, mock_writer, mock_open_conn


@pytest.mark.asyncio
async def test_connect_sends_correct_commands(mock_keysight_connection):
    keysight, mock_reader, mock_writer, mock_open_conn = mock_keysight_connection
    expected_aperture = 0.0166
    setup_commands = [
        "*rst",
        ':sens:func "curr"',
        ":sens:curr:rang:auto on",
        ":sens:curr:nplc:auto off",
        f":sens:curr:aper {expected_aperture}",
        ":inp on",
    ]
    banner = "Welcome to Keysight B2900A Series.\r\nB2900A> "
    read_until_effects = [f"{s}\r\nB2900A> ".encode("ascii") for s in [banner] + setup_commands]

    mock_reader.readuntil.side_effect = read_until_effects

    with patch("asyncio.sleep") as mock_sleep:
        await keysight.connect()
        mock_sleep.assert_awaited_once_with(2.0)

    mock_open_conn.assert_awaited_once_with("127.0.0.1", 9999, encoding=False)

    expected_write_calls = [call(f"{c}\r\n".encode("ascii")) for c in setup_commands]
    expected_readuntil_calls = [call("B2900A>".encode("ascii")) for _ in read_until_effects]

    mock_writer.write.assert_has_calls(expected_write_calls)
    mock_reader.readuntil.assert_has_calls(expected_readuntil_calls)
    assert mock_writer.write.call_count == len(expected_write_calls)
    assert mock_reader.readuntil.call_count == len(read_until_effects)


@pytest.mark.asyncio
async def test_read_data_sends_command_and_parses_response(mock_keysight_connection):
    keysight, mock_reader, mock_writer, _ = mock_keysight_connection
    keysight._backend._reader = mock_reader
    keysight._backend._writer = mock_writer
    command = "meas:curr?"

    mock_reader.readuntil.return_value = "meas:curr?\r\n  1.2345E-05\r\nB2900A> ".encode("ascii")

    data = await keysight.read_data(Keysight.DataKeys.CURRENT)

    mock_writer.write.assert_called_once_with(f"{command}\r\n".encode("ascii"))
    mock_reader.readuntil.assert_awaited_once_with("B2900A>".encode("ascii"))

    expected_data = 1.2345e-05
    assert data == pytest.approx(expected_data)
