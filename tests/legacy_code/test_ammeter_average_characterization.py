# Characterization tests for legacy/current code
from unittest.mock import patch, MagicMock, AsyncMock, call

import asyncio
import pytest
from pytest import approx
import time

from ops.ecris.drivers import keithley
from ops.ecris.drivers.measurement import AverageMeasurement
from ops.ecris.operations.producers import time_average_current
from ops.ecris.tasks.device_broadcasters import update_plc_average_current
from ops.ecris.drivers.venus_plc import VenusPLC
from ops.ecris.devices.ammeter import Ammeter
from ops.ecris.drivers.keithley import Keysight
from .ammeter_legacy_functions import legacy_current_measurement

LEGACY_MODULE = "tests.legacy_code.ammeter_legacy_functions."
MODULE = "ops.ecris.operations.producers."
VENUS_MODULE = "ops.ecris.devices.venus_plc."


def current_bytes(current_readings):
    return [f"B2900A>      {c:+E}\r\r".encode("ascii") for c in current_readings]


class TestAverage:
    EXPECTED_AVERAGE = 1.5e-5
    EXPECTED_REL_STDEV = approx(27.21655)
    CURRENT_READINGS = [1.0e-05, 1.5e-05, 2.0e-05]
    TIME = time.time()
    TIMESTAMPS = [1000.00, 1000.10, 1000.20, 1000.30, 1000.40, TIME]

    def test_legacy_code_produces_correct_average(self):
        mock_connection = MagicMock()
        mock_connection.read_until.side_effect = current_bytes(self.CURRENT_READINGS)

        with (
            patch(LEGACY_MODULE + "time") as mock_time,
            patch(LEGACY_MODULE + "venus") as mock_venus,
        ):
            mock_time.time.side_effect = self.TIMESTAMPS
            legacy_current_measurement(mock_connection)

        expected_calls = [
            call.write({"fcv1_ammeter": self.EXPECTED_AVERAGE}),
            call.write({"fcv1_ammeter_stdev": self.EXPECTED_REL_STDEV}),
        ]
        mock_venus.assert_has_calls(expected_calls, any_order=True)
        assert mock_connection.read_until.call_count == len(self.CURRENT_READINGS)

    @pytest.mark.asyncio
    async def test_time_average_current(self):
        mock_keithley = AsyncMock()
        ammeter = Ammeter(mock_keithley, Keysight.DataKeys.CURRENT)
        loop = asyncio.get_running_loop()
        mock_keithley.read_data.side_effect = self.CURRENT_READINGS

        with patch(MODULE + "time") as mock_time:
            mock_time.time.side_effect = self.TIMESTAMPS
            measurement = await asyncio.to_thread(time_average_current, loop, ammeter, 0.33)
        expected_calls = [call(Keysight.DataKeys.CURRENT) for _ in self.CURRENT_READINGS]
        assert mock_keithley.read_data.await_args_list == expected_calls
        assert measurement.average == self.EXPECTED_AVERAGE
        assert measurement.standard_deviation == self.EXPECTED_REL_STDEV

    @pytest.mark.asyncio
    async def test_time_average_current_update(self):
        mock_venus_plc = AsyncMock()
        measurement = AverageMeasurement(
            "ammeter", self.TIME, self.EXPECTED_AVERAGE, self.EXPECTED_REL_STDEV.expected
        )

        await update_plc_average_current(mock_venus_plc, measurement)
        expected_calls = [
            call(VenusPLC.DataKeys.AVERAGE_CURRENT, self.EXPECTED_AVERAGE),
            call(VenusPLC.DataKeys.CURRENT_STDEV, self.EXPECTED_REL_STDEV),
        ]
        assert mock_venus_plc.write_data.await_args_list == expected_calls


class TestZeroAverage(TestAverage):
    EXPECTED_AVERAGE = 0
    EXPECTED_REL_STDEV = approx(-2, rel=0)
    CURRENT_READINGS = [-3.5, 1.5, 2.0]
