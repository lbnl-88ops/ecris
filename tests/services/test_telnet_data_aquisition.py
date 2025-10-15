# in: tests/services/test_telnet_acquisition.py

import asyncio
import threading
from unittest.mock import AsyncMock, patch

import pytest
from ops.ecris.model.measurement import Measurement
from ops.ecris.services.base_acquisition import TelnetDataAcquisitionService

MODULE = 'ops.ecris.services.base_acquisition.'

class ConcreteAcquisitionService(TelnetDataAcquisitionService):
    def _acquire_data(self) -> Measurement:
        return Measurement(source='test_source', timestamp=1293)

@pytest.fixture
def mock_device():
    """A pytest fixture to provide a reusable mock TelnetDevice."""
    mock = AsyncMock()
    mock.id = 'mock_device_01'
    return mock

@pytest.mark.asyncio
async def test_start_connects_device_and_starts_producer_thread(mock_device):
    service = ConcreteAcquisitionService(device=mock_device)

    with patch(MODULE + 'threading.Thread') as mock_thread, \
        patch(MODULE + 'producer_thread') as mock_producer:
        await service.start()

    mock_device.connect.assert_awaited_once()

    mock_thread.assert_called_once()
    _, kwargs = mock_thread.call_args
    assert kwargs['target'] == mock_producer
    assert isinstance(kwargs['args'][0], asyncio.AbstractEventLoop)
    assert isinstance(kwargs['args'][1], asyncio.Queue)
    assert kwargs['args'][2] == service._acquire_data
    assert kwargs['daemon'] is True
    assert kwargs['name'] == "mock_device_01_Producer"

    thread_instance = mock_thread.return_value
    thread_instance.start.assert_called_once()
    
    assert service._is_running is True

# @pytest.mark.asyncio
# async def test_stop_disconnects_device_when_running(mocker, mock_device):
#     """
#     Verifies that stop() awaits device disconnect and updates state
#     when the service is running.
#     """
#     # ARRANGE
#     service = ConcreteAcquisitionService(device=mock_device)
    
#     # Manually set the "running" state to isolate this test from start()
#     service._is_running = True
#     mock_device.is_connected = True

#     # ACT
#     await service.stop()

#     # ASSERT
#     mock_device.disconnect.assert_awaited_once()
#     assert service._is_running is False

# @pytest.mark.asyncio
# async def test_stop_does_nothing_when_already_stopped(mocker, mock_device):
#     """
#     Verifies the guard clause in stop() prevents multiple disconnects.
#     """
#     # ARRANGE
#     service = ConcreteAcquisitionService(device=mock_device)
#     service._is_running = False  # Ensure service is already in the "stopped" state

#     # ACT
#     await service.stop()

#     # ASSERT
#     # The key assertion: disconnect should NOT have been called.
#     mock_device.disconnect.assert_not_called()
#     mock_device.disconnect.assert_not_awaited() # More specific for async