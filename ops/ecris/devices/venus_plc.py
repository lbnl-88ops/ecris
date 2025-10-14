import asyncio
from logging import getLogger
from typing import Any, Dict, List, Tuple
from enum import Enum, auto
import random

from ops.ecris.model.device_data import DeviceData
from ops.ecris.model.device import Device
_log = getLogger(__name__)

try:
    from venus_data_utils.venusplc import VENUSController
except ModuleNotFoundError:
    _log.warning(
    "Could not import VENUSController from venus_data_utils. "
    "Falling back to dummy implementation for development/testing.")

    class VENUSController:
        """Dummy class for future import"""
        def __init__(self, read_only: bool):
            pass
        def write(self, data: Dict[str, float]) -> None:
            _log.debug(f'Wrote to VENUS Controller: {data}')
        def read(self, data: List[str]) -> float:
            match data[0]:
                case 'test_float_1':
                    return 1*random.random()
                case 'test_float_2':
                    return 2*random.random()
                case 'test_bool':
                    return random.randint(0, 1)
            raise NotImplementedError('VENUSController is not an implemented class')
        def read_vars(self) -> List[str]:
            return ['test_float_1', 'test_bool', 'test_float_2']
            raise NotImplementedError('VENUSController is not an implemented class')

VENUS_PLC_DATA_DEFINITIONS = DeviceData(
    {
        "Beam line": [
            ("Batman electromagnet field", "G", "batman_field"),
            ("Batman electromagnet current", "A", "batman_i"),
            ("Batman electromagnet current setpoint", "A", "batman_i_set"),
            ("Boolean indicating CSD is in progress", "boolean", "csd_in_progress"),
            ("Boolean to inform program to take CSD", "boolean", "csd_request"),
            ("Extraction I", "mA", "extraction_i"),
            ("Extraction V", "kV", "extraction_v"),
            ("Extraction V setpoint", "kV", "extraction_v_set"),
            ("Faraday cup current from fast Ammeter", "A", "fcv1_ammeter"),
            ("Faraday cup current on display", "A", "fcv1_i"),
            ("Faraday cup status in beam line (True: in)", "boolean", "fcv1_in"),
            ("Glaser 1 current", "A", "glaser_1"),
            ("Glaser 1 current setpoint", "A", "glaser_1_set"),
            ("M/Q value calculated by PLC", "none", "m_over_q"),
            ("Puller power supply current", "mA", "puller_i"),
            ("Gap between the puller and extraction electrode", "mm", "puller_raw_gap"),
            ("Puller power supply voltage", "kV", "puller_v"),
            ("Puller voltage setpoint", "V", "puller_v_set"),
            ("Robin magnet current", "A", "robin_i"),
            ("Robin magnet current setpoint", "A", "robin_i_set"),
        ],
        "Cryostat": [
            (
                "Temperature at bottom of liquid nitrogen vessel",
                "K",
                "bottom_ln_vessel",
            ),
            ("Cryostat vacuum pressure", "torr", "cryo_vac_torr"),
            ("Conduction bar temperature", "K", "fifty_k_cond_bar"),
            ("Conduction bar temperature", "K", "fifty_k_cond_bar_ne"),
            ("Conduction bar temperature", "K", "fifty_k_cond_bar_nw"),
            ("Conduction shield temperature", "K", "fifty_k_shield_bot"),
            ("Liquid helium temperature", "K", "four_k_cold_mass"),
            ("Liquid helium temperature (east)", "K", "four_k_cryo_e"),
            ("Liquid helium temperature (northeast)", "K", "four_k_cryo_ne"),
            ("Liquid helium temperature (northwest)", "K", "four_k_cryo_nw"),
            ("Liquid helium temperature (west)", "K", "four_k_cryo_w"),
            ("Liquid helium temperature", "K", "four_k_heat_cond"),
            ("Liquid helium temperature", "K", "four_k_heater_k"),
            ("Power added to liquid helium heater", "W", "four_k_heater_power"),
            ("Liquid helium temperature", "K", "four_k_i_feedthrough"),
            (
                "Liquid helium level as percentage of full tank",
                "percentage",
                "LHe_level_percent",
            ),
            ("Liquid helium pressure", "psi", "LHe_psi"),
            ("Conduction bar temperature", "K", "seventy_k_cond_bar"),
        ],
        "Gasses": [
            ("Gas balzer 1 status", "nan", "gas_balzer_1"),
            ("Gas balzer 1 setpoint", "nan", "gas_balzer_1_set"),
            ("Gas balzer 2 status", "nan", "gas_balzer_2"),
            ("Gas balzer 2 setting", "nan", "gas_balzer_2_set"),
            ("Gas balzer 5 status", "nan", "gas_balzer_5"),
            ("Gas balzer 5 setting", "nan", "gas_balzer_5_set"),
            ("Gas balzer 6 status", "nan", "gas_balzer_6"),
            ("Gas balzer 6 setting", "nan", "gas_balzer_6_set"),
            ("Gas balzer 7 status", "nan", "gas_balzer_7"),
            ("Gas balzer 7 setting", "nan", "gas_balzer_7_set"),
            ("Gas Balzer 1 gas label", "nan", "gas_name_1"),
            ("Gas Balzer 2 gas label", "nan", "gas_name_2"),
            ("Gas Balzer 5 gas label", "nan", "gas_name_5"),
            ("Gas Balzer 6 gas label", "nan", "gas_name_6"),
            ("Gas Balzer 7 gas label", "nan", "gas_name_7"),
        ],
        "Misc": [
            ("Boolean for write access", "boolean", "permissive"),
            ("Unix epoch time", "s", "time"),
        ],
        "Ovens": [
            ("High temperature resistive oven current", "A", "ht_oven_i"),
            ("High temperature resistive oven voltage", "V", "ht_oven_v"),
            ("Inductive oven current", "A", "ind_oven_amps"),
            ("Inductive oven frequency", "kHz", "ind_oven_frequency"),
            ("Inductive oven requested current", "A", "ind_oven_req"),
            ("Inductive oven power", "W", "ind_oven_watts"),
            ("Low temperature oven 1 temperature set point", "C", "lt_oven_1_sp"),
            ("Low temperature oven 1 temperature", "C", "lt_oven_1_temp"),
            ("Low temperature oven 2 temperature set point", "C", "lt_oven_2_sp"),
            ("Low temperature oven 2 temperature", "C", "lt_oven_2_temp"),
        ],
        "Plasma": [
            ("Biased disk I", "mA", "bias_i"),
            ("Biased disk V", "V", "bias_v"),
            ("28 GHz input power", "kW", "g28_fw"),
            ("28 GHz power setpoint", "W", "g28_req_set"),
            ("18 GHz (2) troubleshooting diagnostic", "mA", "k18_2_bodycurrent"),
            ("18 GHz (2) forward power", "W", "k18_2_fw"),
            ("18 GHz (2) reflected power", "W", "k18_2_ref"),
            ("18 GHz (1) troubleshooting diagnostic", "nan", "k18_bodycurrent"),
            ("18 GHz (1) forward power", "W", "k18_fw"),
            ("18 GHz power setpoint", "W", "k18_fw_set"),
            ("18 GHz (1) reflected power", "W", "k18_ref"),
            ("nan", "nan", "klystron_rf_reflected"),
            ("nan", "nan", "klystron_rf_transmitted"),
            ("X-rays at the plasma chamber source exit", "mrem", "x_ray_exit"),
            ("X-rays at plasma chamber high voltage cage", "mrem", "x_ray_source"),
        ],
        "Superconductor": [
            ("Extraction coil current", "A", "ext_i"),
            ("Extraction coil current setpoint", "A", "ext_i_set"),
            ("Extraction coil power supply voltage", "V", "ext_ps_v"),
            ("Extraction coil voltage", "V", "ext_v"),
            ("Injection coil current", "A", "inj_i"),
            ("Injection coil current setpoint", "A", "inj_i_set"),
            ("Injection coil power supply voltage", "V", "inj_ps_v"),
            ("Injection coil voltage", "V", "inj_v"),
            ("Middle coil current", "A", "mid_i"),
            ("Middle coil current setpoint", "A", "mid_i_set"),
            ("Middle coil power supply voltage", "V", "mid_ps_v"),
            ("Middle coil voltage", "V", "mid_v"),
            ("Sextapole coil current", "A", "sext_i"),
            ("Sextapole coil current setpoint", "A", "sext_i_set"),
            ("Sextapole coil power supply voltage", "V", "sext_ps_v"),
            ("Sextapole voltage", "V", "sext_v"),
        ],
        "Vacuum": [
            ("Beam line pressure", "torr", "bl_mig2_torr"),
            ("Extraction pressure", "mbar", "ext_mbar"),
            ("Injection pressure", "mbar", "inj_mbar"),
        ],
    }
)

