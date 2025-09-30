from dataclasses import dataclass

@dataclass(frozen=True)
class Measurement():
    source: str

@dataclass(frozen=True)
class CurrentMeasurement(Measurement):
    average: float
    standard_deviation: float