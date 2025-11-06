from unittest.mock import AsyncMock

import pytest

from ops.ecris.devices.ammeter import POSITIVE_VALUES_ONLY, BiasedAmmeter
from ops.ecris.drivers.device import Device


@pytest.mark.parametrize("input, output", [(100, 100), (0, 0), (-10, 0)])
@pytest.mark.asyncio
async def test_biased_ammeter(input, output):
    mock_device = AsyncMock(spec=Device)
    key = "test_key"
    biased_ammeter = BiasedAmmeter(mock_device, key, POSITIVE_VALUES_ONLY)
    mock_device.read_data.return_value = input
    returned_value = await biased_ammeter.read_current()
    mock_device.read_data.assert_awaited_once_with(key)
    assert returned_value == output
