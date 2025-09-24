# Characterization tests for legacy/current code
from unittest.mock import patch, MagicMock, AsyncMock

import numpy as np
import pytest

from ops.ecris.measure_current import time_average_current
from .legacy_code.legacy_functions import legacy_current_measurement, getCurrent

LEGACY_MODULE = 'tests.legacy_code.legacy_functions.'
MODULE = 'ops.ecris.measure_current.'


@pytest.fixture
def current_readings():
    return [1.0E-05, 1.5E-05, 2.0E-05]

@pytest.fixture
def current_bytes(current_readings):
    return [
        f'B2900A>       {c:E}\r\r'.encode('ascii') for c in current_readings
    ]

@pytest.fixture
def timestamps():
    return [1000.00, 1000.10, 1000.20, 1000.30, 1000.40] 

def test_legacy_code_produces_correct_average(current_bytes, timestamps):
    
    mock_connection = MagicMock()
    mock_connection.read_until.side_effect = current_bytes

    with patch(LEGACY_MODULE + 'time') as mock_time, \
         patch(LEGACY_MODULE + 'venus') as mock_venus:

        mock_time.time.side_effect = timestamps
        legacy_current_measurement(mock_connection)

    expected_average = 1.5e-5
    expected_stdev = 27.216552697590874
    mock_venus.write.assert_called_with([{'fcv1_ammeter': expected_average}, 
                                         {'fcv1_ammeter_stdev': expected_stdev}])

    assert mock_connection.read_until.call_count == 3

@pytest.mark.asyncio
async def test_time_average_current(current_readings, timestamps):
    mock_ammeter = AsyncMock()
    mock_ammeter.get_data.side_effect =[
        {'time': t, 'current': c} for t, c in zip(timestamps, current_readings)
    ]
    
    with patch(MODULE + 'time') as mock_time:
        mock_time.time.side_effect = timestamps
        average, std = await time_average_current(mock_ammeter, 0.33)

    assert average == 1.5e-5
    assert std == pytest.approx(27.21655)

