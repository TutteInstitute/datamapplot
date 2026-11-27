"""Tests for the re-embed server."""

import json
import time
import urllib.error
import urllib.request
import zipfile

import numpy as np
import pandas as pd
import pytest
from sklearn.neighbors import NearestNeighbors

from datamapplot.reembed_server import (
    ReembedServer,
    _load_vectors,
    encode_knn,
    main,
    pack_arrays,
    unpack_arrays,
)


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


def test_encode_knn_roundtrip():
    rng = np.random.default_rng(0)
    n, width = 500, 8
    indices = np.concatenate([np.arange(n)[:, None], rng.integers(0, n, (n, width - 1))], axis=1)
    distances = np.sort(rng.random((n, width)).astype(np.float32), axis=1)
    distances[:, 0] = 0
    distances[1, 1:3] = [-1e-7, 6e-8]  # rounding noise around a duplicate
    distances[2, 1:4] = distances[2, 4]  # ties
    distances[3, 1:] = distances[3, 1:][::-1].copy()  # unsorted row
    payload = pack_arrays({}, encode_knn("knn", indices, distances))
    assert len(payload) < (indices.astype(np.int32).nbytes + distances.nbytes) * 0.6
    header, arrays = unpack_arrays(payload)
    step = header["arrays"][1]["step"]
    order = np.argsort(distances, axis=1, kind="stable")
    sorted_indices = np.take_along_axis(indices, order, axis=1)
    sorted_distances = np.take_along_axis(np.maximum(distances, 0), order, axis=1)
    got_i, got_d = arrays["knn_indices"], arrays["knn_distances"]
    assert got_i.dtype == np.int32 and got_d.dtype == np.float32
    np.testing.assert_array_equal(got_i[[0] + list(range(4, n))], sorted_indices[[0] + list(range(4, n))])
    assert sorted(got_i[3]) == sorted(indices[3])
    np.testing.assert_allclose(got_d, sorted_distances, atol=step)
    assert (np.diff(got_d, axis=1) >= 0).all()
    assert got_d[1, 1] == 0 and got_d[1, 2] > 0  # noise below 0 -> 0; nonzero stays nonzero
    assert got_d[2, 1] == got_d[2, 2] == got_d[2, 3] == got_d[2, 4]

    distances[0, -1] = np.inf  # not encodable: sent as is
    header, arrays = unpack_arrays(pack_arrays({}, encode_knn("knn", indices, distances)))
    assert "encoding" not in header["arrays"][0]
    np.testing.assert_array_equal(arrays["knn_distances"], distances)


