import pytest
from unittest.mock import MagicMock, patch

from ops.ecris.devices.venus_plc import VenusPLC

MODULE = 'ops.ecris.devices.venus_plc.'

@pytest.mark.asyncio
async def test_venus_sends_correct_current():
    expected_current = 1.56E-6
    mock_controller = MagicMock()

    plc = VenusPLC(mock_controller)
    await plc.write_data(VenusPLC.DataKeys.AVERAGE_CURRENT, 
                            expected_current)
    mock_controller.write.assert_called_once_with(
        {'fcv1_ammeter': expected_current}
        )

