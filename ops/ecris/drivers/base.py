from abc import ABC, abstractmethod
from logging import getLogger
from typing import Any

_log = getLogger(__name__)


class DataSource(ABC):
    """
    An abstract base class for a data source.
    """

    @abstractmethod
    async def read_data(self, data_key: Any) -> float:
        """
        Fetches a single data point from the device.
        Raises:
            KeyError: If the data_key is not supported for reading.
        """
        pass

    @abstractmethod
    async def write_data(self, data_key: Any, value: float) -> None:
        """
        Writes a single data value to the device.
        Raises:
            KeyError: If the data_key is not supported for writing.
        """
        pass


class Connectable(ABC):
    @property
    def is_connected(self) -> bool:
        raise NotImplementedError()

    @abstractmethod
    async def connect(self) -> None:
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        pass


class SessionDriver(Connectable, DataSource):
    pass
