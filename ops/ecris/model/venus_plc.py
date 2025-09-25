import asyncio
from typing import Any, Dict, List

#from venus_data_utils.venusplc as import VENUSController

class VENUSController:
    def __init__(self, read_only: bool):
        pass
    def write(self, data: Dict[str, float]) -> None:
        print(f'Wrote to VENUS Controller: {data}')
    def read(self, data: List[str]) -> float | Dict[str, float]:
        raise NotImplementedError('VENUSController is not an implemented class')

class VenusPLC:
    def __init__(self, *args, **kwargs):
        self._sync_venus = VENUSController(*args, **kwargs)

    async def write(self, data: Dict[str, Any]) -> None:
        """
        Asynchronously writes data to the PLC.
        """
        await asyncio.to_thread(self._sync_venus.write, data)

    async def read(self, register: List[str]) -> float | Dict[str, float]:
        """
        Asynchronously reads data from a PLC register.
        """
        return await asyncio.to_thread(self._sync_venus.read, register)
