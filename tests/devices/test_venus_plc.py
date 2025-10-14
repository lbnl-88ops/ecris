import pytest
from unittest.mock import MagicMock
from ops.ecris.devices.venus_plc import VenusPLC

@pytest.fixture
def venus_setup() -> tuple[VenusPLC, MagicMock]:
    mock_controller = MagicMock()
    plc = VenusPLC(mock_controller)
    return plc, mock_controller

class TestVenusWriteData:
    params = [
        (VenusPLC.DataKeys.AVERAGE_CURRENT, 1.56E-6, 'fcv1_ammeter'),
        (VenusPLC.DataKeys.CURRENT_STDEV, 3.67E-2, 'fcv1_ammeter_stdev')
    ]
    ids = ['average current', 'current stdev']

    @pytest.mark.asyncio
    @pytest.mark.parametrize('key, value, plc_key', params, ids=ids)
    async def test_write_data(self, venus_setup, key, value, plc_key):
        plc, mock_controller = venus_setup
        await plc.write_data(key, value)
        mock_controller.write.assert_called_once_with({plc_key: value})

class TestVenusReadData:
    params = [
        (VenusPLC.DataKeys.EXTRACTION_VOLTAGE, 123, 'extraction_v'),
        (VenusPLC.DataKeys.BATMAN_CURRENT, 3E-5, 'batman_i_set')
    ]
    ids = ['extraction voltage', 'BATMAN current']

    @pytest.mark.asyncio
    @pytest.mark.parametrize('key, value, plc_key', params, ids=ids)
    async def test_read_data(self, venus_setup, key, value, plc_key):
        plc, mock_controller = venus_setup
        mock_controller.read.return_value = value

        return_value = await plc.read_data(key)

        mock_controller.read.assert_called_once_with([plc_key])
        assert return_value == value
