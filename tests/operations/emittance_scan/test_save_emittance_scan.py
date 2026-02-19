import h5py
import numpy as np
import pytest
from pathlib import Path

from ops.ecris.operations.emittance_scan.save_scan import save_emittance_scan
from ops.ecris.operations.emittance_scan.parameters import LinearScanParameters
from ops.ecris.devices.motor_controller_specification import Axis


def test_save_emittance_scan_creates_file_and_stores_data(tmp_path):
    """
    Verifies that the function creates an HDF5 file, creates missing directories,
    saves the numpy array, and correctly serializes parameters (including Enums).
    """
    save_path = tmp_path / "scans" / "test_scan.h5"

    scan_shape = (20, 10)
    data_to_save = np.random.random(scan_shape)

    params = LinearScanParameters(
        axis=Axis.VenusX,
        position_min=-10.0,
        position_max=10.0,
        position_step=1.0,
        divergence_min=-5.0,
        divergence_max=5.0,
        divergence_step=0.5,
        samples_per_point=100,
    )

    extra_metadata = {"operator": "Test User", "notes": None}

    save_emittance_scan(save_path, data_to_save, params, additional_metadata=extra_metadata)

    assert save_path.exists(), "File was not created"

    with h5py.File(save_path, "r") as f:
        assert "scan_data" in f
        dataset = f["scan_data"]

        # Check array shape and values
        assert dataset.shape == scan_shape
        np.testing.assert_array_equal(dataset[:], data_to_save)

        # Check Attributes (Metadata)
        attrs = dataset.attrs

        # Check simple float values
        assert attrs["position_min"] == -10.0
        assert attrs["samples_per_point"] == 100

        assert "time_saved" in attrs

        # Check Enum conversion (Should be string "VenusX", not the Enum object)
        assert attrs["axis"] == "VenusX"

        # Check extra metadata
        assert attrs["operator"] == "Test User"

        # Check None conversion (Should be string "None")
        assert attrs["notes"] == "None"
