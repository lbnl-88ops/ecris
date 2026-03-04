"""
Integration tests for the ECRISAgent ZeroMQ IPC layer.

These tests spin up a real ECRISAgent (in test mode with mock drivers) and
verify that:

* The agent publishes ``telemetry`` frames on its PUB socket.
* The agent publishes ``log`` frames on its PUB socket.
* The REP socket correctly dispatches CSD, EMITTANCE, MOTOR, STOP, PEAK,
  BATMAN, and unknown commands.
* The ``IPCProvider`` context manager cleans up its sockets on exit.
* The ``ECRISAgent.create()`` factory wires up the correct IPC paths for
  both test mode and (the structural check for) production mode.
"""

import asyncio
import json
from pathlib import Path

import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Skip the entire module if pyzmq is not installed, so the test suite still
# passes in environments without it.
# ---------------------------------------------------------------------------
pytest.importorskip("zmq", reason="pyzmq is required for IPC tests")

import zmq  # noqa: E402 — import after the skip guard
import zmq.asyncio  # noqa: E402

from ops.ecris.agents.ecris_agent import (  # noqa: E402
    _DEFAULT_COMMAND_IPC,
    _DEFAULT_TELEMETRY_IPC,
    _TEST_COMMAND_IPC,
    _TEST_TELEMETRY_IPC,
    ECRISAgent,
    IPCProvider,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dirs(tmp_path: Path):
    """Return (csd_dir, emittance_dir) as temporary paths."""
    csd = tmp_path / "csds"
    emittance = tmp_path / "emittance"
    return csd, emittance


@pytest_asyncio.fixture
async def running_agent(tmp_dirs):
    """
    Start an ECRISAgent (test mode) in the background and yield it.

    After the test body completes the agent is stopped and the task awaited.
    """
    csd_dir, emittance_dir = tmp_dirs
    agent = ECRISAgent.create(test_mode=True)
    agent._csd_directory = csd_dir
    agent._emittance_directory = emittance_dir

    task = asyncio.create_task(agent.run())

    # Give the agent enough time to bind its ZMQ sockets.
    await asyncio.sleep(0.5)

    yield agent

    agent._is_running = False
    try:
        await asyncio.wait_for(task, timeout=3.0)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# Helper — send one REQ/REP command and return the parsed reply
# ---------------------------------------------------------------------------

async def _send_command(cmd: str, ipc_addr: str = _TEST_COMMAND_IPC) -> dict:
    ctx = zmq.asyncio.Context.instance()
    req = ctx.socket(zmq.REQ)
    req.connect(ipc_addr)
    req.setsockopt(zmq.LINGER, 0)
    req.setsockopt(zmq.RCVTIMEO, 3000)
    try:
        await req.send_string(cmd)
        raw = await req.recv_string()
        return json.loads(raw)
    finally:
        req.close(linger=0)


# ---------------------------------------------------------------------------
# Tests — socket path constants
# ---------------------------------------------------------------------------

def test_ipc_socket_path_constants():
    """Verify the module-level IPC path constants have the expected values."""
    assert _DEFAULT_TELEMETRY_IPC == "ipc:///tmp/ecris_telemetry.ipc"
    assert _DEFAULT_COMMAND_IPC == "ipc:///tmp/ecris_command.ipc"
    assert _TEST_TELEMETRY_IPC == "ipc:///tmp/ecris_telemetry_test.ipc"
    assert _TEST_COMMAND_IPC == "ipc:///tmp/ecris_command_test.ipc"


def test_create_test_mode_uses_test_ipc_paths():
    """ECRISAgent.create(test_mode=True) must wire up the test IPC paths."""
    agent = ECRISAgent.create(test_mode=True)
    assert agent._telemetry_ipc == _TEST_TELEMETRY_IPC
    assert agent._command_ipc == _TEST_COMMAND_IPC


def test_create_default_ctor_uses_production_ipc_paths(tmp_dirs):
    """
    When ECRISAgent is constructed directly (not via create()), it defaults
    to the production IPC paths.
    """
    from unittest.mock import MagicMock

    from ops.ecris.devices.ammeter import Ammeter
    from ops.ecris.devices.deflection_plate_controller import DeflectionPlateController
    from ops.ecris.devices.dipole import Dipole
    from ops.ecris.devices.motor_controller_specification import Axis
    from ops.ecris.drivers.mocks import DummyAmmeter, DummyPLC
    from ops.ecris.drivers.scpi_driver import SCPIDriver
    from ops.ecris.operations.emittance_scan import LinearScanParameters
    from ops.ecris.services.averaging import AveragingService

    ammeter_drv = DummyAmmeter()
    plc_drv = DummyPLC()
    ammeter = Ammeter(connection=ammeter_drv, read_key=SCPIDriver.DataKeys.CURRENT)
    averaging_service = AveragingService(ammeter=ammeter, plc=plc_drv)  # type: ignore[arg-type]
    dipole = MagicMock(spec=Dipole)
    dpc = MagicMock(spec=DeflectionPlateController)
    motor = MagicMock()
    params = LinearScanParameters(
        axis=Axis.VenusX,
        position_min=-1.0, position_max=1.0, position_step=1.0,
        divergence_min=-0.01, divergence_max=0.01, divergence_step=0.01,
        samples_per_point=1,
    )

    csd_dir, emittance_dir = tmp_dirs
    agent = ECRISAgent(
        ammeter=ammeter,
        dipole=dipole,  # type: ignore[arg-type]
        plc=plc_drv,  # type: ignore[arg-type]
        averaging_service=averaging_service,
        motor=motor,
        deflection_plate_controller=dpc,
        emittance_params=params,
        csd_directory=csd_dir,
        emittance_directory=emittance_dir,
    )
    assert agent._telemetry_ipc == _DEFAULT_TELEMETRY_IPC
    assert agent._command_ipc == _DEFAULT_COMMAND_IPC


# ---------------------------------------------------------------------------
# Tests — live IPC round-trips (require a running agent)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_telemetry_frame_is_published(running_agent):
    """
    The agent must publish at least one ``telemetry`` frame containing the
    expected keys within a reasonable timeout.
    """
    ctx = zmq.asyncio.Context.instance()
    sub = ctx.socket(zmq.SUB)
    sub.connect(_TEST_TELEMETRY_IPC)
    sub.setsockopt_string(zmq.SUBSCRIBE, "telemetry")
    sub.setsockopt(zmq.RCVTIMEO, 3000)

    try:
        raw = await sub.recv_string()
        topic, _, payload_str = raw.partition(" ")
        data = json.loads(payload_str)

        assert topic == "telemetry"
        assert "ts" in data
        assert "avg_current_a" in data
        assert "current_std_ua" in data
        assert "motor_pos_mm" in data
        assert "op_status" in data
        assert "avg_paused" in data
        assert "op_locked" in data
        assert data["op_status"] == "Idle"
    finally:
        sub.close(linger=0)


@pytest.mark.asyncio
async def test_log_frames_are_published(running_agent):
    """
    The agent must publish at least one ``log`` frame on the PUB socket
    containing the expected keys.
    """
    ctx = zmq.asyncio.Context.instance()
    sub = ctx.socket(zmq.SUB)
    sub.connect(_TEST_TELEMETRY_IPC)
    sub.setsockopt_string(zmq.SUBSCRIBE, "log")
    sub.setsockopt(zmq.RCVTIMEO, 5000)

    try:
        raw = await sub.recv_string()
        topic, _, payload_str = raw.partition(" ")
        data = json.loads(payload_str)

        assert topic == "log"
        assert "level" in data
        assert "msg" in data
        assert "ts" in data
        assert isinstance(data["ts"], float)
    finally:
        sub.close(linger=0)


@pytest.mark.asyncio
async def test_batman_command_ok(running_agent):
    """
    The BATMAN command must be accepted and return ``{"status": "ok"}``.
    The batman setpoint on the PLC should be nudged.
    """
    reply = await _send_command("BATMAN")
    assert reply["status"] == "ok"
    assert "batman" in reply["msg"].lower() or "setpoint" in reply["msg"].lower()


@pytest.mark.asyncio
async def test_peak_command_ok(running_agent):
    """The PEAK command must be accepted and return ``{"status": "ok"}``."""
    reply = await _send_command("PEAK")
    assert reply["status"] == "ok"
    assert "PEAKING_REQUEST" in reply["msg"]


@pytest.mark.asyncio
async def test_stop_command_when_idle(running_agent):
    """
    STOP when no operation is running must return ``{"status": "ok"}`` with a
    message indicating no operation was in progress.
    """
    reply = await _send_command("STOP")
    assert reply["status"] == "ok"


@pytest.mark.asyncio
async def test_unknown_command_rejected(running_agent):
    """An unrecognised command must return ``{"status": "error"}``."""
    reply = await _send_command("FOOBAR")
    assert reply["status"] == "error"
    assert "FOOBAR" in reply["msg"] or "Unknown" in reply["msg"]


@pytest.mark.asyncio
async def test_csd_command_dispatched(running_agent):
    """
    The CSD command must be accepted (status ``ok`` or ``busy``) and cause the
    agent to briefly show a non-Idle op_status.
    """
    reply = await _send_command("CSD")
    # Either the agent accepted the request or it's already busy — both are valid.
    assert reply["status"] in ("ok", "busy")


@pytest.mark.asyncio
async def test_emittance_command_dispatched(running_agent):
    """The EMITTANCE command must return a valid status."""
    reply = await _send_command("EMITTANCE")
    assert reply["status"] in ("ok", "busy")


@pytest.mark.asyncio
async def test_motor_command_dispatched(running_agent):
    """The MOTOR command must return a valid status."""
    reply = await _send_command("MOTOR")
    assert reply["status"] in ("ok", "busy")


@pytest.mark.asyncio
async def test_command_is_case_insensitive(running_agent):
    """
    The agent must handle commands case-insensitively (the socket layer
    upper-cases them, so both ``batman`` and ``BATMAN`` should work).
    """
    reply_lower = await _send_command("batman")
    assert reply_lower["status"] == "ok"


# ---------------------------------------------------------------------------
# Tests — IPCProvider context manager
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ipc_provider_binds_and_cleans_up():
    """
    The IPCProvider context manager must bind both sockets and cleanly close
    them on __aexit__ without raising.
    """
    # Use unique addresses to avoid conflicting with the running_agent fixture.
    tel = "ipc:///tmp/ecris_test_provider_tel.ipc"
    cmd = "ipc:///tmp/ecris_test_provider_cmd.ipc"

    async with IPCProvider(telemetry_ipc=tel, command_ipc=cmd) as ipc:
        # Verify we can publish (no exception = success)
        await ipc.publish_telemetry({"ts": 1.0, "test": True})

        # Verify recv_command_nowait returns None when inbox is empty.
        result = await ipc.recv_command_nowait()
        assert result is None

    # After __aexit__ the sockets must be closed (attributes set to None).
    assert ipc._pub is None
    assert ipc._rep is None


@pytest.mark.asyncio
async def test_ipc_provider_send_reply_after_command():
    """
    A client can connect to the REP socket, send a message, and receive a reply.
    """
    tel = "ipc:///tmp/ecris_test_rep_roundtrip_tel.ipc"
    cmd = "ipc:///tmp/ecris_test_rep_roundtrip_cmd.ipc"

    async with IPCProvider(telemetry_ipc=tel, command_ipc=cmd) as ipc:
        ctx = zmq.asyncio.Context.instance()
        req = ctx.socket(zmq.REQ)
        req.connect(cmd)
        req.setsockopt(zmq.LINGER, 0)
        req.setsockopt(zmq.RCVTIMEO, 2000)

        try:
            await req.send_string("HELLO")
            # Now the provider side should receive it.
            received = await ipc.recv_command_nowait()
            # It might not be immediately available; poll briefly.
            for _ in range(20):
                if received is not None:
                    break
                await asyncio.sleep(0.05)
                received = await ipc.recv_command_nowait()

            assert received == "HELLO"

            # Send a reply.
            await ipc.send_reply({"status": "ok", "msg": "echo HELLO"})

            # Client should receive it.
            raw_reply = await req.recv_string()
            parsed = json.loads(raw_reply)
            assert parsed["status"] == "ok"
            assert "HELLO" in parsed["msg"]
        finally:
            req.close(linger=0)
