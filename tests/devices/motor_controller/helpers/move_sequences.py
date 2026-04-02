from ops.ecris.devices.motor_controller_specification import Axis, Bit, Commands


class MoveSequences:
    @staticmethod
    def _drive_sequence(axis: Axis, position: float, move_steps: int, relative=False) -> list[str]:
        """
        Generates the commands for a DRIVEN move.
        """
        move_cmd = (
            Commands.RELATIVE_MOVE(axis, position) if relative else Commands.MOVE(axis, position)
        )
        return [Commands.DRIVE_ON(axis), move_cmd + " : " + Commands.WAIT_UNTIL_STOP]

    @staticmethod
    def _in_motion_check(coastdown_steps: int) -> list[str]:
        """
        Generates the commands for a COASTING stop (after DRIVE OFF).
        """
        return [Commands.CHECK_IN_MOTION()] * (coastdown_steps + 1)

    @staticmethod
    def _move_to(
        axis: Axis,
        position_to_move: float,
        move_steps: int,
        relative=False,
        coastdown_steps: int = 0,
    ):
        """
        Building block for _move_to_position_unsafe WITHOUT axis clear logic.
        """
        move_cmd = (
            Commands.RELATIVE_MOVE(axis, position_to_move)
            if relative
            else Commands.MOVE(axis, position_to_move)
        )
        return [
            Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis),
            Commands.DRIVE_ON(axis),
            move_cmd + " : " + Commands.WAIT_UNTIL_STOP,
        ]

    @staticmethod
    def _move_out_sequence(axis: Axis, move_steps: int):
        """
        Building block for _move_axis_to_positive_eof_unsafe.
        """
        return MoveSequences._move_to(axis, 200, move_steps) + [
            Commands.CLEAR_BIT(Bit.KILL_ALL_MOVES(axis)),
            Commands.DRIVE_OFF(axis),
        ]

    @staticmethod
    def _cleanup_after_limit_sequence(axis: Axis, coastdown_steps: int = 0):
        """
        Building block for axis clear logic inside _move_to_position_unsafe.
        """
        return (
            [Commands.CLEAR_BIT(Bit.KILL_ALL_MOVES(axis))]
            + [
                Commands.CHECK_IN_MOTION()
            ]  # _movement_stopped(perpendicular) polls once since no DRIVE OFF
            + [Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis)]
        )
