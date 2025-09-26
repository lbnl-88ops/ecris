import pytest
from unittest.mock import patch, MagicMock, mock_open, call
import time

from tests.legacy_code.legacy_functions import datasheet

MODULE = 'tests.legacy_code.legacy_functions.'

class TestDataSheet:
    VAR_NAMES = ['extraction_v', 'fcv1_ammeter', 'batman_i_set']
    VAR_VALUES = [15003.1, 1.23456E-6, 0.05]
    TIMESTAMP = str(int(time.time()))
    DIRECTORY = '/tmp/test_data'
    EXPECTED_FILEPATH = f'{DIRECTORY}/dsht_{TIMESTAMP}'

    def test_legacy_datasheet_characterization(self):
        mock_venus = MagicMock()
        mock_venus.read_vars.return_value = self.VAR_NAMES
        mock_venus.read.side_effect = self.VAR_VALUES

        with patch(MODULE + 'venus', mock_venus), \
            patch(MODULE + 'directory', self.DIRECTORY), \
            patch(MODULE + 'open', mock_open()) as mocked_file:
            
            datasheet(self.TIMESTAMP)

        mocked_file.assert_called_once_with(self.EXPECTED_FILEPATH, 'w')
        mock_venus.read_vars.assert_called_once_with()
        expected_read_calls = [call([name]) for name in self.VAR_NAMES]

        assert mock_venus.read.call_args_list == expected_read_calls

        handle = mocked_file()
        expected_writes = [
            call("   0 1.50031e+04 extraction_v\n"),
            call("   1 1.23456e-06 fcv1_ammeter\n"),
            call("   2 5.00000e-02 batman_i_set\n")
        ]
        
        assert handle.write.call_args_list == expected_writes

    def test_datasheet_characterization(self):
        pass