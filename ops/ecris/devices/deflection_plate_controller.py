from typing import Callable

from .power_supply import VoltageSource, Voltmeter

CAPACITOR_PLATE_DISTANCE_IN_M = 0.0189992  # 0.748"
CAPACITOR_LENGTH_IN_M = 0.1199896  # 4.724"

# Emmitance scanner capacitor length
# L and plate distance d
#
#  |<----------- L ----------->|
#  + + + + + + + + + + + + + + +
#  + + + + + + + + + + + + + + +  __
#                                  |
#                                  d
#                                  |
#  - - - - - - - - - - - - - - -  --
#  - - - - - - - - - - - - - - -


def LABJACK_DEFLECTION_PLATE_BIAS(unbiased_voltage: float) -> float:
    return unbiased_voltage / 100 + 3.188


class DeflectionPlateController:
    """
    A controller for the capacitor used as a deflection plate in the emittance scanner.
    The main purpose of the class is to take the extraction voltage and the desired
    divergence and convert that into a voltage for the plates.
    """

    def __init__(
        self, extraction_voltmeter: Voltmeter, deflection_voltage_source: VoltageSource
    ) -> None:
        self._extraction_voltmeter = extraction_voltmeter
        self._deflection_voltage_source = deflection_voltage_source

    async def connect(self) -> None:
        """Connects the underlying voltmeter and voltage source."""
        await self._extraction_voltmeter.connect()
        await self._deflection_voltage_source.connect()

    async def disconnect(self) -> None:
        """Disconnects the underlying voltmeter and voltage source."""
        await self._extraction_voltmeter.disconnect()
        await self._deflection_voltage_source.disconnect()

    async def _calculate_voltage(self, divergence: float) -> float:
        """Calculates the deflector voltage based on a target divergence.

        This coroutine reads the current extraction voltage and applies the
        standard formula to determine the required deflector plate voltage.

        :param divergence: The desired particle divergence in radians (rad).
        :type divergence: float
        :return: The calculated voltage to be applied to the plates in Volts (V).
        :rtype: float
        """
        v_extr = await self._extraction_voltmeter.read_voltage()
        return 2 * divergence * CAPACITOR_PLATE_DISTANCE_IN_M * v_extr / CAPACITOR_LENGTH_IN_M

    async def set_divergence(self, divergence: float) -> None:
        """
        Sets the deflection plates to a state corresponding to the desired divergence.

        :param divergence: The desired particle divergence in radians (rad).
        :type divergence: float
        """
        voltage_to_set = await self._calculate_voltage(divergence)
        await self._deflection_voltage_source.set_voltage(voltage_to_set)
