import numpy as np

from datamapplot import create_interactive_plot
from datamapplot.interactive_helpers import label_text_and_polygon_dataframes


def test_marker_alpha_array_is_not_modified():
    coords = np.random.RandomState(0).rand(100, 2) * 10
    labels = ["Cluster A"] * 30 + ["Cluster B"] * 40 + ["Cluster C"] * 30
    marker_alpha_array = np.full(len(labels), 0.5)

    create_interactive_plot(coords, labels, marker_alpha_array=marker_alpha_array)

    np.testing.assert_array_equal(marker_alpha_array, np.full(len(labels), 0.5))


def test_topic_tree_ids_and_related_points():
    # Interleaved labels, so each cluster's points are not contiguous, with
    # enough unlabelled points under "A" and "B" to give each one a "Minor
    # subtopics" entry. Seven blocks make the clusters large enough that an
    # unstable grouping of point indices would reorder them.
    n_blocks = 7
    coarse = np.tile(
        np.array(["B", "A", "B", "A", "B", "A", "B", "A", "A"], dtype=object),
        n_blocks,
    )
    fine = np.tile(
        np.array(
            ["b2", "a1", "b1", "Unlabelled", "b2", "a1"] + ["Unlabelled"] * 3,
            dtype=object,
        ),
        n_blocks,
    )
    coords = np.arange(2 * len(fine), dtype=np.float64).reshape(-1, 2)

    parents = [[]]
    coarse_df, fine_df = (
        label_text_and_polygon_dataframes(
            labels,
            coords,
            include_zoom_bounds=True,
            include_related_points=True,
            parents=parents,
        )
        for labels in (coarse, fine)
    )

    def points_with(labels, label, parent=None):
        selected = labels == label
        if parent is not None:
            selected &= coarse == parent
        return np.flatnonzero(selected).tolist()

    assert coarse_df["id"].tolist() == ["base_0", "base_1"]
    assert coarse_df["relatedPoints"].tolist() == [
        points_with(coarse, "A"),
        points_with(coarse, "B"),
    ]
    assert fine_df["label"].tolist() == ["a1", "b1", "b2"] + ["Minor subtopics"] * 2
    assert fine_df["id"].tolist() == [
        "base_0_0",
        "base_1_1",
        "base_1_2",
        "base_0_-1",
        "base_1_-1",
    ]
    assert fine_df["parent"].tolist() == ["base_0", "base_1", "base_1"] + [
        "base_0",
        "base_1",
    ]
    assert fine_df["relatedPoints"].tolist() == [
        points_with(fine, "a1"),
        points_with(fine, "b1"),
        points_with(fine, "b2"),
        points_with(fine, "Unlabelled", parent="A"),
        points_with(fine, "Unlabelled", parent="B"),
    ]
    expected_x = [
        coords[points_with(fine, label), 0].mean() for label in ("a1", "b1", "b2")
    ]
    expected_x += [
        coords[points_with(fine, "Unlabelled", parent), 0].mean() for parent in "AB"
    ]
    np.testing.assert_array_equal(fine_df["x"], expected_x)
    assert parents[0].shape == (2, len(fine))
