"""
ECRIS TUI — Textual Terminal User Interface for the ECRIS Agent.

A real-time operator dashboard that connects to a running
:class:`~ops.ecris.agents.ecris_agent.ECRISAgent` via **ZeroMQ IPC** sockets
and displays live beam-current data, operation status, motor position, and an
activity log in a single terminal window.

Usage
-----
**IPC mode (default)** — connect to a separately-running agent::

    python -m ops.ecris.agents.ecris_tui

**IPC test mode** — connect to a test-mode agent (different socket paths)::

    python -m ops.ecris.agents.ecris_tui --test

**Standalone mode** — run the agent *inside* the TUI process (legacy behaviour,
no external agent required)::

    python -m ops.ecris.agents.ecris_tui --standalone
    python -m ops.ecris.agents.ecris_tui --standalone --test

Key bindings
~~~~~~~~~~~~
=====  ============================
Key    Action
=====  ============================
``q``  Quit the application
``c``  Start a CSD sweep
``e``  Start an Emittance scan
``m``  Move motor OUT (park probe)
=====  ============================

Architecture
~~~~~~~~~~~~
**IPC mode** (default):

    The :class:`ECRISApp` opens two ZMQ sockets:

    * **SUB** → ``ipc:///tmp/ecris_telemetry[_test].ipc`` — receives telemetry
      frames (current, motor pos, op status) and log messages from the agent.
    * **REQ** → ``ipc:///tmp/ecris_command[_test].ipc`` — sends operator
      commands (CSD, Emittance, Motor, Stop, Peak, Batman) and receives replies.

    A single background worker reads from both sockets every 250 ms and pushes
    reactive updates to the UI widgets.  Buttons are disabled while a command
    is awaiting its REP reply so the socket is never in an inconsistent state.

**Standalone mode** (``--standalone``):

    Behaves like the original TUI — the :class:`ECRISAgent` is created
    in-process and run in a Textual worker.  Telemetry is polled directly from
    the agent's internal state (no ZMQ sockets).  Useful for single-terminal
    demos or environments where running a separate agent process is impractical.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Footer, Header, Label, RichLog

if TYPE_CHECKING:
    from ops.ecris.agents.ecris_agent import ECRISAgent

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
_log = logging.getLogger(__name__)

# IPC socket paths (mirrored from ecris_agent.py)
_DEFAULT_TELEMETRY_IPC = "ipc:///tmp/ecris_telemetry.ipc"
_DEFAULT_COMMAND_IPC = "ipc:///tmp/ecris_command.ipc"
_TEST_TELEMETRY_IPC = "ipc:///tmp/ecris_telemetry_test.ipc"
_TEST_COMMAND_IPC = "ipc:///tmp/ecris_command_test.ipc"


# ---------------------------------------------------------------------------
# Styling constants
# ---------------------------------------------------------------------------
_CSS = """
/* ── Root ────────────────────────────────────────────────────────────────── */
Screen {
    background: #0d0d1a;
    layout: vertical;
}

/* ── Header strip ─────────────────────────────────────────────────────────── */
Header {
    background: #1a1a3e;
    color: #a8d8ff;
    text-style: bold;
}

Footer {
    background: #1a1a3e;
    color: #6e88a8;
}

/* ── Main grid ────────────────────────────────────────────────────────────── */
#main-grid {
    layout: horizontal;
    height: 1fr;
    margin: 1 2;
}

/* ── Left column  (panels) ────────────────────────────────────────────────── */
#left-column {
    layout: vertical;
    width: 45;
    margin-right: 1;
}

/* Right-column children get a small top margin for spacing */
#left-column > * {
    margin-bottom: 1;
}

/* ── Right column (log) ───────────────────────────────────────────────────── */
#right-column {
    layout: vertical;
    width: 1fr;
}

/* ── Generic panel card ───────────────────────────────────────────────────── */
.panel {
    border: round #2a2a5a;
    background: #111128;
    padding: 0 1;
}

.panel-title {
    color: #6a9fdf;
    text-style: bold;
    padding: 0 0;
    margin-bottom: 1;
    border-bottom: solid #2a2a5a;
}

/* ── Live data rows ───────────────────────────────────────────────────────── */
.data-row {
    layout: horizontal;
    height: 1;
    margin: 0 0;
}

.data-label {
    color: #7090b8;
    width: 20;
}

.data-value {
    color: #d0f0ff;
    text-style: bold;
    width: 1fr;
}

