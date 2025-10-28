from .fake_motor_controller import FakeMotorController
from ops.ecris.devices.motor_controller_specification import Commands, Axis


def test_fake_axis_check_returns_correct_values():
    fake_controller = FakeMotorController()
    fake_controller.read_buffer()
    command = Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(Axis.X)
    fake_controller.handle_command(command.encode("ascii"))
    expected_buffer = f"{command}\r\n1\r\n{fake_controller._prompt}".encode("ascii")
    assert expected_buffer == fake_controller._buffer


def test_fake_buffer_reads_all_correctly():
    fake_controller = FakeMotorController()

    n_commands = 5
    for i in range(n_commands):
        fake_controller.handle_command("test command\r\n".encode("ascii"))
        assert not fake_controller.buffer_clear
        # Buffer should have an extra line for the banner
        assert fake_controller.buffer_lines == i + 3, rf"{fake_controller._buffer}"
        assert fake_controller._buffer == (
            f"{fake_controller._banner}\r\n{fake_controller._prompt}"
            + f"test command\r\n{fake_controller._prompt}" * (i + 1)
        ).encode("ascii")
    value = fake_controller.read_buffer()
    assert value == (
        f"{fake_controller._banner}\r\n{fake_controller._prompt}"
        + f"test command\r\n{fake_controller._prompt}" * (n_commands)
    ).encode("ascii")
    assert fake_controller.buffer_clear


def test_fake_buffer_reads_to_prompt_correctly():
    fake_controller = FakeMotorController()
    assert not fake_controller.buffer_clear
    fake_controller.read_buffer(fake_controller._prompt.encode("ascii"))
    assert fake_controller.buffer_clear

    n_commands = 5
    for i in range(n_commands):
        fake_controller.handle_command("test command\r\n".encode("ascii"))
        assert not fake_controller.buffer_clear
        assert fake_controller.buffer_lines == i + 2

    print(rf"{fake_controller._buffer}")
    for i in range(n_commands):
        assert not fake_controller.buffer_clear
        assert fake_controller._buffer == (
            f"test command\r\n{fake_controller._prompt}" * (n_commands - i)
        ).encode("ascii")
        fake_controller.read_buffer(fake_controller._prompt.encode("ascii"))
        assert fake_controller.buffer_lines == n_commands - i, rf"{fake_controller._buffer}"

    assert fake_controller.buffer_clear

