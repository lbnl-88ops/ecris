from unittest.mock import AsyncMock

import pytest
from pytest import approx

from ops.ecris.devices.deflection_plate_controller import DeflectionPlateController
from ops.ecris.devices.power_supply import VoltageSource, Voltmeter


@pytest.fixture
def mock_voltmeter():
    return AsyncMock(spec=Voltmeter)


@pytest.fixture
def mock_voltage_source():
    return AsyncMock(spec=VoltageSource)


@pytest.mark.asyncio
async def test_voltage_calculation(mock_voltmeter, mock_voltage_source):
    mock_voltmeter.read_voltage.return_value = 120
    momentum = 20  # rad
    expected_voltage = 760.033869602

    test_controller = DeflectionPlateController(mock_voltmeter, mock_voltage_source)

    calculated_voltage = await test_controller._calculate_voltage(momentum)
    assert calculated_voltage == approx(expected_voltage)


@pytest.mark.asyncio
async def test_voltage_set(mock_voltmeter, mock_voltage_source):
    mock_voltmeter.read_voltage.return_value = 120
    momentum = 20  # rad
    expected_voltage = 760.033869602 * 1e-3

    test_controller = DeflectionPlateController(mock_voltmeter, mock_voltage_source)
    await test_controller.set_voltage(momentum)
    mock_voltage_source.set_voltage.assert_awaited_once_with(approx(expected_voltage))
