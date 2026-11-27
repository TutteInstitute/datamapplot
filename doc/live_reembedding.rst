Live Re-embedding
=================

.. note::

    Live re-embedding is experimental: its options and the server's API may
    still change.

A data map lays out all of your data at once, so the structure *within* a
region often gets compressed to make room for everything else. Live
re-embedding lets you select part of an interactive plot and re-run UMAP on
just those points, in the browser. The rest of the map fades away, the
selection zooms to fill the view, and UMAP optimizes the layout of just the
selected points, *starting from where they are now*, with every epoch
animated, so you can watch how the layout changes once it only has to account
for the selection. Topic labels whose points all lie in the selection follow
them, and finer labels appear as there is room for them. Re-embeddings can be
nested, and "Back" animates out again to the previous layout.

This needs two pieces:

* a :class:`~datamapplot.ReembedWidget` in the plot, which runs UMAP in the
  browser (a WebAssembly build of UMAP, on the GPU via WebGPU when the browser
  supports it, otherwise on the CPU), and
* a :class:`~datamapplot.reembed_server.ReembedServer` in Python, which holds
  the high-dimensional vectors behind the map (for example text embeddings) and
  computes the k-nearest-neighbour graph of each selection.

Installing for re-embedding
---------------------------

The server needs `pynndescent <https://github.com/lmcinnes/pynndescent>`_,
which the ``reembed`` extra installs:

.. code-block:: bash

    pip install "datamapplot[reembed]"

Getting started with re-embedding
---------------------------------

You need the data map coordinates (and labels, as for any interactive plot)
and the vectors they were computed from, with rows in the same order.

**From a script:** start the server first (it compiles its code and builds a
global kNN graph in the background while the plot is created), then let it
serve the plot and open its address in a browser:

.. code-block:: python

    import datamapplot
    from datamapplot.reembed_server import ReembedServer

    server = ReembedServer(vectors, metric="cosine").start()
    plot = datamapplot.create_interactive_plot(
        data_map_coords,
        labels,
        widgets=[datamapplot.SearchWidget(), datamapplot.ReembedWidget(server=server)],
    )
    server.serve_figure(plot)
    print("Open", server.url)
    server.wait()  # serve until interrupted

**In a Jupyter notebook:** start the server in the kernel and show the plot
inline as usual; the widget finds the server by itself:

.. code-block:: python

    server = ReembedServer(vectors, metric="cosine").start()
    datamapplot.create_interactive_plot(
        data_map_coords, labels, widgets=[datamapplot.ReembedWidget(server=server)]
    )

See the gallery examples ``reembed_20newsgroups.py``, ``reembed_notebook.py``
and ``reembed_cord19.py`` (half a million papers) for complete versions.

Selecting and re-embedding
--------------------------

Any selection on the map can be re-embedded:

* a lasso: hold Shift and drag;
* search results (:class:`~datamapplot.SearchWidget`), which are often
  scattered over the map;
* a legend entry (:class:`~datamapplot.ColormapSelectorWidget`), a saved
  selection group (:class:`~datamapplot.SelectionControlWidget`) or a
  histogram range;
* combinations of these, combined as the map combines them (for example a
  lasso within search results selects the results inside the lasso).

The "Re-embed" button shows how many points are selected. Once a selection is
re-embedded the lasso is cleared, but other selections stay active (a search
stays in its search box), so you can lasso within a re-embedding to re-embed
again, or go back with "Back" or the breadcrumbs.

While a re-embedding is shown:

* the **min_dist**, **spread** and **repulsion** sliders (under "Settings")
  re-optimize the current layout with the new values;
* **Pause** stops the animation (the optimization pauses too);
* the **engine** can be switched between WebGPU and the CPU for the next
  re-embedding ("auto" uses WebGPU when available);
* once the layout has settled, hovering over and clicking points works as on
  the full map.

Large selections and slow connections
-------------------------------------

The widget avoids waiting with nothing on screen. It predicts how long a
selection will take to start moving (computing and downloading its kNN graph,
then setting up the optimizer), learning the connection's speed as it goes, and
stretches the zoom into the selection (up to 2.5 seconds) to cover the wait.
If that is not enough, or if optimizing every point would be slow (by default
above 400,000 points on WebGPU or 25,000 on the CPU), it first animates a
random sample of the selection, drawn larger, while the full graph downloads
and its optimizer is built in the background; then it places the other points
next to their neighbours in the sample and refines them all.

The status line under the buttons reports where the time went, for example
``request 4.83 s (upload 0.81 MB 0.08 s, server 0.48 s incl. kNN 0.43 s,
download 10.3 MB 3.84 s, other 0.43 s) · setup 1.12 s``: the server's work, the
transfers in both directions, and setting up the optimizer in the browser.
Hover over it for more detail.

