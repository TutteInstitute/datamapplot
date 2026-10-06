import numpy as np
import pandas as pd

from ..interactive_helpers import array_to_colors


def test_array_to_colors_timezone_aware_datetimes():
    # https://github.com/TutteInstitute/datamapplot/issues/136
    naive = pd.Series(pd.date_range("2025-07-19", periods=5, freq="D"))
    aware = naive.dt.tz_localize("UTC")

    naive_metadata = {}
    naive_colors = array_to_colors(naive, "viridis", naive_metadata)
    aware_metadata = {}
    aware_colors = array_to_colors(aware, "viridis", aware_metadata)

    assert aware_metadata["kind"] == "datetime"
    assert aware_metadata["valueRange"] == naive_metadata["valueRange"]
    np.testing.assert_array_equal(aware_colors, naive_colors)
