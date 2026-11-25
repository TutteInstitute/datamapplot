"""Server-side support for live re-embedding with :class:`~datamapplot.widgets.ReembedWidget`.

The browser runs UMAP itself (in WebAssembly, optionally on WebGPU), but it only
has the 2D map coordinates. A :class:`ReembedServer` holds the high-dimensional
vectors and, for each selection the user re-embeds, returns the k-nearest
neighbour graph of just that subset. The graph is built with NN-descent seeded
from a precomputed global kNN graph, which typically takes well under a second
for tens of thousands of points.

Point identity is the row index of the vectors, which must match the row order
of the data map coordinates passed to the plot.

Example
-------
>>> server = ReembedServer(vectors, metric="cosine").start(port=8765)
>>> plot = datamapplot.create_interactive_plot(
...     data_map_coords, labels, widgets=[ReembedWidget(server_url=server.url)]
... )
>>> server.serve_figure(plot)  # open server.url in a browser

Requires ``pynndescent`` (``pip install datamapplot[reembed]``).

REST contract
-------------
``GET /api/info``
    JSON: ``{"stage", "format", "n", "dim", "metric", "k", "ready", "globalGraphReady"}``;
    ``stage`` is "warming up", "building global kNN graph" or "ready".

``POST /api/reembed[?sample=M]``
    Body: little-endian int32 row ids of the selection (unique, at least
    ``k + 2`` of them). Response (``application/octet-stream``): a uint32
    little-endian header length, a JSON header, then the arrays it lists, each
    described by ``name``, ``dtype``, ``shape``, ``offset`` (from the end of the
    header) and ``bytes``:

    * ``knn_indices`` int32 ``(n, k + 1)`` and ``knn_distances`` float32
      ``(n, k + 1)``, indices local to the selection (row ``i`` includes ``i``);
    * with ``0 < M < n``: ``sample_local`` int32 ``(M,)`` (sorted local indices of
      a random sample) plus ``sample_knn_indices`` / ``sample_knn_distances`` for
      the sample, indices local to the sample.

All ``/api/`` endpoints send permissive CORS headers so plots opened from files
or shown in notebooks can call the server; the figure served at ``/`` does not.
"""

import contextlib
import http.server
import json
import socketserver
import struct
import threading
import time
import warnings
import webbrowser
from urllib.parse import parse_qs, urlparse

import numba
import numpy as np

FORMAT = "datamapplot-reembed/1"


def _nndescent_settings(n_samples, n_neighbors):
    """pynndescent settings UMAP 0.6 uses with ``compatibility_layout=False``."""
    return {
        "n_trees": max(4, min(8, 5 + int(round(n_samples**0.5 / 20.0)))),
        "max_candidates": max(20, min(60, int(1.5 * n_neighbors))),
    }


def _seed_iterations(padded_fraction):
    """NN-descent iterations for a seeded subset graph.

    A re-embedding only needs a good, not exact, kNN graph. The seed (the global
    graph restricted to the subset) is already accurate except in rows that had
    to be padded with random candidates, so the number of iterations follows the
    padded fraction. On CORD-19 / 20 Newsgroups lasso-like subsets this keeps
    recall@15 >= ~0.97 while saving 30-60% of the time on large subsets.
    """
    if padded_fraction < 0.005:
        return 0
    if padded_fraction < 0.03:
        return 1
    if padded_fraction < 0.08:
        return 2
    return None  # pynndescent default (log2 n, with early stopping)


@numba.njit(parallel=True)
def _restricted_seed(global_knn, ids, local, fill):
    """The global graph restricted to ``ids`` (as local indices); short rows are
    completed from ``fill`` (random local indices), skipping the row itself and
    duplicates so every row has ``width`` distinct candidates (needs
    ``len(ids) > width``). Returns the seed and the number of filled slots."""
    n, width = fill.shape
    seed = np.empty((n, width), dtype=np.int64)
    padded = np.zeros(n, dtype=np.int64)
    for i in numba.prange(n):
        c = 0
        for j in range(global_knn.shape[1]):
            m = local[global_knn[ids[i], j]]
            if m >= 0:
                seed[i, c] = m
                c += 1
                if c == width:
                    break
        padded[i] = width - c
        for t in range(c, width):
            m = fill[i, t]
            while True:
                fresh = m != i
                for u in range(t):
                    if seed[i, u] == m:
                        fresh = False
                        break
                if fresh:
                    break
                m = (m + 1) % n
            seed[i, t] = m
    return seed, padded.sum()


