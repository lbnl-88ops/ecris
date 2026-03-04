import pytest

from ops.ecris.devices.biases import SCALE_VALUE


@pytest.mark.parametrize(
    "scale_factor, input_value, expected",
    [
        # Amps to Volts: 1 A * 0.04 = 0.04 V
        (0.04, 1.0, 0.04),
        (0.04, 25.0, 1.0),
        (0.04, 0.0, 0.0),
        (0.04, -10.0, -0.4),
        # Volts to Tesla: 1 V * 0.4 = 0.4 T
        (0.4, 1.0, 0.4),
        (0.4, 2.5, 1.0),
        (0.4, 0.0, 0.0),
        (0.4, -5.0, -2.0),
    ],
)
def test_scale_value(scale_factor: float, input_value: float, expected: float):
    bias = SCALE_VALUE(scale_factor)
    assert bias(input_value) == pytest.approx(expected)


def test_scale_value_returns_callable():
    bias = SCALE_VALUE(0.04)
    assert callable(bias)


def test_scale_value_amps_to_volts():
    """0.04 scale factor converts Amps to Volts for this instrument."""
    amps_to_volts = SCALE_VALUE(0.04)
    assert amps_to_volts(50.0) == pytest.approx(2.0)


def test_scale_value_volts_to_tesla():
    """0.4 scale factor converts Volts to Tesla for this instrument."""
    volts_to_tesla = SCALE_VALUE(0.4)
    assert volts_to_tesla(5.0) == pytest.approx(2.0)
