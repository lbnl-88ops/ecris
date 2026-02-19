import asyncio
from logging import getLogger

from .scpi_driver import SCPIDriver

_log = getLogger(__name__)

ID: str = "Keithley DMM7512"


class Keithley(SCPIDriver):
    def __init__(
        self,
        read_frequency_per_min: float,
        ip: str | None = None,
        port: int | None = None,
        prompt=None,
        id=ID,
    ):
        super().__init__(read_frequency_per_min, ip, port, prompt, id, command_echo=False)

    async def _handshake(self) -> None:
        response = await self.send_command(SCPIDriver.Commands.TEST)
        if response != "0":
            raise ConnectionError(f"Handshake failed, response: {response}")
        response = await self.send_command(SCPIDriver.Commands.IDENTITY)
        _log.info(f"Successfully connected to {response}.")
        return

    async def _setup(self) -> None:
        await self.reset()
        _log.debug(f"Setting up {self.id} at {self._host}...")
        await asyncio.sleep(2)
        setup_commands = [
            SCPIDriver.Commands.SET_LANG,
            SCPIDriver.Commands.CURRENT_FUNCTION,
            SCPIDriver.Commands.CURRENT_AUTO_RANGE,
            SCPIDriver.Commands.CURRENT_NPLC_AUTO_OFF,
            SCPIDriver.Commands.SET_NPLC.format(self.nplc_setting),
            SCPIDriver.Commands.INPUT_ON,
        ]
        for command in setup_commands:
            await self.send_silent_command(command)
