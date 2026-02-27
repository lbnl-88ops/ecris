import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ops.ecris.agents.csd_agent import CSDAgent
from ops.ecris.devices.ammeter import Ammeter
from ops.ecris.devices.dipole import Dipole
from ops.ecris.drivers.venus_plc import VenusPLC
from ops.ecris.services.averaging import AveragingService


@pytest.fixture
def mock_agent_deps():
    ammeter = MagicMock(spec=Ammeter)
    dipole = MagicMock(spec=Dipole)
    dipole.read_field = AsyncMock(return_value=0.5)
    dipole.set_current = AsyncMock()

    plc = MagicMock(spec=VenusPLC)
    plc.read_data = AsyncMock()
    plc.write_data = AsyncMock()

    averaging_service = MagicMock(spec=AveragingService)
    averaging_service.start = AsyncMock()
    averaging_service.stop = AsyncMock()
    averaging_service.pause = AsyncMock()
    averaging_service.resume = AsyncMock()

    return ammeter, dipole, plc, averaging_service


@pytest.mark.asyncio
async def test_csd_agent_dispatch(mock_agent_deps, tmp_path):
    ammeter, dipole, plc, averaging_service = mock_agent_deps

    # Configure PLC to trigger a CSD request once, then stop the agent
    responses = [
        # Initialization
        131.0,  # BATMAN_I_SET (1.0A)
        # First loop iteration
        1.0,  # CSD_REQUEST = True
        0.0,  # CSD_CUSTOM_REQUEST = False
        131.0,  # BATMAN_I_SET
        0.0,  # PEAKING_REQUEST = False
    ]
    plc.read_data.side_effect = responses + [0.0] * 100

    agent = CSDAgent(ammeter, dipole, plc, averaging_service, csd_directory=tmp_path)

    # Use a task to run the agent and a timeout to stop it
    agent_task = asyncio.create_task(agent.run())

    # Wait for the agent to process the request
    # We need to wait enough time for the loop to run
    await asyncio.sleep(0.5)

    # Stop the agent
    agent._is_running = False
    await agent_task

    # Verify CSDOperation was triggered
    # CSDOperation writes CSD_IN_PROGRESS = 1 then 0
    calls = plc.write_data.call_args_list
    in_progress_writes = [c.args for c in calls if c.args[0] == VenusPLC.DataKeys.CSD_IN_PROGRESS]
    assert (VenusPLC.DataKeys.CSD_IN_PROGRESS, 1.0) in in_progress_writes
    assert (VenusPLC.DataKeys.CSD_IN_PROGRESS, 0.0) in in_progress_writes

    # Verify averaging service was started and stopped
    assert averaging_service.start.called
    assert averaging_service.stop.called


@pytest.mark.asyncio
async def test_csd_agent_batman_tracking(mock_agent_deps, tmp_path):
    ammeter, dipole, plc, averaging_service = mock_agent_deps

    # Batman setpoint changes: 131.0 -> 262.0 (1.0A -> 2.0A)
    plc.read_data.side_effect = [
        131.0,  # Init
        0.0,
        0.0,  # No CSD req
        262.0,  # BATMAN_I_SET changed!
        0.0,  # No peaking req
    ] + [0.0] * 100

    agent = CSDAgent(ammeter, dipole, plc, averaging_service, csd_directory=tmp_path)
    agent_task = asyncio.create_task(agent.run())

    await asyncio.sleep(0.3)

    agent._is_running = False
    await agent_task

    # Verify dipole current was updated
    dipole.set_current.assert_any_call(2.0)
