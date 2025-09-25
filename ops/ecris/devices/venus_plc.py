import asyncio
from typing import Any, Dict, List
from enum import Enum, auto

from ops.ecris.model.device import Device

#from venus_data_utils.venusplc as import VENUSController

class VENUSController:
    """Dummy class for future import"""
    def __init__(self, read_only: bool):
        pass
    def write(self, data: Dict[str, float]) -> None:
        print(f'Wrote to VENUS Controller: {data}')
    def read(self, data: List[str]) -> float | Dict[str, float]:
        raise NotImplementedError('VENUSController is not an implemented class')

class VenusPLC(Device):
    class DataKeys(Enum):
        AVERAGE_CURRENT = auto()
        CURRENT_STDEV = auto()
        BATMAN_CURRENT = auto()
        EXTRACTION_VOLTAGE = auto()

    def __init__(self, venus_controller: VENUSController):
        self._sync_venus = venus_controller

    async def write_data(self, data_key: Any, value: float) -> None:
        match data_key:
            case VenusPLC.DataKeys.AVERAGE_CURRENT:
                key = 'fcv1_ammeter'
            case VenusPLC.DataKeys.CURRENT_STDEV:
                key = 'fcv1_ammeter_stdev'
            case _:
                raise KeyError(f'Write operation for data_key {data_key.name} not implemented.')
        await asyncio.to_thread(self._sync_venus.write, {key: value})
        return

    async def read_data(self, data_key: DataKeys) -> float:
        raise KeyError(f'Read operation for data_key {data_key.name} not implemented.')
    
