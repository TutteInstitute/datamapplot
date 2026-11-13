import numpy as np

from datamapplot.overlap_computations import text_line_overlaps
from datamapplot.text_placement import fix_crossings


def test_fix_crossings_resumes_scan_after_each_swap():
    # Label 0 swaps more than once in a pass
    label_locations = np.array([[-2.0, 1.0], [1.0, 2.0], [-3.0, -1.0], [0.0, 2.0]])
    text_locations = np.array([[-3.0, -6.0], [0.0, 0.0], [5.0, 0.0], [3.0, -5.0]])

    fix_crossings(text_locations, label_locations)

    np.testing.assert_array_equal(
        text_locations, [[3.0, -5.0], [5.0, 0.0], [-3.0, -6.0], [0.0, 0.0]]
    )


def test_text_line_overlaps_pairs_in_box_then_line_order():
    # Each box is centred on its own text location, as in a real plot. The
    # expected pairs need both box diagonals and leave out each line crossing
    # its own box.
    label_locations = np.array([[-3.0, 2.0], [0.0, -4.0], [-2.0, 2.0]])
    text_locations = np.array([[0.0, -1.0], [-2.0, -4.0], [1.0, 1.0]])
    boxes = np.array(
        [
            # xmin, xmax, ymin, ymax
            [-2.0, 2.0, -4.0, 2.0],
            [-5.0, 1.0, -5.0, -3.0],
            [-1.0, 3.0, -1.0, 3.0],
        ]
    )

    overlaps = text_line_overlaps(text_locations, label_locations, boxes)

    assert overlaps == [(0, 2), (2, 0)]
