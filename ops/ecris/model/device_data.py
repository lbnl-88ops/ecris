from dataclasses import dataclass
from collections import OrderedDict
from typing import Dict, List, Tuple

@dataclass
class DataLabel:
    label: str
    units: str | None
    key: str

    def label_with_units(self, include_tag: bool = False) -> str:
        labels = [self.label]

        if self.units is not None:
            labels.append(f'({self.units})')
        if include_tag:
            labels.append(f'[{self.key}]')
        return ' '.join(labels)

class DeviceData:
    def __init__(self, labels: Dict[str, List[Tuple[str, str | None, str]]]):
        self._raw_labels = labels

    @property
    def labels(self) -> List[DataLabel]:
        return [
            DataLabel(label=f"{category} {data}", units=units, key=key)
            for category, key_data_pairs in self._raw_labels.items()
            for data, units, key in key_data_pairs
        ]

    @property
    def labels_by_category(self) -> Dict[str, List[DataLabel]]:
        return {
            category: [
                DataLabel(label=data, units=units, key=key)
                for data, units, key in key_data_pairs
            ]
            for category, key_data_pairs in self._raw_labels.items()}

    @property
    def labels_by_key(self) -> Dict[str, DataLabel]:
        return {d.key: d for d in self.labels}

