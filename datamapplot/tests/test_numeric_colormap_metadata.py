import numpy as np

from ..interactive_helpers import array_to_colors


def test_numeric_colormap_records_integer_data():
    # https://github.com/TutteInstitute/datamapplot/issues/161
    float_metadata = {}
    array_to_colors(np.linspace(0.0, 1.0, 10), "viridis", float_metadata)
    assert float_metadata["integerData"] is False

    int_metadata = {}
    array_to_colors(np.arange(10), "viridis", int_metadata)
    assert int_metadata["integerData"] is True

    nan_metadata = {}
    array_to_colors(np.array([1.0, np.nan, 3.0]), "viridis", nan_metadata)
    assert nan_metadata["integerData"] is True