.data-value.ok    { color: #50e0a0; }
.data-value.warn  { color: #f0c030; }
.data-value.error { color: #ff5050; }
.data-value.idle  { color: #7090b8; }

/* ── Status indicator ─────────────────────────────────────────────────────── */
#agent-status {
    color: #50e0a0;
    text-style: bold;
}

#agent-status.stopped { color: #ff5050; }
#agent-status.paused  { color: #f0c030; }

/* ── Operation status ─────────────────────────────────────────────────────── */
#op-status-value {
    color: #50e0a0;
    text-style: bold;
}

#op-status-value.busy { color: #f0c030; }
#op-status-value.error { color: #ff5050; }

/* ── Control buttons ──────────────────────────────────────────────────────── */
#controls-panel {
    height: auto;
}

.btn-row {
    layout: horizontal;
    height: 3;
    margin-top: 1;
}

.btn-row > Button {
    margin-right: 1;
}

Button {
    min-width: 12;
    height: 3;
}

Button.btn-csd      { background: #1a3a6a; border: tall #2a6aaa; color: #a8d8ff; }
Button.btn-emittance { background: #1a4a2a; border: tall #2a9a5a; color: #a0f0c0; }
Button.btn-motor    { background: #3a2a0a; border: tall #9a7a1a; color: #f0d080; }
Button.btn-peak     { background: #3a1a3a; border: tall #8a3a8a; color: #f0a0f0; }
Button.btn-batman   { background: #3a1a1a; border: tall #9a3a3a; color: #f0a0a0; }
Button.btn-stop     { background: #4a1010; border: tall #cc3333; color: #ffaaaa; }

Button:hover { opacity: 0.8; }
Button:focus { border: tall #ffffff; }
Button.-disabled { opacity: 0.4; }

/* ── Activity log ─────────────────────────────────────────────────────────── */
#log-panel {
    height: 1fr;
}

#activity-log {
    height: 1fr;
    background: #0a0a18;
    border: none;
    scrollbar-color: #2a2a5a;
}
"""


# ---------------------------------------------------------------------------
# Helper widgets
# ---------------------------------------------------------------------------

class DataRow(Widget):
    """A single labelled data row inside a panel."""

    DEFAULT_CSS = """
    DataRow {
        layout: horizontal;
        height: 1;
    }
    """

    def __init__(self, label: str, widget_id: str, initial: str = "—", **kw) -> None:
        super().__init__(**kw)
        self._label_text = label
        self._widget_id = widget_id
        self._initial = initial

    def compose(self) -> ComposeResult:
        yield Label(self._label_text, classes="data-label")
        yield Label(self._initial, id=self._widget_id, classes="data-value")


class SectionPanel(Widget):
    """A titled panel card."""

    DEFAULT_CSS = """
    SectionPanel {
        border: round #2a2a5a;
        background: #111128;
        padding: 0 1;
        height: auto;
    }
    """

    def __init__(self, title: str, *children: Widget, **kw) -> None:
        super().__init__(**kw)
        self._title = title
        self._children = children

    def compose(self) -> ComposeResult:
        yield Label(f" {self._title} ", classes="panel-title")
        yield from self._children


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class ECRISApp(App[None]):
    """
    Textual TUI for the ECRIS project.

    In **IPC mode** (default) it connects to a separately running
    :class:`~ops.ecris.agents.ecris_agent.ECRISAgent` via ZeroMQ sockets,
    displaying live telemetry and forwarding button presses as commands.

    In **standalone mode** (``--standalone``) it hosts the agent in a
    background Textual worker and polls its internal state directly — no
    external process required.
    """

    TITLE = "ECRIS Control Dashboard"
    CSS = _CSS
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("c", "start_csd", "CSD Sweep"),
        Binding("e", "start_emittance", "Emittance"),
        Binding("m", "motor_out", "Motor OUT"),
    ]

    # ── Reactive state ────────────────────────────────────────────────────────
    agent_running: reactive[bool] = reactive(False)
    current_ua: reactive[float] = reactive(0.0)
    current_std: reactive[float] = reactive(0.0)
    plc_avg_current: reactive[float] = reactive(0.0)
    plc_status: reactive[str] = reactive("—")
    motor_position: reactive[float] = reactive(0.0)
    op_status: reactive[str] = reactive("Idle")
    averaging_paused: reactive[bool] = reactive(False)
    clock_str: reactive[str] = reactive("")
    ipc_connected: reactive[bool] = reactive(False)

    def __init__(
        self,
        test_mode: bool = False,
        standalone: bool = False,
        **kw,
    ) -> None:
        super().__init__(**kw)
        self._test_mode = test_mode
        self._standalone = standalone

        # Choose socket paths based on mode.
        self._telemetry_ipc = _TEST_TELEMETRY_IPC if test_mode else _DEFAULT_TELEMETRY_IPC
        self._command_ipc = _TEST_COMMAND_IPC if test_mode else _DEFAULT_COMMAND_IPC

        # Standalone-mode state.
        self._agent: Optional[ECRISAgent] = None

        # IPC mode: one pending command at a time (REQ/REP is strictly serial).
        self._cmd_lock: asyncio.Lock = asyncio.Lock()

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="main-grid"):
            # Left column — live data + controls
            with Vertical(id="left-column"):

                # ── Agent status banner ──────────────────────────────────────
                with Container(classes="panel", id="status-panel"):
                    yield Label(" ◈ Agent Status ", classes="panel-title")
                    with Horizontal(classes="data-row"):
                        yield Label("Agent:", classes="data-label")
                        yield Label("● Connecting…", id="agent-status", classes="data-value")
                    with Horizontal(classes="data-row"):
                        yield Label("Mode:", classes="data-label")
                        yield Label(
                            ("TEST (mock)" if self._test_mode else "PRODUCTION")
                            + (" [standalone]" if self._standalone else " [IPC]"),
                            id="mode-label",
                            classes="data-value warn" if self._test_mode else "data-value ok",
                        )
                    with Horizontal(classes="data-row"):
                        yield Label("Time:", classes="data-label")
                        yield Label("—", id="clock-label", classes="data-value idle")

                # ── Current data ─────────────────────────────────────────────
                with Container(classes="panel", id="current-panel"):
                    yield Label(" ⚡ Current Data ", classes="panel-title")
                    with Horizontal(classes="data-row"):
                        yield Label("Ammeter (μA):", classes="data-label")
                        yield Label("—", id="ammeter-ua", classes="data-value ok")
                    with Horizontal(classes="data-row"):
                        yield Label("Std Dev (μA):", classes="data-label")
                        yield Label("—", id="ammeter-std", classes="data-value")
                    with Horizontal(classes="data-row"):
                        yield Label("PLC Avg (μA):", classes="data-label")
                        yield Label("—", id="plc-avg", classes="data-value")
                    with Horizontal(classes="data-row"):
                        yield Label("Averaging:", classes="data-label")
                        yield Label("Active", id="avg-status", classes="data-value ok")

                # ── Operation status ─────────────────────────────────────────
                with Container(classes="panel", id="op-panel"):
                    yield Label(" ⟳ Operation Status ", classes="panel-title")
                    with Horizontal(classes="data-row"):
                        yield Label("Current Op:", classes="data-label")
                        yield Label("Idle", id="op-status-value", classes="data-value ok")
                    with Horizontal(classes="data-row"):
                        yield Label("Op Lock:", classes="data-label")
                        yield Label("Free", id="op-lock-status", classes="data-value ok")

                # ── Motor position ───────────────────────────────────────────
                with Container(classes="panel", id="motor-panel"):
                    yield Label(" ↔ Motor Position ", classes="panel-title")
                    with Horizontal(classes="data-row"):
                        yield Label("Axis (VenusX):", classes="data-label")
                        yield Label("— mm", id="motor-pos", classes="data-value")

                # ── Controls ─────────────────────────────────────────────────
                with Container(classes="panel", id="controls-panel"):
                    yield Label(" ⌨ Manual Controls ", classes="panel-title")
                    with Horizontal(classes="btn-row"):
                        yield Button("◈ CSD [c]", id="btn-csd",
                                     classes="btn-csd", tooltip="Start a CSD sweep")
                        yield Button("⟳ Emittance [e]", id="btn-emittance",
                                     classes="btn-emittance", tooltip="Start an emittance scan")
                    with Horizontal(classes="btn-row"):
                        yield Button("↔ Motor OUT [m]", id="btn-motor",
                                     classes="btn-motor", tooltip="Move motor to OUT (park probe)")
                        yield Button("⊗ Stop Op", id="btn-stop",
                                     classes="btn-stop", tooltip="Abort current operation")
                    with Horizontal(classes="btn-row"):
                        yield Button("⚡ Peak", id="btn-peak",
                                     classes="btn-peak", tooltip="Trigger Peak current change")
                        yield Button("⚡ Batman", id="btn-batman",
                                     classes="btn-batman",
                                     tooltip="Trigger Batman setpoint change")

            # Right column — activity log
            with Vertical(id="right-column"):
                with Container(classes="panel", id="log-panel"):
                    yield Label(" ☰ Activity Log ", classes="panel-title")
                    yield RichLog(id="activity-log", markup=True, highlight=True,
                                  wrap=False, auto_scroll=True)

        yield Footer()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        """Wire up workers depending on operating mode."""
        if self._standalone:
            self._build_agent()
            self._start_agent_worker()
            self._poll_telemetry_standalone()
        else:
            # IPC mode: start the ZMQ subscriber + command worker.
            self._poll_ipc()

        self._tick_clock()
        self._log("info", "ECRIS TUI started.")
        if self._test_mode:
            self._log("warn", "Running in TEST mode — mock drivers active, no hardware required.")
        if self._standalone:
            self._log("info", "Standalone mode — agent running in-process.")
        else:
            self._log("info", f"IPC mode — connecting to agent on {self._telemetry_ipc}")

    # ── Standalone helpers ────────────────────────────────────────────────────

    def _build_agent(self) -> None:
        """Construct the ECRISAgent (real or mock) for standalone mode."""
        try:
            from ops.ecris.agents.ecris_agent import ECRISAgent
            self._agent = ECRISAgent.create(test_mode=self._test_mode)
            _log.info("ECRISAgent created (test_mode=%s).", self._test_mode)
        except Exception as exc:
            self._log("error", f"Failed to create ECRISAgent: {exc}")
            _log.exception("ECRISAgent creation failed")
            self._agent = None

    @work(name="ecris-agent", group="agent", exit_on_error=False)
    async def _start_agent_worker(self) -> None:
        """Run the ECRISAgent event loop in a background Textual worker (standalone only)."""
        if self._agent is None:
            self._log("error", "Cannot start agent — no ECRISAgent instance.")
            return

        self.agent_running = True
        self._refresh_agent_status()
        self._log("info", "ECRISAgent worker started.")
        try:
            await self._agent.run()
        except asyncio.CancelledError:
            self._log("info", "ECRISAgent worker cancelled.")
        except Exception as exc:
            self._log("error", f"ECRISAgent worker error: {exc}")
            _log.exception("ECRISAgent worker raised")
        finally:
            self.agent_running = False
            self._refresh_agent_status()
            self._log("warn", "ECRISAgent worker has stopped.")

    @work(name="telemetry-poll-standalone", group="telemetry", exit_on_error=False)
    async def _poll_telemetry_standalone(self) -> None:
        """
        Standalone-mode telemetry: poll the in-process agent's state every 250 ms.
        """
        from ops.ecris.devices.motor_controller_specification import Axis
        from ops.ecris.drivers.venus_plc import VenusPLC

        while True:
            await asyncio.sleep(0.25)
            if self._agent is None:
                continue

            try:
                avg_svc = getattr(self._agent, "_averaging_service", None)
                plc = getattr(self._agent, "_plc", None)
                motor = getattr(self._agent, "_motor", None)

                if avg_svc is not None:
                    self.averaging_paused = avg_svc.is_paused

                if plc is not None:
                    try:
                        avg_i = await plc.read_data(VenusPLC.DataKeys.AVERAGE_CURRENT)
                        std_pct = await plc.read_data(VenusPLC.DataKeys.CURRENT_STDEV)
                        self.plc_avg_current = float(avg_i)
                        if avg_i and avg_i != 0:
                            self.current_std = abs(avg_i * std_pct / 100.0) * 1e6
                        else:
                            self.current_std = 0.0
                        self.current_ua = float(avg_i) * 1e6
                        self.plc_status = "OK"
                    except Exception:
                        self.plc_status = "Read error"

                if motor is not None:
                    try:
                        pos = await motor.get_position(Axis.VenusX)
                        self.motor_position = float(pos)
                    except Exception:
                        pass

                op_status = getattr(self._agent, "_current_op", "Idle")
                self.op_status = op_status

                op_lock = getattr(self._agent, "_operation_lock", None)
                if op_lock is not None:
                    self._update_op_lock_display(op_lock.locked())

            except asyncio.CancelledError:
                break
            except Exception as exc:
                _log.debug("Standalone telemetry poll error: %s", exc)

    # ── IPC workers ───────────────────────────────────────────────────────────

    @work(name="ipc-poll", group="telemetry", exit_on_error=False)
    async def _poll_ipc(self) -> None:
        """
        IPC mode: open ZMQ SUB + REQ sockets and receive telemetry/log frames.

        This worker runs continuously, draining the SUB socket on every
        iteration and forwarding telemetry values to reactive attributes and
        log messages to the activity log.
        """
        try:
            import zmq
            import zmq.asyncio
        except ImportError:
            self._log("error", "pyzmq is not installed — IPC mode unavailable. "
                               "Install it with: pip install pyzmq")
            self.agent_running = False
            self._refresh_agent_status()
            return

        ctx = zmq.asyncio.Context.instance()

        # SUB socket — receives telemetry + log topics.
        sub = ctx.socket(zmq.SUB)
        sub.connect(self._telemetry_ipc)
        sub.setsockopt_string(zmq.SUBSCRIBE, "telemetry")
        sub.setsockopt_string(zmq.SUBSCRIBE, "log")

        self._log("info", f"SUB socket connected to {self._telemetry_ipc}")

        # Give the agent a moment to bind before we start polling.
        await asyncio.sleep(0.5)

        try:
            while True:
                await asyncio.sleep(0.05)  # ~20 Hz drain loop

                # Drain all pending frames (non-blocking).
                while True:
                    try:
                        raw = await sub.recv_string(flags=zmq.NOBLOCK)
                        await self._handle_ipc_frame(raw)
                    except zmq.Again:
                        break
                    except zmq.ZMQError as exc:
                        _log.debug("SUB recv error: %s", exc)
                        break

        except asyncio.CancelledError:
            pass
        finally:
            sub.close(linger=0)
            self._log("warn", "IPC telemetry socket closed.")

    async def _handle_ipc_frame(self, raw: str) -> None:
        """
        Parse a raw topic-prefixed frame from the SUB socket and dispatch it.

        Frame format: ``"<topic> <json-payload>"``
        """
        try:
            topic, _, payload_str = raw.partition(" ")
            data = json.loads(payload_str)

            if topic == "telemetry":
                await self._apply_telemetry(data)
            elif topic == "log":
                self._apply_log(data)
        except Exception as exc:
            _log.debug("IPC frame parse error: %s  raw=%r", exc, raw[:120])

    async def _apply_telemetry(self, data: dict) -> None:
        """Update reactive attributes from a telemetry frame dict."""
        try:
            avg_a: float = float(data.get("avg_current_a", 0.0))
            self.plc_avg_current = avg_a
            self.current_ua = avg_a * 1e6
            self.current_std = float(data.get("current_std_ua", 0.0))
            self.motor_position = float(data.get("motor_pos_mm", 0.0))
            self.averaging_paused = bool(data.get("avg_paused", False))
            op_locked: bool = bool(data.get("op_locked", False))
            op_status: str = str(data.get("op_status", "Idle"))
            self.op_status = op_status
            self._update_op_lock_display(op_locked)

            # Mark the agent as running once we receive the first telemetry frame.
            if not self.agent_running:
                self.agent_running = True
                self._refresh_agent_status()
        except Exception as exc:
            _log.debug("apply_telemetry error: %s", exc)

    def _apply_log(self, data: dict) -> None:
        """Forward a log frame from the agent to the activity log widget."""
        try:
            level_name = str(data.get("level", "INFO")).upper()
            msg = str(data.get("msg", ""))
            ts_epoch = float(data.get("ts", 0.0))
            ts = datetime.fromtimestamp(ts_epoch).strftime("%H:%M:%S") if ts_epoch else "—"

            level_map = {
                "DEBUG": ("dim", "·"),
                "INFO": ("cyan", "ℹ"),
                "WARNING": ("yellow", "⚠"),
                "ERROR": ("red", "✖"),
                "CRITICAL": ("red bold", "✖"),
            }
            colour, icon = level_map.get(level_name, ("white", "·"))
            try:
                log_widget = self.query_one("#activity-log", RichLog)
                log_widget.write(
                    f"[dim]{ts}[/dim] [{colour}]{icon} {msg}[/{colour}]"
                )
            except NoMatches:
                pass
        except Exception as exc:
            _log.debug("apply_log error: %s", exc)

    # ── IPC command sender ────────────────────────────────────────────────────

    async def _send_ipc_command(self, cmd: str) -> dict:
        """
        Send *cmd* to the agent's REP socket and return the reply dict.

        Uses ``_cmd_lock`` to ensure only one outstanding REQ/REP cycle at a
        time (the ZMQ REQ socket is strictly request-then-reply).

        Args:
            cmd: Command string (e.g. ``"CSD"``, ``"EMITTANCE"``, …).

        Returns:
            Parsed reply dict from the agent, or an error dict if the send
            fails or times out.
        """
        try:
            import zmq
            import zmq.asyncio
        except ImportError:
            return {"status": "error", "msg": "pyzmq not installed."}

        async with self._cmd_lock:
            ctx = zmq.asyncio.Context.instance()
            req = ctx.socket(zmq.REQ)
            req.connect(self._command_ipc)
            # Linger=0 so the socket closes immediately even if the reply is lost.
            req.setsockopt(zmq.LINGER, 0)
            # RCVTIMEO: 3 s timeout so the TUI doesn't hang if the agent is busy.
            req.setsockopt(zmq.RCVTIMEO, 3000)
            try:
                await req.send_string(cmd)
                reply_str = await req.recv_string()
                return json.loads(reply_str)
            except zmq.Again:
                return {"status": "error", "msg": "Timeout — agent did not reply."}
            except zmq.ZMQError as exc:
                return {"status": "error", "msg": f"ZMQ error: {exc}"}
            except Exception as exc:
                return {"status": "error", "msg": str(exc)}
            finally:
                req.close(linger=0)

    async def _dispatch_command(self, cmd: str, label: str) -> None:
        """
        Send *cmd* over IPC (or invoke the standalone handler) and log the result.

        In standalone mode, invokes the agent handler directly instead of using
        the network sockets.

        Args:
            cmd:   Command string for the IPC socket.
            label: Human-readable label for log messages.
        """
        if self._standalone:
            # Standalone mode: call the agent directly.
            await self._dispatch_standalone(cmd, label)
            return

        self._log("info", f"{label} command sent → agent.")
        reply = await self._send_ipc_command(cmd)
        status = reply.get("status", "?")
        msg = reply.get("msg", "")
        if status == "ok":
            self._log("info", f"{label}: {msg}")
        elif status == "busy":
            self._log("warn", f"{label}: {msg}")
        else:
            self._log("error", f"{label} error: {msg}")

    async def _dispatch_standalone(self, cmd: str, label: str) -> None:
        """Standalone mode: invoke the relevant agent handler directly."""
        if self._agent is None:
            self._log("error", f"No agent — cannot {label}.")
            return

        op_lock = getattr(self._agent, "_operation_lock", None)
        if op_lock is not None and op_lock.locked():
            self._log("warn", f"{label}: another operation is already running — ignored.")
            return

        self._log("info", f"Manual {label} initiated (standalone).")
        try:
            handler_map = {
                "CSD": ("_handle_csd_request", "CSD"),
                "EMITTANCE": ("_handle_emittance_request", "Emittance"),
                "MOTOR": ("_handle_motor_move_request", "MotorMove"),
                "PEAK": None,
                "BATMAN": None,
                "STOP": None,
            }
            entry = handler_map.get(cmd.upper())
            if entry is None:
                # Special cases handled inline.
                if cmd.upper() == "STOP":
                    self._stop_current_operation()
                elif cmd.upper() == "PEAK":
                    await self._agent._ipc_peak()
                elif cmd.upper() == "BATMAN":
                    await self._agent._ipc_batman()
                return

            handler_name, exclusive_label = entry
            handler = getattr(self._agent, handler_name, None)
            if handler is not None:
                await self._agent._run_exclusive(handler, exclusive_label)
            self._log("info", f"{label} complete (standalone).")
        except Exception as exc:
            self._log("error", f"{label} failed: {exc}")

    # ── Worker: clock tick ────────────────────────────────────────────────────

    @work(name="clock-tick", group="clock", exit_on_error=False)
    async def _tick_clock(self) -> None:
        """Update the header clock every second."""
        while True:
            await asyncio.sleep(1.0)
            self.clock_str = datetime.now().strftime("%H:%M:%S")

    # ── Reactive watchers ─────────────────────────────────────────────────────

    def watch_clock_str(self, value: str) -> None:
        try:
            self.query_one("#clock-label", Label).update(value)
        except NoMatches:
            pass

    def watch_current_ua(self, value: float) -> None:
        try:
            lbl = self.query_one("#ammeter-ua", Label)
            lbl.update(f"{value:+.4f}")
            lbl.remove_class("ok", "warn", "error")
            lbl.add_class("ok" if abs(value) < 1000 else "warn")
        except NoMatches:
            pass

    def watch_current_std(self, value: float) -> None:
        try:
            self.query_one("#ammeter-std", Label).update(f"{value:.4f}")
        except NoMatches:
            pass

    def watch_plc_avg_current(self, value: float) -> None:
        try:
            ua = value * 1e6
            self.query_one("#plc-avg", Label).update(f"{ua:+.4f}")
        except NoMatches:
            pass

    def watch_plc_status(self, value: str) -> None:
        pass  # Surfaced in log; no dedicated label

    def watch_motor_position(self, value: float) -> None:
        try:
            lbl = self.query_one("#motor-pos", Label)
            lbl.update(f"{value:+.3f} mm")
        except NoMatches:
            pass

    def watch_op_status(self, value: str) -> None:
        try:
            lbl = self.query_one("#op-status-value", Label)
            lbl.update(value)
            lbl.remove_class("ok", "busy", "error", "idle")
            if value == "Idle":
                lbl.add_class("ok")
            elif "Error" in value or "Failed" in value:
                lbl.add_class("error")
            else:
                lbl.add_class("busy")
        except NoMatches:
            pass

    def watch_averaging_paused(self, paused: bool) -> None:
        try:
            lbl = self.query_one("#avg-status", Label)
            if paused:
                lbl.update("Paused")
                lbl.remove_class("ok")
                lbl.add_class("warn")
            else:
                lbl.update("Active")
                lbl.remove_class("warn")
                lbl.add_class("ok")
        except NoMatches:
            pass

    def watch_agent_running(self, running: bool) -> None:
        self._refresh_agent_status()

    def watch_ipc_connected(self, connected: bool) -> None:
        self._refresh_agent_status()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _refresh_agent_status(self) -> None:
        """Update the agent status label to reflect current connectivity."""
        try:
            lbl = self.query_one("#agent-status", Label)
            if self._standalone:
                if self.agent_running:
                    lbl.update("● Running (standalone)")
                    lbl.remove_class("stopped", "paused")
                else:
                    lbl.update("● Stopped")
                    lbl.remove_class("paused")
                    lbl.add_class("stopped")
            else:
                if self.agent_running:
                    lbl.update("● Connected (IPC)")
                    lbl.remove_class("stopped", "paused")
                else:
                    lbl.update("● Waiting for agent…")
                    lbl.remove_class("paused")
                    lbl.add_class("stopped")
        except NoMatches:
            pass

    def _update_op_lock_display(self, locked: bool) -> None:
        """Reflect the operation lock state in the UI."""
        try:
            lbl = self.query_one("#op-lock-status", Label)
            if locked:
                lbl.update("[yellow]Locked[/yellow]")
                lbl.remove_class("ok")
                lbl.add_class("warn")
            else:
                lbl.update("Free")
                lbl.remove_class("warn")
                lbl.add_class("ok")
        except NoMatches:
            pass

    def _log(self, level: str, message: str) -> None:
        """Write a timestamped entry to the RichLog widget."""
        ts = datetime.now().strftime("%H:%M:%S")
        colours = {"info": "cyan", "warn": "yellow", "error": "red"}
        colour = colours.get(level, "white")
        icon = {"info": "ℹ", "warn": "⚠", "error": "✖"}.get(level, "·")
        try:
            log_widget = self.query_one("#activity-log", RichLog)
            log_widget.write(
                f"[dim]{ts}[/dim] [{colour}]{icon} {message}[/{colour}]"
            )
        except NoMatches:
            pass
        getattr(_log, {"info": "info", "warn": "warning", "error": "error"}.get(level, "debug"))(
            message
        )

    # ── Action: manual operations ──────────────────────────────────────────────

    def action_start_csd(self) -> None:
        """Trigger a manual CSD sweep."""
        self._run_csd()

    def action_start_emittance(self) -> None:
        """Trigger a manual Emittance scan."""
        self._run_emittance()

    def action_motor_out(self) -> None:
        """Move the motor axis to its OUT (park) position."""
        self._run_motor_out()

    # ── Button handlers ───────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-csd")
    def on_btn_csd(self) -> None:
        self._run_csd()

    @on(Button.Pressed, "#btn-emittance")
    def on_btn_emittance(self) -> None:
        self._run_emittance()

    @on(Button.Pressed, "#btn-motor")
    def on_btn_motor_out(self) -> None:
        self._run_motor_out()

    @on(Button.Pressed, "#btn-stop")
    def on_btn_stop(self) -> None:
        self._stop_current_operation()

    @on(Button.Pressed, "#btn-peak")
    def on_btn_peak(self) -> None:
        self._run_peak()

    @on(Button.Pressed, "#btn-batman")
    def on_btn_batman(self) -> None:
        self._run_batman()

    # ── Workers: manual operations ────────────────────────────────────────────

    @work(name="manual-csd", group="manual-op", exclusive=True, exit_on_error=False)
    async def _run_csd(self) -> None:
        """Send a CSD command to the agent (IPC) or invoke directly (standalone)."""
        self.op_status = "CSD Running…"
        try:
            await self._dispatch_command("CSD", "CSD sweep")
        except Exception as exc:
            self._log("error", f"CSD sweep failed: {exc}")
            self.op_status = "CSD Failed"
            await asyncio.sleep(2)
        finally:
            # In IPC mode, the op_status is driven by telemetry; only reset it
            # in standalone mode where we control it directly.
            if self._standalone:
                self.op_status = "Idle"

    @work(name="manual-emittance", group="manual-op", exclusive=True, exit_on_error=False)
    async def _run_emittance(self) -> None:
        """Send an Emittance command to the agent (IPC) or invoke directly (standalone)."""
        self.op_status = "Emittance Running…"
        try:
            await self._dispatch_command("EMITTANCE", "Emittance scan")
        except Exception as exc:
            self._log("error", f"Emittance scan failed: {exc}")
            self.op_status = "Emittance Failed"
            await asyncio.sleep(2)
        finally:
            if self._standalone:
                self.op_status = "Idle"

    @work(name="manual-motor", group="manual-op", exclusive=True, exit_on_error=False)
    async def _run_motor_out(self) -> None:
        """Send a Motor OUT command to the agent (IPC) or invoke directly (standalone)."""
        self.op_status = "Motor Moving → OUT"
        try:
            await self._dispatch_command("MOTOR", "Motor move")
        except Exception as exc:
            self._log("error", f"Motor move failed: {exc}")
            self.op_status = "Motor Move Failed"
            await asyncio.sleep(2)
        finally:
            if self._standalone:
                self.op_status = "Idle"

    @work(name="manual-peak", group="manual-op", exclusive=True, exit_on_error=False)
    async def _run_peak(self) -> None:
        """Send a Peak request to the agent."""
        try:
            await self._dispatch_command("PEAK", "Peak request")
        except Exception as exc:
            self._log("error", f"Peak request failed: {exc}")

    @work(name="manual-batman", group="manual-op", exclusive=True, exit_on_error=False)
    async def _run_batman(self) -> None:
        """Send a Batman setpoint nudge to the agent."""
        try:
            await self._dispatch_command("BATMAN", "Batman setpoint nudge")
        except Exception as exc:
            self._log("error", f"Batman change failed: {exc}")

    def _stop_current_operation(self) -> None:
        """
        In standalone mode: cancel all running manual-op workers.
        In IPC mode: send STOP command to the agent.
        """
        if self._standalone:
            self._log("warn", "Stop requested — cancelling all manual-op workers.")
            self.workers.cancel_group(self, "manual-op")
            self.op_status = "Idle"
        else:
            self._run_stop_ipc()

    @work(name="manual-stop", group="manual-op", exit_on_error=False)
    async def _run_stop_ipc(self) -> None:
        """Send STOP command to the agent over IPC."""
        try:
            await self._dispatch_command("STOP", "Stop")
        except Exception as exc:
            self._log("error", f"Stop command failed: {exc}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ecris-tui",
        description=(
            "ECRIS Textual TUI — operator dashboard for the ECRIS agent.\n\n"
            "By default (IPC mode) it connects to a separately running ECRISAgent "
            "via ZeroMQ IPC sockets. Use --standalone to run the agent in-process."
        ),
    )
    parser.add_argument(
        "--test",
        action="store_true",
        default=False,
        help="Run in test/simulation mode with mock hardware drivers. "
             "In IPC mode this connects to the test socket paths. "
             "In standalone mode this uses dummy drivers.",
    )
    parser.add_argument(
        "--standalone",
        action="store_true",
        default=False,
        help="Run the ECRISAgent inside the TUI process (legacy behaviour). "
             "No external agent process is required.",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Python logging level (default: WARNING).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    app = ECRISApp(test_mode=args.test, standalone=args.standalone)
    app.run()


if __name__ == "__main__":
    main()
