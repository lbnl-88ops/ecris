from logging import getLogger

from .scpi_driver import SCPIDriver

_log = getLogger(__name__)


class Keysight(SCPIDriver):
    def __init__(
        self,
        read_frequency_per_min: float,
        ip: str | None = None,
        port: int | None = None,
        prompt: str = "B2900A>",
        id: str = "KeySight B2900A",
    ):
        super().__init__(read_frequency_per_min, ip, port, prompt, id)
