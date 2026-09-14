# In: dev_tools/manual_scan.py
import argparse
import asyncio
import logging
import uuid

import numpy as np

from ops.ecris.devices import (
    BiasedAmmeter,
    BiasedVoltageSource,
    DeflectionPlateController,
    MotorController,
    Voltmeter,
)
from ops.ecris.devices.biases import POSITIVE_VALUES_ONLY, SCALE_VALUE
from ops.ecris.devices.deflection_plate_controller import (
    LABJACK_DEFLECTION_PLATE_BIAS,
)
from ops.ecris.devices.motor_controller_specification import Axis
from ops.ecris.drivers.keithley import Keithley
from ops.ecris.drivers.scpi_driver import SCPIDriver
from ops.ecris.drivers.labjack import LabJack
from ops.ecris.drivers.scpi_driver import SCPIDriver
from ops.ecris.drivers.venus_plc import VENUSController, VenusPLC
from ops.ecris.devices.exceptions import InterlockError
from ops.ecris.operations.emittance_scan import LinearEmittanceScan, LinearScanParameters
from ops.ecris.operations.emittance_scan.save_scan import save_emittance_scan
from ops.ecris.drivers.phidget import PhidgetVoltageOutput

# Set up basic logging to see the output from our scan classes
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
_log = logging.getLogger()


async def main():
    _log.info("--- Manual Emittance Scan Tool ---")

    _log.info("Assembling hardware drivers and logical devices...")

    # Drivers
    labjack_driver = LabJack()
    venus = VENUSController(read_only=True)
    venus_plc_driver = VenusPLC(venus)

    async def is_fcv1_out() -> bool:
        # fcv1_in is True when IN (blocking), False when OUT (clear)
        return not bool(await venus_plc_driver.read_data(VenusPLC.DataKeys.FARADAY_CUP_IN))

    motor_controller = MotorController(ip="10.10.100.60", port=5002, fast_ramp=True)
    await asyncio.wait_for(motor_controller.connect(), timeout=20)
    _log.info("Motor controller connected")

        # Voltage-mode: instrument reads voltage; scale_factor converts V → A (or desired units).
    keithley_driver = Keithley.connect_at_usb(
        resource_name="USB0::1510::29970::04684146\x00\x00::0::INSTR",
        aperture_time=1e-3,
        mode=SCPIDriver.MeasurementMode.VOLTAGE,
    )
    _log.info("Connected to Keithley via USB.")
    await keithley_driver.connect()
    await keithley_driver.send_silent_command(SCPIDriver.Commands.VOLTAGE_FUNCTION)
    await keithley_driver.send_silent_command(SCPIDriver.Commands.VOLTAGE_AUTOZERO_OFF)
    await keithley_driver.send_silent_command(SCPIDriver.Commands.VOLTAGE_DELAY_DISABLE)
    await keithley_driver.send_silent_command(SCPIDriver.Commands.VOLTAGE_AUTO_RANGE_OFF)
    await keithley_driver.send_silent_command(SCPIDriver.Commands.set_voltage_range(10))

    phidget = PhidgetVoltageOutput(serial_number=717445, channel=0)
    await phidget.connect()

    deflector_v_source = BiasedVoltageSource(
        connection=labjack_driver,
        set_key=LabJack.DataKeys.DAC1,
        bias_function=LABJACK_DEFLECTION_PLATE_BIAS,
    )

    dpc = DeflectionPlateController(
        extraction_voltmeter=Voltmeter(
            connection=venus_plc_driver, read_key=VenusPLC.DataKeys.EXTRACTION_VOLTAGE
        ),
        deflection_voltage_source=BiasedVoltageSource(
            connection=phidget,
            set_key=PhidgetVoltageOutput.DataKeys.VOLTAGE,
            bias_function=SCALE_VALUE(0.01)
        ),
    )

    scan_parameters = LinearScanParameters(
        axis=Axis.VenusX,
        position_min=-2,
        position_max=2,
        position_step=1.0,
        divergence_min=-100,
        divergence_max=100,
        divergence_step=50.0,
        samples_per_point=1,
    )

    while True:
        _log.info("--- Manual emittance scan ---")
        _log.info(f"Current parameters: {scan_parameters}")

        
    


        # Emittance scan
        scaling_factor = int(venus.read(["emittance_keithley_multiplier"]))
        _log.info(f"Scaling factor set to {scaling_factor}")
        scanner_ammeter = BiasedAmmeter(
            connection=keithley_driver,
            read_key=Keithley.DataKeys.VOLTAGE,
            bias_function=SCALE_VALUE(-10**(-scaling_factor)),
        )
        scan_operation = LinearEmittanceScan(
            motor=motor_controller,
        ammeter=scanner_ammeter,
        deflection_plate_controller=dpc,
        scan_params=scan_parameters,
        interlock_check=is_fcv1_out,
        )
        await keithley_driver.send_silent_command(SCPIDriver.Commands.AUTOZERO_ONCE)
        results = await scan_operation.run(keep_centered=True, disconnect_on_end=False)

        id = uuid.uuid7()
        save_emittance_scan(
            filepath=f"manual_scan_{id}.h5",
            data=results,
            parameters=scan_parameters,
            additional_metadata={"user": "manual_emittance_scan"},
        )




if __name__ == "__main__":
    _log.setLevel(logging.DEBUG)

    asyncio.run(main())
