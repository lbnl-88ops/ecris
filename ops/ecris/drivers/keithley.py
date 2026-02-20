import asyncio
from logging import getLogger

from .scpi_driver import SCPIDriver

_log = getLogger(__name__)

ID: str = "Keithley DMM7512"


class Keithley(SCPIDriver):
    def __init__(
        self,
        sample_frequency_hz: float,
        ip: str | None = None,
        port: int | None = None,
        prompt=None,
        id=ID,
    ):
        super().__init__(sample_frequency_hz, ip, port, prompt, id, command_echo=False)

    async def _handshake(self) -> None:
        await self.send_silent_command(SCPIDriver.Commands.SET_LANG)
        await self.send_silent_command(SCPIDriver.Commands.CLEAR_BUFFER)
        response = await self.send_command(SCPIDriver.Commands.TEST)
        if response != "0":
            response = await self.send_command("\n")
            if response != "0":
                raise ConnectionError(f"Handshake failed, response: {response}")
        response = await self.send_command(SCPIDriver.Commands.IDENTITY)
        if isinstance(response, list):
            response = " ".join(response)
        _log.info(f"Successfully connected to {response}.")
        return

    async def _setup(self) -> None:
        await self.reset()
        _log.debug(f"Setting up {self.id} at {self._host}...")
        await asyncio.sleep(2)
        setup_commands = [
            SCPIDriver.Commands.CURRENT_FUNCTION,
            SCPIDriver.Commands.CURRENT_AUTO_RANGE,
            SCPIDriver.Commands.SET_NPLC.format(self.nplc_setting),
        ]
        for command in setup_commands:
            print("sending command {command}")
            await self.send_silent_command(command)
        await asyncio.sleep(5)
        _log.debug(f"Setup complete.")
