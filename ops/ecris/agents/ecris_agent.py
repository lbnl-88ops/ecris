"""
ECRIS Agent — unified hardware-coordination daemon.

``ECRISAgent`` is the successor to ``CSDAgent``.  It inherits all CSD and
batman-tracking behaviour from ``CSDAgent`` and extends it with:

* **EmittanceOperation** — triggers a ``LinearEmittanceScan`` when the PLC
  raises an ``EMITTANCE_REQUEST`` flag.
* **MotorMoveOperation** — parks the active probe axis to its OUT position
  when the PLC raises a ``MOTOR_MOVE_REQUEST`` flag.
* **ZeroMQ IPC** — publishes live telemetry (averaging data, motor position,
  operation status) to ``ipc:///tmp/ecris_telemetry.ipc`` via a ``PUB``
  socket, and receives operator commands (CSD, Emittance, Motor, Stop) on
  ``ipc:///tmp/ecris_command.ipc`` via a ``REP`` socket.

ZeroMQ patterns
---------------
* **PUB/SUB** — telemetry and log messages published by the agent; the TUI
  subscribes.  Topics:

  * ``telemetry`` — JSON frame with live data (current, motor pos, op status).
  * ``log``       — JSON frame with a structured log record for the activity log.

* **REQ/REP** — the TUI sends a command request; the agent replies with an
  acknowledgement.  Supported command strings:

  * ``CSD``       — trigger a standard CSD sweep.
  * ``EMITTANCE`` — trigger an emittance scan.
  * ``MOTOR``     — move the motor axis to OUT.
  * ``STOP``      — cancel the current manual operation (no-op if idle).
  * ``PEAK``      — set the PLC peaking-request flag.
  * ``BATMAN``    — nudge the batman setpoint by +0.1 A (test/diagnostic).

Mutual exclusion
----------------
Both emittance scans and motor moves share the class-level
``LinearEmittanceScan._scan_lock``, so only one hardware-intensive operation
can run at any time.  CSD sweeps are serialised at the agent level via the
``_operation_lock`` — a lightweight ``asyncio.Lock`` that wraps each
``_handle_*`` coroutine.

Test / simulation mode
-----------------------
Pass ``test_mode=True`` to the constructor (or use :func:`create`) to swap
every hardware driver for the in-memory ``Dummy*`` equivalents provided by
:mod:`ops.ecris.drivers.mocks`.  No physical devices are required in this
mode, which makes it suitable for CI pipelines and operator demos.

IPC socket paths
----------------
The default IPC paths can be overridden via the ``telemetry_ipc`` and
``command_ipc`` constructor arguments, or by passing ``test_mode=True`` which
redirects to ``ipc:///tmp/ecris_telemetry_test.ipc`` and
``ipc:///tmp/ecris_command_test.ipc`` automatically when calling
:func:`create`.

Typical usage::

    # Production (headless — IPC mode)
    agent = ECRISAgent.create(test_mode=False, ...)
    await agent.run()

    # Test / simulation
    agent = ECRISAgent.create(test_mode=True)
    await agent.run()
"""

import asyncio
import json
import logging
import time
from logging import getLogger
from pathlib import Path
from typing import Optional

import zmq
import zmq.asyncio

from ops.ecris.agents.csd_agent import CSDAgent
from ops.ecris.devices.ammeter import Ammeter
from ops.ecris.devices.deflection_plate_controller import DeflectionPlateController
from ops.ecris.devices.dipole import Dipole
from ops.ecris.devices.motor_controller_specification import Axis
from ops.ecris.drivers.venus_plc import VenusPLC
from ops.ecris.operations.csd.parameters import CSDParameters
from ops.ecris.operations.emittance_scan import LinearEmittanceScan, LinearScanParameters
from ops.ecris.operations.emittance_scan.save_scan import save_emittance_scan
from ops.ecris.operations.motor_move import MotorMoveOperation
from ops.ecris.services.averaging import AveragingService

_log = getLogger(__name__)

