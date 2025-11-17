from typing import Any
from enum import Enum, auto

from .base import DataSource


class ConstantDataSource(DataSource):
    """
    A dummy driver that acts as a simple, controllable data source for testing.

    This class implements the DataSource interface but does not connect to any
    real hardware. It holds values in memory that can be set and read, making

    it an ideal "fake" object for unit tests or for running the application
    without live hardware.
    """

    class DataKeys(Enum):
        READ_VALUE = auto()
        SET_VALUE = auto()

    def __init__(self, initial_read_value: float = 0.0, name: str = "DummySource"):
        """
        Initializes the dummy data source.

        :param initial_read_value: The starting value this source will return when read.
        :param name: An optional name for logging or identification.
        """
        self._read_value = initial_read_value
        # The writable value starts at 0.0 unless configured otherwise.
        self._set_value = 0.0
        self.name = name

    async def read_data(self, data_key: DataKeys) -> float:
        """Reads a value from the fake in-memory source."""
        match data_key:
            case ConstantDataSource.DataKeys.READ_VALUE:
                return self._read_value
            case ConstantDataSource.DataKeys.SET_VALUE:
                # Allows a test to verify what was last written.
                return self._set_value
            case _:
                raise KeyError(f"Read operation for data_key {data_key.name} not implemented")

    async def write_data(self, data_key: DataKeys, value: float) -> None:
        """Writes a value to the fake in-memory source."""
        match data_key:
            case ConstantDataSource.DataKeys.SET_VALUE:
                self._set_value = value
            case _:
                raise KeyError(f"Write operation for data_key {data_key} not implemented")
