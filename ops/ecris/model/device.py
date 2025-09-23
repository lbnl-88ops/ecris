from abc import ABC, abstractmethod
from typing import Dict, List, Type
from ipaddress import IPv6Address, ip_address, IPv4Address

class TelnetDevice(ABC):
    def __init__(self):
        self._ip = None
        self._port = None

    @property
    def ip(self) -> IPv6Address | IPv4Address | None:
        return self._ip

    @ip.setter
    def ip(self, to_set: str | IPv4Address) -> None:
        if isinstance(to_set, IPv4Address):
            self._ip = to_set
        else:
            self._ip = ip_address(to_set)

class DataDevice(ABC):
    @abstractmethod
    def get_data() -> Dict:
        pass

    @property
    def data_types(self) -> Dict[str, Type]:
        raise NotImplementedError

    @property
    def data_keys(self) -> List[str]:
        raise NotImplementedError