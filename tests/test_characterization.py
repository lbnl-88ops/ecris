# Characterization tests for legacy/current code
import pytest

from unittest.mock import patch, MagicMock, call

from .legacy_code.legacy_functions import legacy_current_measurement, getCurrent

LEGACY_MODULE = 'tests.legacy_code.legacy_functions.'

@pytest.fixture
def current_readings():
    return [
        b'B2900A>       1.0E-05\r\n',
        b'B2900A>       1.5E-05\r\n',
        b'B2900A>       2.0E-05\r\n',
    ]

@pytest.fixture
def timestamps():
    return [1000.00, 1000.10, 1000.20, 1000.30, 1000.40] 

def test_legacy_code_produces_correct_average(current_readings, timestamps):
    
    mock_connection = MagicMock()
    mock_connection.read_until.side_effect = current_readings

    with patch(LEGACY_MODULE + 'time') as mock_time, \
         patch(LEGACY_MODULE + 'venus') as mock_venus:
 
        mock_time.time.side_effect = timestamps
        legacy_current_measurement(mock_connection)

    expected_average = 1.5e-5
    mock_venus.write.assert_called_once_with({'fcv1_ammeter': expected_average})

    assert mock_connection.read_until.call_count == 3