GAS_NAMES = {
    0: 'Cocktail O', 1: '16 O', 2: '17 O', 3: '40 Ar', 4: '36 Ar',
    5: '136 Xe', 6: '124 Xe', 7: 'Xe', 8: '78 Kr', 9: '86 Kr', 
    10: 'Kr', 11: '4 He', 12: '3 He', 13: 'N', 14: '21 Ne', 15: 'Ne'
}

class VenusPLC(Device):
    class DataKeys(Enum):
        AVERAGE_CURRENT = auto()
        CURRENT_STDEV = auto()
        BATMAN_CURRENT = auto()
        EXTRACTION_VOLTAGE = auto()

    _PLC_WRITE_KEYS: Dict[DataKeys, str] = {
        DataKeys.AVERAGE_CURRENT: 'fcv1_ammeter',
        DataKeys.CURRENT_STDEV: 'fcv1_ammeter_stdev',
    }

    def __init__(self, venus_controller: VENUSController):
        self._sync_venus = venus_controller
        self._lock = asyncio.Lock()
    
    async def get_all_data(self) -> Dict[int, Tuple[str, float]]:
        async with self._lock:
            data_values: Dict[int, Tuple[str, float]] = {}
            all_data_keys = await asyncio.to_thread(self._sync_venus.read_vars)
            for idx, data_key in enumerate(all_data_keys):
                data_values[idx] = data_key, await asyncio.to_thread(
                    self._sync_venus.read, [data_key])
            return data_values

    async def write_data(self, data_key: DataKeys, value: float) -> None:
        async with self._lock:
            try:
                key = self._PLC_WRITE_KEYS[data_key]
            except KeyError:
                raise KeyError(f'Write operation for data_key {data_key.name} not implemented.')
            await asyncio.to_thread(self._sync_venus.write, {key: value})
        return

    async def read_data(self, data_key: DataKeys) -> float:
        async with self._lock:
            match data_key:
                case VenusPLC.DataKeys.EXTRACTION_VOLTAGE:
                    key = 'extraction_v'
                case VenusPLC.DataKeys.BATMAN_CURRENT:
                    key = 'batman_i_set'
                case _:
                    raise KeyError(f'Read operation for data_key {data_key.name} not implemented.')
            value = await asyncio.to_thread(self._sync_venus.read, [key])
            return value
        
