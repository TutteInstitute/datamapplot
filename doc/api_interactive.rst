.. currentmodule:: datamapplot
    
Basic Interactive Plotting
==========================

.. autofunction:: create_interactive_plot

Advanced Interactive Plotting Options
=====================================

.. autofunction:: render_html

Live Re-embedding
=================

Lasso a subset of an interactive plot and re-run UMAP on just those points,
live in the browser. Requires ``pynndescent`` on the server side
(``pip install datamapplot[reembed]``).

.. autoclass:: ReembedWidget

.. autoclass:: datamapplot.reembed_server.ReembedServer
   :members: start, stop, wait, serve_figure, url, subset_graph