from logging import getLogger
from ipaddress import ip_address, IPv4Address

from .device import DataDevice, TelnetDevice

_log = getLogger(__name__)

class Ammeter(TelnetDevice):
    def __init__(self, 
                 ip: str | IPv4Address | None, 
                 port: int | None):
        super().__init__()
        if ip is not None:
            self.ip = ip
        if port is not None:
            self.port = port

    def connect(self) -> None | RuntimeError:
        if self.ip is None and self.port is None:
            raise RuntimeError('Cannot connect ammeter, ip address and port not set')
        _log.info(f'Connecting to ammeter at {self.ip}:{self.port}')

