import argparse
import asyncio
import logging
import time
from typing import List

import numpy as np
import telnetlib3

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
_log = logging.getLogger(__name__)

PROMPT = b'B2900A> '
SEPARATOR = b'\r\n'

def parse_response(response: bytes) -> List[str]:
    lines = [r.removeprefix(PROMPT).decode('ascii').strip() for r in response.split(SEPARATOR)]
    return [str(l) for l in lines if l]

async def run_timing_test(reader, writer, command: str, nplc: float, iterations: int = 100):
    """
    Runs a timing test for a given command and reports the average response time.

    This function uses the robust method of reading until the next prompt to
    capture the entire transaction in one operation.
    """
    _log.info(f"--- Starting timing test for command '{command}' with NPLC {nplc} ({iterations} iterations) ---")

    _log.info(f"Configuring ammeter for fast measurements (NPLC={nplc})...")
    setup_cmd = f":SENS:CURR:NPLC {nplc}\r\n".encode('ascii')
    writer.write(setup_cmd)
    await writer.drain()
    await reader.readuntil(PROMPT) # Consume the prompt after setup
    command_bytes = f"{command}\r\n".encode('ascii')
    times = []
    values = []

    for i in range(iterations):
        start_time = time.perf_counter()

        writer.write(command_bytes)
        await writer.drain()

        full_response = await reader.readuntil(PROMPT)

        end_time = time.perf_counter()
        duration = end_time - start_time
        times.append(duration)

        response_lines = parse_response(full_response)
        value = None
        for line in response_lines:
            try:
                value = float(line)
            except ValueError:
                continue
        if value is None:
            _log.warning(f"Could not parse a float from response: {full_response!r}")
        values.append(value)
        _log.debug(f"Iter {i+1}/{iterations}: Received {value:.4E} in {duration*1000:.2f} ms")

    avg_time_ms = np.average(times) * 1000
    rate_hz = 1 / np.average(times)
    _log.info(f"--- Timing test finished for '{command}' ---")
    _log.info(f"Average response time: {avg_time_ms:.2f} ms")
    _log.info(f"Effective sample rate: {rate_hz:.2f} Hz")
    _log.info(f"Value average: {np.average(values):.5E} A")
    _log.info(f"Value stdev: {np.std(values):.5E} A")
    return rate_hz, np.std(values)

async def ammeter_interface(host: str, port: int):
    """Main interactive loop."""
    _log.info(f"Connecting to {host}:{port}...")
    reader, writer = await telnetlib3.open_connection(host, port, encoding=False)
    initial_output = await reader.readuntil(PROMPT)
    _log.info("Connected and synchronized with prompt.")
    _log.info("--- Banner ---\n" + '\n'.join(parse_response(initial_output)) + "\n--------------")

    for command in [
        ':sens:func "curr"',
        ':sens:curr:rang:auto on',
        ':sens:curr:nplc:auto off'
    ]:
        writer.write(f"{command}\r\n".encode('ascii'))
        await writer.drain()
        response = await reader.readuntil(PROMPT) # Consume the prompt after setup
        _log.info("Setup command response: " + '\n'.join(parse_response(response)))

    _log.info("Configuration complete.")

    while True:
        command = await asyncio.to_thread(input, "\n> Enter command or 'test': ")
        match command.lower():
            case 'quit' | 'exit':
                break
            case 'test':
                hzs = []
                stds = []
                nplcs = []
                for nplc in [0.1]:
                    hz, std = await run_timing_test(reader, writer, ":meas:curr?", nplc)
                    nplcs.append(float(nplc))
                    hzs.append(float(hz))
                    stds.append(float(std))
                for l in [nplcs, hzs, stds]:
                    print('[' + ','.join([str(v) for v in l]), ']')
            case _:
                writer.write(f"{command}\r\n".encode('ascii'))
                await writer.drain()
                response = await reader.readuntil(PROMPT)
                print(f"--> {response.removesuffix(PROMPT).strip().decode('ascii')}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Interactive Telnet probe for a network device using telnetlib3."
    )
    parser.add_argument("host", help="The IP address of the device.")
    parser.add_argument("port", type=int, help="The Telnet port number of the device.")
    args = parser.parse_args()

    asyncio.run(ammeter_interface(args.host, args.port))
