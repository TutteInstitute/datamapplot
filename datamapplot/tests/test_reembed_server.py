"""Tests for the re-embed server."""

import json
import urllib.error
import urllib.request

import numpy as np
import pytest
from sklearn.neighbors import NearestNeighbors

from datamapplot.reembed_server import ReembedServer, pack_arrays, unpack_arrays


def _clustered_vectors(n=3000, dim=16, seed=0):
    rng = np.random.default_rng(seed)
    centers = rng.normal(scale=4.0, size=(12, dim))
    return (centers[rng.integers(12, size=n)] + rng.normal(size=(n, dim))).astype(np.float32)


def _global_knn(vectors, k=30):
    # kneighbors() without X excludes each point itself.
    return NearestNeighbors(n_neighbors=k, metric="cosine").fit(vectors).kneighbors(return_distance=False)


def test_pack_unpack_roundtrip():
    a = np.arange(12, dtype=np.int32).reshape(3, 4)
    b = np.linspace(0, 1, 7, dtype=np.float32)
    payload = pack_arrays({"n": 3}, [("a", a), ("b", b)])
    header, arrays = unpack_arrays(payload)
    assert header["n"] == 3
    np.testing.assert_array_equal(arrays["a"], a)
    np.testing.assert_array_equal(arrays["b"], b)
    # Arrays start 8-byte aligned so the browser can view them without copying.
    head_len = int.from_bytes(payload[:4], "little")
    assert (4 + head_len) % 8 == 0


def test_payload_rejects_bad_ids():
    server = ReembedServer(np.zeros((50, 4)), verbose=False)
    with pytest.raises(ValueError, match="at least"):
        server.reembed_payload(np.arange(5))
    with pytest.raises(ValueError, match="unique"):
        server.reembed_payload(np.r_[np.arange(20), 3])
    with pytest.raises(ValueError, match="range"):
        server.reembed_payload(np.arange(40, 60))


def test_subset_graph_recall():
    pytest.importorskip("pynndescent")
    vectors = _clustered_vectors()
    server = ReembedServer(vectors, knn_indices=_global_knn(vectors), verbose=False)
    rng = np.random.default_rng(1)
    ids = np.sort(rng.choice(len(vectors), 800, replace=False))
    indices, distances = server.subset_graph(ids, rng)
    assert indices.shape == distances.shape == (800, 16)
    assert indices.dtype == np.int32 and distances.dtype == np.float32
    # Rows include the point itself, as in the server's graph.
    exact = (
        NearestNeighbors(n_neighbors=16, metric="cosine")
        .fit(vectors[ids])
        .kneighbors(vectors[ids], return_distance=False)
    )
    recall = np.mean([len(set(row) & set(true)) / 16 for row, true in zip(indices, exact)])
    assert recall > 0.95


def test_http_api():
    pytest.importorskip("pynndescent")
    vectors = _clustered_vectors(n=600)
    server = ReembedServer(
        vectors, knn_indices=_global_knn(vectors), token="secret", verbose=False
    ).start(port=0)
    auth = {"Authorization": "Bearer secret"}

    def request(path, data=None, headers=auth, method=None):
        return urllib.request.urlopen(
            urllib.request.Request(server.url + path, data=data, headers=headers, method=method),
            timeout=60,
        )

    try:
        with pytest.raises(urllib.error.HTTPError) as error:
            request("/api/info", headers={})
        assert error.value.code == 401
        assert json.load(request("/api/info"))["n"] == 600

        ids = np.arange(0, 600, 3, dtype="<i4")
        response = request("/api/reembed?sample=60", data=ids.tobytes(), method="POST")
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        header, arrays = unpack_arrays(response.read())
        assert header["n"] == 200 and header["seeded"]
        assert arrays["knn_indices"].shape == (200, 16)
        assert arrays["knn_indices"].max() < 200
        assert arrays["sample_local"].shape == (60,)
        assert arrays["sample_knn_indices"].max() < 60

        with pytest.raises(urllib.error.HTTPError) as error:
            request("/api/reembed", data=np.zeros(20, dtype="<i4").tobytes(), method="POST")
        assert error.value.code == 400

        preflight = request("/api/reembed", headers={}, method="OPTIONS")
        assert preflight.status == 204
        assert preflight.headers["Access-Control-Allow-Private-Network"] == "true"

        server.serve_figure("<html>map</html>")
        page = request("/", headers={})
        assert page.read() == b"<html>map</html>"
        assert page.headers["Access-Control-Allow-Origin"] is None
    finally:
        server.stop()
