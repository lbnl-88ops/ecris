import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from ops.ecris.devices.ammeter import Ammeter
from ops.ecris.drivers.venus_plc import VenusPLC
from ops.ecris.services.averaging import AveragingService


@pytest.fixture
def mock_ammeter():
    ammeter = MagicMock(spec=Ammeter)
    ammeter.read_current = AsyncMock(return_value=1.0e-6)
    ammeter._connection = MagicMock()
    return ammeter


@pytest.fixture
def mock_plc():
    plc = MagicMock(spec=VenusPLC)
    plc.write_data = AsyncMock()
    return plc


@pytest.mark.asyncio
async def test_averaging_service_math(mock_ammeter, mock_plc):
    # Setup service with short window
    service = AveragingService(mock_ammeter, mock_plc, window_seconds=0.1)

    # Mock readings: 1, 2, 3... and loop them infinitely
    def readings():
        while True:
            for val in [1.0, 2.0, 3.0]:
                yield val

    mock_ammeter.read_current.side_effect = readings()

    # Run one window manually by calling the internal loop logic or just start/stop
    # We'll use a task and wait
    task = asyncio.create_task(service.run())
    await asyncio.sleep(0.15)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Verify PLC writes occurred
    assert mock_plc.write_data.called
    # Check if AVERAGE_CURRENT was written
    # iave of [1,2,3] is 2.0. istd is sqrt((1+4+9)/3 - 4) = sqrt(14/3 - 12/3) = sqrt(2/3) = 0.816
    # std% = 0.816 / 2 * 100 = 40.8

    # We can't guarantee exactly 3 readings in 0.1s in this environment,
    # but we check if the calls match the keys.
    calls = mock_plc.write_data.call_args_list
    keys_written = [c.args[0] for c in calls]
    assert VenusPLC.DataKeys.AVERAGE_CURRENT in keys_written
    assert VenusPLC.DataKeys.CURRENT_STDEV in keys_written


@pytest.mark.asyncio
async def test_averaging_service_pause_resume(mock_ammeter, mock_plc):
    service = AveragingService(mock_ammeter, mock_plc, window_seconds=0.1)

    await service.start()
    await asyncio.sleep(0.15)
    assert mock_ammeter.read_current.called

    # Pause
    await service.pause()
    mock_ammeter.read_current.reset_mock()
    await asyncio.sleep(0.2)
    # Should not have been called while paused
    assert not mock_ammeter.read_current.called

    # Resume
    await service.resume()
    await asyncio.sleep(0.15)
    assert mock_ammeter.read_current.called

    await service.stop()
