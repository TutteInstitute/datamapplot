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
import webbrowser
from urllib.parse import parse_qs, urlparse

import numpy as np

FORMAT = "datamapplot-reembed/1"


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
        Small subsets use fewer threads, which is faster.

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
        import numba

        NNDescent = _require_pynndescent()
        t0 = time.time()
        rng = np.random.default_rng(0)
        warm = rng.normal(size=(2000, 8)).astype(np.float32)
        seed = rng.integers(0, 2000, size=(2000, self.n_neighbors + 1))
        # numba's default "workqueue" threading layer aborts the process on concurrent
        # parallel calls, so background work is serialised with requests unless the
        # layer is thread-safe.
        with self._compute_lock:
            NNDescent(warm, n_neighbors=self.n_neighbors + 1, metric=self.metric, random_state=0).neighbor_graph
            NNDescent(
                warm, n_neighbors=self.n_neighbors + 1, metric=self.metric, random_state=0, init_graph=seed
            ).neighbor_graph
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
                )
                indices, _ = index.neighbor_graph
            self._global_knn = self._normalize_knn(indices)
            self._log(
                f"global {self.global_n_neighbors}-NN graph for {len(self.vectors):,} points "
                f"in {time.time() - t0:.1f}s"
            )

    def _seed_graph(self, ids, rng):
        """The global graph restricted to ``ids`` (as local indices), short rows padded randomly."""
        n = len(ids)
        width = self.n_neighbors + 1
        local = np.full(self.vectors.shape[0], -1, dtype=np.int64)
        local[ids] = np.arange(n)
        mapped = local[self._global_knn[ids]]
        order = np.argsort(mapped < 0, axis=1, kind="stable")
        seed = np.take_along_axis(mapped, order, axis=1)[:, :width]
        if seed.shape[1] < width:
            seed = np.hstack([seed, np.full((n, width - seed.shape[1]), -1)])
        missing = seed < 0
        seed[missing] = rng.integers(0, n, size=int(missing.sum()))
        return seed

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
        import numba

        NNDescent = _require_pynndescent()
        ids = np.asarray(ids, dtype=np.int64)
        rng = rng if rng is not None else np.random.default_rng()
        limit = self.max_threads or numba.config.NUMBA_NUM_THREADS
        # Thread count is thread-local in numba; small subsets are faster with few threads.
        numba.set_num_threads(int(min(limit, max(4, len(ids) // 12500))))
        kwargs = {}
        if self._global_knn is not None:
            kwargs["init_graph"] = self._seed_graph(ids, rng)
        with self._compute_lock:
            index = NNDescent(
                self.vectors[ids],
                n_neighbors=self.n_neighbors + 1,
                metric=self.metric,
                random_state=int(rng.integers(1 << 31)),
                low_memory=True,
                **kwargs,
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
