"""Tests for cluster boundary polygon generation, especially for tiny clusters.

Clusters with 0, 1 or 2 points (or degenerate/collinear point sets) cannot
produce a meaningful alpha shape. These should be handled gracefully rather
than raising.
"""

import warnings

import numpy as np
import pytest

from datamapplot.alpha_shapes import create_boundary_polygons, smooth_polygon
from datamapplot.interactive_helpers import label_text_and_polygon_dataframes


@pytest.mark.parametrize("n_points", [0, 1, 2])
def test_create_boundary_polygons_tiny_cluster(n_points):
    """Too few points to triangulate -> no polygons, a warning, no exception."""
    points = np.zeros((n_points, 2), dtype=np.float64)
    simplices = np.empty((0, 3), dtype=np.int32)

    with pytest.warns(UserWarning, match="too small to form a boundary"):
        assert create_boundary_polygons(points, simplices, alpha=1.0) == []


def test_create_boundary_polygons_alpha_too_low_still_raises():
    """A genuinely too-small alpha must still tell the user what went wrong."""
    from scipy.spatial import Delaunay

    rng = np.random.default_rng(42)
    points = rng.normal(size=(50, 2))
    simplices = Delaunay(points).simplices

    with pytest.raises(ValueError, match="polygon_alpha"):
        create_boundary_polygons(points, simplices, alpha=1e-8)


@pytest.mark.parametrize(
    "polygon",
    [
        np.empty((0, 2)),
        np.array([[0.0, 0.0]]),
        np.array([[0.0, 0.0], [0.0, 0.0]]),  # single vertex, closed
        np.array([[0.0, 0.0], [1.0, 1.0], [0.0, 0.0]]),  # two vertices, closed
        np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]),  # triangle
        np.array([[0.0, 0.0], [0.0, 0.0], [1.0, 0.0], [0.0, 0.0]]),  # duplicates
    ],
)
def test_smooth_polygon_degenerate(polygon):
    """Degenerate polygons must not blow up the spline fit."""
    result = smooth_polygon(polygon)
    assert result.ndim == 2 and result.shape[1] == 2
    assert np.all(np.isfinite(result))


def test_smooth_polygon_normal_case():
    """Regression: ordinary polygons are still smoothed and up-sampled."""
    theta = np.linspace(0, 2 * np.pi, 12, endpoint=False)
    polygon = np.vstack([np.cos(theta), np.sin(theta)]).T
    polygon = np.vstack([polygon, polygon[0]])

    result = smooth_polygon(polygon)
    assert result.shape[0] > polygon.shape[0]
    assert np.all(np.isfinite(result))


@pytest.mark.parametrize("n_points", [1, 2, 3])
def test_label_dataframe_with_tiny_cluster(n_points):
    """A tiny cluster alongside a normal one must not break polygon building."""
    rng = np.random.default_rng(0)
    big = rng.normal(size=(100, 2))
    tiny = np.array([[10.0 + 0.1 * i, 10.0] for i in range(n_points)])
    coords = np.vstack([big, tiny])
    labels = np.array(["big"] * 100 + ["tiny"] * n_points)

    with pytest.warns(UserWarning) as warned:
        df = label_text_and_polygon_dataframes(
            labels, coords, cluster_polygons=True, alpha=0.5
        )
    messages = " ".join(str(w.message) for w in warned)
    assert "tiny" in messages
    assert "fewer than three points" in messages or "degenerate" in messages

    big_polygon = df.loc[df["label"] == "big", "polygon"].iloc[0]
    assert big_polygon is not None and len(big_polygon[0]) > 3
    assert df.loc[df["label"] == "tiny", "polygon"].iloc[0] is None


def test_label_dataframe_all_tiny_clusters():
    """Every cluster being tiny is degenerate but must not raise."""
    coords = np.array(
        [[0.0, 0.0], [0.1, 0.0], [5.0, 5.0], [5.0, 5.1]], dtype=np.float64
    )
    labels = np.array(["a", "a", "b", "b"])

    with pytest.warns(UserWarning, match="fewer than three points"):
        df = label_text_and_polygon_dataframes(
            labels, coords, cluster_polygons=True, alpha=0.5
        )
    assert len(df) == 2


def test_no_warning_when_every_cluster_has_a_boundary():
    """Healthy clusters must stay quiet."""
    rng = np.random.default_rng(1)
    coords = np.vstack([rng.normal(size=(100, 2)), rng.normal(size=(100, 2)) + 10])
    labels = np.array(["a"] * 100 + ["b"] * 100)

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        df = label_text_and_polygon_dataframes(
            labels, coords, cluster_polygons=True, alpha=0.5
        )

    assert all(polygon is not None for polygon in df["polygon"])


def test_warning_lists_a_bounded_number_of_clusters():
    """Many tiny clusters give one warning, not one per cluster."""
    coords = np.array([[float(i), 0.0] for i in range(20)])
    labels = np.array([f"c{i}" for i in range(20)])

    with pytest.warns(UserWarning) as warned:
        label_text_and_polygon_dataframes(
            labels, coords, cluster_polygons=True, alpha=0.5
        )

    polygon_warnings = [w for w in warned if "boundary" in str(w.message)]
    assert len(polygon_warnings) == 1
    assert "15 more" in str(polygon_warnings[0].message)
