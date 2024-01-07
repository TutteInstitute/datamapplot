.. DataMapPlot documentation master file, created by
   sphinx-quickstart on Mon Dec 18 21:48:14 2023.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. image:: datamapplot_text_horizontal.png
  :width: 600
  :alt: DataMapPlot logo
  :align: center

DataMapPlot: Creating beautiful plot of data maps
=================================================

Creating beautiful plots of data maps. DataMapPlot is a small library designed to help you make beautiful data map
plots for inclusion in presentations, posters and papers. The focus is on producing static plots that are great
looking with as little work for you as possible. All you need to do is label clusters of points in the data map and
DataMapPlot will take care of the rest. While this involves automating most of the aesthetic choices, the library
provides a wide variety of ways to customize the resulting plot to your needs.

Installation
------------

DataMapPlot requires a few libraries, but all are widely available and easy to install:

 * Numpy
 * Matplotlib
 * Scikit-learn
 * Pandas
 * Datashader
 * Scikit-image
 * Numba

To install DataMapPlot you can use pip:

.. code:: bash

    pip install datamapplot

or use conda with conda-forge

.. code:: bash

    conda install -c conda-forge datamapplot


User Guide
----------

DataMapPlot can be very simple to use, but also supports a lot of options for customization.
This guide will step you through, starting with a demo of what DataMapPlot can do
and followed by guides on basic usage, through to the more complicated options available.

.. toctree::
   :maxdepth: 1
   :caption: Contents:

   demo
   basic_usage
   customization
   size_controls
   colour_controls
   placement_controls
   auto_examples/index
   api
   faq




Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
