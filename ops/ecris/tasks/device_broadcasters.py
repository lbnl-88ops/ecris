from ops.ecris.drivers.venus_plc import VenusPLC
from ops.ecris.drivers.measurement import AverageMeasurement


async def update_plc_average_current(venus_plc: VenusPLC, current: AverageMeasurement) -> None:
    await venus_plc.write_data(VenusPLC.DataKeys.AVERAGE_CURRENT, current.average)
    await venus_plc.write_data(VenusPLC.DataKeys.CURRENT_STDEV, current.standard_deviation)