The re-embed server
-------------------

:class:`~datamapplot.reembed_server.ReembedServer` options worth knowing:

``metric``
    Any metric pynndescent supports; use the one your embedding was made for
    (``"cosine"`` for most text embeddings).

``knn_indices`` and ``global_knn_cache``
    Each selection's graph is seeded from a global kNN graph of all the
    vectors. By default the server builds one when it starts (in seconds to a
    few minutes, depending on the data and the number of cores). Pass
    ``knn_indices`` to reuse one you have (for example a fitted UMAP model's
    ``_knn_indices``), or ``global_knn_cache="path/to/graph.npy"`` to save the
    graph it builds and load it on later runs.

``n_neighbors``
    Neighbours per point in each selection's graph, counting the point itself
    as umap-learn does (default 15).

``token``
    Require a token on API requests (the widget sends it when given the
    server); use it when others can reach the server's port.

The first time in a Python process the server spends about 20 seconds
compiling its kNN code; the widget says "Server warming up" until it is ready.
Requests typically take well under a second, even for selections of hundreds
of thousands of points.

Remote and notebook setups
--------------------------

The page needs to reach the server:

* **Served by the server** (``server.serve_figure``): open ``server.url``.
  If Python runs on another machine, forward the port, for example
  ``ssh -L 8765:127.0.0.1:8765 host``, and open ``http://127.0.0.1:8765``.
* **In a notebook**, ``ReembedWidget(server=server)`` tries the server's own
  address (when the browser runs on the same machine as the kernel) and, when
  Jupyter runs elsewhere (JupyterHub, or JupyterLab on a server reached over
  SSH), Jupyter's own address: ``<Jupyter URL>/proxy/<port>/``. The latter
  needs `jupyter-server-proxy <https://jupyter-server-proxy.readthedocs.io>`_
  installed where the Jupyter server runs (``pip install
  jupyter-server-proxy``, then restart Jupyter); requests then use Jupyter's
  own login. The server listens on port 8765, or on any free port when that is
  taken (for example by a server from an earlier run of the cell).
* **Elsewhere** (a saved HTML file, a server behind your own web server), give
  the widget the server's address: ``ReembedWidget(server_url="https://...")``.
  The page only works while the server runs.

The widget checks that it reached the right server, and the status line says
what it tried if it cannot, or if the server's number of vectors does not
match the map's number of points.

The re-embed REST API
---------------------

The widget talks to the server over a small HTTP API, so other servers can
provide the same service:

``GET /api/info``
    JSON ``{"stage", "id", "format", "n", "dim", "metric", "k", "ready",
    "globalGraphReady"}``. ``stage`` is ``"warming up"``, ``"building global
    kNN graph"`` or ``"ready"``; ``format`` is ``"datamapplot-reembed/1"``.

``POST /api/reembed[?sample=M][&encoding=varint]``
    The body is the selection's row ids as little-endian int32 (unique, in any
    order; local indices in the response follow this order). The response is a
    little-endian uint32 header length, a JSON header, then the arrays the
    header lists, each with its ``name``, ``dtype``, ``shape``, ``offset`` (from
    the end of the header) and ``bytes``:

    * ``knn_indices`` (int32) and ``knn_distances`` (float32), shape
      ``(n, k)``: each row starts with the point itself, as in umap-learn;
    * with ``sample=M``, also ``sample_local`` (int32, the sample's local
      indices) and ``sample_knn_indices`` / ``sample_knn_distances``, the
      graph of just the sample.

    With ``encoding=varint`` the graphs are compressed (typically 2-2.5 times
    smaller): indices as varints of the zigzagged offset from their row, and
    distances as varint increments of a quantization ``step`` given in their
    entry, with ``encoding`` set to ``"row-delta-varint"`` and
    ``"step-varint"``. The header also reports the server's timings in
    seconds (``receiveSeconds``, ``knnSeconds``, ``encodeSeconds``,
    ``serverSeconds``).

API requests accept ``Authorization: Bearer <token>`` or ``X-Reembed-Token:
<token>`` when the server has a token, and send permissive CORS headers so
pages from other origins (files, notebooks) can use them.

Credits for the UMAP engine
---------------------------

The in-browser UMAP is a WebAssembly build of the Rust port of umap-learn 0.6
(including its Adam optimizer, whose smooth motion makes the animation
possible) from Apple's `Embedding Atlas
<https://github.com/apple/embedding-atlas>`_ (MIT licence), with additions for
starting from a given layout and stepping the optimization epoch by epoch.
