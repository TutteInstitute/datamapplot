"""
Live re-embedding of a lasso selection
--------------------------------------

Re-run UMAP in the browser on just the points you select.

Hold Shift and drag to lasso a region of the 20 Newsgroups map, then press
"Re-embed": the rest of the map fades away, the selection zooms to fill the
view, and UMAP re-optimizes the layout of just those points, starting from
where they are now, with every epoch animated. Re-embeds can be nested, and
"Back" (or the breadcrumbs) returns to the previous layout.

The :class:`~datamapplot.reembed_server.ReembedServer` holds the
high-dimensional vectors and computes the k-nearest-neighbour graph of each
selection; the optimization runs client-side (Rust/WASM UMAP from
apple/embedding-atlas, on WebGPU when available). The server also serves the
plot, so the page and the API share an origin.

This example requires ``pynndescent`` (``pip install datamapplot[reembed]``)
and keeps running until interrupted.
"""

import numpy as np
import pandas as pd

import datamapplot
from datamapplot.reembed_server import ReembedServer

DATA_URL = (
    "https://huggingface.co/datasets/lmcinnes/20newsgroups_embedded/"
    "resolve/main/data/train-00000-of-00001.parquet"
)

if __name__ == "__main__":
    newsgroups = pd.read_parquet(DATA_URL)
    vectors = np.stack(newsgroups["embedding"].values).astype(np.float32)
    data_map = np.stack(newsgroups["map"].values)
    labels = newsgroups["newsgroup"].values
    hover_text = newsgroups["post"].str.strip().str.slice(0, 200).values

    # Start the server first: it builds a global kNN graph in the background,
    # which seeds the per-selection graphs.
    server = ReembedServer(vectors, metric="cosine").start(port=8765)

    plot = datamapplot.create_interactive_plot(
        data_map,
        labels,
        hover_text=hover_text,
        widgets=[
            datamapplot.TitleWidget(
                title="20 Newsgroups",
                sub_title="Shift-drag to lasso a region, then Re-embed",
            ),
            datamapplot.ReembedWidget(),
        ],
    )
    server.serve_figure(plot, open_browser=True)
    print(f"Open {server.url} ; press Ctrl-C to stop.")
    server.wait()
