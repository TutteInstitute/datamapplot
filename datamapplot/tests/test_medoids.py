"""Tests for the bandit medoid search used to place cluster labels."""

import numba
import numpy as np

from datamapplot.medoids import medoid


def test_medoid_with_tied_candidates():
    points = np.array([[-1.0, 0.0], [1.0, 0.0], [0.0, 0.0], [0.0, 0.0]], dtype=np.float32)
    result = medoid.py_func(points)
    np.testing.assert_array_equal(result, [0.0, 0.0])


@numba.njit
def _seed_numba(seed):
    np.random.seed(seed)


def test_medoid_keeps_searching_when_distinct_candidates_tie():
    points = np.column_stack([np.arange(-7, 8), np.zeros(15)]).astype(np.float32)
    _seed_numba(22)
    np.testing.assert_array_equal(medoid(points), [0.0, 0.0])


def test_medoid_accepts_fortran_ordered_points():
    points = np.asfortranarray(np.column_stack([np.arange(-7, 8), np.zeros(15)]).astype(np.float32))
    _seed_numba(22)
    np.testing.assert_array_equal(medoid(points), [0.0, 0.0])
