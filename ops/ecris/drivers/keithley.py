import asyncio
from logging import getLogger

from .base import SessionDriver
from .scpi_driver import SCPIDriver
from .telnet_driver import TelnetDriver
from .visa_driver import VISADriver

_log = getLogger(__name__)

ID: str = "Keithley DMM7512"


class Keithley(SCPIDriver):
    """
    Driver for Keithley DMM7512 digital multimeters.

    This class extends SCPIDriver with specific handshake and setup routines
    tailored for Keithley instruments.
    """

    def __init__(
        self,
        sample_frequency_hz: float,
        connection: SessionDriver,
        id: str = ID,
        command_echo: bool = False,
    ):
        super().__init__(
            sample_frequency_hz=sample_frequency_hz,
            connection=connection,
            id=id,
            command_echo=command_echo,
        )

    @classmethod
    def connect_at_ip(
        cls,
        ip: str,
        port: int,
        prompt: str | None = None,
        id: str = ID,
        sample_frequency_hz: float = 60.0,
        command_echo: bool = False,
        **kwargs,
    ):
        telnet_driver = TelnetDriver(id=id, ip=ip, port=port, prompt=prompt)
        return cls(
            sample_frequency_hz=sample_frequency_hz,
            connection=telnet_driver,
            id=id,
            command_echo=command_echo,
            **kwargs,
        )

    @classmethod
    def connect_at_usb(
        cls,
        resource_name: str,
        id: str = ID,
        sample_frequency_hz: float = 60.0,
        command_echo: bool = False,
        **kwargs,
    ):
        visa_driver = VISADriver(resource_name, id=id)
        return cls(
            sample_frequency_hz=sample_frequency_hz,
            connection=visa_driver,
            id=id,
            command_echo=command_echo,
            **kwargs,
        )

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
            SCPIDriver.Commands.CURRENT_DELAY_DISABLE,
            SCPIDriver.Commands.SET_NPLC.format(self.nplc_setting),
        ]
        for command in setup_commands:
            print(f"sending command {command}")
            await self.send_silent_command(command)
        await asyncio.sleep(5)
        _log.debug("Setup complete.")
