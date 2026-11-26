"""
Live re-embedding at scale: CORD-19
-----------------------------------

Re-run UMAP in the browser on a lasso selection of the 517,229 paper CORD-19
data map.

Hold Shift and drag to lasso a region, then press "Re-embed": the rest of the
map fades away, the selection zooms to fill the view, and UMAP re-optimizes the
layout of just those points with every epoch animated. Very large selections
first animate a random sample, then place the remaining points next to their
neighbours and refine the whole selection. The status line reports where the
time went: the request (with the kNN graph computation and the download of the
graph within it) and the setup of the optimizer.

Besides the files used by the interactive CORD-19 example, this needs the
768-dimensional SPECTER vectors of the papers as a ``.npy`` file (``--vectors``).
The global 30-NN graph of the vectors, which seeds the graph of each
selection, is built in the background at startup (seconds to minutes,
depending on the number of cores); it is saved next to the vectors
(``--knn-cache``) and reused on later runs.

This example requires ``pynndescent`` (``pip install datamapplot[reembed]``)
and keeps running until interrupted. On a remote machine, forward the port
(``ssh -L 8766:127.0.0.1:8766 host``) and open the printed URL locally.
"""

import argparse
import os
import time

import colorcet
import numpy as np

import datamapplot
from datamapplot.reembed_server import ReembedServer

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--vectors",
        default="cord19_specter_vectors.npy",
        help="(n, 768) float32 SPECTER vectors, in data map order",
    )
    parser.add_argument(
        "--data-dir",
        default=HERE,
        help="directory holding the cord19_*.npz files of the interactive CORD-19 example",
    )
    parser.add_argument(
        "--knn-cache",
        default=None,
        help="global kNN graph cache (default: next to the vectors)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument(
        "--no-polygons",
        action="store_true",
        help="skip cluster boundary polygons (builds the page faster)",
    )
    args = parser.parse_args()

    def data(name, **kwargs):
        return np.load(os.path.join(args.data_dir, name), **kwargs)["arr_0"]

    vectors = np.load(args.vectors, mmap_mode="r")
    knn_cache = args.knn_cache or os.path.splitext(args.vectors)[0] + "_knn30.npy"

    # Start the server first: it compiles its kNN code and loads (or builds)
    # the global kNN graph while the plot is created.
    server = ReembedServer(
        vectors, metric="cosine", global_knn_cache=knn_cache
    ).start(host=args.host, port=args.port)

    t0 = time.time()
    data_map = data("cord19_umap_vectors.npz")
    if len(data_map) != len(vectors):
        raise ValueError(
            f"{len(vectors):,} vectors but {len(data_map):,} points in the data map"
        )
    # Cluster label layers, finest first.
    label_layers = [
        data(f"cord19_layer{i}_cluster_labels.npz", allow_pickle=True)
        for i in range(6)
    ]
    hover_text = data("cord19_large_hover_text.npz", allow_pickle=True)
    marker_size = np.log(1 + data("cord19_marker_size_array.npz"))

    plot = datamapplot.create_interactive_plot(
        data_map,
        *label_layers,
        hover_text=hover_text,
        marker_size_array=marker_size,
        initial_zoom_fraction=0.99,
        font_family="Cinzel",
        cmap=colorcet.cm.CET_C2s,
        noise_color="#aaaaaa66",
        cluster_boundary_polygons=not args.no_polygons,
        widgets=[
            datamapplot.TitleWidget(
                title="CORD-19 Data Map",
                sub_title="Shift-drag to lasso a region, then Re-embed",
            ),
            datamapplot.ReembedWidget(server=server),
        ],
    )
    print(f"Built the plot in {time.time() - t0:.1f}s")
    server.serve_figure(plot)
    print(f"Open {server.url} ; press Ctrl-C to stop.")
    server.wait()
