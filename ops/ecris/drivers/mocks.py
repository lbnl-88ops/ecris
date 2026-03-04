"""
Mock (dummy) drivers for the ECRIS project.

These objects implement the same interfaces as the real hardware drivers but operate
entirely in memory — no physical devices required.  Use them in unit tests, CI
pipelines, or any situation where real hardware is unavailable.

Quick-start
-----------
Use ``get_driver_factory`` to obtain a bundle of either real or mock drivers
depending on a ``test_mode`` flag:

    factory = get_driver_factory(test_mode=True)
    ammeter_driver   = factory.ammeter()
    plc_driver       = factory.plc()
    motor_driver     = factory.motor_controller()
    labjack_driver   = factory.labjack()
"""

import asyncio
import random
import time
from enum import Enum, auto
from logging import getLogger
from typing import Dict, Optional, Tuple

import numpy as np

from ops.ecris.devices.motor_controller_specification import Axis, MID_POINT_OFFSETS, PERPENDICULAR_AXIS
from ops.ecris.drivers.base import DataSource, SessionDriver
from ops.ecris.drivers.scpi_driver import SCPIDriver

_log = getLogger(__name__)


# ---------------------------------------------------------------------------
# DummyAmmeter
# ---------------------------------------------------------------------------

class DummyAmmeter(SessionDriver):
    """
    Mock driver for a Keithley DMM7512 / BiasedAmmeter.

    Implements the full ``SessionDriver`` interface (``connect``, ``disconnect``,
    ``read_data``, ``write_data``) without touching any real hardware.

    Simulated behaviour
    -------------------
    * ``read_data(DataKeys.CURRENT)`` returns a Gaussian-distributed random
      sample drawn from *mean* ± *std_dev*.
    * ``read_data(DataKeys.VOLTAGE)`` returns the same distribution scaled by
      *voltage_scale* (default 1.0, so identical to CURRENT unless overridden).
    * ``read_data_points`` returns a numpy array of *n_points* samples together
      with synthetic timestamps, mimicking the real ``SCPIDriver`` API.
    * ``write_data`` raises ``KeyError`` for all keys (the real Keithley is
      read-only in current/voltage mode).
    """

    # Mirror the real SCPIDriver DataKeys so callers can use the same enum.
    DataKeys = SCPIDriver.DataKeys

    def __init__(
        self,
        mean: float = 1e-9,
        std_dev: float = 1e-11,
        voltage_scale: float = 1.0,
        name: str = "DummyAmmeter",
    ) -> None:
        """
        :param mean:          Mean current value returned by ``read_data`` (A).
        :param std_dev:       Standard deviation of the simulated current noise (A).
        :param voltage_scale: Multiplicative factor applied when reading VOLTAGE.
        :param name:          Human-readable identifier used in log messages.
        """
        self._mean = mean
        self._std_dev = std_dev
        self._voltage_scale = voltage_scale
        self.name = name
        self._connected = False
        self._connection_lock = asyncio.Lock()

    # --- Connectable ---

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        async with self._connection_lock:
            if self._connected:
                _log.debug("%s is already connected.", self.name)
                return
            _log.info("Connecting %s (mock — no hardware required).", self.name)
            self._connected = True

    async def disconnect(self) -> None:
        async with self._connection_lock:
            if not self._connected:
                _log.debug("%s is already disconnected.", self.name)
                return
            _log.info("Disconnecting %s.", self.name)
            self._connected = False

    # --- DataSource ---

    async def read_data(self, data_key: SCPIDriver.DataKeys) -> float:
        """Returns a normally distributed random sample for CURRENT or VOLTAGE."""
        if not self._connected:
            raise ConnectionError(f"{self.name} is not connected.")
        sample = random.gauss(self._mean, self._std_dev)
        match data_key:
            case SCPIDriver.DataKeys.CURRENT:
                return sample
            case SCPIDriver.DataKeys.VOLTAGE:
                return sample * self._voltage_scale
            case _:
                raise KeyError(
                    f"Read operation for data_key {data_key.name} not implemented."
                )

    async def write_data(self, data_key: SCPIDriver.DataKeys, value: float) -> None:
        raise KeyError(
            f"Write operation for data_key {data_key.name} not implemented "
            f"(DummyAmmeter is read-only)."
        )

    # --- Extra helpers that mirror SCPIDriver.read_data_points ---

    async def read_data_points(
        self,
        data_key: SCPIDriver.DataKeys,
        n_points: int,
        timing: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Returns *n_points* simulated readings plus synthetic timestamps.

        The simulated acquisition takes approximately ``n_points * timing``
        seconds (capped at 0.1 s total so tests stay fast unless overridden).

        :param data_key: Must be ``DataKeys.CURRENT``.
        :param n_points: Number of data points to generate.
        :param timing:   Aperture time per point (seconds) — used to build
                         realistic timestamps but not to actually sleep.
        :returns:        ``(data_array, time_array)`` — both 1-D numpy arrays
                         of length *n_points*.
        """
        if data_key != SCPIDriver.DataKeys.CURRENT:
            raise KeyError(
                f"Read operation for data_key {data_key.name} not implemented."
            )
        if not self._connected:
            raise ConnectionError(f"{self.name} is not connected.")

        data = np.random.normal(self._mean, self._std_dev, n_points)
        t0 = time.time()
        timestamps = np.array(
            [str(t0 + i * timing) for i in range(n_points)]
        )
        return data, timestamps


# ---------------------------------------------------------------------------
# DummyPLC
# ---------------------------------------------------------------------------

class DummyPLC(DataSource):
    """
    Mock driver for the VenusPLC / VENUSController.

    Implements the full ``DataSource`` interface (``read_data``, ``write_data``)
    and additionally exposes ``get_all_data`` so it can stand in for
    ``VenusPLC`` directly.

    Simulated behaviour
    -------------------
    * All PLC registers are initialised to physically plausible default values.
    * ``write_data`` stores values in memory; ``read_data`` reads them back.
    * ``get_all_data`` returns every register that VenusPLC would expose.
    * Boolean registers (``csd_in_progress``, ``fcv1_in``, …) remain at 0
      until written.
    """

    # Mirror the real VenusPLC DataKeys.
    from ops.ecris.drivers.venus_plc import VenusPLC as _VenusPLC  # local import to avoid cycles

    DataKeys = _VenusPLC.DataKeys
    _PLC_KEYS = _VenusPLC._PLC_KEYS

    # Default register values that look like a plausible quiescent machine state.
    _DEFAULTS: Dict[str, float] = {
        # Beam line
        "batman_field":      0.0,
        "batman_i":          0.0,
        "batman_i_set":      0.0,
        "csd_in_progress":   0,
        "csd_request":       0,
        "csd_custom_request": 0,
        "csd_custom_in_progress": 0,
        "csd_MQ_min":        2.0,
        "csd_MQ_max":        8.0,
        "num_csd_points":    10,
        "extraction_i":      0.0,
        "extraction_v":      18.0,    # kV — typical operating voltage
        "extraction_v_set":  18.0,
        "fcv1_ammeter":      5e-9,    # A — small background current
        "fcv1_ammeter_stdev": 1e-11,
        "fcv1_i":            5e-9,
        "fcv1_in":           1,       # Faraday cup is in the beam by default
        "glaser_1":          0.0,
        "glaser_1_set":      0.0,
        "m_over_q":          4.0,
        "puller_i":          0.0,
        "puller_raw_gap":    10.0,
        "puller_v":          0.0,
        "puller_v_set":      0.0,
        "robin_i":           0.0,
        "robin_i_set":       0.0,
        "slit_south":        0.0,
        "slit_north":        0.0,
        "tuner_number":      1,
        "peaking_request":   0,
        "peaking_in_progress": 0,
        # Cryostat
        "bottom_ln_vessel":  77.0,
        "cryo_vac_torr":     1e-7,
        "fifty_k_cond_bar":  50.0,
        "fifty_k_cond_bar_ne": 50.0,
        "fifty_k_cond_bar_nw": 50.0,
        "fifty_k_shield_bot": 50.0,
        "four_k_cold_mass":  4.2,
        "four_k_cryo_e":     4.2,
        "four_k_cryo_ne":    4.2,
        "four_k_cryo_nw":    4.2,
        "four_k_cryo_w":     4.2,
        "four_k_heat_cond":  4.2,
        "four_k_heater_k":   4.2,
        "four_k_heater_power": 0.0,
        "four_k_i_feedthrough": 4.2,
        "LHe_level_percent": 80.0,
        "LHe_level":         40.0,
        "LHe_psi":           2.0,
        "seventy_k_cond_bar": 70.0,
        # Gasses
        "gas_balzer_1":      0.0,
        "gas_balzer_1_set":  0.0,
        "gas_balzer_2":      0.0,
        "gas_balzer_2_set":  0.0,
        "gas_balzer_5":      0.0,
        "gas_balzer_5_set":  0.0,
        "gas_balzer_6":      0.0,
        "gas_balzer_6_set":  0.0,
        "gas_balzer_7":      0.0,
        "gas_balzer_7_set":  0.0,
        "gas_name_1":        1,
        "gas_name_2":        0,
        "gas_name_5":        0,
        "gas_name_6":        0,
        "gas_name_7":        0,
        # Misc
        "permissive":        1,
        "time":              0.0,
        # Ovens
        "ht_oven_i":         0.0,
        "ht_oven_v":         0.0,
        "ind_oven_amps":     0.0,
        "ind_oven_frequency": 0.0,
        "ind_oven_req":      0.0,
        "ind_oven_watts":    0.0,
        "ind_oven_status":   0,
        "lt_oven_1_sp":      20.0,
        "lt_oven_1_temp":    20.0,
        "lt_oven_2_sp":      20.0,
        "lt_oven_2_temp":    20.0,
        # Plasma
        "bias_i":            0.0,
        "bias_v":            0.0,
        "g28_fw":            0.0,
        "g28_req_set":       0.0,
        "k18_2_bodycurrent": 0.0,
        "k18_2_fw":          0.0,
        "k18_2_ref":         0.0,
        "k18_bodycurrent":   0.0,
        "k18_fw":            0.0,
        "k18_fw_set":        0.0,
        "k18_ref":           0.0,
        "klystron_rf_reflected": 0.0,
        "klystron_rf_transmitted": 0.0,
        "x_ray_exit":        0.0,
        "x_ray_source":      0.0,
        # Superconductor
        "ext_i":             0.0,
        "ext_i_set":         0.0,
        "ext_ps_v":          0.0,
        "ext_v":             0.0,
        "inj_i":             0.0,
        "inj_i_set":         0.0,
        "inj_ps_v":          0.0,
        "inj_v":             0.0,
        "mid_i":             0.0,
        "mid_i_set":         0.0,
        "mid_ps_v":          0.0,
        "mid_v":             0.0,
        "sext_i":            0.0,
        "sext_i_set":        0.0,
        "sext_ps_v":         0.0,
        "sext_v":            0.0,
        # Vacuum
        "bl_mig2_torr":      1e-7,
        "ext_mbar":          1e-7,
        "inj_mbar":          1e-7,
    }

    def __init__(self, initial_values: Optional[Dict[str, float]] = None) -> None:
        """
        :param initial_values: Optional mapping of register-name → value that
                               overrides the built-in defaults.  Unknown keys
                               are silently added to the register bank.
        """
        self._registers: Dict[str, float] = dict(self._DEFAULTS)
        if initial_values:
            self._registers.update(initial_values)
        self._lock = asyncio.Lock()

    # --- DataSource ---

    async def read_data(self, data_key: "DummyPLC.DataKeys") -> float:
        async with self._lock:
            try:
                reg_name = self._PLC_KEYS[data_key]
            except KeyError:
                raise KeyError(
                    f"Read operation for data_key {data_key.name} not implemented."
                )
            if reg_name not in self._registers:
                raise KeyError(f"PLC register '{reg_name}' not found in DummyPLC.")
            self._registers["time"] = time.time()
            return self._registers[reg_name]

    async def write_data(self, data_key: "DummyPLC.DataKeys", value: float) -> None:
        async with self._lock:
            try:
                reg_name = self._PLC_KEYS[data_key]
            except KeyError:
                raise KeyError(
                    f"Write operation for data_key {data_key.name} not implemented."
                )
            _log.debug("DummyPLC: writing %s = %s", reg_name, value)
            self._registers[reg_name] = value

    # --- Extra helpers that mirror VenusPLC.get_all_data ---

    async def get_all_data(self) -> Dict[int, Tuple[str, float]]:
        """
        Returns every register in the dummy PLC bank, keyed by index.

        The return format matches ``VenusPLC.get_all_data``:
        ``{index: (register_name, value)}``.
        """
        async with self._lock:
            self._registers["time"] = time.time()
            return {
                idx: (name, value)
                for idx, (name, value) in enumerate(self._registers.items())
            }

    # --- Direct register access (useful in tests) ---

    def set_register(self, register_name: str, value: float) -> None:
        """Write directly to a named register — no async required."""
        self._registers[register_name] = value

    def get_register(self, register_name: str) -> float:
        """Read directly from a named register — no async required."""
        return self._registers[register_name]


# ---------------------------------------------------------------------------
# DummyMotor
# ---------------------------------------------------------------------------

class DummyMotor:
    """
    Mock driver for the ``MotorController`` (ACR74C stepper-motor controller).

    Implements the same async public API as ``MotorController`` so it can be
    used wherever the real controller is expected, without any network
    connection.

    Simulated behaviour
    -------------------
    * Each axis starts at position 0.0 (configurable via *initial_positions*).
    * ``move_to_position`` updates the in-memory position after a short
      configurable delay that represents travel time (see *move_delay_s*).
    * ``center_axis`` resets an axis to position 0.0 and marks it centered.
    * ``is_axis_clear_to_move`` always returns ``True`` by default; individual
      axes can be blocked via ``set_axis_clear``.
    * The ``connect`` / ``disconnect`` cycle is simulated in memory.
    """

    def __init__(
        self,
        initial_positions: Optional[Dict[Axis, float]] = None,
        move_delay_s: float = 0.05,
        name: str = "DummyMotor",
    ) -> None:
        """
        :param initial_positions: Optional dict mapping ``Axis`` → starting
                                  position (mm).  Defaults to 0.0 for all axes.
        :param move_delay_s:      Simulated travel time per ``move_to_position``
                                  call (seconds).  Keep small for fast tests.
        :param name:              Human-readable identifier used in log messages.
        """
        self._positions: Dict[Axis, float] = {a: 0.0 for a in Axis}
        if initial_positions:
            self._positions.update(initial_positions)

        self._centered: Dict[Axis, bool] = {a: False for a in Axis}
        self._axis_clear: Dict[Axis, bool] = {a: True for a in Axis}
        self._move_delay_s = move_delay_s
        self.name = name
        self._connected = False
        self._connection_lock = asyncio.Lock()
        self._move_lock = asyncio.Lock()

    # --- Connectable ---

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        async with self._connection_lock:
            if self._connected:
                _log.debug("%s already connected.", self.name)
                return
            _log.info("Connecting %s (mock — no hardware required).", self.name)
            self._connected = True

    async def disconnect(self) -> None:
        async with self._connection_lock:
            if not self._connected:
                _log.debug("%s already disconnected.", self.name)
                return
            _log.info("Disconnecting %s.", self.name)
            self._connected = False

    # --- MotorController public API ---

    def is_centered(self, axis: Axis) -> bool:
        """Returns ``True`` if *axis* has been centered (homed)."""
        return self._centered[axis]

    async def get_position(self, axis: Axis) -> float:
        """Returns the current simulated position of *axis* in mm."""
        return self._positions[axis]

    async def get_scale(self) -> float:
        """Returns a fixed scale value matching the real controller default."""
        return 19685.0  # steps/mm — typical ACR74C configuration

    async def is_axis_clear_to_move(self, axis: Axis) -> bool:
        """Returns the configured clear-to-move flag for *axis*."""
        async with self._move_lock:
            return self._axis_clear[axis]

    async def move_to_position(
        self, axis: Axis, position: float, *, relative: bool = False
    ) -> None:
        """
        Moves *axis* to *position* (or by *position* if *relative* is True).

        Acquires the same move-lock as the real controller, waits
        *move_delay_s* to simulate travel time, then updates the stored
        position.

        :raises ConnectionError: If the motor is not connected.
        :raises RuntimeError:    If the perpendicular axis is not clear and
                                 cannot be moved out of the way (mirrors the
                                 real controller's safety interlock behaviour).
        """
        if not self._connected:
            raise ConnectionError(f"{self.name} is not connected.")
        async with self._move_lock:
            await self._move_to_position_unsafe(axis, position, relative=relative)

    async def _move_to_position_unsafe(
        self, axis: Axis, position: float, *, relative: bool = False
    ) -> None:
        """Internal move without acquiring the move-lock (caller must hold it)."""
        if not self._axis_clear[axis]:
            perp = PERPENDICULAR_AXIS[axis]
            _log.debug(
                "DummyMotor: axis %s not clear, moving perpendicular %s out of the way.",
                axis, perp,
            )
            await self._move_to_position_unsafe(perp, 200.0)
            if not self._axis_clear[axis]:
                raise RuntimeError(
                    f"DummyMotor: perpendicular axis {perp} could not be cleared."
                )

        target = (self._positions[axis] + position) if relative else position
        _log.debug("DummyMotor: moving %s → %.4f mm.", axis, target)
        await asyncio.sleep(self._move_delay_s)
        self._positions[axis] = target

    async def move_axis_to_positive_eof(self, axis: Axis) -> None:
        """Moves *axis* to the positive end-of-travel limit (200 mm)."""
        async with self._move_lock:
            await self._move_to_position_unsafe(axis, 200.0)

    async def center_axis(self, axis: Axis) -> None:
        """
        Homes *axis* to its mechanical centre, mirroring the real homing
        sequence (move to negative EOF, then offset to midpoint, then zero
        the encoder).

        After this call ``is_centered(axis)`` returns ``True`` and
        ``get_position(axis)`` returns ``0.0``.
        """
        if not self._connected:
            raise ConnectionError(f"{self.name} is not connected.")
        async with self._move_lock:
            if not self._axis_clear[axis]:
                perp = PERPENDICULAR_AXIS[axis]
                await self._move_to_position_unsafe(perp, 200.0)
                if not self._axis_clear[axis]:
                    raise RuntimeError(
                        f"DummyMotor: cannot center {axis}, perpendicular axis not clear."
                    )
            if self._centered[axis]:
                _log.debug("DummyMotor: %s already centered, moving to 0.", axis)
                await self._move_to_position_unsafe(axis, 0.0)
                return
            # Simulate: go to negative EOF, then move offset, then reset encoder.
            await self._move_to_position_unsafe(axis, -200.0)
            await self._move_to_position_unsafe(axis, MID_POINT_OFFSETS[axis], relative=True)
            # "Reset axis" sets the encoder origin to the current position.
            self._positions[axis] = 0.0
            self._centered[axis] = True
            _log.info("DummyMotor: axis %s centered.", axis)

    # --- Test helpers ---

    def set_axis_clear(self, axis: Axis, clear: bool) -> None:
        """
        Programmatically block or unblock an axis (simulates a physical
        obstruction interlock).  Useful for testing error-handling paths.
        """
        self._axis_clear[axis] = clear

    def set_position(self, axis: Axis, position: float) -> None:
        """Directly set the stored position of *axis* without simulating travel."""
        self._positions[axis] = position


# ---------------------------------------------------------------------------
# DummyLabJack
# ---------------------------------------------------------------------------

class DummyLabJack(SessionDriver):
    """
    Mock driver for the LabJack T8 (``DeflectionPlateController``).

    Implements the full ``SessionDriver`` interface and mirrors the
    ``LabJack.DataKeys`` enum so it can be used as a drop-in replacement.

    Simulated behaviour
    -------------------
    * ``write_data(DAC0 | DAC1, voltage)`` stores the voltage in memory.
    * ``read_data(AIN0)`` returns the last voltage written to DAC0 plus a
      small amount of Gaussian noise (simulating ADC measurement of the
      output, which is the typical use-case for the real hardware).
    * DAC channels are initialised to ``0.0 V``.
    """

    from ops.ecris.drivers.labjack import LabJack as _LabJack  # local import

    DataKeys = _LabJack.DataKeys

    def __init__(
        self,
        ain0_noise_std: float = 0.001,
        name: str = "DummyLabJack",
    ) -> None:
        """
        :param ain0_noise_std: Standard deviation of Gaussian noise added to
                               AIN0 reads (Volts).  Set to 0 for noiseless
                               reads.
        :param name:           Human-readable identifier used in log messages.
        """
        self._ain0_noise_std = ain0_noise_std
        self.name = name
        self._connected = False
        self._connection_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()

        # In-memory register bank: key → voltage (V)
        from ops.ecris.drivers.labjack import LabJack
        self._registers: Dict["DummyLabJack.DataKeys", float] = {
            LabJack.DataKeys.DAC0: 0.0,
            LabJack.DataKeys.DAC1: 0.0,
            LabJack.DataKeys.AIN0: 0.0,
        }

    # --- Connectable ---

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        async with self._connection_lock:
            if self._connected:
                _log.debug("%s is already connected.", self.name)
                return
            _log.info("Connecting %s (mock — no hardware required).", self.name)
            self._connected = True

    async def disconnect(self) -> None:
        async with self._connection_lock:
            if not self._connected:
                _log.debug("%s is already disconnected.", self.name)
                return
            _log.info("Disconnecting %s.", self.name)
            self._connected = False

    # --- DataSource ---

    async def write_data(self, data_key: "DummyLabJack.DataKeys", value: float) -> None:
        """Stores *value* (V) in the in-memory register for *data_key*."""
        if not self._connected:
            raise ConnectionError(f"Cannot write, {self.name} not connected.")
        from ops.ecris.drivers.labjack import LabJack
        async with self._write_lock:
            if data_key not in self._registers:
                raise KeyError(
                    f"Write operation for data_key {data_key.name} not implemented."
                )
            if data_key == LabJack.DataKeys.AIN0:
                raise KeyError(
                    f"Write operation for data_key {data_key.name} not implemented "
                    f"(AIN0 is read-only on the real hardware)."
                )
            _log.debug("DummyLabJack: writing %s = %.4f V", data_key.name, value)
            self._registers[data_key] = value

    async def read_data(self, data_key: "DummyLabJack.DataKeys") -> float:
        """
        Returns the stored voltage for *data_key*.

        For ``AIN0`` the returned value is the last DAC0 output plus a small
        Gaussian noise term (simulating the feedback read-back path used in the
        real emittance-scanner setup).
        """
        if not self._connected:
            raise ConnectionError(f"Cannot read, {self.name} not connected.")
        from ops.ecris.drivers.labjack import LabJack
        if data_key not in self._registers:
            raise KeyError(
                f"Read operation for data_key {data_key.name} not implemented."
            )
        if data_key == LabJack.DataKeys.AIN0:
            # Simulate reading back the voltage at the output of DAC0.
            dac0_voltage = self._registers[LabJack.DataKeys.DAC0]
            return dac0_voltage + random.gauss(0.0, self._ain0_noise_std)
        return self._registers[data_key]

    # --- Test helpers ---

    def get_dac_voltage(self, data_key: "DummyLabJack.DataKeys") -> float:
        """Read the stored voltage for *data_key* synchronously (for assertions in tests)."""
        return self._registers[data_key]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class DriverFactory:
    """
    A bundle of callables (factories) that produce either real or mock drivers.

    Obtain an instance via ``get_driver_factory(test_mode=…)`` rather than
    constructing this class directly.

    Each attribute is a zero-argument callable that returns a fresh driver
    instance.  In test mode the callables return the corresponding ``Dummy*``
    class; in production mode they return the real hardware class.

    Example usage::

        factory = get_driver_factory(test_mode=True)

        # Create mock drivers
        ammeter_driver = factory.ammeter()
        plc_driver     = factory.plc()
        motor_driver   = factory.motor_controller()
        labjack_driver = factory.labjack()
    """

    def __init__(
        self,
        ammeter_cls,
        plc_cls,
        motor_controller_cls,
        labjack_cls,
        test_mode: bool,
    ) -> None:
        self._ammeter_cls = ammeter_cls
        self._plc_cls = plc_cls
        self._motor_controller_cls = motor_controller_cls
        self._labjack_cls = labjack_cls
        self.test_mode = test_mode

    def ammeter(self, **kwargs) -> "DummyAmmeter | object":
        """Return a new ammeter driver (real or mock depending on ``test_mode``)."""
        return self._ammeter_cls(**kwargs)

    def plc(self, **kwargs) -> "DummyPLC | object":
        """Return a new PLC driver (real or mock depending on ``test_mode``)."""
        return self._plc_cls(**kwargs)

    def motor_controller(self, **kwargs) -> "DummyMotor | object":
        """Return a new motor-controller driver (real or mock depending on ``test_mode``)."""
        return self._motor_controller_cls(**kwargs)

    def labjack(self, **kwargs) -> "DummyLabJack | object":
        """Return a new LabJack driver (real or mock depending on ``test_mode``)."""
        return self._labjack_cls(**kwargs)

    def __repr__(self) -> str:
        mode = "TEST (mock drivers)" if self.test_mode else "PRODUCTION (real hardware)"
        return f"<DriverFactory mode={mode}>"


def get_driver_factory(test_mode: bool = False) -> DriverFactory:
    """
    Return a :class:`DriverFactory` configured for either test or production use.

    In **test mode** (``test_mode=True``) every factory method returns one of
    the ``Dummy*`` classes defined in this module.  No hardware connections are
    opened and no external packages (``labjack``, ``venus_data_utils``, …) are
    required.

    In **production mode** (``test_mode=False``) the factory methods return the
    real driver classes.  The caller is responsible for supplying any required
    constructor arguments (IP addresses, resource names, …).

    :param test_mode: When ``True``, returns mock drivers.  When ``False``,
                      returns real hardware drivers.
    :returns:         A :class:`DriverFactory` instance.

    Example::

        # In a test
        factory = get_driver_factory(test_mode=True)
        driver  = factory.ammeter(mean=1e-8, std_dev=1e-10)

        # In production
        factory = get_driver_factory(test_mode=False)
        driver  = factory.ammeter()   # returns the real Keithley class
    """
    if test_mode:
        _log.info("get_driver_factory: returning MOCK drivers (test_mode=True).")
        return DriverFactory(
            ammeter_cls=DummyAmmeter,
            plc_cls=DummyPLC,
            motor_controller_cls=DummyMotor,
            labjack_cls=DummyLabJack,
            test_mode=True,
        )

    # Production: import real drivers.  We do this lazily inside the function
    # so that the mock module itself never hard-depends on optional hardware
    # packages like ``labjack`` or ``venus_data_utils``.
    _log.info("get_driver_factory: returning REAL drivers (test_mode=False).")

    from ops.ecris.drivers.keithley import Keithley
    from ops.ecris.drivers.venus_plc import VenusPLC
    from ops.ecris.devices.motor_controller import MotorController
    from ops.ecris.drivers.labjack import LabJack

    return DriverFactory(
        ammeter_cls=Keithley,
        plc_cls=VenusPLC,
        motor_controller_cls=MotorController,
        labjack_cls=LabJack,
        test_mode=False,
    )
