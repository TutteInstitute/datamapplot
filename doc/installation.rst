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
 * Requests
 * Jinja2

To install DataMapPlot you can use pip:

.. code:: bash

    pip install datamapplot

or use conda with conda-forge

.. code:: bash

    conda install -c conda-forge datamapplot

If you want to use :doc:`live re-embedding <live_reembedding>` you will also
need pynndescent, which you can install along with DataMapPlot using the
``reembed`` extra:

.. code:: bash

    pip install "datamapplot[reembed]"