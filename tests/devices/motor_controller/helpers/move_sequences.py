from ops.ecris.devices.motor_controller_specification import Axis, Bit, Commands


class MoveSequences:
    @staticmethod
    def _drive_sequence(axis: Axis, position: float, move_steps: int, relative=False) -> list[str]:
        """
        Generates the commands for a DRIVEN move.
        STARTS with DRIVE ON, ENDS when the polling for that move is complete.
        Does NOT include the initial axis clear check or the final DRIVE OFF.
        """
        move_cmd = (
            Commands.RELATIVE_MOVE(axis, position) if relative else Commands.MOVE(axis, position)
        )
        return [Commands.DRIVE_ON(axis), move_cmd] + [Commands.CHECK_IN_MOTION()] * (
            move_steps + 1
        )

    @staticmethod
    def _in_motion_check(coastdown_steps: int) -> list[str]:
        """
        Generates the commands for a COASTING stop.
        STARTS with DRIVE OFF, ENDS when the polling for that coast is complete.
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
        expected_commands = (
            [
                Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis),
                Commands.DRIVE_ON(axis),
                Commands.RELATIVE_MOVE(axis, position_to_move)
                if relative
                else Commands.MOVE(axis, position_to_move),
            ]
            + [Commands.CHECK_IN_MOTION()] * (move_steps + 1)
            + [Commands.DRIVE_OFF(axis)]
        )
        return expected_commands

    @staticmethod
    def _move_out_sequence(axis: Axis, move_steps: int):
        return MoveSequences._move_to(axis, 200, move_steps) + [
            Commands.CLEAR_BIT(Bit.KILL_ALL_MOVES(axis)),
            Commands.DRIVE_OFF(axis),
        ]

    @staticmethod
    def _cleanup_after_limit_sequence(axis: Axis, coastdown_steps: int = 0):
        return (
            [Commands.CLEAR_BIT(Bit.KILL_ALL_MOVES(axis)), Commands.DRIVE_OFF(axis)]
            + [Commands.CHECK_IN_MOTION()] * (coastdown_steps + 1)
            + [Commands.CHECK_PERPENDICULAR_AXIS_CLEAR(axis)]
        )