def test_payload_rejects_bad_ids():
    server = ReembedServer(np.zeros((50, 4)), verbose=False, warm_up=False)
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
    assert indices.shape == distances.shape == (800, 15)
    assert indices.dtype == np.int32 and distances.dtype == np.float32
    # Rows include the point itself, as in the server's graph.
    exact = (
        NearestNeighbors(n_neighbors=15, metric="cosine")
        .fit(vectors[ids])
        .kneighbors(vectors[ids], return_distance=False)
    )
    recall = np.mean([len(set(row) & set(true)) / 15 for row, true in zip(indices, exact)])
    assert recall > 0.95
    # Every row is complete with the point itself first, also for the whole set
    # (seed = global graph, no NN-descent iterations) and a tiny, heavily padded subset.
    for subset in (ids, np.arange(len(vectors)), ids[:40]):
        indices, _ = server.subset_graph(subset, rng)
        assert (indices >= 0).all() and (indices[:, 0] == np.arange(len(subset))).all()


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
        info = json.load(request("/api/info"))
        assert info["n"] == 600 and info["id"] == server.id
        # The widget's header (passes through Jupyter's proxy, which uses Authorization itself).
        assert json.load(request("/api/info", headers={"X-Reembed-Token": "secret"}))["id"] == server.id
        assert info["stage"] in ("warming up", "building global kNN graph", "ready")

        ids = np.arange(0, 600, 3, dtype="<i4")
        response = request("/api/reembed?sample=60", data=ids.tobytes(), method="POST")
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        header, arrays = unpack_arrays(response.read())
        assert header["n"] == 200 and header["seeded"]
        for key in ("receiveSeconds", "queueSeconds", "knnSeconds", "encodeSeconds", "serverSeconds"):
            assert header[key] >= 0
        assert header["serverSeconds"] >= header["knnSeconds"]
        assert arrays["knn_indices"].shape == (200, 15)
        assert arrays["knn_indices"].max() < 200
        assert arrays["sample_local"].shape == (60,)
        assert arrays["sample_knn_indices"].max() < 60

        # Compact encoding; ids in any order (local indices follow it).
        shuffled = np.random.default_rng(1).permutation(ids)
        response = request("/api/reembed?sample=60&encoding=varint", data=shuffled.tobytes(), method="POST")
        header, arrays = unpack_arrays(response.read())
        assert header["arrays"][0]["encoding"] == "row-delta-varint"
        indices = arrays["knn_indices"]
        assert indices.shape == (200, 15) and indices.max() < 200
        np.testing.assert_array_equal(indices[:, 0], np.arange(200))
        assert (np.diff(arrays["knn_distances"], axis=1) >= 0).all()
        assert arrays["sample_knn_indices"].shape == (60, 15)
        # Same neighbourhoods as the exact graph, up to NN-descent's approximation.
        exact = NearestNeighbors(n_neighbors=14, metric="cosine").fit(vectors[shuffled]).kneighbors(return_distance=False)
        recall = np.mean([len(set(a[1:]) & set(b)) / 14 for a, b in zip(indices, exact)])
        assert recall > 0.9

        with pytest.raises(urllib.error.HTTPError) as error:
            request("/api/reembed?encoding=zip", data=ids.tobytes(), method="POST")
        assert error.value.code == 400

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


def test_start_default_port_falls_back():
    import socket

    blocker = socket.socket()
    try:
        blocker.bind(("127.0.0.1", 8765))
        blocker.listen()
    except OSError:
        pass  # already taken by something else: just as good
    server = ReembedServer(np.zeros((50, 4)), verbose=False, warm_up=False)
    try:
        server.start()
        assert server.port != 8765
        assert server.url == f"http://127.0.0.1:{server.port}"
        with pytest.raises(OSError):
            ReembedServer(np.zeros((50, 4)), verbose=False, warm_up=False).start(port=server.port)
    finally:
        server.stop()
        blocker.close()


def test_global_knn_cache(tmp_path):
    pytest.importorskip("pynndescent")
    vectors = _clustered_vectors(n=500)
    cache = tmp_path / "global"
    server = ReembedServer(vectors, global_knn_cache=cache, verbose=False)
    for _ in range(600):
        if server.global_graph_ready and (tmp_path / "global.npy").exists():
            break
        time.sleep(0.1)
    assert (tmp_path / "global.npy").exists()
    reloaded = ReembedServer(vectors, global_knn_cache=cache, verbose=False, warm_up=False)
    assert reloaded.global_graph_ready
    np.testing.assert_array_equal(reloaded._global_knn, server._global_knn)


# A saved plot as InteractiveFigure.save writes it with inline_data=False: data files
# (here with a legacy prefix in a subfolder) and density tiles beside it.
SAVED_PLOT = (
    '<div class="container-box reembed-container"></div><script>'
    "[`${originURL}/maps/demo_point_data_0.zip`, `${originURL}/demo_density_L0_R0_C0_x.png`]"
    "</script>"
)


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, response.headers["Content-Type"], response.read()
    except urllib.error.HTTPError as error:
        return error.code, None, None


