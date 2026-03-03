from unittest.mock import AsyncMock

import pytest

from ops.ecris.devices.deflection_plate_controller import LABJACK_DEFLECTION_PLATE_BIAS
from ops.ecris.devices.power_supply import BiasedVoltageSource
from ops.ecris.drivers.labjack import LabJack


@pytest.mark.asyncio
async def test_biased_voltage_source():
    mock_labjack = AsyncMock(spect=LabJack)
    key = LabJack.DataKeys.DAC1
    biased_voltage_source = BiasedVoltageSource(
        mock_labjack, LabJack.DataKeys.DAC1, LABJACK_DEFLECTION_PLATE_BIAS
    )
    input_voltage = 120
    expected_output = 1.2 + 3.188
    await biased_voltage_source.set_voltage(input_voltage)
    mock_labjack.write_data.assert_awaited_once_with(key, expected_output)
