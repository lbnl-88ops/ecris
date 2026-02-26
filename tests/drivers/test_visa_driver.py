import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from ops.ecris.drivers.visa_driver import VISADriver

@pytest.mark.asyncio
async def test_visa_driver_connect():
    with patch("pyvisa.ResourceManager") as mock_rm_class:
        mock_rm = mock_rm_class.return_value
        mock_instrument = MagicMock()
        mock_rm.open_resource.return_value = mock_instrument
        
        driver = VISADriver(resource_name="USB0::1234::5678::INSTR")
        await driver.connect()
        
        mock_rm_class.assert_called_once_with("@py")
        mock_rm.open_resource.assert_called_once_with("USB0::1234::5678::INSTR")
        assert driver.is_connected

@pytest.mark.asyncio
async def test_visa_driver_write():
    with patch("pyvisa.ResourceManager") as mock_rm_class:
        mock_rm = mock_rm_class.return_value
        mock_instrument = MagicMock()
        mock_rm.open_resource.return_value = mock_instrument
        
        driver = VISADriver(resource_name="USB0::1234::5678::INSTR")
        await driver.connect()
        
        await driver._write("*RST")
        mock_instrument.write.assert_called_once_with("*RST")

@pytest.mark.asyncio
async def test_visa_driver_read_until():
    with patch("pyvisa.ResourceManager") as mock_rm_class:
        mock_rm = mock_rm_class.return_value
        mock_instrument = MagicMock()
        mock_rm.open_resource.return_value = mock_instrument
        mock_instrument.read.return_value = "RESPONSE\n"
        
        driver = VISADriver(resource_name="USB0::1234::5678::INSTR")
        await driver.connect()
        
        response = await driver._read_until()
        assert response == "RESPONSE"
        mock_instrument.read.assert_called_once()
