import logging
import asyncio
import time

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

    sample_frequency_hz = [1000, 10000, 20000, 30000, 40000]

    for read_frequency in sample_frequency_hz:
        print(f"> Running test for read frequency [bold cyan]{read_frequency}[/bold cyan]")
        keithley_driver = Keithley(read_frequency, IPS[mod], PORT)
        await keithley_driver.connect()
        ammeter = Ammeter(
            keithley_driver,
            read_key=SCPIDriver.DataKeys.CURRENT,
            name=f"Keithley DMM7512 Module {mod}",
        )
        iterations = 100
        current_readings = []
        times = []
        try:
            for i in track(range(iterations), description="Testing..."):
                start_time = time.perf_counter()
                value = await ammeter.read_current()
                end_time = time.perf_counter()
                current_readings.append(value)
                times.append(end_time - start_time)
            await keithley_driver.disconnect()
            avg_time_ms = np.average(times) * 1000
            rate_hz = 1 / np.average(times)

            print("[green bold]Results:[/green bold]")
            print(f" > Set frequency: {read_frequency} Hz")
            print(f" > Set NPLC: {keithley_driver.nplc_setting}")
            print(f" > Average response time {avg_time_ms:.2f} ms")
            print(f" > Effective NPLC: {avg_time_ms / 1000 * 60:.2f}")
            print(f" > Effective sample rate: {rate_hz:.2f} Hz")
            print(f" > Current average: {np.average(current_readings):.5E} A")
            print(f" > Current stdev: {np.std(current_readings):.5E} A")
        except Exception as exc:
            _log.error(exc)
            await keithley_driver.disconnect()


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
    while True:
        try:
            measure_time = time.time()
            value = await ammeter.read_current()
            print(value)
        except BaseException as exc:
            print("Disconnecting and saving data.")
            await keithley_driver.disconnect()
            break


if __name__ == "__main__":
    # asyncio.run(run_timing_test(mod=1))
    asyncio.run(run_timing_test(mod=1))
