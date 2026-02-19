import logging
import asyncio
import time

import numpy as np

from ops.ecris.drivers.scpi_driver import SCPIDriver
from rich import print
from rich.progress import track

from ops.ecris.devices.ammeter import Ammeter
from ops.ecris.drivers.keithley import Keithley

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
_log = logging.getLogger("ops")

IPS = {1: "10.10.100.82", 2: "10.10.100.83"}
PORT = 23


async def run_test(mod: int):
    print("[bold green]--- Keithley testing ---[/bold green]")
    for read_frequency in [1000]:
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
            print(f" > Average response time {avg_time_ms:.2f} ms")
            print(f" > Effective sample rate: {rate_hz:.2f} Hz")
            print(f" > Current average: {np.average(current_readings):.5E} A")
            print(f" > Current stdev: {np.std(current_readings):.5E} A")
        except:
            await keithley_driver.disconnect()


if __name__ == "__main__":
    asyncio.run(run_test(mod=1))
