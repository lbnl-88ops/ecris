import pytest
from pytest import approx
from unittest.mock import patch

from ops.ecris.drivers.labjack import LabJack

MODULE = "ops.ecris.drivers.labjack."


@pytest.fixture
def labjack():
    return LabJack()


@pytest.mark.asyncio
async def test_labjback_connect_sends_correct_command(labjack):
    with patch(MODULE + "ljm") as mock_ljm:
        handle: int = 5
        mock_ljm.openS.return_value = handle
        await labjack.connect()
        mock_ljm.openS.assert_called_once_with("T8", "usb", "ANY")
        assert labjack._handle == handle


@pytest.mark.asyncio
async def test_labjack_get_b_field_sends_correct_request(labjack):
    labjack._handle = 5
    with patch(MODULE + "ljm") as mock_ljm:
        expected_b_field = 1.2
        mock_ljm.eReadName.return_value = expected_b_field
        b_field = await labjack.read_data(LabJack.DataKeys.BATMAN_FIELD)
        mock_ljm.eReadName.assert_called_once_with(labjack._handle, "AIN0")
        assert b_field == approx(1.2)


@pytest.mark.asyncio
async def test_labjack_set_batman_current_sends_correct_request(labjack):
    labjack._handle = 5
    with patch(MODULE + "ljm") as mock_ljm:
        current_to_send = 0.12
        await labjack.write_data(LabJack.DataKeys.BATMAN_CURRENT, current_to_send)
        mock_ljm.eWriteName.assert_called_once_with(labjack._handle, "DAC0", current_to_send)