@numba.njit(parallel=True)
def _seed_distances(data, seed, dist):
    """``dist`` (pynndescent's internal distance) for every seed entry, in parallel:
    pynndescent's own pass over an ``init_graph`` is serial."""
    n, width = seed.shape
    out = np.full((n, width), np.inf, dtype=np.float32)
    for i in numba.prange(n):
        for j in range(width):
            k = seed[i, j]
            if k >= 0 and k != i:
                out[i, j] = dist(data[i], data[k])
    return out


def _require_pynndescent():
    try:
        from pynndescent import NNDescent
    except ImportError as error:  # pragma: no cover - depends on environment
        raise ImportError(
            "ReembedServer requires pynndescent; install it with "
            "`pip install pynndescent` or `pip install datamapplot[reembed]`."
        ) from error
    return NNDescent


def pack_arrays(header, arrays):
    """Encode a JSON header and named arrays in the re-embed binary format.

    Parameters
    ----------
    header : dict
        JSON-serialisable metadata. An ``"arrays"`` entry describing each array
        is added.
    arrays : list of (str, ndarray)
        Arrays to append, in order.

    Returns
    -------
    bytes
    """
    entries = []
    offset = 0
    for name, array in arrays:
        entries.append(
            {
                "name": name,
                "dtype": str(array.dtype),
                "shape": list(array.shape),
                "offset": offset,
                "bytes": int(array.nbytes),
            }
        )
        offset += array.nbytes
    head = json.dumps({**header, "arrays": entries}).encode()
    # Pad so the arrays start 8-byte aligned.
    head += b" " * ((-len(head) - 4) % 8)
    blobs = [np.ascontiguousarray(array).tobytes() for _, array in arrays]
    return b"".join([struct.pack("<I", len(head)), head] + blobs)


def unpack_arrays(payload):
    """Decode the re-embed binary format into ``(header, {name: ndarray})``."""
    (head_len,) = struct.unpack("<I", payload[:4])
    header = json.loads(payload[4 : 4 + head_len])
    base = 4 + head_len
    arrays = {}
    for entry in header["arrays"]:
        start = base + entry["offset"]
        arrays[entry["name"]] = np.frombuffer(
            payload[start : start + entry["bytes"]], dtype=entry["dtype"]
        ).reshape(entry["shape"])
    return header, arrays


