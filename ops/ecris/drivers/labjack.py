import asyncio
from enum import Enum, auto
from logging import getLogger
from typing import Any, Dict

from labjack import ljm

from ops.ecris.drivers.device import Device
from ops.ecris.utilities.decorators import with_lock_named
from ops.ecris.drivers.device_data import DeviceData

_log = getLogger(__name__)

LABJACK_DATA_DEFINITIONS = DeviceData(
    {
        # TODO: Ask Damon about these definitions
        "Beam line": [
            ("Batman electromagnet current", "A", "DAC0"),
            ("Batman electromagnet voltage", "V", "DAC1"),
            ("Batman electromagnet field", "G", "AIN0"),
        ]
    }
)


class LabJack(Device):
    class DataKeys(Enum):
        BATMAN_CURRENT = auto()
        BATMAN_VOLTAGE = auto()
        BATMAN_FIELD = auto()

    _KEYS: Dict[DataKeys, str] = {
        DataKeys.BATMAN_CURRENT: "DAC0",
        DataKeys.BATMAN_VOLTAGE: "DAC1",
        DataKeys.BATMAN_FIELD: "AIN0",
    }

    def __init__(self) -> None:
        self._connection_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._handle: int | None = None

    @property
    def is_connected(self) -> bool:
        """Returns True if the device handle is open."""
        return self._handle is not None

    async def connect(self) -> None:
        """Opens a connection to the LabJack device."""
        async with self._connection_lock:
            if self.is_connected:
                _log.debug("LabJack is already connected")
                return

            _log.info("Connecting to LabJack T8...")
            self._handle = await asyncio.to_thread(ljm.openS, "T8", "usb", "ANY")
            _log.info("LabJack connected.")

    async def disconnect(self) -> None:
        """Closes the connection to the LabJack device."""
        async with self._connection_lock:
            if not self.is_connected:
                _log.debug("LabJack is already disconnected.")
                return

            _log.info("Disconnecting from LabJack...")
            await asyncio.to_thread(ljm.close, self._handle)
            self._handle = None
            _log.info("LabJack disconnected.")

    @with_lock_named("_write_lock")
    async def write_data(self, data_key: DataKeys, value: float) -> None:
        if not self.is_connected:
            raise ConnectionError("Cannot write, LabJack not connected.")
        try:
            key = self._KEYS[data_key]
        except KeyError:
            raise KeyError(f"Write operation for data_key {data_key.name} not implemented.")
        await asyncio.to_thread(ljm.eWriteName, self._handle, key, value)
        return

    async def read_data(self, data_key: DataKeys) -> float:
        if not self.is_connected:
            raise ConnectionError("Cannot write, LabJack not connected.")
        try:
            key = self._KEYS[data_key]
        except KeyError:
            raise KeyError(f"Read operation for data_key {data_key.name} not implemented.")
        value = await asyncio.to_thread(ljm.eReadName, self._handle, key)
        return value
