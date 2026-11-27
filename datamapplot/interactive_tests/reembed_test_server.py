"""Re-embed test server for the Playwright suite (tests/reembed.spec.ts).

Serves a small synthetic data map (clusters in 32 dimensions, laid out in 2D)
with a SearchWidget and a ReembedWidget from a ReembedServer, and keeps running
until interrupted. Each point's hover text has a random tag word, so searching
for a tag selects points scattered over the whole map.

    python datamapplot/interactive_tests/reembed_test_server.py [--port 8766]

Requires pynndescent (``pip install datamapplot[reembed]``).
"""

import argparse

import numpy as np

import datamapplot
from datamapplot.reembed_server import ReembedServer

TAGS = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "theta", "kappa"]


def synthetic_map(n=6000, n_clusters=12, dim=32, seed=0):
    rng = np.random.default_rng(seed)
    cluster = rng.integers(n_clusters, size=n)
    centers = rng.normal(scale=6.0, size=(n_clusters, dim))
    vectors = (centers[cluster] + rng.normal(size=(n, dim))).astype(np.float32)
    # Each cluster at its own place in the map, with the vectors' local structure.
    places = rng.uniform(-12, 12, size=(n_clusters, 2))
    data_map = places[cluster] + 0.6 * (vectors[:, :2] - centers[cluster, :2])
    # Coarse labels, and finer ones splitting each cluster in two.
    coarse = np.array([f"Topic {c}" for c in cluster])
    fine = np.array([f"Topic {c}{'ab'[int(v > 0)]}" for c, v in zip(cluster, vectors[:, 2] - centers[cluster, 2])])
    tags = rng.choice(TAGS, size=n)
    hover = np.array([f"Point {i} of topic {c}, tagged {t}" for i, (c, t) in enumerate(zip(cluster, tags))])
    return vectors, data_map, [fine, coarse], hover


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    vectors, data_map, labels, hover = synthetic_map()
    server = ReembedServer(vectors, metric="euclidean").start(host=args.host, port=args.port)
    plot = datamapplot.create_interactive_plot(
        data_map,
        *labels,
        hover_text=hover,
        widgets=[
            datamapplot.SearchWidget(),
            # CPU: deterministic in CI, where browsers have no usable WebGPU anyway.
            datamapplot.ReembedWidget(server=server, engine="cpu"),
        ],
    )
    server.serve_figure(plot)
    print(f"Serving at {server.url}", flush=True)
    server.wait()


if __name__ == "__main__":
    main()
