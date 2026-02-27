import asyncio
from logging import getLogger

from .base import SessionDriver
from .scpi_driver import SCPIDriver
from .telnet_driver import TelnetDriver
from .visa_driver import VISADriver

_log = getLogger(__name__)

ID: str = "KeySight B2900A"
DEFAULT_PROMPT: str = "B2900A>"


class Keysight(SCPIDriver):
    """
    Driver for Keysight B2900A series source measure units (SMUs).

    This class extends SCPIDriver with specific handshake and setup routines
    tailored for Keysight instruments.
    """

    def __init__(
        self,
        sample_frequency_hz: float,
        connection: SessionDriver,
        id: str = ID,
        command_echo: bool = True,
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
        prompt: str | None = DEFAULT_PROMPT,
        id: str = ID,
        sample_frequency_hz: float = 60.0,
        command_echo: bool = True,
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
        command_echo: bool = True,
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
