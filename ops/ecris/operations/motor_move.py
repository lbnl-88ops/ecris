"""
Motor Move Operation.

Moves a stepper-motor axis to its positive end-of-travel (OUT) position.
This is the safe "retracted" state for emittance-scanner probes — used to
park the wire/slit out of the beam path after a scan or on demand.

The operation acquires the shared ``_move_lock`` found on
``LinearEmittanceScan`` so that a motor move and an emittance scan can
never run concurrently, even when triggered from different code paths.
"""

import asyncio
from logging import getLogger
from typing import TYPE_CHECKING

from ops.ecris.devices.motor_controller_specification import Axis

if TYPE_CHECKING:
    from ops.ecris.devices.motor_controller import MotorController

_log = getLogger(__name__)

# Re-use the same class-level lock that LinearEmittanceScan uses so that
# motor moves and scans are mutually exclusive across the entire process.
from ops.ecris.operations.emittance_scan.linear_emittance_scan import LinearEmittanceScan

_SHARED_SCAN_LOCK: asyncio.Lock = LinearEmittanceScan._scan_lock


class MotorMoveOperation:
    """
    Operation that moves a motor axis to its OUT (positive end-of-travel) position.

    This parks the probe out of the beam path.  The operation is intentionally
    lightweight: it connects the motor, moves the requested axis to positive EOF
    (≈ 200 mm), then disconnects.

    Mutual exclusion with ``LinearEmittanceScan`` is guaranteed via the shared
    ``LinearEmittanceScan._scan_lock`` class-level lock.

    Args:
        motor: The ``MotorController`` (or compatible mock) to drive.
        axis:  The ``Axis`` to move out.  Defaults to ``Axis.VenusX``.
    """

    def __init__(self, motor: "MotorController", axis: Axis = Axis.VenusX) -> None:
        self._motor = motor
        self._axis = axis

    async def run(self) -> None:
        """
        Execute the move: connect → move to positive EOF → disconnect.

        Raises:
            ConnectionError: If the motor cannot connect.
            RuntimeError:    If the perpendicular axis cannot be cleared
                             (mirrors the real controller's safety interlock).
        """
        async with _SHARED_SCAN_LOCK:
            _log.info(
                "MotorMoveOperation: moving axis %s to OUT (positive EOF).", self._axis.name
            )
            try:
                await self._motor.connect()
                await self._motor.move_axis_to_positive_eof(self._axis)
                _log.info(
                    "MotorMoveOperation: axis %s successfully parked at OUT position.",
                    self._axis.name,
                )
            finally:
                await self._motor.disconnect()
