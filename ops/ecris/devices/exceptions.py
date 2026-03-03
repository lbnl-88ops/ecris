class DeviceError(RuntimeError):
    pass


class DeviceMalfunctionError(DeviceError):
    pass

class InterlockError(RuntimeError):
    pass