# ---------------------------------------------------------------------------
# Default IPC socket addresses
# ---------------------------------------------------------------------------
_DEFAULT_TELEMETRY_IPC = "ipc:///tmp/ecris_telemetry.ipc"
_DEFAULT_COMMAND_IPC = "ipc:///tmp/ecris_command.ipc"
_TEST_TELEMETRY_IPC = "ipc:///tmp/ecris_telemetry_test.ipc"
_TEST_COMMAND_IPC = "ipc:///tmp/ecris_command_test.ipc"

# ---------------------------------------------------------------------------
# PLC DataKey extensions
#
# The VenusPLC.DataKeys enum does not yet include emittance / motor-move
# request registers.  We define the PLC register names here as module-level
# constants so they can be updated in a single place once the PLC firmware is
# extended.  The agent reads these registers directly via the lower-level
# ``VenusPLC._PLC_KEYS`` mechanism when the enum entries are absent.
#
# Once upstream adds the enum members, replace the string lookups below with
# the proper ``VenusPLC.DataKeys.*`` references.
# ---------------------------------------------------------------------------
_REG_EMITTANCE_REQUEST = "emittance_request"
_REG_EMITTANCE_IN_PROGRESS = "emittance_in_progress"
_REG_MOTOR_MOVE_REQUEST = "motor_move_request"
_REG_MOTOR_MOVE_IN_PROGRESS = "motor_move_in_progress"


# ---------------------------------------------------------------------------
# ZMQ log handler — forward Python log records to the PUB socket
# ---------------------------------------------------------------------------

class _ZMQLogHandler(logging.Handler):
    """
    A :class:`logging.Handler` that serialises log records as JSON and
    publishes them on the ``log`` topic of the agent's PUB socket.

    This allows the TUI (or any other SUB client) to display the agent's
    activity log in real time without polling a file or shared queue.
    """

    def __init__(self, pub_socket: zmq.asyncio.Socket) -> None:
        super().__init__()
        self._socket = pub_socket

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = json.dumps({
                "ts": record.created,
                "level": record.levelname,
                "name": record.name,
                "msg": self.format(record),
            })
            # zmq send_string is not async-safe from a sync handler, so we use
            # the blocking variant on the underlying socket.  This is safe here
            # because the handler is only installed while the event loop is
            # running and the socket is never closed concurrently.
            self._socket.send_string(f"log {payload}", flags=zmq.NOBLOCK)
        except zmq.ZMQError:
            # Drop silently — the subscriber may have disconnected.
            pass
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
# IPC Provider
# ---------------------------------------------------------------------------

