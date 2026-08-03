import asyncio
from enum import Enum, auto
from logging import getLogger

from Phidget22.Devices.VoltageOutput import VoltageOutput

from ops.ecris.utilities.decorators import with_lock_named

from .base import SessionDriver

_log = getLogger(__name__)

class PhidgetVoltageOutput(SessionDriver):
    class DataKeys(Enum):
        VOLTAGE = auto()

    def __init__(self, serial_number: int, channel: int = 0) -> None:
        self._connection_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._connection: VoltageOutput | None = None
        self._serial_number = serial_number
        self._channel = channel

    @property
    def is_connected(self) -> bool:
        """Returns True if the device handle is open."""
        return self._connection is not None

    async def connect(self) -> None:
        """Opens a connection to the LabJack device."""
        async with self._connection_lock:
            if self.is_connected:
                _log.debug(f"Phidget voltage source {self._serial_number} is already connected")
                return

            _log.info(f"Connecting to phidget {self._serial_number}...")
            self._connection = VoltageOutput()
            self._connection.setDeviceSerialNumber(self._serial_number)
            self._connection.openWaitForAttachment(5000)
            self._connection.setChannel(self._channel)
            _log.info("Phidget connected.")

    async def disconnect(self) -> None:
        """Closes the connection to the LabJack device."""
        async with self._connection_lock:
            if not self.is_connected:
                _log.debug("Phidget is already disconnected.")
                return

            _log.info("Disconnecting from phidget...")
            self._connection.close()
            self._connection = None
            _log.info("Phidget disconnected.")

    @with_lock_named("_write_lock")
    async def write_data(self, data_key: DataKeys, value: float) -> None:
        if not self.is_connected:
            raise ConnectionError("Cannot write, phidget not connected.")
        # try:
        #     key = self._KEYS[data_key]
        # except KeyError:
        #     raise KeyError(f"Write operation for data_key {data_key.name} not implemented.")
        match data_key:
            case PhidgetVoltageOutput.DataKeys.VOLTAGE:
                self._connection.setVoltage(value)
        return

    async def read_data(self, data_key: DataKeys) -> float:
        raise NotImplementedError()
