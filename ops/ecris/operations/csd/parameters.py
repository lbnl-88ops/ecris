from dataclasses import dataclass


@dataclass
class CSDParameters:
    """
    Configuration parameters for the Charge State Distribution (CSD) sweep.

    These values replicate the constants and logic found in the legacy
    00_operationFastCSD.py script.
    """

    mq_min: float = 0.84  # M/Q range minimum
    mq_max: float = 8.90  # M/Q range maximum
    n_steps: int = 1200  # Number of sweep points
    dipole_alpha: float = 0.00824  # Magnet geometry constant (dipolealpha)
    dipole_slope: float = 79e-5  # B vs I linear slope (T/A)
    hall_scale: float = 0.4  # T per V on AIN0 (2T = 5V)
    dac_scale: float = 0.04  # V per A on DAC0
    i_max_clamp: float = 250.0  # Absolute maximum dipole current (A)
    slow_ramp_density: int = 3  # Steps per amp for slow transitions (changeslow)
    settle_time: float = 10.0  # Faraday-cup insertion settle time (s)
    field_reset_timeout: float = 7.5  # Max time for field reset closed-loop (s)
    field_reset_step: float = 0.007  # A per step during field reset (resetbatman)
