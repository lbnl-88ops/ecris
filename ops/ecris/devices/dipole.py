from ops.ecris.devices.power_supply import CurrentSource, Voltmeter


class Dipole:
    """
    Abstractions for the "Batman" analyzing dipole magnet.
    """

    def __init__(
        self,
        current_source: CurrentSource,
        hall_probe: Voltmeter,
    ):
        """
        Initializes the Dipole device.

        Args:
            current_source: The current source used to drive the magnet.
            hall_probe: The voltmeter used to read the Hall probe.
        """
        self._current_source = current_source
        self._hall_probe = hall_probe

    async def set_current(self, amps: float) -> None:
        """
        Sets the dipole magnet current.

        Args:
            amps: The target current in Amperes.
        """
        await self._current_source.set_current(amps)

    async def read_field(self) -> float:
        """
        Reads the magnetic field from the Hall probe.

        Returns:
            The magnetic field voltage from the Hall probe.
        """
        return await self._hall_probe.read_voltage()
