import pytest
from unittest.mock import MagicMock, patch, AsyncMock, call
from ops.ecris.drivers.keithley import Keithley

@pytest.mark.asyncio
async def test_keithley_visa_connect():
    with patch("pyvisa.ResourceManager") as mock_rm_class:
        mock_rm = mock_rm_class.return_value
        mock_instrument = MagicMock()
        mock_rm.open_resource.return_value = mock_instrument
        
        # Identity and test query responses
        mock_instrument.query.side_effect = ["0", "KEITHLEY DMM7512"]
        mock_instrument.read.side_effect = ["0", "KEITHLEY DMM7512"]
        
        keithley = Keithley(sample_frequency_hz=60, resource_name="USB0::0x05E6::0x7510::INSTR")
        
        with patch("asyncio.sleep") as mock_sleep:
            await keithley.connect()
        
        assert keithley.is_connected
        mock_rm.open_resource.assert_called_once_with("USB0::0x05E6::0x7510::INSTR")
        
        # Verify SCPI commands sent during handshake and setup
        expected_write_calls = [
            call("*lang scpi"),
            call(":trace:clear"),
            call("*tst?"),
            call("*idn?"),
            call("*rst"),
            call(':sens:func "curr"'),
            call(":sens:curr:rang:auto on"),
            call(":sens:curr:delay:auto off"),
            call(":sens:curr:nplc 100.0"),
        ]
        # Depending on how send_command/send_silent_command are called, 
        # it might use write or query. 
        # In my SCPIDriver.send_command, it uses _write then _read_until (which uses read for VISA).
        # send_silent_command uses _write.
        
        mock_instrument.write.assert_has_calls(expected_write_calls, any_order=True)
