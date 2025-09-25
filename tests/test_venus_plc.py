import pytest
from unittest.mock import MagicMock, patch

from ops.ecris.devices.venus_plc import VenusPLC

MODULE = 'ops.ecris.devices.venus_plc.'

class TestVenusWriteData:
    mock_controller = MagicMock()
    plc = VenusPLC(mock_controller)
    params = [
        (VenusPLC.DataKeys.AVERAGE_CURRENT, 1.56E-6, 'fcv1_ammeter'),
        (VenusPLC.DataKeys.CURRENT_STDEV, 3.67E-2, 'fcv1_ammeter_stdev')
    ]
    ids = ['average current', 
           'current_stdev']

    @pytest.mark.asyncio
    @pytest.mark.parametrize('key, value, plc_key', params, ids=ids)
    async def test_write_data(self, key, value, plc_key):
        self.mock_controller.reset_mock()
        await self.plc.write_data(key, value)
        self.mock_controller.write.assert_called_once_with({plc_key: value})
        