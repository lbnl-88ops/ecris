import aiofiles
from pathlib import Path

from ops.ecris.devices.venus_plc import VenusPLC

async def write_datasheet(output_path: Path, venus_plc: VenusPLC) -> None:
     all_data = await venus_plc.get_all_data()
     async with aiofiles.open(output_path, 'w') as f:
          for idx, data in all_data.items():
               data_name, data_value = data
               await f.write(f'{idx:>4} {data_value:.5e} {data_name}\n')
