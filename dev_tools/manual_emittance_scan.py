# In: dev_tools/manual_scan.py
import asyncio
import logging
import argparse
import numpy as np
import time

from ops.ecris.drivers.labjack import LabJack
from ops.ecris.drivers.telnet_driver import TelnetDriver
from ops.ecris.drivers.venus_plc import VenusPLC, VENUSController

from ops.ecris.devices.motor_controller_specification import Axis
from ops.ecris.devices.motor_controller import MotorController
from ops.ecris.devices.ammeter import Ammeter, BiasedAmmeter, POSITIVE_VALUES_ONLY
from ops.ecris.devices.power_supply import Voltmeter, VoltageSource, BiasedVoltageSource
from ops.ecris.devices.deflection_plate_controller import (
    DeflectionPlateController,
    LABJACK_DEFLECTION_PLATE_BIAS,
)

from ops.ecris.operations.emittance_scan.base import LinearEmittanceScan
from ops.ecris.operations.emittance_scan.parameters import LinearScanParameters


# Set up basic logging to see the output from our scan classes
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
_log = logging.getLogger()


async def main(args):
    _log.info("--- Manual Emittance Scan Tool ---")

    _log.info("Assembling hardware drivers and logical devices...")

    # Drivers
    labjack_driver = LabJack()
    motor_driver = MotorController(ip="10.10.100.60", port=5024)
    venus_plc_driver = VenusPLC(VENUSController(read_only=True))

    # Devices
    scanner_ammeter = BiasedAmmeter(
        connection=labjack_driver,
        read_key=LabJack.DataKeys.AIN0,
        bias_function=POSITIVE_VALUES_ONLY,
    )

    deflector_v_source = BiasedVoltageSource(
        connection=labjack_driver,
        set_key=LabJack.DataKeys.DAC1,
        bias_function=LABJACK_DEFLECTION_PLATE_BIAS,
    )

    extraction_voltmeter = Voltmeter(
        connection=venus_plc_driver, read_key=VenusPLC.DataKeys.EXTRACTION_VOLTAGE
    )

    dpc = DeflectionPlateController(
        extraction_voltmeter=extraction_voltmeter,
        deflection_voltage_source=deflector_v_source,
    )

    scan_parameters = LinearScanParameters(
        axis=Axis.VenusX,
        position_min=-10,
        position_max=10,
        position_step=1.0,
        divergence_min=-20,
        divergence_max=20,
        divergence_step=1.0,
    )

    # Emittance scan
    scan_operation = LinearEmittanceScan(
        motor=motor_driver,
        ammeter=scanner_ammeter,
        deflection_plate_controller=dpc,
        scan_params=scan_parameters,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a manual emittance scan.")
    args = parser.parse_args()
    if args.verbose:
        _log.setLevel(logging.DEBUG)

    asyncio.run(main(args))
