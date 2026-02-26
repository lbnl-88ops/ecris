import asyncio
import logging
import time
from ops.ecris.drivers.keithley import Keithley
from ops.ecris.drivers.scpi_driver import SCPIDriver
from rich import print

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
_log = logging.getLogger("keithley_test")

async def main():
    resource_name = "USB0::1510::29970::04684146\x00\x00::0::INSTR"
    print(f"[bold green]Starting Keithley USB Connection Test[/bold green]")
    print(f"Target Resource: [cyan]{resource_name}[/cyan]")
    
    # Initialize the driver
    # Using 60Hz as a standard sample frequency for NPLC 1.0
    keithley = Keithley(sample_frequency_hz=60, resource_name=resource_name)
    
    try:
        print("Connecting to instrument...")
        await keithley.connect()
        print("[bold green]Connected successfully![/bold green]")
        
        print("\n[bold]Reading 10 data points (noise level):[/bold]")
        for i in range(10):
            val = await keithley.read_data(SCPIDriver.DataKeys.CURRENT)
            print(f"  Point {i+1}: [yellow]{val:.6e} A[/yellow]")
            await asyncio.sleep(0.1) # Small delay between reads
            
    except Exception as e:
        print(f"[bold red]An error occurred during the test:[/bold red] {e}")
        _log.exception(e)
    finally:
        if keithley.is_connected:
            print("\nDisconnecting...")
            await keithley.disconnect()
            print("Disconnected.")

if __name__ == "__main__":
    asyncio.run(main())
