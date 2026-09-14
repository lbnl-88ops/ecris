# In: dev_tools/manual_scan.py
import argparse
import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

import numpy as np

from ops.ecris.devices import (
    BiasedAmmeter,
    BiasedVoltageSource,
    DeflectionPlateController,
    MotorController,
    Voltmeter,
)
from ops.ecris.devices.motor_controller import DeviceMalfunctionError
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


@dataclass
class HardwareContext:
    motor_controller: MotorController
    keithley_driver: Keithley
    phidget: PhidgetVoltageOutput
    venus: VENUSController
    venus_plc_driver: VenusPLC
    labjack_driver: LabJack
    dpc: DeflectionPlateController
    is_fcv1_out: Callable[[], Awaitable[bool]]
    scan_parameters: LinearScanParameters


async def setup_hardware() -> HardwareContext:
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

    dpc = DeflectionPlateController(
        extraction_voltmeter=Voltmeter(
            connection=venus_plc_driver, read_key=VenusPLC.DataKeys.EXTRACTION_VOLTAGE
        ),
        deflection_voltage_source=BiasedVoltageSource(
            connection=phidget,
            set_key=PhidgetVoltageOutput.DataKeys.VOLTAGE,
            bias_function=SCALE_VALUE(0.01),
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

    return HardwareContext(
        motor_controller=motor_controller,
        keithley_driver=keithley_driver,
        phidget=phidget,
        venus=venus,
        venus_plc_driver=venus_plc_driver,
        labjack_driver=labjack_driver,
        dpc=dpc,
        is_fcv1_out=is_fcv1_out,
        scan_parameters=scan_parameters,
    )


def print_help():
    print("\nAvailable Commands:")
    print("  params                         - Show current scan parameters")
    print("  params set <field> <value>      - Set a scan parameter")
    print("                                   (axis, position_min/max/step,")
    print("                                    divergence_min/max/step, samples_per_point)")
    print("  scan                           - Run emittance scan with current parameters")
    print("  move <axis> <position>         - Move to absolute position (e.g., move X 15.5)")
    print("  rmove <axis> <distance>        - Move by a relative distance (e.g., rmove X -10)")
    print("  center <axis>                  - Center the specified axis (e.g., center X)")
    print("  reset [axis]                   - Move axis to positive EOF (defaults to current scan axis)")
    print("  help                           - Show this message")
    print("  quit / exit                    - Disconnect and exit\n")


async def handle_params(ctx: HardwareContext, args: list[str]):
    if not args:
        print("\nCurrent Scan Parameters:")
        for field in ctx.scan_parameters.__dataclass_fields__:
            val = getattr(ctx.scan_parameters, field)
            print(f"  {field} = {val}")
        return

    if len(args) < 3 or args[0] != "set":
        print("  ! Usage: params set <field> <value>")
        return

    field = args[1]
    value_str = args[2]

    if not hasattr(ctx.scan_parameters, field):
        print(f"  ! Unknown parameter field: {field}")
        return

    try:
        # Get expected type
        field_type = ctx.scan_parameters.__annotations__[field]
        if field_type is Axis:
            new_val = Axis(value_str.upper())
        elif field_type is int:
            new_val = int(value_str)
        else:
            new_val = float(value_str)

        # Validation
        temp_params = LinearScanParameters(**{**ctx.scan_parameters.__dict__, field: new_val})
        if temp_params.position_min >= temp_params.position_max:
            raise ValueError("position_min must be less than position_max")
        if temp_params.divergence_min >= temp_params.divergence_max:
            raise ValueError("divergence_min must be less than divergence_max")
        if temp_params.position_step <= 0 or temp_params.divergence_step <= 0:
            raise ValueError("Steps must be greater than 0")
        if temp_params.samples_per_point < 1:
            raise ValueError("samples_per_point must be at least 1")

        setattr(ctx.scan_parameters, field, new_val)
        print(f"  > Set {field} to {new_val}")
        await handle_params(ctx, [])  # Show result
    except Exception as e:
        print(f"  ! Error setting parameter: {e}")


async def handle_scan(ctx: HardwareContext):
    _log.info("--- Starting Manual Emittance Scan ---")
    
    # Check interlock
    if not await ctx.is_fcv1_out():
        print("  ! Interlock Error: Faraday cup is NOT out. Scan aborted.")
        return

    try:
        scaling_factor = int(ctx.venus.read(["emittance_keithley_multiplier"]))
        _log.info(f"Scaling factor set to {scaling_factor}")
        scanner_ammeter = BiasedAmmeter(
            connection=ctx.keithley_driver,
            read_key=Keithley.DataKeys.VOLTAGE,
            bias_function=SCALE_VALUE(-(10 ** (-scaling_factor))),
        )
        scan_operation = LinearEmittanceScan(
            motor=ctx.motor_controller,
            ammeter=scanner_ammeter,
            deflection_plate_controller=ctx.dpc,
            scan_params=ctx.scan_parameters,
            interlock_check=ctx.is_fcv1_out,
        )
        await ctx.keithley_driver.send_silent_command(SCPIDriver.Commands.AUTOZERO_ONCE)
        results = await scan_operation.run(keep_centered=True, disconnect_on_end=False)

        scan_id = uuid.uuid7()
        filename = f"manual_scan_{scan_id}.h5"
        save_emittance_scan(
            filepath=filename,
            data=results,
            parameters=ctx.scan_parameters,
            additional_metadata={"user": "manual_emittance_scan"},
        )
        print(f"  > Scan complete. Saved to: {filename}")
        print(f"  > Data shape: {results.shape}, Min: {np.min(results):.2e}, Max: {np.max(results):.2e}")

    except (InterlockError, DeviceMalfunctionError) as e:
        print(f"  ! Hardware Error: {e}")
    except Exception as e:
        _log.exception("Unexpected error during scan")
        print(f"  ! Unexpected Error: {e}")


async def main():
    _log.info("--- Manual Emittance Scan Tool ---")
    ctx = None
    try:
        ctx = await setup_hardware()
        print_help()

        while True:
            try:
                user_input = await asyncio.to_thread(input, "scan> ")
                parts = user_input.strip().split()
                if not parts:
                    continue

                cmd = parts[0].lower()
                args = parts[1:]

                if cmd in ["quit", "exit"]:
                    confirm = await asyncio.to_thread(input, f"Reset {ctx.scan_parameters.axis.name} to positive EOF before exiting? (y/n): ")
                    if confirm.lower() == 'y':
                        print(f"  > Resetting {ctx.scan_parameters.axis.name}...")
                        await ctx.motor_controller.move_axis_to_positive_eof(ctx.scan_parameters.axis)
                    break
                
                elif cmd == "help":
                    print_help()
                
                elif cmd == "params":
                    await handle_params(ctx, args)
                
                elif cmd == "scan":
                    await handle_scan(ctx)
                
                elif cmd == "move":
                    if len(args) < 2:
                        print("  ! Usage: move <axis> <position>")
                    else:
                        axis = Axis(args[0].upper())
                        pos = float(args[1])
                        await ctx.motor_controller.move_to_position(axis, pos)
                        new_pos = await ctx.motor_controller.get_position(axis)
                        print(f"  > Axis {axis.name} at position: {new_pos}")
                
                elif cmd == "rmove":
                    if len(args) < 2:
                        print("  ! Usage: rmove <axis> <distance>")
                    else:
                        axis = Axis(args[0].upper())
                        dist = float(args[1])
                        await ctx.motor_controller.move_to_position(axis, dist, relative=True)
                        new_pos = await ctx.motor_controller.get_position(axis)
                        print(f"  > Axis {axis.name} at position: {new_pos}")
                
                elif cmd == "center":
                    if not args:
                        print("  ! Usage: center <axis>")
                    else:
                        axis = Axis(args[0].upper())
                        await ctx.motor_controller.center_axis(axis)
                        print(f"  > Axis {axis.name} centered.")
                
                elif cmd == "reset":
                    axis = ctx.scan_parameters.axis
                    if args:
                        axis = Axis(args[0].upper())
                    print(f"  > Resetting {axis.name} to positive EOF...")
                    await ctx.motor_controller.move_axis_to_positive_eof(axis)
                    print(f"  > {axis.name} reset.")
                
                else:
                    print(f"  ! Unknown command: {cmd}")

            except (ValueError, TypeError, KeyError, DeviceMalfunctionError, InterlockError) as e:
                print(f"  ! Error: {e}")
            except Exception:
                _log.exception("An unexpected error occurred in the command loop.")
                break

    except Exception:
        _log.exception("Failed to initialize hardware.")
    finally:
        if ctx:
            _log.info("Closing hardware connections...")
            try:
                await ctx.motor_controller.disconnect()
            except: pass
            try:
                await ctx.keithley_driver.disconnect()
            except: pass
            try:
                await ctx.phidget.disconnect()
            except: pass
            try:
                await ctx.labjack_driver.disconnect()
            except: pass
        _log.info("Application finished.")


if __name__ == "__main__":
    _log.setLevel(logging.INFO)
    asyncio.run(main())

