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


class DeflectionPlateController:
    """
    A controller for the capacitor used a deflection plate in the emittance scanner.
    The main purpose of the class is to take the extraction voltage and the desired
    momentum and convert that into a voltage for the plates.
    """

    def __init__(
        self, extraction_voltmeter: Voltmeter, deflection_voltage_source: VoltageSource
    ) -> None:
        self._extraction_voltmeter = extraction_voltmeter
        self._deflection_voltage_source = deflection_voltage_source

    async def connect(self) -> None:
        await self._extraction_voltmeter.connect()
        await self._deflection_voltage_source.connect()

    async def _calculate_voltage(self, momentum: float) -> float:
        """Calculates the deflector voltage based on a target momentum.

        This coroutine reads the current extraction voltage and applies the
        standard formula to determine the required deflector plate voltage.

        :param momentum: The desired particle momentum in radians (rad).
        :type momentum: float
        :return: The calculated voltage to be applied to the plates in Volts (V).
        :rtype: float
        """
        v_extr = await self._extraction_voltmeter.read_voltage()
        return 2 * momentum * CAPACITOR_PLATE_DISTANCE_IN_M * v_extr / CAPACITOR_LENGTH_IN_M

    async def set_voltage(self, momentum: float) -> None:
        voltage_to_set = await self._calculate_voltage(momentum * 1e-3)
        await self._deflection_voltage_source.set_voltage(voltage_to_set)