def test_serve_file_serves_only_referenced_files(tmp_path):
    site = tmp_path / "site"
    (site / "maps").mkdir(parents=True)
    (site / "plot.html").write_text(SAVED_PLOT)
    (site / "maps" / "demo_point_data_0.zip").write_bytes(b"points")
    (site / "demo_density_L0_R0_C0_x.png").write_bytes(b"tile")
    (site / "other_point_data_0.zip").write_bytes(b"not referenced")
    (site / "notes.txt").write_text("private")
    (tmp_path / "outside_point_data_0.zip").write_bytes(b"outside")
    bundle = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle, "w") as zf:
        zf.writestr("index.html", SAVED_PLOT)
        zf.writestr("maps/demo_point_data_0.zip", b"bundled points")

    server = ReembedServer(np.zeros((50, 4)), verbose=False, warm_up=False).start(port=0)
    try:
        server.serve_file(site / "plot.html")
        assert _get(server.url + "/")[2] == SAVED_PLOT.encode()
        # The page requests its files relative to its folder, as "//name" when served at /.
        assert _get(server.url + "//maps/demo_point_data_0.zip")[2] == b"points"
        status, content_type, body = _get(server.url + "/demo_density_L0_R0_C0_x.png")
        assert (status, content_type, body) == (200, "image/png", b"tile")
        for path in ("/other_point_data_0.zip", "/notes.txt", "/plot.html", "/../outside_point_data_0.zip",
                     "/%2e%2e/outside_point_data_0.zip"):
            assert _get(server.url + path)[0] == 404, path

        server.serve_file(bundle)
        assert _get(server.url + "//maps/demo_point_data_0.zip")[2] == b"bundled points"
        server.serve_figure("<html>map</html>")
        assert _get(server.url + "//maps/demo_point_data_0.zip")[0] == 404

        (site / "plain.html").write_text("<html>no widget</html>")
        with pytest.warns(UserWarning, match="no ReembedWidget"):
            server.serve_file(site / "plain.html")
    finally:
        server.stop()


def test_load_vectors(tmp_path):
    vectors = np.arange(12, dtype=np.float32).reshape(4, 3)
    np.save(tmp_path / "v.npy", vectors)
    np.savez(tmp_path / "one.npz", vectors)
    np.savez(tmp_path / "two.npz", a=vectors, b=vectors[:, :2])
    pd.DataFrame({"title": list("abcd"), "embedding": list(vectors)}).to_parquet(tmp_path / "t.parquet")
    pd.DataFrame(vectors, columns=["x", "y", "z"]).to_feather(tmp_path / "wide.feather")

    np.testing.assert_array_equal(_load_vectors(tmp_path / "v.npy"), vectors)
    np.testing.assert_array_equal(_load_vectors(tmp_path / "one.npz"), vectors)
    assert _load_vectors(tmp_path / "two.npz", "b").shape == (4, 2)
    with pytest.raises(ValueError, match="several arrays"):
        _load_vectors(tmp_path / "two.npz")
    np.testing.assert_array_equal(_load_vectors(tmp_path / "t.parquet", "embedding"), vectors)
    with pytest.raises(ValueError, match="several columns"):
        _load_vectors(tmp_path / "t.parquet")
    np.testing.assert_array_equal(_load_vectors(tmp_path / "wide.feather"), vectors)
    with pytest.raises(ValueError, match="unsupported"):
        _load_vectors(tmp_path / "v.csv")


def test_cli_rejects_unusable_input(tmp_path, capsys):
    pytest.importorskip("pynndescent")
    np.save(tmp_path / "v.npy", np.zeros((50, 4), dtype=np.float32))
    (tmp_path / "plain.html").write_text("<html>no widget</html>")
    (tmp_path / "plot.html").write_text(SAVED_PLOT)
    for args, message in [
        ([str(tmp_path / "plain.html")], "has no re-embed widget"),
        ([str(tmp_path / "plot.html"), "--metric", "nope"], "unknown metric"),
        ([str(tmp_path / "missing.html")], "cannot read the plot"),
    ]:
        with pytest.raises(SystemExit) as exit_info:
            main(args + ["--vectors", str(tmp_path / "v.npy")])
        assert exit_info.value.code == 2
        assert message in capsys.readouterr().err
