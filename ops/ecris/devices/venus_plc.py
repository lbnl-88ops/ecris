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

VENUS_PLC_DATA_DEFINITIONS = DeviceData({
        "Vacuum": [
            ("Injection", "mbar", "inj_mbar"),
            ("Extraction", "mbar", "ext_mbar"),
            ("Beamline", "torr", "bl_mig2_torr"),
        ],
        "Superconductor": [
            ("Injection I", "A", "inj_i"),
            ("Middle I", "A", "mid_i"),
            ("Extraction I", "A", "ext_i"),
            ("Sextapole i", "A", "sext_i"),
        ],
        "High-Voltage": [
            ("Extraction V", "V", "extraction_v"),
            ("Extraction I", "A", "extraction_i"),
            ("Puller V", "V", "puller_v"),
            ("Puller I", "A", "puller_i"),
            ("Biased disk V", "V", "bias_v"),
            ("Biased disk I", "A", "bias_i"),
        ],
        "RF": [
            ("28 GHz, forward", "W", "g28_fw"),
            ("18 GHz (1), forward", "W", "k18_fw"),
            ("18 GHz (1), reflected", "W", "k18_ref"),
            ("18 GHz (2), forward", "W", "k18_2_fw"),
            ("18 GHz (2), reflected", "W", "k18_2_ref"),
        ],
        "Low temperature Oven": [
            ("Oven 1 set-point", "C", "lt_oven_1_sp"),
            ("Oven 1 temperature", "C", "lt_oven_1_temp"),
            ("Oven 2 set-point", "C", "lt_oven_2_sp"),
            ("Oven 2 temperature", "C", "lt_oven_2_temp"),
        ],
        "High temperature oven": [
            ("Resistive I", "A", "ht_oven_i"),
            ("Resistive V", "V", "ht_oven_v"),
            ("Inductive I", "A", "ind_oven_amps"),
            ("Inductive Power", "W", "ind_oven_watts")
        ],
        "Gasses": [entry for i in [1, 2, 5, 6, 7]
                   for entry in [
                    (f"Gas Balzer {i} setting", None, f"gas_balzer_{i}"),
                    (f"Gas Balzer {i} gas", None, f"gas_name_{i}"),
                   ]],
        "Misc": [
            ("Glaser", "A", "glaser_1"),
        ],
    })

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
        
