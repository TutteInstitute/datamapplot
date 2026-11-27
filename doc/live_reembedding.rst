Live Re-embedding
=================

.. note::

    Live re-embedding is experimental. Its options, and the API of the
    re-embed server, may change in future releases.

A data map has to find room for all of your data at once. That is great for
getting an overview, but it means that the structure *within* any one region
often gets squeezed to make room for everything else. Suppose you have a data
map of newsgroup posts and want a closer look at the posts about computer
hardware. You can zoom in, but the layout you are zooming in on was optimized
for the whole dataset, not for those posts in particular. What you would really
like is a data map of just that region.

Live re-embedding gives you exactly that. You select part of an interactive
plot, press a button, and DataMapPlot re-runs UMAP on just the selected points,
right there in the browser. The rest of the map fades away, the selection zooms
to fill the view, and UMAP optimizes the layout of the selected points,
starting from where they are now. Every epoch of the optimization is animated,
so the motion itself gives you a real sense of how the layout changes once UMAP
only has to account for the selection. Topic labels whose points all lie within
the selection follow their points as they move, and finer labels appear as room
is made for them. You can re-embed within a re-embedding as many times as you
like, and the "Back" button animates you back out to the previous layout.

This guide will walk you through setting up live re-embedding, both from a
script and in a Jupyter notebook, how to select and re-embed points, and the
options available for large datasets and remote setups.

How Live Re-embedding Works
---------------------------

Live re-embedding has two parts that work together:

* A :class:`~datamapplot.ReembedWidget` in the interactive plot, which runs
  UMAP in the browser. It uses a WebAssembly build of UMAP that runs on the GPU
  via WebGPU when your browser supports it, and on the CPU otherwise.
* A :class:`~datamapplot.reembed_server.ReembedServer` running in Python, which
  holds the high-dimensional vectors behind the map (text embeddings, for
  example) and computes the k-nearest-neighbour graph of each selection.

Why the split? The high-dimensional vectors are usually far too large to send
to the browser, and finding nearest neighbours among them is much faster in
Python. The optimization itself, on the other hand, is quick enough to run in
the browser, where every epoch can be drawn as it happens.

Installing Re-embedding Support
-------------------------------

The re-embed server uses `pynndescent <https://github.com/lmcinnes/pynndescent>`_
to find nearest neighbours. You can install it along with DataMapPlot using the
``reembed`` extra:

.. code:: bash

    pip install "datamapplot[reembed]"

Nothing extra is needed in the browser; the widget includes everything it needs
to run UMAP in the plot's HTML.

Getting Started with Live Re-embedding
--------------------------------------

To get started you'll need three things: the data map coordinates, labels for
the points (as for any interactive plot), and the high-dimensional vectors that
the data map was made from. The vectors need to be in the same order as the
data map, so that each row of the vectors belongs to the corresponding point in
the map.

Re-embedding from a Script
~~~~~~~~~~~~~~~~~~~~~~~~~~

Let's start with a script. The first step is to create a ``ReembedServer`` with
the vectors and start it. It is worth starting the server before creating the
plot: it compiles its code and builds a nearest neighbour graph of all the
vectors in the background, so that work can get done while the plot is being
made. Next we create the plot, adding a ``ReembedWidget`` that is given the
server. Finally we have the server serve the plot itself, so that the page and
the server share an address.

.. code:: python

    import datamapplot
    from datamapplot.reembed_server import ReembedServer

    # Start the server early; it gets ready in the background
    server = ReembedServer(vectors, metric="cosine").start()

    plot = datamapplot.create_interactive_plot(
        data_map_coords,
        labels,
        widgets=[
            datamapplot.SearchWidget(),
            datamapplot.ReembedWidget(server=server),
        ],
    )

    # Serve the plot, and keep serving it until interrupted
    server.serve_figure(plot)
    print("Open", server.url)
    server.wait()

Open the printed address in your browser and you should see your data map, with
the re-embed widget in the top right corner. We have added a ``SearchWidget`` as
well, since search results make for interesting selections to re-embed, as
we'll see shortly.

Re-embedding in a Jupyter Notebook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In a notebook things are even simpler. Start the server in the notebook's
kernel, and show the plot inline as usual; the widget will find the server by
itself.

.. code:: python

    import datamapplot
    from datamapplot.reembed_server import ReembedServer

    server = ReembedServer(vectors, metric="cosine").start()
    datamapplot.create_interactive_plot(
        data_map_coords,
        labels,
        widgets=[datamapplot.ReembedWidget(server=server)],
    )

The server runs in a background thread in the kernel, so you can carry on
working in the notebook while it handles requests. If your notebook runs on a
remote machine, see :ref:`Connecting the Widget to the Re-embed Server` below.

