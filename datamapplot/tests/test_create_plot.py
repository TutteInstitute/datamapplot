from unittest.mock import patch

import numpy as np
import pytest

import datamapplot as dmp


@pytest.mark.parametrize("n_points", [2, 3])
def test_create_plot_treats_empty_string_labels_as_unlabelled(n_points):
    data_map = np.arange(n_points * 2, dtype=np.float32).reshape(n_points, 2)

    with patch("datamapplot.create_plots.render_plot") as mock_render:
        mock_render.return_value = (None, None)
        dmp.create_plot(data_map, [""] * n_points, use_system_fonts=True)

    _, color_list, label_text, label_locations, label_cluster_sizes = (
        mock_render.call_args.args[:5]
    )
    assert color_list == ["#999999"] * n_points
    assert label_text == []
    np.testing.assert_array_equal(label_locations, np.zeros((0, 2), dtype=np.float32))
    assert label_cluster_sizes.size == 0
