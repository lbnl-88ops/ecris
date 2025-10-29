from argparse import ArgumentParser
import asyncio
import logging
from typing import Any

from ops.ecris.devices.motor_controller import MotorController, Axis, DeviceMalfunctionError

_log = logging.getLogger("ops")

COMMAND_MAP = {
    "move": ("move_to_position", [Axis, float]),
    "rmove": ("move_to_position", [Axis, float, {"relative": True}]),  # Special case for relative
    "center": ("center_axis", [Axis]),
    "is_clear": ("is_axis_clear_to_move", [Axis]),
    "is_centered": ("is_centered", [Axis]),
}


def print_help():
    """Prints a helpful list of available commands."""
    print("\nAvailable Commands:")
    print("  move <axis> <position>         - Move to absolute position (e.g., move A 15.5)")
    print("  rmove <axis> <distance>        - Move by a relative distance (e.g., rmove Z -10)")
    print("  center <axis>                - Center the specified axis (e.g., center A)")
    print("  is_clear <axis>              - Check if the perpendicular axis is clear")
    print("  is_centered <axis>           - Check if the axis has been centered")
    print("  help                         - Show this message")
    print("  quit / exit                  - Disconnect and close the application\n")


async def _parse_and_execute(controller: MotorController, user_input: str):
    """Parses user input, converts arguments, and executes the command."""
    parts = user_input.strip().split()
    if not parts:
        return

    command_str, *raw_args = parts
    if command_str not in COMMAND_MAP:
        raise ValueError(f"Unknown command '{command_str}'. Type 'help' for options.")

    method_name, expected_types = COMMAND_MAP[command_str]
    method = getattr(controller, method_name)
    kwargs = {}
    if isinstance(expected_types[-1], dict):
        kwargs = expected_types.pop()

    if len(raw_args) != len(expected_types):
        raise TypeError(
            f"Wrong number of arguments for '{command_str}'. "
            f"Expected {len(expected_types)}, got {len(raw_args)}."
        )

    args = []
    for raw_arg, arg_type in zip(raw_args, expected_types):
        if arg_type is Axis:
            args.append(Axis[raw_arg.upper()])
        else:
            args.append(arg_type(raw_arg))

    result = await method(*args, **kwargs)
    if result is not None:
        print(f"  > Result: {result}")


async def run_interactive_test(host: str, port: int):
    """Connects to the controller and runs the interactive command loop."""
    controller = MotorController(ip=host, port=port)
    try:
        _log.info(f"Attempting to connect to motor controller at {host}:{port}...")
        await asyncio.wait_for(controller.connect(), timeout=3.0)
        _log.info("Successfully connected to motor controller.")
        print_help()

        while True:
            try:
                user_input = await asyncio.to_thread(input, "motor> ")
                if user_input.lower() in ["quit", "exit"]:
                    break
                if user_input.lower() == "help":
                    print_help()
                    continue

                await _parse_and_execute(controller, user_input)

            except (ValueError, TypeError, KeyError, DeviceMalfunctionError) as e:
                print(f"  ! Error: {e}")
            except Exception:
                _log.exception("An unexpected error occurred in the command loop.")
                break

    except asyncio.TimeoutError:
        _log.error("Connection timed out. Check host and port.")
    except Exception:
        _log.exception("Failed to connect or run the test.")
    finally:
        if controller.is_connected:
            _log.info("Disconnecting from motor controller...")
            await controller.disconnect()
        _log.info("Application finished.")


if __name__ == "__main__":
    parser = ArgumentParser(description="Interactive motor controller movement tester")
    parser.add_argument("host", help="The IP address of the device.")
    parser.add_argument("port", type=int, help="The port number of the device.")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug level logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    asyncio.run(run_interactive_test(args.host, args.port))