Complete versions of both, using the 20 Newsgroups dataset, can be found in the
:doc:`gallery <auto_examples/index>` as ``reembed_20newsgroups.py`` and
``reembed_notebook.py``. If you want to see how things work at scale,
``reembed_cord19.py`` does the same for a data map of over half a million
CORD-19 papers.

Selecting Points to Re-embed
----------------------------

Once your plot is up and running, the first thing to do is select some points.
Any selection you can make on the map can be re-embedded:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Selection
     - How to make it
   * - Lasso
     - Hold down the shift key and draw a lasso with your mouse
   * - Search results
     - Type into the search box of a :class:`~datamapplot.SearchWidget`
   * - Legend entries
     - Click on entries in the legend of a
       :class:`~datamapplot.ColormapSelectorWidget`
   * - Selection groups
     - Choose a saved selection group in a
       :class:`~datamapplot.SelectionControlWidget`
   * - Histogram ranges
     - Click on a bin, or hold shift and drag, in the histogram

You can combine these too, and they combine just as they do elsewhere on the
map: a lasso drawn within some search results, for example, selects just the
search results inside the lasso.

Search results are particularly interesting to re-embed. The points matching a
search are often scattered all over the map, and re-embedding them brings them
together into a map of their own, showing how they relate to each other rather
than to everything else.

The "Re-embed" button shows how many points are currently selected. Press it and
the rest of the map fades away, the selection zooms to fill the view, and the
optimization gets underway. (The button is disabled when nothing is selected,
or when everything currently shown is selected, since there would be nothing
new to focus on.)

After a re-embedding the lasso is cleared, but any other selections stay
active; a search, for example, stays in its search box and is still in effect
when you go back. That means you can lasso a region within a re-embedding and
re-embed again. To return to an earlier layout use the "Back" button, or click
on an earlier level in the breadcrumbs (``Full map › 2,345``) below the
buttons.

Exploring a Re-embedded Selection
---------------------------------

While a re-embedding is shown there are a few more things you can do. Under
"Settings" you will find sliders for UMAP's **min_dist**, **spread** and
**repulsion** parameters. Moving them re-optimizes the current layout with the
new values, so you can see their effect directly. The settings also let you
choose the number of epochs, and the **engine**, for the next re-embedding:
WebGPU, the CPU, or "Auto" (which uses WebGPU when it is available).

The "Pause" button pauses the optimization, and its animation, until you press
"Resume". Once the layout has settled, hovering over points and clicking on them
works just as it does on the full map.

The defaults for all of these can be set when you create the widget; see
:class:`~datamapplot.ReembedWidget` for the details.

Large Selections and Slow Connections
-------------------------------------

Re-embedding hundreds of thousands of points takes a little time, and
DataMapPlot tries hard to make sure you are never left looking at a stalled
screen. Before each re-embedding the widget predicts how long it will be before
the points can start moving (the time to compute and download the selection's
nearest neighbour graph, and then set up the optimizer), learning how fast your
connection is as it goes. It then stretches the zoom into the selection, up to
2.5 seconds, to cover the wait.

If that isn't enough, or if optimizing every point would simply be slow (by
default, for more than 400,000 points with WebGPU, or 25,000 points on the
CPU), the widget starts with a random sample of the selection instead. The
sample is drawn with larger points and animated while the full graph downloads
and its optimizer is set up in the background. Once that is ready, the rest of
the points are placed next to their neighbours in the sample, and the whole
selection is refined together. In practice this looks like a two stage
optimization: the sample finds its shape, and then everything else fills in
around it. You can tune this with the ``subsample_threshold``, ``sample_size``
and ``refine_epochs`` parameters of :class:`~datamapplot.ReembedWidget`.

If you want to know where the time went, the status line below the buttons
reports it, for example::

    request 4.83 s (upload 0.81 MB 0.08 s, server 0.48 s incl. kNN 0.43 s,
    download 10.3 MB 3.84 s, other 0.43 s) · setup 1.12 s

This covers the server's work, the transfers in each direction, and setting up
the optimizer in the browser. Hover over the status line for more detail.

Re-embed Server Options
-----------------------

The default server settings work well for most uses, but there are a few
options of :class:`~datamapplot.reembed_server.ReembedServer` worth knowing
about:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Option
     - Description
   * - ``metric``
     - The distance to use when finding nearest neighbours. Any metric that
       pynndescent supports will work; use the one your embedding was made for
       (``"cosine"`` for most text embeddings).
   * - ``knn_indices``
     - Each selection's graph starts from a nearest neighbour graph of all the
       vectors, which the server builds when it starts. That takes anywhere
       from seconds to a few minutes, depending on the size of your data and
       the number of cores you have. If you already have such a graph, such as
       the ``_knn_indices`` of a fitted UMAP model, pass it here to skip that
       step.
   * - ``global_knn_cache``
     - A path, such as ``"path/to/graph.npy"``, to save the graph the server
       builds to, so that later runs can load it rather than build it again.
   * - ``n_neighbors``
     - The number of neighbours per point in each selection's graph, counting
       the point itself as umap-learn does. The default is 15.
   * - ``token``
     - Require a token on API requests. The widget sends it for you when it is
       given the server. This is a good idea if other people can reach the
       server's port.

