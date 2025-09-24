# Characterization tests for legacy/current code

from unittest.mock import patch, MagicMock, call

from .legacy_code.legacy_functions import legacy_current_measurement, getCurrent

MODULE = 'tests.legacy_code.legacy_functions.'

def test_legacy_code_produces_correct_average():
    mock_current_values = [1.0e-5, 1.5e-5, 2.0e-5]
    
    mock_timestamps = [1000.00, 1000.10, 1000.20, 1000.30, 1000.40] 
    
    mock_connection = MagicMock()
    mock_connection.read_until.side_effect = [
        b'B2900A>       1.0E-05\r\n',
        b'B2900A>       1.5E-05\r\n',
        b'B2900A>       2.0E-05\r\n',
    ]

    with patch(MODULE + 'time') as mock_time, \
         patch(MODULE + 'venus') as mock_venus:
 
        mock_time.time.side_effect = mock_timestamps
        legacy_current_measurement(mock_connection)

    expected_average = 1.5e-5
    mock_venus.write.assert_called_once_with({'fcv1_ammeter': expected_average})

    assert mock_connection.read_until.call_count == 3