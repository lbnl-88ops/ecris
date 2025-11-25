from unittest.mock import AsyncMock

import pytest

from ops.ecris.devices.ammeter import BiasedAmmeter
from ops.ecris.devices.biases import POSITIVE_VALUES_ONLY
from ops.ecris.drivers.base import DataSource


@pytest.mark.parametrize("input, output", [(100, 100), (0, 0), (-10, 0)])
@pytest.mark.asyncio
async def test_biased_ammeter(input, output):
    mock_device = AsyncMock(spec=DataSource)
    key = "test_key"
    biased_ammeter = BiasedAmmeter(mock_device, key, POSITIVE_VALUES_ONLY)
    mock_device.read_data.return_value = input
    returned_value = await biased_ammeter.read_current()
    mock_device.read_data.assert_awaited_once_with(key)
    assert returned_value == output
