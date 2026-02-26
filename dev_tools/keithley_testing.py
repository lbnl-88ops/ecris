import logging
import asyncio
import time

import pyvisa
import numpy as np
import matplotlib.pyplot as plt

from ops.ecris.drivers import keithley
from ops.ecris.drivers.scpi_driver import SCPIDriver
from rich import print
from rich.progress import track

from ops.ecris.devices.ammeter import Ammeter
from ops.ecris.drivers.keithley import Keithley

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
_log = logging.getLogger("ops")

IPS = {1: "10.10.100.82", 2: "10.10.100.83"}
PORT = 23


async def run_timing_test(mod: int):
    print("[bold green]--- Keithley timing testing ---[/bold green]")

    n_points = 1
    min_ap = np.log10(8.4e-6)
    max_ap = np.log10(36e-3)
    aperatures = np.logspace(min_ap, max_ap, 100)

    # aperatures = [0.35, 0.80]
    averages = []
    stdevs = []

    keithley_driver = Keithley(108000, IPS[mod], PORT)
    await keithley_driver.connect()
    ammeter = Ammeter(
        keithley_driver,
        read_key=SCPIDriver.DataKeys.CURRENT,
        name=f"Keithley DMM7512 Module {mod}",
    )
    connection: SCPIDriver = ammeter._connection
    # await connection.send_silent_command(SCPIDriver.Commands.AUTOZERO_OFF)
    await connection.send_silent_command(SCPIDriver.Commands.set_range(3e-3))

    for aperature in aperatures:
        print(f"> Running test for [bold cyan]{aperature} s[/bold cyan]")
        iterations = 1000
        times = []
        await connection.send_silent_command(
            SCPIDriver.Commands.CURRENT_SET_APERATURE.format(aperature)
        )
        await connection.read_data(SCPIDriver.DataKeys.CURRENT)
        try:
            # await connection.read_data_points(
            #     SCPIDriver.DataKeys.CURRENT, n_points=points, timing=read_time / 1000
            # )
            for i in track(range(iterations), description="Testing..."):
                start_time = time.perf_counter()
                await connection.read_data(SCPIDriver.DataKeys.CURRENT)
                # await connection.read_loop(points)
                end_time = time.perf_counter()
                times.append(end_time - start_time)
            averages.append(np.average(times))
            stdevs.append(np.std(times))
        except Exception as exc:
            _log.error(exc)
            await keithley_driver.disconnect()
    await keithley_driver.disconnect()
    np.save("averages_auto_range", np.array(averages))
    np.save("stdevs_auto_range", np.array(stdevs))


def run_usb_test():
    print("[bold green]--- Keithley timing testing ---[/bold green]")
    rm = pyvisa.ResourceManager()
    keithley = rm.open_resource("USB0::1510::29970::04684146\x00\x00::0::INSTR")
    keithley.write(SCPIDriver.Commands.CURRENT_FUNCTION)
    keithley.write(SCPIDriver.Commands.set_range(6e-3))
    keithley.write(SCPIDriver.Commands.CURRENT_DELAY_DISABLE)
    keithley.write(SCPIDriver.Commands.AUTOZERO_OFF)
    keithley.write(SCPIDriver.Commands.AUTOZERO_ONCE)

    min_ap = np.log10(8.4e-6)
    max_ap = np.log10(36e-3)
    # aperatures = np.logspace(min_ap, max_ap, 100)
    aperatures = [0.5e-3]
    averages = []
    stdevs = []
    values = []

    for i, aperature in enumerate(aperatures):
        print(f"> Running test {i + 1}/{len(aperatures)} for [bold cyan]{aperature} s[/bold cyan]")
        iterations = 1000
        times = []
        keithley.write(SCPIDriver.Commands.CURRENT_SET_APERATURE.format(aperature))
        try:
            for j in track(range(iterations), description="Testing..."):
                start_time = time.perf_counter()
                value = keithley.query_ascii_values(SCPIDriver.Commands.MEASURE_CURRENT)
                end_time = time.perf_counter()
                times.append(end_time - start_time)
                if j == 0:
                    values.append(value)
            if i == 0:
                np.save("times_usb", np.array(times))
            averages.append(np.average(times[1:]))
            stdevs.append(np.std(times[1:]))
        except Exception as exc:
            _log.error(exc)
    # np.save("values_usb", np.array(values))
    # np.save("averages_usb", np.array(averages))
    # np.save("stdevs_usb", np.array(stdevs))


async def run_signal_test(mod: int):
    print("[bold green]--- Keithley signal testing ---[/bold green]")

    keithley_driver = Keithley(36000, IPS[mod], PORT)
    await keithley_driver.connect()
    ammeter = Ammeter(
        keithley_driver,
        read_key=SCPIDriver.DataKeys.CURRENT,
        name=f"Keithley DMM7512 Module {mod}",
    )
    print("[bold green]Reading signal, press Ctrl+C to end...")
    factor = 1
    timing = 1e-3
    total_time = 1
    n_points = total_time / timing

    try:
        await keithley_driver.send_silent_command(
            SCPIDriver.Commands.set_range(value_to_measure=1e-3)
        )
        start = time.perf_counter()
        data_array, time_array = await keithley_driver.read_data_points(
            SCPIDriver.DataKeys.CURRENT, n_points=n_points, timing=timing
        )
        end = time.perf_counter()
        print(end - start)
        start = time.perf_counter()
        data_array, time_array = await keithley_driver.read_loop(n_points)
        end = time.perf_counter()
        print(end - start)
        start = time.perf_counter()
        data_array, time_array = await keithley_driver.read_loop(n_points)
        end = time.perf_counter()
        print(end - start)
        np.save("current", data_array)
        np.save("time", time_array)
    except BaseException as exc:
        print(f"Disconnecting and saving data.: {exc}")
        await keithley_driver.disconnect()


if __name__ == "__main__":
    # asyncio.run(run_timing_test(mod=1))
    # asyncio.run(run_signal_test(mod=1))
    run_usb_test()
