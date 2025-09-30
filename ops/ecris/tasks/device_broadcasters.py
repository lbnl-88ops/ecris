from ops.ecris.devices import VenusPLC
from ops.ecris.model.measurement import CurrentMeasurement

async def update_plc_average_current(venus_plc: VenusPLC, current: CurrentMeasurement) -> None:
    await venus_plc.write_data(VenusPLC.DataKeys.AVERAGE_CURRENT, current.average)
    await venus_plc.write_data(VenusPLC.DataKeys.CURRENT_STDEV, current.standard_deviation)