from unittest.mock import MagicMock, patch, create_autospec
from dataclasses import dataclass

import numpy as np
import pytest

from ops.ecris.devices.motor_controller_specification import Axis
from ops.ecris.legacy.emittance_scan import Variables, Motor, Read_and_Analyze

MODULE = "ops.ecris.legacy.emittance_scan."


ALL_AXES = [Axis.VenusX, Axis.VenusY, Axis.AcerX, Axis.AcerY]


@dataclass(frozen=True)
class _TestData:
    X_PARAMS = (-10, 10, 1)
    Y_PARAMS = (-14, 12, 2)
    XP_PARAMS = (-20, 20, 1)
    YP_PARAMS = (-22, 12, 2)

    @staticmethod
    def _range(params):
        min, max, step = params
        return [v for v in range(min, max + step, step)]


@pytest.fixture
def mock_variables():
    mock = create_autospec(Variables, instance=True)
    mock.x_min, mock.x_max, mock.x_step = _TestData.X_PARAMS
    mock.y_min, mock.y_max, mock.y_step = _TestData.Y_PARAMS
    mock.xp_min, mock.xp_max, mock.xp_step = _TestData.XP_PARAMS
    mock.yp_min, mock.yp_max, mock.yp_step = _TestData.YP_PARAMS
    return mock


@pytest.fixture
def mock_motor():
    return create_autospec(Motor, instance=True)


def test_read_and_analyze_init(mock_variables, mock_motor):
    rnd = Read_and_Analyze(mock_variables, mock_motor)
    assert rnd.x.tolist() == _TestData._range(_TestData.X_PARAMS)
    assert rnd.y.tolist() == _TestData._range(_TestData.Y_PARAMS)
    assert rnd.x_prime.tolist() == _TestData._range(_TestData.XP_PARAMS)
    assert rnd.y_prime.tolist() == _TestData._range(_TestData.YP_PARAMS)
