import numpy as np
import pandas as pd

from ..interactive_helpers import prepare_colormap_data


def test_cluster_layer_colormaps_without_other_colormaps():
    # https://github.com/TutteInstitute/datamapplot/issues/126
    rng = np.random.RandomState(42)
    n = 40
    point_dataframe = pd.DataFrame(
        rng.randint(0, 256, size=(n, 3)), columns=["r", "g", "b"]
    )
    label_layers = [
        np.array(["a", "b"] * (n // 2)),
        np.array(["c", "d", "e", "f"] * (n // 4)),
    ]
    cluster_colormap = {
        "a": "#ff0000",
        "b": "#00ff00",
        "c": "#0000ff",
        "d": "#ffff00",
        "e": "#ff00ff",
        "f": "#00ffff",
    }

    color_metadata, color_data, enable_selector, rawdata = prepare_colormap_data(
        point_dataframe,
        None,
        None,
        None,
        True,
        label_layers,
        cluster_colormap,
        "#999999",
    )

    assert enable_selector
    # the default cluster colouring plus one colormap per label layer
    assert len(color_metadata) == len(label_layers) + 1
    assert len(rawdata) == len(label_layers)