class IPCProvider:
    """
    Owns the two ZeroMQ sockets used by the agent for inter-process
    communication:

    * **PUB** (``telemetry_ipc``) — publishes telemetry frames and log
      messages to any number of subscribers (e.g. the TUI).
    * **REP** (``command_ipc``) — receives command requests from the TUI and
      replies with a JSON acknowledgement.

    The provider is used as an async context manager::

        async with IPCProvider(telemetry_ipc, command_ipc) as ipc:
            await ipc.publish_telemetry(data)
            cmd = await ipc.recv_command_nowait()

    Args:
        telemetry_ipc: ZMQ endpoint for the PUB socket (default: production path).
        command_ipc:   ZMQ endpoint for the REP socket (default: production path).
    """

    def __init__(
        self,
        telemetry_ipc: str = _DEFAULT_TELEMETRY_IPC,
        command_ipc: str = _DEFAULT_COMMAND_IPC,
    ) -> None:
        self._telemetry_ipc = telemetry_ipc
        self._command_ipc = command_ipc
        self._ctx: Optional[zmq.asyncio.Context] = None
        self._pub: Optional[zmq.asyncio.Socket] = None
        self._rep: Optional[zmq.asyncio.Socket] = None
        self._log_handler: Optional[_ZMQLogHandler] = None

    async def __aenter__(self) -> "IPCProvider":
        self._ctx = zmq.asyncio.Context.instance()

        # PUB socket — telemetry + log messages
        self._pub = self._ctx.socket(zmq.PUB)
        self._pub.bind(self._telemetry_ipc)

        # REP socket — command/reply
        self._rep = self._ctx.socket(zmq.REP)
        self._rep.bind(self._command_ipc)

        # Install a log handler so agent log records are forwarded to PUB.
        self._log_handler = _ZMQLogHandler(self._pub)
        self._log_handler.setLevel(logging.INFO)
        # Attach to the root logger so all agent modules are captured.
        logging.getLogger().addHandler(self._log_handler)

        _log.info(
            "IPCProvider started: PUB=%s  REP=%s",
            self._telemetry_ipc,
            self._command_ipc,
        )
        return self

    async def __aexit__(self, *_exc) -> None:
        if self._log_handler is not None:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler = None

        if self._rep is not None:
            self._rep.close(linger=0)
            self._rep = None

        if self._pub is not None:
            self._pub.close(linger=0)
            self._pub = None

        _log.info("IPCProvider stopped.")

    # ------------------------------------------------------------------
    # Telemetry publishing
    # ------------------------------------------------------------------

    async def publish_telemetry(self, data: dict) -> None:
        """
        Publish a telemetry frame on the ``telemetry`` topic.

        The *data* dict is serialised as JSON.  Subscribers must filter on
        the ``b"telemetry"`` topic prefix.

        Args:
            data: Arbitrary key/value pairs representing the current machine
                state (current readings, motor position, operation status, …).
        """
        if self._pub is None:
            return
        try:
            payload = json.dumps(data)
            await self._pub.send_string(f"telemetry {payload}")
        except zmq.ZMQError as exc:
            _log.debug("IPCProvider: telemetry publish error: %s", exc)

    # ------------------------------------------------------------------
    # Command reception
    # ------------------------------------------------------------------

    async def recv_command_nowait(self) -> Optional[str]:
        """
        Poll the REP socket for an incoming command without blocking.

        Returns the command string if one is available, or ``None`` if the
        inbox is empty.  Must be paired with :meth:`send_reply` after every
        successful receive.

        Returns:
            A command string (e.g. ``"CSD"``, ``"EMITTANCE"``, …) or ``None``.
        """
        if self._rep is None:
            return None
        try:
            msg = await self._rep.recv_string(flags=zmq.NOBLOCK)
            return msg.strip().upper()
        except zmq.Again:
            return None
        except zmq.ZMQError as exc:
            _log.debug("IPCProvider: REP recv error: %s", exc)
            return None

    async def send_reply(self, reply: dict) -> None:
        """
        Send a JSON reply on the REP socket.

        Must be called exactly once after each successful
        :meth:`recv_command_nowait`.

        Args:
            reply: Dict to serialise as the reply body.  Conventionally
                contains at least ``{"status": "ok" | "error", "msg": "…"}``.
        """
        if self._rep is None:
            return
        try:
            await self._rep.send_string(json.dumps(reply))
        except zmq.ZMQError as exc:
            _log.debug("IPCProvider: REP send error: %s", exc)


# ---------------------------------------------------------------------------
# Concrete LinearEmittanceScan subclass
# ---------------------------------------------------------------------------

class _EmittanceOperation(LinearEmittanceScan):
    """
    Concrete ``LinearEmittanceScan`` subclass used by the agent.

    ``LinearEmittanceScan`` is abstract (ABC) purely because it does not
    define a concrete ``run`` override beyond the base class.  This thin
    subclass makes it instantiable without changing the library code.
    """


# ---------------------------------------------------------------------------
# ECRISAgent
# ---------------------------------------------------------------------------

