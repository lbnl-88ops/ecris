import pytest
from unittest.mock import patch

from ops.ecris.devices.labjack import LabJack

MODULE = 'ops.ecris.devices.labjack.'

@pytest.fixture
def labjack():
    return LabJack()

@pytest.mark.asyncio
async def test_labjback_connect_sends_correct_command(labjack):
    with patch(MODULE + 'ljm') as mock_ljm:
        handle: int = 5
        mock_ljm.openS.return_value = handle
        await labjack.connect()
        mock_ljm.openS.assert_called_once_with("T8", "usb", "ANY")
        assert labjack._handle == handle
        


