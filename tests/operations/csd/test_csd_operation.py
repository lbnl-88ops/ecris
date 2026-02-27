import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from ops.ecris.devices.ammeter import Ammeter
from ops.ecris.devices.dipole import Dipole
from ops.ecris.drivers.venus_plc import VenusPLC
from ops.ecris.operations.csd.csd_operation import CSDOperation
from ops.ecris.operations.csd.parameters import CSDParameters
from ops.ecris.services.averaging import AveragingService


@pytest.fixture
def mock_devices():
    ammeter = MagicMock(spec=Ammeter)
    ammeter.read_current = AsyncMock(return_value=1.0e-7)

    mock_connection = MagicMock()
    mock_connection.send_silent_command = AsyncMock()
    ammeter._connection = mock_connection

    dipole = MagicMock(spec=Dipole)
    dipole.read_field = AsyncMock(return_value=0.5)
    dipole.set_current = AsyncMock()

    plc = MagicMock(spec=VenusPLC)
    plc.read_data = AsyncMock()
    plc.write_data = AsyncMock()

    averaging_service = MagicMock(spec=AveragingService)
    averaging_service.pause = AsyncMock()
    averaging_service.resume = AsyncMock()

    return ammeter, dipole, plc, averaging_service


@pytest.mark.asyncio
async def test_csd_operation_sequence(mock_devices):
    ammeter, dipole, plc, averaging_service = mock_devices

    # Configure PLC responses
    plc.read_data.side_effect = lambda key: {
        VenusPLC.DataKeys.FARADAY_CUP_IN: True,
        VenusPLC.DataKeys.EXTRACTION_VOLTAGE: 20.0,
        VenusPLC.DataKeys.BATMAN_I_SET: 131.0,  # Should be 1.0A
    }.get(key, 0.0)

    params = CSDParameters(n_steps=10, settle_time=0.1, field_reset_timeout=0.1)

    op = CSDOperation(ammeter, dipole, plc, averaging_service, params=params)

    result = await op.run()

    # Verify sequence
    assert averaging_service.pause.called
    assert averaging_service.resume.called

    # Verify sweep steps
    assert dipole.set_current.call_count >= 10
    assert ammeter.read_current.call_count >= 10

    # Verify result
    assert len(result.timestamps) == 10
    assert result.extraction_voltage == 20.0


@pytest.mark.asyncio
async def test_csd_operation_faraday_cup_handling(mock_devices):
    ammeter, dipole, plc, averaging_service = mock_devices

    # Faraday cup starts OUT
    plc.read_data.side_effect = lambda key: {
        VenusPLC.DataKeys.FARADAY_CUP_IN: False,
        VenusPLC.DataKeys.EXTRACTION_VOLTAGE: 20.0,
        VenusPLC.DataKeys.BATMAN_I_SET: 131.0,
    }.get(key, 0.0)

    params = CSDParameters(n_steps=5, settle_time=0.1, field_reset_timeout=0.1)
    op = CSDOperation(ammeter, dipole, plc, averaging_service, params=params)

    await op.run()

    # Verify it was inserted then retracted
    # Search for write_data(FARADAY_CUP_IN, 1.0) and write_data(FARADAY_CUP_IN, 0.0)
    calls = plc.write_data.call_args_list
    fc_writes = [c.args for c in calls if c.args[0] == VenusPLC.DataKeys.FARADAY_CUP_IN]

    assert (VenusPLC.DataKeys.FARADAY_CUP_IN, 1.0) in fc_writes
    assert (VenusPLC.DataKeys.FARADAY_CUP_IN, 0.0) in fc_writes
