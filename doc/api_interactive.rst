.. currentmodule:: datamapplot
    
Basic Interactive Plotting
==========================

.. autofunction:: create_interactive_plot

Advanced Interactive Plotting Options
=====================================

.. autofunction:: render_html

Live Re-embedding Widget and Server
===================================

See :doc:`live_reembedding` for a guide to using these.

.. autoclass:: ReembedWidget

.. autoclass:: datamapplot.reembed_server.ReembedServer
   :members: start, stop, wait, serve_figure, url, port, subset_graph