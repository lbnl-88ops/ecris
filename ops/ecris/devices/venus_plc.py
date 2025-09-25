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

    def __init__(self, *args, **kwargs):
        self._sync_venus = VENUSController(*args, **kwargs)

    async def write_data(self, data_key: Any, value: float) -> None:
        match data_key:
            case VenusPLC.DataKeys.AVERAGE_CURRENT:
                self._sync_venus.write({'fcv1_ammeter': value})
        raise KeyError(f'Read operation for data_key {data_key.name} not implemented.')

    async def get_data(self, data_key: DataKeys) -> float:
        raise KeyError(f'Read operation for data_key {data_key.name} not implemented.')
    
