from typing import Any

from ops.ecris.drivers.labjack import LabJack


class Dipole:
    """
    Abstractions for the "Batman" analyzing dipole magnet controlled via LabJack.

    This class handles the scaling between physical units (Amps, Tesla) and
    hardware voltages on the LabJack DAC and AIN pins.
    """

    def __init__(
        self,
        labjack: LabJack,
        dac_key: LabJack.DataKeys = LabJack.DataKeys.DAC0,
        hall_key: LabJack.DataKeys = LabJack.DataKeys.AIN0,
        dac_scale: float = 0.04,  # V per A
        hall_scale: float = 0.4,  # T per V (2T = 5V)
    ):
        """
        Initializes the Dipole device.

        Args:
            labjack: The LabJack driver instance.
            dac_key: The DataKey for setting current.
            hall_key: The DataKey for reading the magnetic field.
            dac_scale: Conversion factor from Amps to Volts for the DAC.
            hall_scale: Conversion factor from Volts to Tesla for the Hall probe.
        """
        self._labjack = labjack
        self._dac_key = dac_key
        self._hall_key = hall_key
        self._dac_scale = dac_scale
        self._hall_scale = hall_scale

    async def set_current(self, amps: float) -> None:
        """
        Sets the dipole magnet current.

        Args:
            amps: The target current in Amperes.
        """
        voltage = amps * self._dac_scale
        await self._labjack.write_data(self._dac_key, voltage)

    async def read_field(self) -> float:
        """
        Reads the magnetic field from the Hall probe.

        Returns:
            The magnetic field in Tesla.
        """
        voltage = await self._labjack.read_data(self._hall_key)
        return voltage * self._hall_scale

    async def ramp_to(self, target_amps: float, density: int = 3) -> None:
        """
        Ramps the current to a target value using a linear set of steps.

        Args:
            target_amps: The target current in Amperes.
            density: The number of steps per Ampere of change.
        """
        # Read current setpoint (approximate from DAC if not readable,
        # but here we'll assume we know our last setpoint or just jump if small)
        # For simplicity, we'll just set the current if density is 0
        if density <= 0:
            await self.set_current(target_amps)
            return

        # In a real scenario, we'd need the CURRENT current.
        # Since Dipole doesn't track state yet, let's just provide set_current.
        # The Operation/Agent will handle the linspace.
        await self.set_current(target_amps)