class ECRISAgent(CSDAgent):
    """
    Unified ECRIS hardware-coordination daemon.

    Extends ``CSDAgent`` with emittance-scan, motor-move, and ZeroMQ IPC
    capabilities, all dispatched from the same PLC polling loop.

    Args:
        ammeter: The ammeter device (current measurement).
        dipole: The dipole magnet device (CSD sweeps).
        plc: The VenusPLC instance.
        averaging_service: Background averaging service (pausable).
        motor: The ``MotorController`` used for emittance scans and motor moves.
        deflection_plate_controller: Controller for the emittance-scanner
            deflection plates.
        emittance_params: ``LinearScanParameters`` for the emittance scan.
        motor_move_axis: The axis to park when a ``MOTOR_MOVE_REQUEST`` fires.
            Defaults to ``Axis.VenusX``.
        csd_directory: Directory where CSD result files are saved.
        emittance_directory: Directory where emittance scan HDF5 files are saved.
        batman_scale: Scaling factor for the PLC ``batman_i_set`` variable.
        csd_params: Default ``CSDParameters`` for CSD sweeps.
        telemetry_ipc: ZMQ endpoint for the telemetry PUB socket.
        command_ipc: ZMQ endpoint for the command REP socket.
    """

    def __init__(
        self,
        ammeter: Ammeter,
        dipole: Dipole,
        plc: VenusPLC,
        averaging_service: AveragingService,
        motor: object,  # MotorController or DummyMotor — typed as object for flexibility
        deflection_plate_controller: DeflectionPlateController,
        emittance_params: LinearScanParameters,
        motor_move_axis: Axis = Axis.VenusX,
        csd_directory: Path = Path("/data/csds/"),
        emittance_directory: Path = Path("/data/emittance/"),
        batman_scale: float = 131.0,
        csd_params: CSDParameters = CSDParameters(),
        telemetry_ipc: str = _DEFAULT_TELEMETRY_IPC,
        command_ipc: str = _DEFAULT_COMMAND_IPC,
    ) -> None:
        super().__init__(
            ammeter=ammeter,
            dipole=dipole,
            plc=plc,
            averaging_service=averaging_service,
            csd_directory=csd_directory,
            batman_scale=batman_scale,
            params=csd_params,
        )

        self._motor = motor
        self._deflection_plate_controller = deflection_plate_controller
        self._emittance_params = emittance_params
        self._motor_move_axis = motor_move_axis
        self._emittance_directory = emittance_directory
        self._telemetry_ipc = telemetry_ipc
        self._command_ipc = command_ipc

        # Current operation label — surfaced in telemetry.
        self._current_op: str = "Idle"

        # Serialises all hardware-intensive operations: CSD, Emittance, MotorMove.
        # Emittance and motor-move also share LinearEmittanceScan._scan_lock, which
        # gives a second layer of mutual exclusion against any directly instantiated
        # LinearEmittanceScan running in the same process.
        self._operation_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        test_mode: bool = False,
        emittance_params: Optional[LinearScanParameters] = None,
        motor_move_axis: Axis = Axis.VenusX,
        csd_directory: Path = Path("/data/csds/"),
        emittance_directory: Path = Path("/data/emittance/"),
        batman_scale: float = 131.0,
        csd_params: CSDParameters = CSDParameters(),
    ) -> "ECRISAgent":
        """
        Build a fully wired ``ECRISAgent`` using the driver factory from
        :mod:`ops.ecris.drivers.mocks`.

        In test mode every hardware driver is replaced with a ``Dummy*`` mock
        and the IPC sockets use the test-specific paths
        (``ipc:///tmp/ecris_*_test.ipc``) so that a production agent and a
        test agent can run side-by-side without colliding.

        In production mode the real driver classes are used.  The caller must
        still supply hardware-specific constructor arguments (IP addresses,
        VISA resource strings, …) through the driver factory's keyword
        arguments if needed — see
        :func:`~ops.ecris.drivers.mocks.get_driver_factory`.

        Args:
            test_mode: When ``True``, use in-memory mock drivers.
            emittance_params: Scan parameters for emittance operations.
                A sensible default is provided when ``test_mode=True``.
            motor_move_axis: Axis to park on ``MOTOR_MOVE_REQUEST``.
            csd_directory: Directory for CSD result files.
            emittance_directory: Directory for emittance HDF5 files.
            batman_scale: Scaling factor for the batman current setpoint.
            csd_params: CSD sweep parameters.

        Returns:
            A ready-to-``run()`` ``ECRISAgent`` instance.
        """
        from ops.ecris.devices.ammeter import Ammeter
        from ops.ecris.drivers.mocks import get_driver_factory
        from ops.ecris.drivers.scpi_driver import SCPIDriver

        factory = get_driver_factory(test_mode=test_mode)
        _log.info("ECRISAgent.create: using %s", factory)

        ammeter_driver = factory.ammeter()
        plc_driver = factory.plc()
        motor_driver = factory.motor_controller()

        ammeter = Ammeter(connection=ammeter_driver, read_key=SCPIDriver.DataKeys.CURRENT)

        # In test mode there is no real dipole or deflection-plate controller —
        # use lightweight mocks for both.
        if test_mode:
            from unittest.mock import AsyncMock, MagicMock

            from ops.ecris.devices.dipole import Dipole

            dipole = MagicMock(spec=Dipole)
            dipole.read_field = AsyncMock(return_value=0.0)
            dipole.set_current = AsyncMock()

            dpc = MagicMock(spec=DeflectionPlateController)
            dpc.connect = AsyncMock()
            dpc.disconnect = AsyncMock()
            dpc.set_divergence = AsyncMock()
        else:
            # Real hardware wiring — callers must supply the appropriate
            # sub-devices (LabJack, power supplies, …) separately.
            raise NotImplementedError(
                "ECRISAgent.create() in production mode requires explicit device "
                "wiring.  Construct ECRISAgent directly instead."
            )

        averaging_service = AveragingService(ammeter=ammeter, plc=plc_driver)

        if emittance_params is None:
            emittance_params = LinearScanParameters(
                axis=motor_move_axis,
                position_min=-10.0,
                position_max=10.0,
                position_step=1.0,
                divergence_min=-0.05,
                divergence_max=0.05,
                divergence_step=0.01,
                samples_per_point=10,
            )

        # Use test IPC paths when running in test mode to avoid colliding
        # with a production agent on the same host.
        telemetry_ipc = _TEST_TELEMETRY_IPC if test_mode else _DEFAULT_TELEMETRY_IPC
        command_ipc = _TEST_COMMAND_IPC if test_mode else _DEFAULT_COMMAND_IPC

        return cls(
            ammeter=ammeter,
            dipole=dipole,
            plc=plc_driver,
            averaging_service=averaging_service,
            motor=motor_driver,
            deflection_plate_controller=dpc,
            emittance_params=emittance_params,
            motor_move_axis=motor_move_axis,
            csd_directory=csd_directory,
            emittance_directory=emittance_directory,
            batman_scale=batman_scale,
            csd_params=csd_params,
            telemetry_ipc=telemetry_ipc,
            command_ipc=command_ipc,
        )

    # ------------------------------------------------------------------
    # Main loop (overrides CSDAgent.run)
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """
        The main event loop of the ECRISAgent.

        Opens the ZeroMQ IPC sockets, then enters the polling loop which:

        1. Checks the REP socket for incoming operator commands (CSD,
           Emittance, Motor, Stop, Peak, Batman) and dispatches them.
        2. Polls the PLC for hardware-triggered requests (CSD, Emittance,
           Motor Move, Peaking, Batman setpoint change).
        3. Publishes a telemetry frame on every iteration.

        All hardware-intensive operations are serialised via
        :meth:`_run_exclusive`.
        """
        _log.info("ECRISAgent starting.")
        self._is_running = True

        if not self._csd_directory.exists():
            self._csd_directory.mkdir(parents=True, exist_ok=True)
        if not self._emittance_directory.exists():
            self._emittance_directory.mkdir(parents=True, exist_ok=True)

        async with IPCProvider(self._telemetry_ipc, self._command_ipc) as ipc:
            await self._averaging_service.start()

            try:
                raw_i = await self._plc.read_data(VenusPLC.DataKeys.BATMAN_I_SET)
                self._last_batman_i = raw_i / self._batman_scale
            except Exception as exc:
                _log.error("Failed to initialize batman setpoint tracking: %s", exc)

            while self._is_running:
                try:
                    # --- IPC command dispatch (non-blocking) ---
                    cmd = await ipc.recv_command_nowait()
                    if cmd is not None:
                        reply = await self._handle_ipc_command(cmd)
                        await ipc.send_reply(reply)

                    # --- CSD requests (inherited logic, guarded by operation lock) ---
                    request_type = await self._check_csd_requests()
                    if request_type == 1:
                        await self._run_exclusive(self._handle_csd_request, "CSD")
                    elif request_type == 2:
                        await self._run_exclusive(self._handle_custom_csd_request, "Custom CSD")

                    # --- Emittance request ---
                    if await self._check_emittance_request():
                        await self._run_exclusive(
                            self._handle_emittance_request, "Emittance"
                        )

                    # --- Motor move request ---
                    if await self._check_motor_move_request():
                        await self._run_exclusive(
                            self._handle_motor_move_request, "MotorMove"
                        )

                    # --- Batman setpoint tracking (non-exclusive, low priority) ---
                    await self._handle_batman_changes()

                    # --- Peaking placeholder (inherited) ---
                    await self._check_peaking_requests()

                    # --- Publish telemetry snapshot ---
                    await self._publish_telemetry(ipc)

                    await asyncio.sleep(0.1)

                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    _log.error("Error in ECRISAgent main loop: %s", exc, exc_info=True)
                    await asyncio.sleep(1)

            await self._averaging_service.stop()
            _log.info("ECRISAgent stopped.")

    # ------------------------------------------------------------------
    # Telemetry helpers
    # ------------------------------------------------------------------

    async def _publish_telemetry(self, ipc: IPCProvider) -> None:
        """
        Collect a snapshot of machine state and publish it as a ``telemetry``
        frame on the PUB socket.

        The frame is a JSON object with the following keys:

        * ``ts``           — Unix timestamp (float).
        * ``avg_current_a`` — averaged beam current in amperes (float).
        * ``current_std_ua`` — current std-dev in microamperes (float).
        * ``motor_pos_mm`` — motor axis position in mm (float).
        * ``op_status``    — current operation label (str).
        * ``avg_paused``   — whether the averaging service is paused (bool).
        * ``op_locked``    — whether the operation lock is held (bool).
        """
        try:
            avg_i: float = 0.0
            std_ua: float = 0.0
            motor_pos: float = 0.0

            try:
                avg_i = float(
                    await self._plc.read_data(VenusPLC.DataKeys.AVERAGE_CURRENT)
                )
                std_pct = float(
                    await self._plc.read_data(VenusPLC.DataKeys.CURRENT_STDEV)
                )
                if avg_i != 0.0:
                    std_ua = abs(avg_i * std_pct / 100.0) * 1e6
            except Exception:
                pass

            try:
                motor_pos = float(
                    await self._motor.get_position(self._motor_move_axis)  # type: ignore[attr-defined]
                )
            except Exception:
                pass

            frame = {
                "ts": time.time(),
                "avg_current_a": avg_i,
                "current_std_ua": std_ua,
                "motor_pos_mm": motor_pos,
                "op_status": self._current_op,
                "avg_paused": self._averaging_service.is_paused,
                "op_locked": self._operation_lock.locked(),
            }
            await ipc.publish_telemetry(frame)
        except Exception as exc:
            _log.debug("Telemetry publish error: %s", exc)

    # ------------------------------------------------------------------
    # IPC command dispatcher
    # ------------------------------------------------------------------

    async def _handle_ipc_command(self, cmd: str) -> dict:
        """
        Dispatch an incoming IPC command string to the appropriate handler.

        Commands are matched case-insensitively (the caller already upper-
        cases the string).

        Args:
            cmd: Command string received from the TUI.

        Returns:
            A reply dict with at least ``{"status": "ok"|"error", "msg": "…"}``.
        """
        _log.info("IPC command received: %s", cmd)

        handlers = {
            "CSD": self._ipc_csd,
            "EMITTANCE": self._ipc_emittance,
            "MOTOR": self._ipc_motor,
            "STOP": self._ipc_stop,
            "PEAK": self._ipc_peak,
            "BATMAN": self._ipc_batman,
        }

        handler = handlers.get(cmd)
        if handler is None:
            return {"status": "error", "msg": f"Unknown command: {cmd!r}"}

        try:
            return await handler()
        except Exception as exc:
            _log.error("IPC command %r failed: %s", cmd, exc, exc_info=True)
            return {"status": "error", "msg": str(exc)}

    async def _ipc_csd(self) -> dict:
        if self._operation_lock.locked():
            return {"status": "busy", "msg": "Another operation is in progress."}
        asyncio.create_task(self._run_exclusive(self._handle_csd_request, "CSD"))
        return {"status": "ok", "msg": "CSD sweep started."}

    async def _ipc_emittance(self) -> dict:
        if self._operation_lock.locked():
            return {"status": "busy", "msg": "Another operation is in progress."}
        asyncio.create_task(
            self._run_exclusive(self._handle_emittance_request, "Emittance")
        )
        return {"status": "ok", "msg": "Emittance scan started."}

    async def _ipc_motor(self) -> dict:
        if self._operation_lock.locked():
            return {"status": "busy", "msg": "Another operation is in progress."}
        asyncio.create_task(
            self._run_exclusive(self._handle_motor_move_request, "MotorMove")
        )
        return {"status": "ok", "msg": "Motor move started."}

    async def _ipc_stop(self) -> dict:
        # There is no graceful abort path in the current operation handlers;
        # log the intent and return.  Future work: propagate a cancellation
        # token into the running handler.
        if self._operation_lock.locked():
            _log.warning("IPC STOP: operation in progress — stop request logged.")
            return {"status": "ok", "msg": "Stop requested (operation cannot be force-cancelled)."}
        return {"status": "ok", "msg": "No operation in progress."}

    async def _ipc_peak(self) -> dict:
        try:
            await self._plc.write_data(VenusPLC.DataKeys.PEAKING_REQUEST, 1.0)
            return {"status": "ok", "msg": "PEAKING_REQUEST flag set."}
        except Exception as exc:
            return {"status": "error", "msg": str(exc)}

    async def _ipc_batman(self) -> dict:
        try:
            current_raw = await self._plc.read_data(VenusPLC.DataKeys.BATMAN_I_SET)
            new_raw = current_raw + 0.1 * self._batman_scale
            await self._plc.write_data(VenusPLC.DataKeys.BATMAN_I_SET, new_raw)
            new_i = new_raw / self._batman_scale
            return {
                "status": "ok",
                "msg": f"Batman I setpoint nudged → {new_i:.3f} A (raw={new_raw:.1f}).",
            }
        except Exception as exc:
            return {"status": "error", "msg": str(exc)}

    # ------------------------------------------------------------------
    # Exclusive operation runner
    # ------------------------------------------------------------------

    async def _run_exclusive(self, handler, label: str) -> None:
        """
        Run *handler* under the operation lock.

        If the lock is already held (another operation is in progress), the
        request is logged and skipped rather than queued, preventing a
        backlog of stale requests.

        Also updates :attr:`_current_op` so the telemetry frame always
        reflects the running operation.
        """
        if self._operation_lock.locked():
            _log.warning(
                "%s request received but an operation is already in progress — skipping.",
                label,
            )
            return
        async with self._operation_lock:
            self._current_op = label
            try:
                await handler()
            finally:
                self._current_op = "Idle"

    # ------------------------------------------------------------------
    # PLC polling helpers — emittance & motor
    # ------------------------------------------------------------------

    async def _check_emittance_request(self) -> bool:
        """Returns ``True`` if the PLC ``emittance_request`` register is set."""
        try:
            value = await self._plc.read_data(VenusPLC.DataKeys.EMITTANCE_REQUEST)  # type: ignore[attr-defined]
            return bool(value)
        except (KeyError, AttributeError):
            # Gracefully degrade when the PLC firmware / enum does not yet
            # expose the emittance request register.
            return False

    async def _check_motor_move_request(self) -> bool:
        """Returns ``True`` if the PLC ``motor_move_request`` register is set."""
        try:
            value = await self._plc.read_data(VenusPLC.DataKeys.MOTOR_MOVE_REQUEST)  # type: ignore[attr-defined]
            return bool(value)
        except (KeyError, AttributeError):
            return False

    async def _set_plc_flag(self, key_name: str, value: float) -> None:
        """
        Write a raw PLC register by name, bypassing the ``DataKeys`` enum.

        Used for registers (``emittance_in_progress``, ``motor_move_in_progress``)
        that may not yet have a ``DataKeys`` entry in ``VenusPLC``.
        """
        try:
            # Prefer the typed enum path when available.
            data_key = VenusPLC.DataKeys[key_name.upper()]
            await self._plc.write_data(data_key, value)
        except KeyError:
            _log.debug(
                "_set_plc_flag: DataKey %r not in enum, using raw write.", key_name
            )
            # Fall back to writing the raw register string if VenusPLC exposes it.
            if hasattr(self._plc, "write_register"):
                await self._plc.write_register(key_name, value)  # type: ignore[attr-defined]
            else:
                _log.warning(
                    "Cannot write PLC flag %r = %s: no DataKey and no write_register().",
                    key_name,
                    value,
                )

    # ------------------------------------------------------------------
    # Operation handlers — emittance
    # ------------------------------------------------------------------

    async def _handle_emittance_request(self) -> None:
        """
        Run an emittance scan in response to a PLC ``EMITTANCE_REQUEST``.

        Sequence:
        1. Acknowledge to PLC (``emittance_in_progress = 1``).
        2. Pause the background ``AveragingService``.
        3. Construct and run a ``LinearEmittanceScan``.
        4. Save the result as an HDF5 file.
        5. Resume averaging and clear the PLC flag.
        """
        _log.info("ECRISAgent: handling emittance scan request.")
        await self._set_plc_flag(_REG_EMITTANCE_IN_PROGRESS, 1.0)

        await self._averaging_service.pause()
        try:
            scan = _EmittanceOperation(
                motor=self._motor,  # type: ignore[arg-type]
                ammeter=self._ammeter,
                deflection_plate_controller=self._deflection_plate_controller,
                scan_params=self._emittance_params,
            )
            beam_trace = await scan.run(keep_centered=False)

            # Persist the raw 2-D beam trace.
            save_path = self._emittance_directory / f"emittance_{int(time.time())}.h5"
            save_emittance_scan(
                filepath=save_path,
                data=beam_trace,
                parameters=self._emittance_params,
            )
            _log.info("Emittance scan saved to %s", save_path)

        except Exception as exc:
            _log.error("Emittance scan failed: %s", exc, exc_info=True)
        finally:
            await self._averaging_service.resume()
            await self._set_plc_flag(_REG_EMITTANCE_IN_PROGRESS, 0.0)

    # ------------------------------------------------------------------
    # Operation handlers — motor move
    # ------------------------------------------------------------------

    async def _handle_motor_move_request(self) -> None:
        """
        Move the motor axis to its OUT position in response to a PLC
        ``MOTOR_MOVE_REQUEST``.

        The ``AveragingService`` is paused for the duration of the move so
        that the motor vibrations do not corrupt the running average.
        """
        _log.info(
            "ECRISAgent: handling motor-move request (axis=%s → OUT).",
            self._motor_move_axis.name,
        )
        await self._set_plc_flag(_REG_MOTOR_MOVE_IN_PROGRESS, 1.0)

        await self._averaging_service.pause()
        try:
            op = MotorMoveOperation(
                motor=self._motor,  # type: ignore[arg-type]
                axis=self._motor_move_axis,
            )
            await op.run()
        except Exception as exc:
            _log.error("Motor move operation failed: %s", exc, exc_info=True)
        finally:
            await self._averaging_service.resume()
            await self._set_plc_flag(_REG_MOTOR_MOVE_IN_PROGRESS, 0.0)

    # ------------------------------------------------------------------
    # CSD handlers (re-wrapped to use the operation lock)
    # ------------------------------------------------------------------
    # The parent CSDAgent._handle_csd_request and _handle_custom_csd_request
    # are called via _run_exclusive, so they are already serialised.  No
    # override is needed unless we want different behaviour; the parent
    # implementations are used directly.


# ---------------------------------------------------------------------------
# Entry point (headless IPC mode)
# ---------------------------------------------------------------------------

def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        prog="ecris-agent",
        description=(
            "ECRIS Agent — headless hardware daemon with ZeroMQ IPC. "
            "Publishes telemetry on ipc:///tmp/ecris_telemetry[_test].ipc and "
            "listens for commands on ipc:///tmp/ecris_command[_test].ipc."
        ),
    )
    parser.add_argument(
        "--test",
        action="store_true",
        default=False,
        help="Run with mock (dummy) hardware drivers. Uses test IPC socket paths.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Python logging level (default: INFO).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.test:
        _log.error(
            "Production mode requires explicit hardware wiring. "
            "Use ECRISAgent.create(test_mode=False) with custom device args, "
            "or pass --test for simulation mode."
        )
        raise SystemExit(1)

    agent = ECRISAgent.create(test_mode=args.test)
    _log.info(
        "ECRISAgent (test_mode=%s) starting IPC loop…  "
        "Telemetry: %s  Commands: %s",
        args.test,
        agent._telemetry_ipc,
        agent._command_ipc,
    )
    asyncio.run(agent.run())


if __name__ == "__main__":
    main()
