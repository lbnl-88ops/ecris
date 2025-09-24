from unittest.mock import patch, MagicMock, call, AsyncMock
import pytest

from .legacy_code import legacy_functions
from ops.ecris.model import Ammeter

LEGACY_SETUP_MODULE = 'tests.legacy_code.legacy_functions'

class TestSetup:
    IP = "10.10.100.75"
    PORT = 5024
    MEASUREMENT_FREQUENCY = 60.0 
    EXPECTED_NPLC = 1.0 / MEASUREMENT_FREQUENCY * 60.0

    def test_legacy_setup_sends_correct_command_sequence(self):
        mock_connection = MagicMock()
        
        with patch(f'{LEGACY_SETUP_MODULE}.Telnet') as mock_telnet, \
             patch(f'{LEGACY_SETUP_MODULE}.time.sleep') as mock_sleep, \
             patch.object(legacy_functions, 'measurementFrequency', self.MEASUREMENT_FREQUENCY):
            
            mock_telnet.return_value = mock_connection
            
            returned_connection = legacy_functions.setupSystem(verbose=0)

        mock_telnet.assert_called_once_with(self.IP, self.PORT, timeout=3)
        mock_connection.read_until.assert_called_once_with(b'\n')
        mock_sleep.assert_called_once_with(2)
        assert returned_connection is mock_connection

        expected_command_calls = [
            call.write(b'*rst\n'),
            call.write(b':sens:func "curr"\n'),
            call.write(b':sens:curr:rang:auto on\n'),
            call.write(b':sens:curr:nplc:auto off\n'),
            call.write(f':sens:curr:nplc {self.EXPECTED_NPLC}\n'.encode('ascii')),
            call.write(b':inp on\n'),
        ]

        mock_connection.assert_has_calls(expected_command_calls)

    @pytest.mark.asyncio
    async def test_new_ammeter_setup_matches_legacy_behavior(self):
        ammeter = Ammeter(read_frequency_per_min=self.MEASUREMENT_FREQUENCY, ip=self.IP, port=self.PORT)
        ammeter._write = AsyncMock()
        
        with patch('asyncio.sleep') as mock_sleep:
            await ammeter.setup()

        mock_sleep.assert_called_once_with(2)
        
        expected_command_calls = [
            call('*rst'),
            call(':sens:func "curr"'),
            call(':sens:curr:rang:auto on'),
            call(':sens:curr:nplc:auto off'),
            call(f':sens:curr:nplc {self.EXPECTED_NPLC}'),
            call(':inp on'),
        ]
        
        ammeter._write.assert_has_calls(expected_command_calls)