import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open, call, AsyncMock
import time

from ops.ecris.devices.venus_plc import VenusPLC
from tests.legacy_code.legacy_functions import datasheet

from ops.ecris.tasks.csd import write_datasheet

LEGACY_MODULE = 'tests.legacy_code.legacy_functions.'
VENUS_MODULE = 'ops.ecris.devices.venus_plc.'
MODULE = 'ops.ecris.tasks.csd.'


class MockAsyncFile:
    file_handler = AsyncMock()
    async def write(self):
        pass

    async def __aenter__(self):
        return self.file_handler

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

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
        mock_all_data = {i: (self.VAR_NAMES[i], self.VAR_VALUES[i])
                         for i in range(len(self.VAR_NAMES))}

        mock_venus_plc = AsyncMock(spec=VenusPLC)
        mock_venus_plc.get_all_data.return_value = mock_all_data
        
        path = Path(self.EXPECTED_FILEPATH)
        mock_async_file = MockAsyncFile()

        with patch('aiofiles.open', return_value=mock_async_file) as mock_open:
            await write_datasheet(path, mock_venus_plc)
        
        mock_open.assert_called_once_with(path, 'w')
        mock_venus_plc.get_all_data.assert_awaited_once_with()

        handler = mock_async_file.file_handler 
        assert handler.write.await_args_list == self.EXPECTED_WRITES