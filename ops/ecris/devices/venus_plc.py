import asyncio
from logging import getLogger
from typing import Any, Dict, List, Tuple
from enum import Enum, auto
import random

from ops.ecris.model.device import Device
_log = getLogger(__name__)

#from venus_data_utils.venusplc as import VENUSController

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
    
    async def get_all_data(self) -> Dict[int, Tuple[str, float]]:
        data_values: Dict[int, Tuple[str, float]] = {}
        all_data_keys = await asyncio.to_thread(self._sync_venus.read_vars)
        for idx, data_key in enumerate(all_data_keys):
            data_values[idx] = data_key, await asyncio.to_thread(
                self._sync_venus.read, [data_key])
        return data_values

    async def write_data(self, data_key: DataKeys, value: float) -> None:
        try:
            key = self._PLC_WRITE_KEYS[data_key]
        except KeyError:
            raise KeyError(f'Write operation for data_key {data_key.name} not implemented.')
        await asyncio.to_thread(self._sync_venus.write, {key: value})
        return

    async def read_data(self, data_key: DataKeys) -> float:
        match data_key:
            case VenusPLC.DataKeys.EXTRACTION_VOLTAGE:
                key = 'extraction_v'
            case VenusPLC.DataKeys.BATMAN_CURRENT:
                key = 'batman_i_set'
            case _:
                raise KeyError(f'Read operation for data_key {data_key.name} not implemented.')
        value = await asyncio.to_thread(self._sync_venus.read, [key])
        return value
    
