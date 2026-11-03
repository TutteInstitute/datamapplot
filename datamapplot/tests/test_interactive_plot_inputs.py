import numpy as np

from datamapplot import create_interactive_plot


def test_marker_alpha_array_is_not_modified():
    coords = np.random.RandomState(0).rand(100, 2) * 10
    labels = ["Cluster A"] * 30 + ["Cluster B"] * 40 + ["Cluster C"] * 30
    marker_alpha_array = np.full(len(labels), 0.5)

    create_interactive_plot(coords, labels, marker_alpha_array=marker_alpha_array)

    np.testing.assert_array_equal(marker_alpha_array, np.full(len(labels), 0.5))
