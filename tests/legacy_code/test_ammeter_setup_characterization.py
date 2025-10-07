from unittest.mock import patch, MagicMock, call

import tests.legacy_code.ammeter_legacy_functions as ammeter_legacy_functions

LEGACY_SETUP_MODULE = 'tests.legacy_code.ammeter_legacy_functions'

class TestSetup:
    IP = "10.10.100.75"
    PORT = 5024
    MEASUREMENT_FREQUENCY = 60.0 
    EXPECTED_NPLC = 1.0 / MEASUREMENT_FREQUENCY * 60.0
    EXPECTED_COMMANDS = [
            '*rst', 
            ':sens:func "curr"', 
            ':sens:curr:rang:auto on', 
            ':sens:curr:nplc:auto off', 
            f':sens:curr:nplc {EXPECTED_NPLC}', 
            ':inp on']

    def test_legacy_setup_sends_correct_command_sequence(self):
        mock_connection = MagicMock()
        
        with patch(f'{LEGACY_SETUP_MODULE}.Telnet') as mock_telnet, \
             patch(f'{LEGACY_SETUP_MODULE}.time.sleep') as mock_sleep, \
             patch.object(ammeter_legacy_functions, 'measurementFrequency', self.MEASUREMENT_FREQUENCY):
            
            mock_telnet.return_value = mock_connection
            
            returned_connection = ammeter_legacy_functions.setupSystem(verbose=0)

        mock_telnet.assert_called_once_with(self.IP, self.PORT, timeout=3)
        mock_connection.read_until.assert_called_once_with(b'\n')
        mock_sleep.assert_called_once_with(2)
        assert returned_connection is mock_connection

        expected_command_calls = [call(f"{c}\n".encode('ascii')) for c in self.EXPECTED_COMMANDS]

        mock_connection.write.assert_has_calls(expected_command_calls)
