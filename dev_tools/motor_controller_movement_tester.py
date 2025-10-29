from argparse import ArgumentParser
import asyncio
import logging

from ops.ecris.devices.motor_controller import MotorController

_log = logging.getLogger("ops")


async def run_interactive_test(host: str, port: int):
    controller = MotorController(ip=host, port=port)
    _log.info(f"Attempting to connect to Motor Controller at {host}:{port}...")
    await asyncio.wait_for(controller.connect(), timeout=3.0)
    _log.info(f"Successfully connected to Motor Controller...")


if __name__ == "__main__":
    parser = ArgumentParser(description="Interactive motor controller movement tester")
    parser.add_argument("host", help="The IP address of the device.")
    parser.add_argument("port", type=int, help="The Telnet port number of the device.")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug level logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    asyncio.run(run_interactive_test(args.host, args.port))
