import asyncio
import time
from logging import getLogger

import numpy as np

from ops.ecris.devices.ammeter import Ammeter
from ops.ecris.drivers.scpi_driver import SCPIDriver
from ops.ecris.drivers.venus_plc import VenusPLC

_log = getLogger(__name__)


class AveragingService:
    """
    Service that continuously polls an Ammeter and publishes averaged readings to a PLC.

    The service collects readings over a fixed time window (default 0.33s),
    calculates the mean and standard deviation percentage, and writes them to the
    configured PLC keys. It also handles periodic auto-zeroing of the ammeter.
    """

    def __init__(
        self,
        ammeter: Ammeter,
        plc: VenusPLC,
        window_seconds: float = 0.33,
        autozero_interval: float = 600.0,
    ):
        """
        Initializes the AveragingService.

        Args:
            ammeter: The Ammeter device to poll.
            plc: The VenusPLC to publish results to.
            window_seconds: The duration of the averaging window in seconds.
            autozero_interval: The interval between automatic auto-zero commands in seconds.
        """
        self._ammeter = ammeter
        self._plc = plc
        self._window_seconds = window_seconds
        self._autozero_interval = autozero_interval

        self._run_gate = asyncio.Event()
        self._run_gate.set()
        self._paused = False
        self._last_autozero = time.monotonic()
        self._task: asyncio.Task | None = None

    async def pause(self) -> None:
        """Pauses the averaging loop."""
        self._run_gate.clear()
        self._paused = True
        _log.info("AveragingService paused.")

    async def resume(self) -> None:
        """Resumes the averaging loop."""
        self._run_gate.set()
        self._paused = False
        _log.info("AveragingService resumed.")

    @property
    def is_paused(self) -> bool:
        """Returns True if the service is currently paused."""
        return self._paused

    async def start(self) -> None:
        """Starts the averaging service as a background task."""
        if self._task is None:
            self._task = asyncio.create_task(self.run())
            _log.info("AveragingService started.")

    async def stop(self) -> None:
        """Stops the averaging service."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            _log.info("AveragingService stopped.")

    async def run(self) -> None:
        """The main loop of the averaging service."""
        while True:
            try:
                # Wait until we are allowed to run
                await self._run_gate.wait()

                # Check for periodic autozero
                now = time.monotonic()
                if now - self._last_autozero > self._autozero_interval:
                    await self._perform_autozero()
                    self._last_autozero = now

                # Perform averaging window
                t_window_start = time.monotonic()
                readings = []
                while time.monotonic() - t_window_start < self._window_seconds:
                    # Break early if paused during the window
                    if not self._run_gate.is_set():
                        break

                    reading = await self._ammeter.read_current()
                    readings.append(reading)

                if readings:
                    iave = sum(readings) / len(readings)
                    isq = sum(r * r for r in readings) / len(readings)
                    istd = np.sqrt(max(0, isq - iave * iave))

                    # Publish to PLC
                    await self._plc.write_data(VenusPLC.DataKeys.AVERAGE_CURRENT, iave)
                    if iave == 0:
                        await self._plc.write_data(VenusPLC.DataKeys.CURRENT_STDEV, -2.0)
                    else:
                        # Match legacy std dev percentage: (std_dev / mean) * 100
                        await self._plc.write_data(
                            VenusPLC.DataKeys.CURRENT_STDEV, (istd / iave) * 100.0
                        )

                # Yield to other tasks
                await asyncio.sleep(0)

            except asyncio.CancelledError:
                break
            except Exception as e:
                _log.error(f"Error in AveragingService loop: {e}", exc_info=True)
                await asyncio.sleep(1)  # Sleep briefly before retrying

    async def _perform_autozero(self) -> None:
        """Sends a single auto-zero command to the ammeter."""
        _log.info("Performing scheduled auto-zero.")
        # Reach through the ammeter to the underlying driver if it supports SCPI commands
        connection = self._ammeter._connection
        if hasattr(connection, "send_silent_command"):
            await connection.send_silent_command(SCPIDriver.Commands.AUTOZERO_ONCE)
        else:
            _log.warning(
                "Ammeter connection does not support direct SCPI commands; skipping auto-zero."
            )
