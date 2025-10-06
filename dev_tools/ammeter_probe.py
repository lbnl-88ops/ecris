import asyncio
import logging
import argparse
import telnetlib3

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
_log = logging.getLogger(__name__)

async def probe_ammeter_telnet3(host: str, port: int):
    """
    Connects to the ammeter using telnetlib3 to handle the protocol
    and provides an interactive command prompt.
    """
    try:
        _log.info(f"Attempting to connect to Telnet server at {host}:{port}...")
        async with telnetlib3.open_connection(
            host, port, encoding='ascii', connect_timeout=5
        ) as (reader, writer):
            
            _log.info("Successfully connected. Waiting for initial banner...")
            
            initial_output = await reader.readuntil(b'\n', timeout=5)
            print("--- Initial Banner Received ---")
            print(initial_output.strip())
            print("-----------------------------")
            
            _log.info("Synchronized with prompt. Type 'quit' to exit.")

            while True:
                command = await asyncio.to_thread(input, "\n> Send command: ")

                if command.lower() in ('quit', 'exit'):
                    break

                full_command = f"{command}\r\n"
                print(f"Sending command {full_command!r}")
                writer.write(full_command)
                
                try:
                    response = await reader.readuntil(b'\n', timeout=3.0)
                    
                    print("--- Response Received ---")
                    print(f'Raw command: {response!r}')
                    print(f'Decoded: {response.decode("ascii").strip()}')
                    print("-------------------------")

                except asyncio.TimeoutError:
                    _log.warning("Read timed out. The device did not respond.")

    except asyncio.TimeoutError:
        _log.error(f"Connection timed out. Could not connect to {host}:{port}.")
    except ConnectionRefusedError:
        _log.error(f"Connection refused. Is the device on and the IP/port correct?")
    except Exception as e:
        _log.error(f"An unexpected error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Interactive Telnet probe for a network device using telnetlib3."
    )
    parser.add_argument("host", help="The IP address of the device.")
    parser.add_argument("port", type=int, help="The Telnet port number of the device.")
    args = parser.parse_args()

    asyncio.run(probe_ammeter_telnet3(args.host, args.port))