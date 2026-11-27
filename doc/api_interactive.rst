.. currentmodule:: datamapplot
    
Basic Interactive Plotting
==========================

.. autofunction:: create_interactive_plot

Advanced Interactive Plotting Options
=====================================

.. autofunction:: render_html

Live Re-embedding Widget and Server
===================================

Select a subset of an interactive plot and re-run UMAP on just those points,
live in the browser (see :doc:`live_reembedding`). Requires ``pynndescent`` on
the server side (``pip install datamapplot[reembed]``).

The :class:`~datamapplot.reembed_server.ReembedServer` holds the
high-dimensional vectors and computes the kNN graph of each selection. Either
let it serve the plot (``server.serve_figure(plot)``, then open ``server.url``),
or, in a Jupyter notebook, start it in the kernel and show the plot inline:

.. code-block:: python

    server = ReembedServer(vectors).start()
    datamapplot.create_interactive_plot(
        data_map_coords, labels, widgets=[datamapplot.ReembedWidget(server=server)]
    )

When Jupyter runs on another machine (JupyterHub, or Jupyter on a server
reached over SSH), the widget reaches the server through Jupyter's own address;
this needs `jupyter-server-proxy <https://jupyter-server-proxy.readthedocs.io>`_
installed where the Jupyter server runs.

.. autoclass:: ReembedWidget

.. autoclass:: datamapplot.reembed_server.ReembedServer
   :members: start, stop, wait, serve_figure, url, port, subset_graph