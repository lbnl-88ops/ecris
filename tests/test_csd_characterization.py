import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open, call
import time

from ops.ecris.devices.venus_plc import VenusPLC
from tests.legacy_code.legacy_functions import datasheet

from ops.ecris.tasks.csd import write_datasheet

LEGACY_MODULE = 'tests.legacy_code.legacy_functions.'
VENUS_MODULE = 'ops.ecris.devices.venus_plc.'
MODULE = 'ops.ecris.tasks.csd.'

class TestDataSheet:
    VAR_NAMES = ['extraction_v', 'fcv1_ammeter', 'batman_i_set']
    VAR_VALUES = [15003.1, 1.23456E-6, 0.05]
    TIMESTAMP = str(int(time.time()))
    DIRECTORY = '/tmp/test_data'
    EXPECTED_FILEPATH = f'{DIRECTORY}/dsht_{TIMESTAMP}'
    EXPECTED_WRITES = [
            call("   0 1.50031e+04 extraction_v\n"),
            call("   1 1.23456e-06 fcv1_ammeter\n"),
            call("   2 5.00000e-02 batman_i_set\n")
        ]

    def test_legacy_datasheet_characterization(self):
        mock_venus = MagicMock()
        mock_venus.read_vars.return_value = self.VAR_NAMES
        mock_venus.read.side_effect = self.VAR_VALUES

        with patch(LEGACY_MODULE + 'venus', mock_venus), \
            patch(LEGACY_MODULE + 'directory', self.DIRECTORY), \
            patch(LEGACY_MODULE + 'open', mock_open()) as mocked_file:
            
            datasheet(self.TIMESTAMP)

        mocked_file.assert_called_once_with(self.EXPECTED_FILEPATH, 'w')
        mock_venus.read_vars.assert_called_once_with()
        expected_read_calls = [call([name]) for name in self.VAR_NAMES]

        assert mock_venus.read.call_args_list == expected_read_calls

        handle = mocked_file()
        assert handle.write.call_args_list == self.EXPECTED_WRITES

    @pytest.mark.asyncio
    async def test_datasheet_characterization(self):
        mock_controller = MagicMock()
        mock_controller.read_vars.return_value = self.VAR_NAMES
        mock_controller.read.side_effect = self.VAR_VALUES
        venus_plc = VenusPLC(mock_controller)
        path = Path(self.EXPECTED_FILEPATH)

        with patch(VENUS_MODULE + 'VENUSController', mock_controller), \
             patch(MODULE + 'open', mock_open()) as mocked_file:
            await write_datasheet(path, venus_plc)
        
        mocked_file.assert_called_once_with(path, 'w')
        mock_controller.read_vars.assert_called_once_with()
        expected_read_calls = [call([name]) for name in self.VAR_NAMES]

        assert mock_controller.read.call_args_list == expected_read_calls
        handle = mocked_file()
        assert handle.write.call_args_list == self.EXPECTED_WRITES
