"""
Live re-embedding in a notebook
-------------------------------

Re-run UMAP on a selection of a map shown inline in a Jupyter notebook.

The :class:`~datamapplot.reembed_server.ReembedServer` runs in the notebook's
kernel, in a background thread, and computes the k-nearest-neighbour graph of
each selection; the plot is shown inline as usual, with a
:class:`~datamapplot.ReembedWidget` given the server. Hold Shift and drag to
lasso a region, or search, then press "Re-embed".

The widget finds the server wherever the notebook runs. If the browser runs on
the same machine as the kernel, it connects directly. If Jupyter runs elsewhere
(JupyterHub, or Jupyter on a server reached over an SSH tunnel), it goes
through Jupyter's own address, which needs
`jupyter-server-proxy <https://jupyter-server-proxy.readthedocs.io>`_ installed
where the Jupyter server runs (``pip install jupyter-server-proxy``, then
restart Jupyter).

This example requires ``pynndescent`` (``pip install datamapplot[reembed]``).
"""

# %%
import numpy as np
import pandas as pd

import datamapplot
from datamapplot.reembed_server import ReembedServer

newsgroups = pd.read_parquet(
    "https://huggingface.co/datasets/lmcinnes/20newsgroups_topics/"
    "resolve/main/newsgroups_with_topics_customised.parquet"
)
vectors = np.stack(newsgroups["embedding"].values).astype(np.float32)

# %%
# Start the server first: it compiles its kNN code and builds a global kNN
# graph in the background (about 20 seconds) while the plot is created. It
# listens on port 8765, or on any free port if that is taken (e.g. by a server
# from an earlier run of this cell).
server = ReembedServer(vectors, metric="cosine").start()

# %%
data_map = np.stack(newsgroups["map"].values)
topic_layers = [newsgroups[f"layer_{i}_topics"].values for i in range(5)]

datamapplot.create_interactive_plot(
    data_map,
    *topic_layers,
    hover_text=newsgroups["post"].str.strip().str.slice(0, 200).values,
    widgets=[datamapplot.SearchWidget(), datamapplot.ReembedWidget(server=server)],
)

# %%
# The server stops when the kernel does, or with ``server.stop()``.
