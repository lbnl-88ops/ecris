# In: dev_tools/manual_scan.py
import asyncio
import logging
import argparse
import numpy as np
import time

from ops.ecris.drivers.labjack import LabJack
from ops.ecris.drivers.telnet_driver import TelnetDriver
from ops.ecris.drivers.keithley import Keithley
from ops.ecris.drivers.venus_plc import VenusPLC, VENUSController

from ops.ecris.devices.motor_controller_specification import Axis
from ops.ecris.devices import (
    MotorController,
    BiasedAmmeter,
    Voltmeter,
    BiasedVoltageSource,
    DeflectionPlateController,
)
from ops.ecris.devices.biases import POSITIVE_VALUES_ONLY
from ops.ecris.devices.deflection_plate_controller import (
    LABJACK_DEFLECTION_PLATE_BIAS,
)

from ops.ecris.operations.emittance_scan import LinearEmittanceScan, LinearScanParameters
from ops.ecris.operations.emittance_scan.save_scan import save_emittance_scan


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
    keithley_driver = Keithley(
        sample_frequency_hz=60, resource_name="USB0::1510::29970::04684146\x00\x00::0::INSTR"
    )

    # Devices
    scanner_ammeter = BiasedAmmeter(
        connection=keithley_driver,
        read_key=Keithley.DataKeys.CURRENT,
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
        divergence_min=-50,
        divergence_max=50,
        divergence_step=1.0,
        samples_per_point=2000,
    )

    # Emittance scan
    scan_operation = LinearEmittanceScan(
        motor=motor_driver,
        ammeter=scanner_ammeter,
        deflection_plate_controller=dpc,
        scan_params=scan_parameters,
    )

    result = await scan_operation.run()
    save_emittance_scan(
        filepath="scan.h5",
        data=result,
        parameters=scan_parameters,
        additional_metadata={"user": "manual_emittance_scan"},
    )

    _log.info("--- Scan Configuration Summary ---")
    _log.info(f"               Axis: {scan_parameters.axis.name}")
    _log.info(
        f"     Position Range: {scan_parameters.position_min} to {scan_parameters.position_max} (step: {scan_parameters.position_step})"
    )
    _log.info(
        f"   Divergence Range: {scan_parameters.divergence_min} to {scan_parameters.divergence_max} (step: {scan_parameters.divergence_step})"
    )
    _log.info(f"Samples per point: {scan_parameters.samples_per_point}")
    print("-" * 40)

    while True:
        response = await asyncio.to_thread(input, "Proceed with the scan? (y/n): ")
        if response.lower().strip() == "y":
            break
        elif response.lower().strip() == "n":
            _log.warning("Scan cancelled by user.")
            return
        else:
            print("Invalid input. Please enter 'y' or 'n'.")

    _log.info("User confirmed. Starting scan...")
    try:
        await keithley_driver.connect()
        results = await scan_operation.run()
        _log.info("Scan completed successfully.")

        if args.output:
            _log.info(f"Saving results matrix to {args.output}")
            np.savetxt(args.output, results, delimiter=",", fmt="%.6e")
            _log.info("Save complete.")
        else:
            _log.info("Scan results (shape {}):".format(results.shape))
            print(results)

    finally:
        await keithley_driver.disconnect()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a manual emittance scan.")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Optional path to save the resulting data matrix as a CSV file.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose DEBUG level logging.",
    )

    args = parser.parse_args()
    if args.verbose:
        _log.setLevel(logging.DEBUG)

    asyncio.run(main(args))
