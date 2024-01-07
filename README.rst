.. -*- mode: rst -*-

.. image:: doc/datamapplot_text_horizontal.png
  :width: 600
  :alt: DataMapPlot logo
  :align: center

===========
DataMapPlot
===========

Creating beautiful plots of data maps. DataMapPlot is a small library designed to help you make beautiful data map
plots for inclusion in presentations, posters and papers. The focus is on producing static plots that are great
looking with as little work for you as possible. All you need to do is label clusters of points in the data map and
DataMapPlot will take care of the rest. While this involves automating most of the aesthetic choices, the library
provides a wide variety of ways to customize the resulting plot to your needs.

--------
Examples
--------

Some examples of the kind of output that DataMapPlot can provide.

A basic plot, with some highlighted labels:

.. image:: examples/plot_cord19.png
   :width: 1024
   :alt: A data map plot of the CORD-19 dataset
   :align: center

Using darkmode and some custom font choices:

.. image:: examples/plot_arxiv_ml.png
   :width: 1024
   :alt: A data map plot of papers from ArXiv ML
   :align: center

Alternative custom styling:

.. image:: examples/plot_wikipedia.png
   :width: 1024
   :alt: A data map plot of Simple Wikipedia
   :align: center

Custom arrow styles, fonts, and colour maps:

.. image:: examples/plot_simple_arxiv.png
   :width: 1024
   :alt: A styled data map plot of papers from ArXiv ML
   :align: center

------------
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


-------
License
-------

fast_hdbscan is MIT licensed. See the LICENSE file for details.

------------
Contributing
------------

Contributions are more than welcome! If you have ideas for features of projects please get in touch. Everything from
code to notebooks to examples and documentation are all *equally valuable* so please don't feel you can't contribute.
To contribute please `fork the project <https://github.com/TutteInstitute/datamapplot/issues#fork-destination-box>`_ make your
changes and submit a pull request. We will do our best to work through any issues with you and get your code merged in.
