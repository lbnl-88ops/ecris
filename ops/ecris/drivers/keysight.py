import asyncio
from logging import getLogger

from .scpi_driver import SCPIDriver

_log = getLogger(__name__)


class Keysight(SCPIDriver):
    """
    Driver for Keysight B2900A series source measure units (SMUs).

    This class extends SCPIDriver with specific handshake and setup routines
    tailored for Keysight instruments.
    """

    def __init__(
        self,
        sample_frequency_hz: float,
        ip: str | None = None,
        port: int | None = None,
        resource_name: str | None = None,
        prompt: str | None = "B2900A>",
        id: str = "KeySight B2900A",
    ):
        super().__init__(
            sample_frequency_hz, ip, port, resource_name, prompt, id, command_echo=True
        )

    async def _handshake(self) -> None:
        response = await self._read_until(self._prompt if self._prompt else "\n")
        _log.info(f"Successfully connected: {response}.")
        return

    async def _setup(self) -> None:
        await self.reset()
        _log.debug(f"Setting up {self.id} at {self._host}...")
        await asyncio.sleep(2)
        setup_commands = [
            SCPIDriver.Commands.CURRENT_FUNCTION,
            SCPIDriver.Commands.CURRENT_AUTO_RANGE,
            SCPIDriver.Commands.CURRENT_NPLC_AUTO_OFF,
            SCPIDriver.Commands.SET_NPLC.format(self.nplc_setting),
            SCPIDriver.Commands.INPUT_ON,
        ]
        for command in setup_commands:
            await self.send_command(command)
