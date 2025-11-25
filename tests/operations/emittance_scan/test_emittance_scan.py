import pytest
import numpy as np
from unittest.mock import AsyncMock, call, MagicMock

from ops.ecris.operations.emittance_scan.base import LinearEmittanceScan
from ops.ecris.operations.emittance_scan.parameters import LinearScanParameters
from ops.ecris.devices.motor_controller import MotorController
from ops.ecris.devices.ammeter import Ammeter
from ops.ecris.devices.motor_controller_specification import Axis
from ops.ecris.devices.deflection_plate_controller import DeflectionPlateController


@pytest.fixture
def mock_motor() -> AsyncMock:
    """A mock for the MotorController."""
    return AsyncMock(spec=MotorController)


@pytest.fixture
def mock_ammeter() -> AsyncMock:
    """A mock for the Ammeter."""
    return AsyncMock(spec=Ammeter)


@pytest.fixture
def mock_dpc() -> AsyncMock:
    """A mock for the Deflection plate controller."""
    return AsyncMock(spec=DeflectionPlateController)


class TestEmittanceScan:
    @pytest.mark.asyncio
    async def test_run_scan_logic_and_matrix_creation(self, mock_motor, mock_ammeter, mock_dpc):
        scan_params = LinearScanParameters(
            axis=Axis.VenusX,
            position_min=-1.0,
            position_max=2.0,
            position_step=1.0,
            divergence_min=-10,
            divergence_max=2,
            divergence_step=2.0,
            samples_per_point=10,
        )

        expected_positions = [-1.0, 0.0, 1.0, 2.0]
        expected_divergences = [-10, -8.0, -6, -4, -2, 0, 2]
        mock_averages = []
        for i in range(len(expected_positions)):
            for j in range(len(expected_divergences)):
                mock_averages.append(1e-5 * (i + j + 1))
        mock_readings = []
        for avg in mock_averages:
            mock_readings.extend(
                [
                    avg * np.random.normal(1.0, scale=1e-7)
                    for _ in range(scan_params.samples_per_point)
                ]
            )
        mock_ammeter.read_current.side_effect = mock_readings

        scan_operation = LinearEmittanceScan(
            motor=mock_motor,
            ammeter=mock_ammeter,
            deflection_plate_controller=mock_dpc,
            scan_params=scan_params,
        )

        # RUN SCAN
        result_matrix = await scan_operation.run()

        # Motor calls
        for mock in [mock_motor, mock_ammeter, mock_dpc]:
            mock.connect.assert_awaited_once()
            mock.disconnect.assert_awaited_once()

        expected_motor_calls = [
            call.move_to_position(scan_params.axis, pos) for pos in expected_positions
        ]
        mock_motor.assert_has_calls(expected_motor_calls)
        assert mock_motor.move_to_position.call_count == len(expected_positions)

        # Divergence calls
        expected_divergence_calls = []
        for _ in expected_positions:
            for divergence in expected_divergences:
                expected_divergence_calls.append(call.set_divergence(divergence))

        mock_dpc.set_divergence.assert_has_calls(expected_divergence_calls)
        assert mock_dpc.set_divergence.call_count == len(expected_divergence_calls)

        # Ammeter calls
        expected_read_count = len(expected_divergence_calls) * scan_params.samples_per_point
        assert mock_ammeter.read_current.call_count == expected_read_count

        # Check final value
        expected_shape = (len(expected_divergences), len(expected_positions))
        assert result_matrix.shape == expected_shape

        # The values in the matrix should be the averages we configured.
        expected_matrix = np.zeros(shape=(len(expected_divergences), len(expected_positions)))
        for i in range(len(expected_positions)):
            for j in range(len(expected_divergences)):
                expected_matrix[j, i] = 1e-5 * (i + j + 1)

        np.testing.assert_allclose(result_matrix, expected_matrix)
