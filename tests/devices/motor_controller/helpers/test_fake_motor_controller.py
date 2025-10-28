from .fake_motor_controller import FakeMotorController


def test_fake_buffer_reads_all_correctly():
    fake_controller = FakeMotorController()

    n_commands = 5
    for i in range(n_commands):
        fake_controller.handle_command("test command\r\n".encode("ascii"))
        assert not fake_controller.buffer_clear
        assert len(fake_controller._buffer) == i + 2
    fake_controller.read_buffer()
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
        assert len(fake_controller._buffer) == i + 1

    for i in range(n_commands):
        assert not fake_controller.buffer_clear
        fake_controller.read_buffer(fake_controller._prompt.encode("ascii"))
        assert len(fake_controller._buffer) == n_commands - (i + 1)

    assert fake_controller.buffer_clear