class ReembedServer:
    """Serve subset kNN graphs (and optionally a plot) for live re-embedding.

    Parameters
    ----------
    vectors : array-like of shape (n_samples, n_features)
        High-dimensional vectors, row-aligned with the data map coordinates.

    metric : str, optional (default="cosine")
        Any metric supported by pynndescent.

    n_neighbors : int, optional (default=15)
        Neighbours per point (excluding the point itself) in subset graphs.

    knn_indices : array-like of shape (n_samples, k), optional
        A precomputed global kNN graph (for example ``umap_model._knn_indices``)
        used to seed subset graphs. A leading self-column is detected and
        dropped. If not given, a graph with ``global_n_neighbors`` neighbours is
        computed in a background thread when the server starts. Until it is
        ready, requests either wait for it or (when numba's threading layer is
        ``tbb`` or ``omp``, which allow concurrent parallel calls) are computed
        without seeding.

    global_n_neighbors : int, optional (default=30)
        Neighbours in the global graph computed when ``knn_indices`` is None.

    max_threads : int or None, optional (default=None)
        Upper bound on numba threads used per request (default: all cores).
        About one thread per 1,000 selected points is used, up to 16.

    token : str or None, optional (default=None)
        If given, API requests must send ``Authorization: Bearer <token>``
        (use ``ReembedWidget(auth_headers=...)``).

    verbose : bool, optional (default=True)
        Print progress and per-request timings.

    warm_up : bool, optional (default=True)
        Start compiling pynndescent's numba code (about 20 s the first time in a
        process) and building the global graph in the background right away, so
        it overlaps with creating the plot. Otherwise this starts with
        :meth:`start`.
    """

    def __init__(
        self,
        vectors,
        metric="cosine",
        n_neighbors=15,
        knn_indices=None,
        global_n_neighbors=30,
        max_threads=None,
        token=None,
        verbose=True,
        warm_up=True,
    ):
        vectors = np.asarray(vectors)
        if vectors.ndim != 2:
            raise ValueError("vectors must be a 2D array")
        if metric == "cosine":
            # Unit rows (as pynndescent uses internally) on a private copy, so seed
            # distances can be computed directly; cosine distances are unchanged.
            self.vectors = np.array(vectors, dtype=np.float32, order="C", copy=True)
            norms = np.linalg.norm(self.vectors, axis=1, keepdims=True)
            self.vectors /= np.where(norms > 0, norms, 1.0)
        else:
            self.vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        self.metric = metric
        self.n_neighbors = int(n_neighbors)
        self.global_n_neighbors = int(global_n_neighbors)
        self.max_threads = max_threads
        self.token = token
        self.verbose = verbose
        self._global_knn = None
        if knn_indices is not None:
            self._global_knn = self._normalize_knn(knn_indices)
        self._dist_func = None  # pynndescent's internal distance, if seed distances are verified
        self._ready = threading.Event()
        # Re-entrant: reembed_payload holds it around subset_graph calls.
        self._compute_lock = threading.RLock()
        self._html = None
        self._httpd = None
        self._thread = None
        self._background = None
        if warm_up:
            self._start_background()

    def _start_background(self):
        if self._background is None:
            self._background = threading.Thread(target=self._prepare, daemon=True)
            self._background.start()

    # ------------------------------------------------------------------ graphs
    def _log(self, message):
        if self.verbose:
            print(f"[ReembedServer] {message}", flush=True)

    def _normalize_knn(self, knn_indices):
        knn = np.asarray(knn_indices)
        if knn.ndim != 2 or knn.shape[0] != self.vectors.shape[0]:
            raise ValueError("knn_indices must have one row per vector")
        rows = np.arange(knn.shape[0])
        if knn.shape[1] > 1 and np.all(knn[:, 0] == rows):
            knn = knn[:, 1:]
        return np.ascontiguousarray(knn, dtype=np.int64)

    @property
    def ready(self):
        """Whether numba compilation has finished and requests are served quickly."""
        return self._ready.is_set()

    @property
    def global_graph_ready(self):
        """Whether the global kNN graph used for seeding is available."""
        return self._global_knn is not None

    def _prepare(self):
        NNDescent = _require_pynndescent()
        t0 = time.time()
        rng = np.random.default_rng(0)
        warm = rng.normal(size=(2000, 8)).astype(np.float32)
        seed = rng.integers(0, 2000, size=(2000, self.n_neighbors + 1))
        # numba's default "workqueue" threading layer aborts the process on concurrent
        # parallel calls, so background work is serialised with requests unless the
        # layer is thread-safe.
        width = self.n_neighbors + 1
        if self.metric == "cosine":
            warm /= np.linalg.norm(warm, axis=1, keepdims=True)
        with self._compute_lock:
            probe = NNDescent(warm, n_neighbors=width, metric=self.metric, random_state=0)
            probe.neighbor_graph
            self._dist_func = self._verified_distance(NNDescent, probe, warm, seed)
            _restricted_seed(seed, np.arange(2000), np.arange(2000), seed[:, :width])
            thread_safe = numba.threading_layer() in ("tbb", "omp")
        self._ready.set()
        self._log(f"warm-up done in {time.time() - t0:.1f}s")
        if self._global_knn is None:
            t0 = time.time()
            if not thread_safe:
                self._log("requests wait until the global kNN graph is built (numba workqueue threading layer)")
            with self._compute_lock if not thread_safe else contextlib.nullcontext():
                index = NNDescent(
                    self.vectors,
                    n_neighbors=self.global_n_neighbors + 1,
                    metric=self.metric,
                    random_state=0,
                    low_memory=True,
                    **_nndescent_settings(len(self.vectors), self.global_n_neighbors + 1),
                )
                indices, _ = index.neighbor_graph
            self._global_knn = self._normalize_knn(indices)
            self._log(
                f"global {self.global_n_neighbors}-NN graph for {len(self.vectors):,} points "
                f"in {time.time() - t0:.1f}s"
            )

    def _verified_distance(self, NNDescent, probe, data, seed):
        """pynndescent's internal distance function, if seed distances computed with
        it reproduce pynndescent's own initialisation exactly (else None)."""
        try:
            dist = probe._distance_func
            width = self.n_neighbors + 1
            init = seed[:, :width]
            init_dist = _seed_distances(data, init, dist)
            kwargs = dict(n_neighbors=width, metric=self.metric, random_state=0, init_graph=init, n_iters=0)
            with warnings.catch_warnings():
                # The random probe graph leaves some rows short; that is expected here.
                warnings.simplefilter("ignore", UserWarning)
                ours = NNDescent(data, init_dist=init_dist, **kwargs).neighbor_graph
                theirs = NNDescent(data, **kwargs).neighbor_graph
            if np.array_equal(ours[0], theirs[0]) and np.allclose(ours[1], theirs[1], atol=1e-5):
                return dist
        except Exception:  # pragma: no cover - depends on pynndescent internals
            pass
        self._log("seed distances fall back to pynndescent's serial initialisation")
        return None

    def _seed_graph(self, ids, rng):
        """The global graph restricted to ``ids`` (as local indices), short rows
        padded randomly; also returns the padded fraction."""
        n = len(ids)
        width = self.n_neighbors + 1
        local = np.full(self.vectors.shape[0], -1, dtype=np.int64)
        local[ids] = np.arange(n)
        fill = rng.integers(0, n, size=(n, width))
        seed, padded = _restricted_seed(self._global_knn, ids, local, fill)
        return seed, padded / (n * width)

    def subset_graph(self, ids, rng=None):
        """kNN graph of a subset of rows.

        Parameters
        ----------
        ids : array-like of int
            Unique row ids.

        rng : numpy Generator, optional

        Returns
        -------
        (indices, distances) : int32 and float32 arrays of shape (len(ids), n_neighbors + 1)
            Neighbour indices are local to ``ids``; each row includes itself.
        """
        NNDescent = _require_pynndescent()
        ids = np.asarray(ids, dtype=np.int64)
        rng = rng if rng is not None else np.random.default_rng()
        limit = self.max_threads or numba.config.NUMBA_NUM_THREADS
        # Thread count is thread-local in numba. Measured on 64 cores: ~1 thread per 1,000
        # points is fastest for small subsets, and more than 16 gains nothing.
        numba.set_num_threads(int(min(limit, max(4, min(16, len(ids) // 1000)))))
        width = self.n_neighbors + 1
        kwargs = _nndescent_settings(len(ids), width)
        with self._compute_lock:
            data = self.vectors[ids]
            if self._global_knn is not None:
                seed, padded_fraction = self._seed_graph(ids, rng)
                kwargs.update(init_graph=seed, n_iters=_seed_iterations(padded_fraction))
                if self._dist_func is not None:
                    kwargs["init_dist"] = _seed_distances(data, seed, self._dist_func)
            random_state = int(rng.integers(1 << 31))
            index = NNDescent(
                data, n_neighbors=width, metric=self.metric, random_state=random_state, low_memory=True, **kwargs
            )
            indices, distances = index.neighbor_graph
            if kwargs.get("n_iters") is not None and (indices < 0).any():
                # Safety net: the engine needs complete rows.
                kwargs["n_iters"] = None
                index = NNDescent(
                    data, n_neighbors=width, metric=self.metric, random_state=random_state, low_memory=True, **kwargs
                )
                indices, distances = index.neighbor_graph
        return indices.astype(np.int32), distances.astype(np.float32)

    def reembed_payload(self, ids, sample=0, rng=None):
        """Compute the binary response for a re-embed request (see module docs)."""
        ids = np.asarray(ids, dtype=np.int64)
        n_rows = self.vectors.shape[0]
        if ids.ndim != 1 or len(ids) < self.n_neighbors + 2:
            raise ValueError(f"need at least {self.n_neighbors + 2} ids")
        if ids.min() < 0 or ids.max() >= n_rows:
            raise ValueError("ids out of range")
        if len(np.unique(ids)) != len(ids):
            raise ValueError("ids must be unique")
        rng = rng if rng is not None else np.random.default_rng()
        with self._compute_lock:
            t0 = time.time()
            idx, dist = self.subset_graph(ids, rng)
            header = {
                "format": FORMAT,
                "n": len(ids),
                "k": self.n_neighbors,
                "seeded": self._global_knn is not None,
                "knnSeconds": time.time() - t0,
            }
            arrays = [("knn_indices", idx), ("knn_distances", dist)]
            if 0 < sample < len(ids) and sample >= self.n_neighbors + 2:
                t1 = time.time()
                sample_local = np.sort(rng.choice(len(ids), int(sample), replace=False)).astype(np.int32)
                s_idx, s_dist = self.subset_graph(ids[sample_local], rng)
                arrays += [
                    ("sample_local", sample_local),
                    ("sample_knn_indices", s_idx),
                    ("sample_knn_distances", s_dist),
                ]
                header["sampleKnnSeconds"] = time.time() - t1
        self._log(
            f"re-embed {len(ids):,} points: kNN {header['knnSeconds']:.2f}s"
            + (f", sample of {sample:,} {header['sampleKnnSeconds']:.2f}s" if "sampleKnnSeconds" in header else "")
        )
        return pack_arrays(header, arrays)

    def info(self):
        """Metadata served at ``/api/info``."""
        if not self.ready:
            stage = "warming up"
        elif not self.global_graph_ready:
            stage = "building global kNN graph"
        else:
            stage = "ready"
        return {
            "stage": stage,
            "format": FORMAT,
            "n": int(self.vectors.shape[0]),
            "dim": int(self.vectors.shape[1]),
            "metric": self.metric,
            "k": self.n_neighbors,
            "ready": self.ready,
            "globalGraphReady": self.global_graph_ready,
        }

    # ------------------------------------------------------------------ HTTP
    def serve_figure(self, figure, open_browser=False):
        """Serve an interactive figure (or HTML string) at the server root.

        Parameters
        ----------
        figure : InteractiveFigure or str

        open_browser : bool, optional (default=False)
            Open the figure in the default web browser.

        Returns
        -------
        self
        """
        self._html = str(figure).encode("utf-8")
        if open_browser and self._httpd is not None:
            webbrowser.open(self.url)
        return self

    @property
    def url(self):
        """Base URL of the running server."""
        if self._httpd is None:
            raise RuntimeError("server is not running; call start() first")
        host, port = self._httpd.server_address[:2]
        if host in ("0.0.0.0", "::", ""):
            host = "127.0.0.1"
        return f"http://{host}:{port}"

    def start(self, host="127.0.0.1", port=8765, background=True):
        """Start serving.

        Parameters
        ----------
        host : str, optional (default="127.0.0.1")

        port : int, optional (default=8765)
            Use 0 for any free port.

        background : bool, optional (default=True)
            Serve from a daemon thread and return immediately (suitable for
            notebooks). Otherwise block until interrupted.

        Returns
        -------
        self
        """
        if self._httpd is not None:
            raise RuntimeError("server already started")
        self._start_background()
        self._httpd = _ThreadingServer((host, port), _make_handler(self))
        self._log(f"serving at {self.url}")
        if background:
            self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
            self._thread.start()
        else:
            try:
                self._httpd.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                self.stop()
        return self

    def wait(self):
        """Block until interrupted (for scripts that started in the background)."""
        try:
            while self._thread is not None and self._thread.is_alive():
                self._thread.join(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        """Stop serving."""
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
            self._thread = None


class _ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _make_handler(server):
    class Handler(http.server.BaseHTTPRequestHandler):
        def end_headers(self):
            # CORS only for the API: the served figure (which may embed the token)
            # must not be readable by other origins.
            if urlparse(self.path).path.startswith("/api/"):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def _send(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, obj, status=200):
            self._send(status, json.dumps(obj).encode(), "application/json")

        def _authorized(self):
            if not server.token:
                return True
            if self.headers.get("Authorization", "") == f"Bearer {server.token}":
                return True
            self._send_json({"error": "unauthorized"}, 401)
            return False

        def do_OPTIONS(self):
            self.send_response(204)
            if urlparse(self.path).path.startswith("/api/"):
                self.send_header("Access-Control-Allow-Private-Network", "true")
                self.send_header("Access-Control-Max-Age", "600")
            self.end_headers()

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                if server._html is None:
                    body = b"<!doctype html><p>datamapplot ReembedServer is running.</p>"
                    self._send(200, body, "text/html; charset=utf-8")
                else:
                    self._send(200, server._html, "text/html; charset=utf-8")
            elif path == "/api/info":
                if self._authorized():
                    self._send_json(server.info())
            else:
                self._send_json({"error": "not found"}, 404)

        def do_POST(self):
            url = urlparse(self.path)
            if url.path != "/api/reembed":
                return self._send_json({"error": "not found"}, 404)
            if not self._authorized():
                return
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if len(body) % 4:
                return self._send_json({"error": "body must be int32 ids"}, 400)
            ids = np.frombuffer(body, dtype="<i4")
            query = parse_qs(url.query)
            try:
                sample = int(query.get("sample", ["0"])[0])
                payload = server.reembed_payload(ids, sample=sample)
            except ValueError as error:
                return self._send_json({"error": str(error)}, 400)
            self._send(200, payload, "application/octet-stream")

        def log_message(self, format, *args):
            pass

    return Handler
