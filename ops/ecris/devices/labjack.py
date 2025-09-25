import asyncio
from enum import Enum, auto
from logging import getLogger
from typing import Any

from labjack import ljm

from ops.ecris.model.device import Device

_log = getLogger(__name__)

class LabJack(Device):
    HALL_PROBE_CALIBRATION = 0.4

    class DataKeys(Enum):
        B_FIELD = auto()

    def __init__(self) -> None:
        self._connection_lock = asyncio.Lock()
        self._handle: int | None = None

    @property
    def is_connected(self) -> bool:
        """Returns True if the device handle is open."""
        return self._handle is not None

    async def connect(self) -> None:
        """Opens a connection to the LabJack device."""
        async with self._connection_lock:
            if self.is_connected:
                _log.debug('LabJack is already connected')
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

    async def write_data(self, data_key: Any, value: float) -> None:
        pass

    async def get_data(self, data_key: DataKeys) -> float:
        match(data_key):
            case LabJack.DataKeys.B_FIELD:
                b_value = await asyncio.to_thread(ljm.eReadName, self._handle, "AIN0")
                return b_value * LabJack.HALL_PROBE_CALIBRATION
        raise KeyError(f'Read operation for data_Key {data_key.name} not implemented')

