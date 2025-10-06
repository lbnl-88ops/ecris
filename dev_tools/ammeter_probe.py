import asyncio
import logging
import argparse
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

_log = logging.getLogger(__name__)

async def probe_ammeter(host: str, port: int):
    """
    Connects to the ammeter and provides an interactive command prompt.
    """
    writer: Optional[asyncio.StreamWriter] = None
    try:
        _log.info(f"Attempting to connect to ammeter at {host}:{port}...")
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=5.0
        )
        _log.info(f"Successfully connected to {host}:{port}. Type 'quit' to exit.")

        while True:
            command = await asyncio.to_thread(input, "\n> Send command: ")

            if command.lower() in ('quit', 'exit'):
                break
            
            full_command = f"{command}\r\n"
            
            _log.info(f"Sending: {full_command!r}")
            writer.write(full_command.encode('ascii'))
            await writer.drain()

            try:
                response = await asyncio.wait_for(reader.read(4096), timeout=3.0)
                
                print("--- Response Received ---")
                print(f"Raw    : {response!r}")
                print(f"Decoded: {response.decode('ascii', errors='ignore').strip()}")
                print("-------------------------")

            except asyncio.TimeoutError:
                _log.warning("Read timed out. The device did not respond.")

    except asyncio.TimeoutError:
        _log.error(f"Connection timed out. Could not connect to {host}:{port}.")
    except ConnectionRefusedError:
        _log.error(f"Connection refused. Is the device on and the IP/port correct?")
    except Exception as e:
        _log.error(f"An unexpected error occurred: {e}", exc_info=True)
    finally:
        if writer:
            _log.info("Closing connection.")
            writer.close()
            await writer.wait_closed()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Interactive probe for a network device.")
    parser.add_argument("host", help="The IP address of the ammeter.")
    parser.add_argument("port", type=int, help="The port number of the ammeter.")
    args = parser.parse_args()

    asyncio.run(probe_ammeter(args.host, args.port))
