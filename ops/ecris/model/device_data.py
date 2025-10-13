from dataclasses import dataclass
from collections import OrderedDict
from typing import Dict, List, Tuple
from functools import cached_property

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
        self._category_by_key_cache: Dict[str, str] | None = None

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

    @cached_property
    def category_by_key(self) -> Dict[str, str]:
        return {label.key: category
            for category, labels in self.labels_by_category.items()
            for label in labels}

    def get_category(self, key: str) -> str:
        try:
            return self.category_by_key[key]
        except KeyError:
            raise KeyError(f"The data key '{key}' was not found in any category.")