The first time a server starts in a Python process it spends about 20 seconds
compiling its nearest neighbour code, and until it is ready the widget shows
"Server warming up". After that requests are quick, typically well under a
second even for selections of hundreds of thousands of points.

Connecting the Widget to the Re-embed Server
--------------------------------------------

The page showing your plot needs to be able to reach the re-embed server. How
that works depends on where the plot is shown.

**Plots served by the re-embed server.** If the server serves the plot (with
``server.serve_figure``), simply open ``server.url``. If Python is running on
another machine, forward the port first, for example with
``ssh -L 8765:127.0.0.1:8765 host``, and then open ``http://127.0.0.1:8765`` in
your local browser.

**Plots in a Jupyter notebook.** Given the server itself,
``ReembedWidget(server=server)`` tries the server's own address, which works
when your browser runs on the same machine as the kernel. In case Jupyter is
running elsewhere (JupyterHub, or JupyterLab on a server you reach over SSH) it
also tries Jupyter's own address, ``<Jupyter URL>/proxy/<port>/``. For that to
work `jupyter-server-proxy <https://jupyter-server-proxy.readthedocs.io>`_ needs
to be installed where the Jupyter server runs (``pip install
jupyter-server-proxy``, then restart Jupyter); requests then use your Jupyter
login. The server listens on port 8765, or on any free port if that one is
taken (by a server from an earlier run of the cell, for example).

**Anywhere else.** For a saved HTML file, or a server behind your own web
server, give the widget the server's address with
``ReembedWidget(server_url="https://...")``. Keep in mind that the page can
only re-embed while the server is running.

.. tip::

    If something isn't working, check the widget's status line. The widget
    checks that it has reached the right server, and if it can't reach one it
    lists the addresses it tried. It will also tell you if the server's number
    of vectors doesn't match the number of points in the map, which usually
    means the vectors and the data map have got out of step.

The Re-embed REST API
---------------------

Under the hood the widget talks to the server through a small HTTP API. You
won't need to know about it to use live re-embedding, but if you would like to
provide the same service from another server (one that already holds your
vectors, say), this is what it needs to implement.

``GET /api/info``
    Returns a JSON object with the keys ``stage``, ``id``, ``format``, ``n``,
    ``dim``, ``metric``, ``k``, ``ready`` and ``globalGraphReady``. The
    ``stage`` is one of ``"warming up"``, ``"building global kNN graph"`` or
    ``"ready"``, and ``format`` is ``"datamapplot-reembed/1"``.

``POST /api/reembed[?sample=M][&encoding=varint]``
    The request body is the selection's row ids as little-endian int32 values
    (unique, in any order; the local indices in the response follow this
    order). The response starts with a little-endian uint32 giving the length
    of a JSON header, followed by the header itself, and then the arrays the
    header lists. Each array's entry gives its ``name``, ``dtype``, ``shape``,
    ``offset`` (counted from the end of the header) and ``bytes``. The arrays
    are:

    * ``knn_indices`` (int32) and ``knn_distances`` (float32), of shape
      ``(n, k)``. As in umap-learn, each row starts with the point itself.
    * With ``sample=M``, also ``sample_local`` (int32, the sample's local
      indices) and ``sample_knn_indices`` / ``sample_knn_distances``, the
      graph of just the sample.

    With ``encoding=varint`` the graphs are compressed, typically to a half or
    less of their size. Indices are stored as varints of the zigzagged offset
    from their row, and distances as varint increments of a quantization
    ``step`` given in their entry; the entries' ``encoding`` is then
    ``"row-delta-varint"`` and ``"step-varint"`` respectively. The header also
    reports the server's timings in seconds (``receiveSeconds``,
    ``knnSeconds``, ``encodeSeconds`` and ``serverSeconds``).

When the server has a token, API requests need to include it, as either
``Authorization: Bearer <token>`` or ``X-Reembed-Token: <token>``. The server
also sends permissive CORS headers, so that pages from other origins (files
and notebooks, for example) can use it.

Credits for the UMAP Engine
---------------------------

Live re-embedding would not be possible without Apple's `Embedding Atlas
<https://github.com/apple/embedding-atlas>`_ project. The in-browser UMAP is a
WebAssembly build of its Rust port of umap-learn 0.6 (MIT licensed), including
the Adam optimizer new in umap-learn 0.6, whose smooth motion is what makes the
animation possible. We have added support for starting from a given layout and
for stepping the optimization one epoch at a time.
