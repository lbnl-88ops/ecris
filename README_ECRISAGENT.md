# ECRIS Agent

The ECRIS Agent is a background service and interactive TUI application responsible for managing core components of the ECRIS system.

## Responsibilities
The agent handles and orchestrates the following subsystems:
- **CSD (Charge State Distribution):** Monitoring and controlling the charge state parameters.
- **Emittance:** Handling emittance scans and measurements.
- **Motor:** Controlling physical motor movements and positioning.
- **Averaging:** Managing data averaging and smoothing for sensor readouts.

---

## Architecture — ZeroMQ IPC

The ECRIS Agent and TUI communicate over **ZeroMQ IPC sockets**, decoupling the
hardware daemon from the operator interface. This allows the agent to run as a
persistent background service while multiple TUI instances (or other clients)
connect on demand.

```
┌─────────────────────────────────────────────┐
│              ECRISAgent (daemon)             │
│                                             │
│  PLC polling ──► operation dispatch         │
│  AveragingService (background task)         │
│                                             │
│  PUB  ipc:///tmp/ecris_telemetry.ipc  ──────┼──► TUI SUB (telemetry + logs)
│  REP  ipc:///tmp/ecris_command.ipc    ◄─────┼──── TUI REQ (commands)
└─────────────────────────────────────────────┘
```

### PUB/SUB — Telemetry & Logs

The agent publishes on two topics:

| Topic       | Payload | Description |
|-------------|---------|-------------|
| `telemetry` | JSON    | Live machine state: beam current, motor position, op status, averaging pause flag. |
| `log`       | JSON    | Structured log records from all agent modules forwarded to the activity log. |

### REQ/REP — Commands

The TUI sends a command string; the agent replies with a JSON acknowledgement.

| Command     | Effect |
|-------------|--------|
| `CSD`       | Trigger a standard CSD sweep. |
| `EMITTANCE` | Trigger an emittance scan. |
| `MOTOR`     | Move the probe motor axis to OUT (park). |
| `STOP`      | Request abort of the current operation. |
| `PEAK`      | Set the PLC `PEAKING_REQUEST` flag. |
| `BATMAN`    | Nudge the batman current setpoint by +0.1 A (diagnostic). |

Reply format: `{"status": "ok" | "busy" | "error", "msg": "<description>"}`

### Socket Paths

| Mode        | Telemetry (PUB)                            | Commands (REP)                           |
|-------------|--------------------------------------------|------------------------------------------|
| Production  | `ipc:///tmp/ecris_telemetry.ipc`           | `ipc:///tmp/ecris_command.ipc`           |
| Test (`--test`) | `ipc:///tmp/ecris_telemetry_test.ipc` | `ipc:///tmp/ecris_command_test.ipc`      |

---

## Running Manually

### Start the Agent (headless IPC mode)

```bash
# Production hardware (not yet wired — see ecris_agent.py ECRISAgent.create())
python -m ops.ecris.agents.ecris_agent

# Test / simulation mode (mock drivers, test IPC paths)
python -m ops.ecris.agents.ecris_agent --test
```

### Start the TUI

**IPC mode (default)** — connect to a separately running agent:

```bash
# Production (connects to ipc:///tmp/ecris_telemetry.ipc)
python -m ops.ecris.agents.ecris_tui

# Test (connects to ipc:///tmp/ecris_telemetry_test.ipc)
python -m ops.ecris.agents.ecris_tui --test
```

**Standalone mode** — run agent and TUI in a single process (legacy behaviour,
useful for demos or single-terminal setups):

```bash
python -m ops.ecris.agents.ecris_tui --standalone
python -m ops.ecris.agents.ecris_tui --standalone --test
```

### Typical Test Workflow (two terminals)

```
# Terminal 1 — start the agent
python -m ops.ecris.agents.ecris_agent --test

# Terminal 2 — start the TUI
python -m ops.ecris.agents.ecris_tui --test
```

---

## Systemd Service (Headless Mode)

The agent is designed to run in headless mode as a background systemd service for continuous operation. A sample service file is provided in `deploy/ecris-agent.service`.

### Installation and Starting the Service

1. **Copy the service file to the systemd directory:**
   ```bash
   sudo cp deploy/ecris-agent.service /etc/systemd/system/
   ```

2. **Reload the systemd daemon:**
   ```bash
   sudo systemctl daemon-reload
   ```

3. **Enable the service to start automatically on boot:**
   ```bash
   sudo systemctl enable ecris-agent.service
   ```

4. **Start the service:**
   ```bash
   sudo systemctl start ecris-agent.service
   ```

5. **Check the status and logs:**
   ```bash
   sudo systemctl status ecris-agent.service
   journalctl -u ecris-agent.service -f
   ```

6. **Connect the TUI to the running service:**
   ```bash
   python -m ops.ecris.agents.ecris_tui
   ```

---

## Key Bindings (TUI)

| Key | Action              |
|-----|---------------------|
| `q` | Quit the application |
| `c` | Start a CSD sweep   |
| `e` | Start an Emittance scan |
| `m` | Move motor OUT (park probe) |
