import logging
import asyncio
from rich import print

from ops.ecris.drivers.phidget import PhidgetVoltageOutput

from ops.ecris.devices import BiasedVoltageSource
from ops.ecris.devices.biases import SCALE_VALUE

_log = logging.getLogger("ops")

def print_commands():
    print("\n[bold]Available Commands:[/bold]")
    print("  set <voltage>\t\t-Set voltage")
    print("  quit/exit\t\t-Disconnect and close\n")

async def _parse_and_set_voltage(source: BiasedVoltageSource, 
                           user_input) -> None:
    parts = user_input.strip().split()
    if not parts:
        return
    command, voltage = parts
    try:
        voltage = float(voltage)
        _log.info(f"Setting requested voltage to {voltage}")
        await asyncio.wait_for(source.set_voltage(voltage), 
                               timeout=5)
    except ValueError:
        _log.error(f"Unable to parse voltage value {voltage}")
        return

async def run_test() -> None:
    serial_number: int = 717445
    channel: int = 0
    try:
        voltage_source = await asyncio.wait_for(_connect(serial_number, channel), timeout=20)
        while True:
            try:
                print_commands()
                user_input = await asyncio.to_thread(input, "phidget> ")
                if user_input.lower() in ["quit", "exit"]:
                        break
                await _parse_and_set_voltage(voltage_source, 
                                             user_input)
    
    except asyncio.TimeoutError:
        _log.error("Connection timed out.")
    finally:
        if voltage_source.is_connected:
            _log.info("Disconnecting")
            await voltage_source.disconnect()
            _log.info("Disconnected, exiting.")


async def _connect(serial_number: int, channel: int) -> BiasedVoltageSource:
    _log.info("Connecting phidget")
    phidget = PhidgetVoltageOutput(serial_number, channel)
    voltage_source = BiasedVoltageSource(
        connection=phidget,
            set_key=PhidgetVoltageOutput.DataKeys.VOLTAGE,
            bias_function=SCALE_VALUE(0.01))
    await voltage_source.connect()
    _log.info("Phidget connected")
    return voltage_source

if __name__ == "__main__":
    info_format = "%(asctime)s - %(levelname)s - %(message)s"
    debug_format = "%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"

    log_level = logging.DEBUG# if args.debug else logging.INFO
    log_format = debug_format# if args.debug else info_format

    logging.basicConfig(
        level=log_level,
        format=log_format,
    )

