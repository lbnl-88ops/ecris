# Characterization tests for legacy/current code
from unittest.mock import patch, MagicMock, AsyncMock, call

import pytest
from pytest import approx

from ops.ecris.measure_current import time_average_current
from .legacy_code.legacy_functions import legacy_current_measurement

LEGACY_MODULE = 'tests.legacy_code.legacy_functions.'
MODULE = 'ops.ecris.measure_current.'

def current_bytes(current_readings):
    return [
        f'B2900A>      {c:+E}\r\r'.encode('ascii') for c in current_readings
    ]

class TestAverage:
    EXPECTED_AVERAGE = 1.5e-5
    EXPECTED_REL_STDEV = approx(27.21655)
    CURRENT_READINGS = [1.0E-05, 1.5E-05, 2.0E-05]
    TIMESTAMPS = [1000.00, 1000.10, 1000.20, 1000.30, 1000.40] 

    def test_legacy_code_produces_correct_average(self):
        
        mock_connection = MagicMock()
        mock_connection.read_until.side_effect = current_bytes(self.CURRENT_READINGS)

        with patch(LEGACY_MODULE + 'time') as mock_time, \
            patch(LEGACY_MODULE + 'venus') as mock_venus:

            mock_time.time.side_effect = self.TIMESTAMPS
            legacy_current_measurement(mock_connection)

        expected_calls = [
            call.write({'fcv1_ammeter': self.EXPECTED_AVERAGE}),
            call.write({'fcv1_ammeter_stdev': self.EXPECTED_REL_STDEV})
        ]
        mock_venus.assert_has_calls(expected_calls, any_order=True)
        assert mock_connection.read_until.call_count == len(self.CURRENT_READINGS)

    @pytest.mark.asyncio
    async def test_time_average_current(self):
        mock_ammeter = AsyncMock()
        mock_ammeter.get_data.side_effect =[
            {'time': t, 'current': c} for t, c in zip(self.TIMESTAMPS, self.CURRENT_READINGS)
        ]
        
        with patch(MODULE + 'time') as mock_time:
            mock_time.time.side_effect = self.TIMESTAMPS
            average, std = await time_average_current(mock_ammeter, 0.33)

        assert average == self.EXPECTED_AVERAGE
        assert std == self.EXPECTED_REL_STDEV

class TestZeroAverage(TestAverage):
    EXPECTED_AVERAGE = 0
    EXPECTED_REL_STDEV = -2
    CURRENT_READINGS = [-3.5, 1.5, 2.0]
