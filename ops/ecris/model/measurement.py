from dataclasses import dataclass

@dataclass(frozen=True)
class Measurement():
    source: str
    timestamp: float

@dataclass(frozen=True)
class ValueMeasurement(Measurement):
    value: float

@dataclass(frozen=True)
class AverageMeasurement(Measurement):
    average: float
    standard_deviation: float
