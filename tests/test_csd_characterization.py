import pytest
from unittest.mock import patch, MagicMock, mock_open, call
import time

from tests.legacy_code.legacy_functions import datasheet

MODULE = 'tests.legacy_code.legacy_functions.'

def test_datasheet_characterization():
    fake_var_names = ['extraction_v', 'fcv1_ammeter', 'batman_i_set']
    fake_var_values = [15003.1, 1.23456E-6, 0.05]
    
    timestamp_str = str(int(time.time()))
    fake_directory = '/tmp/test_data'
    expected_filepath = f'{fake_directory}/dsht_{timestamp_str}'

    mock_venus = MagicMock()
    mock_venus.read_vars.return_value = fake_var_names
    mock_venus.read.side_effect = fake_var_values

    with patch(MODULE + 'venus', mock_venus), \
         patch(MODULE + 'directory', fake_directory), \
         patch(MODULE + 'open', mock_open()) as mocked_file:
        
        datasheet(timestamp_str)

    mocked_file.assert_called_once_with(expected_filepath, 'w')
    mock_venus.read_vars.assert_called_once_with()
    expected_read_calls = [call([name]) for name in fake_var_names]

    assert mock_venus.read.call_args_list == expected_read_calls

    handle = mocked_file()
    expected_writes = [
        call("   0 1.50031e+04 extraction_v\n"),
        call("   1 1.23456e-06 fcv1_ammeter\n"),
        call("   2 5.00000e-02 batman_i_set\n")
    ]
    
    assert handle.write.call_args_list == expected_writes