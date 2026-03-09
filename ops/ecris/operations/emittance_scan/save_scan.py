# Save emittance scans to an hdf5 file with metadata
import dataclasses
import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import h5py
import numpy as np

from .parameters import LinearScanParameters


def save_emittance_scan(
    filepath: Path | str,
    data: np.ndarray,
    parameters: LinearScanParameters,
    additional_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Saves an emittance scan 2D array and its configuration parameters to an HDF5 file.

    Args:
        filepath: The destination path for the .h5 file.
        data: The 2D numpy array containing the scan results.
        parameters: The LinearScanParameters dataclass used to generate the scan.
        additional_metadata: Optional dictionary for extra info (e.g., operator name, notes).
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if filepath.suffix not in [".h5", ".hdf5"]:
        filepath = filepath.with_suffix(".h5")

    with h5py.File(filepath, "w") as f:
        dset = f.create_dataset("scan_data", data=data, compression="gzip")
        attributes = dataclasses.asdict(parameters)
        attributes["time_saved"] = datetime.datetime.now().isoformat()

        if additional_metadata is not None:
            attributes.update(additional_metadata)

        for key, value in attributes.items():
            dset.attrs[key] = _clean_value_for_hdf5(value)


def _clean_value_for_hdf5(value: Any) -> Any:
    """
    Helper to convert Python objects (Enums, None) into HDF5-compatible types.
    """
    if isinstance(value, Enum):
        return value.name
    if value is None:
        return "None"
    if isinstance(value, (list, tuple)):
        return str(value)
    return value
