Using System Fonts for Offline Work
===================================

DataMapPlot provides the ``use_system_fonts`` parameter to help users work in offline environments or behind restrictive firewalls. This feature allows you to create plots without downloading fonts from Google Fonts, instead using only the fonts installed on your system.

When to Use System Fonts
------------------------

The ``use_system_fonts`` parameter is particularly useful when:

 * Working in environments without internet access
 * Operating behind firewalls that block Google Fonts
 * Working in regulated industries with strict network policies
 * Wanting to avoid font download warning messages
 * Ensuring consistent font rendering across different environments

How It Works
------------

By default, DataMapPlot attempts to download and use Google Fonts for optimal typography. When you set ``use_system_fonts=True``, the library:

 1. Skips all attempts to download fonts from Google Fonts
 2. Uses only fonts already installed on your system
 3. Falls back gracefully if a requested font is not available

Basic Usage
-----------

Here's a simple example of using system fonts:

.. code:: python

    import datamapplot
    import numpy as np

    # Create some sample data
    data_coords = np.random.rand(1000, 2)
    labels = np.random.choice(['Category A', 'Category B', 'Category C'], 1000)

    # Create a plot using system fonts
    fig, ax = datamapplot.create_plot(
        data_coords,
        labels,
        title="My Offline Plot",
        font_family="Arial",  # Use a common system font
        use_system_fonts=True
    )

Common System Fonts
-------------------

When using ``use_system_fonts=True``, it's recommended to use fonts that are commonly available across different operating systems:

 * Arial
 * Helvetica
 * Times New Roman
 * Courier New
 * Georgia
 * Verdana
 * Comic Sans MS
 * Impact
 * Trebuchet MS
 * Palatino

Checking Available Fonts
------------------------

You can check which fonts are available on your system using matplotlib:

.. code:: python

    from matplotlib import font_manager
    
    # Get all available font families
    available_fonts = sorted(set([f.name for f in font_manager.fontManager.ttflist]))
    
    print(f"Total available system fonts: {len(available_fonts)}")
    
    # Check for common fonts
    common_fonts = [
        "Arial", "Helvetica", "Times New Roman", "Georgia", "Verdana",
        "Courier New", "Comic Sans MS", "Impact", "Trebuchet MS", "Palatino"
    ]
    
    for font in common_fonts:
        if font in available_fonts:
            print(f"✓ {font}")
        else:
            print(f"✗ {font} (not available)")

Advanced Usage
--------------

Custom Fonts for Different Elements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can specify different system fonts for various plot elements:

.. code:: python

    fig, ax = datamapplot.create_plot(
        data_coords,
        labels,
        title="Mixed Font Example",
        sub_title="Using different fonts for different elements",
        font_family="Arial",  # Main font
        title_keywords={"fontfamily": "Times New Roman", "fontsize": 24},
        sub_title_keywords={"fontfamily": "Georgia", "fontsize": 16},
        use_system_fonts=True
    )

Comparison with Offline Mode
----------------------------

DataMapPlot offers two different approaches for offline work:

.. list-table::
   :header-rows: 1
   :widths: 30 35 35

   * - Feature
     - ``use_system_fonts``
     - Offline Mode (cached)
   * - Use case
     - Static plots without internet
     - Interactive plots with cached resources
   * - Setup required
     - None
     - Run ``dmp_offline_cache`` tool
   * - Font selection
     - System fonts only
     - Cached Google Fonts
   * - Works with
     - ``create_plot()``
     - ``create_interactive_plot()``
   * - Storage needs
     - None
     - ~10MB for cache files

Troubleshooting
---------------

Font Not Found
~~~~~~~~~~~~~~

If you see warnings like "Font family 'X' not found", it means the specified font is not installed on your system. Solutions:

 1. Use a different font that is installed
 2. Install the missing font on your system
 3. Let matplotlib fall back to its default font

Performance Considerations
~~~~~~~~~~~~~~~~~~~~~~~~~

Using ``use_system_fonts=True`` can slightly improve performance by:

 * Skipping network checks for Google Fonts availability
 * Avoiding font download attempts
 * Reducing warning messages in restricted environments

Example: Working Behind a Firewall
----------------------------------

Here's a complete example for users working in restricted environments:

.. code:: python

    import datamapplot
    import numpy as np
    from sklearn.datasets import make_blobs
    
    # Generate sample clustered data
    X, y = make_blobs(n_samples=1000, centers=5, n_features=2, random_state=42)
    
    # Map numeric labels to categories
    label_names = ['Research', 'Development', 'Production', 'Testing', 'Documentation']
    labels = np.array([label_names[i] for i in y])
    
    # Create plot for offline use
    fig, ax = datamapplot.create_plot(
        X,
        labels,
        title="Project Classification Map",
        sub_title="Internal data visualization - no external resources needed",
        font_family="Arial",  # Safe choice for most systems
        use_system_fonts=True,
        darkness=0.5,
        figsize=(12, 10)
    )
    
    # Save for sharing within the organization
    fig.savefig("project_map.png", dpi=300, bbox_inches='tight')

Best Practices
--------------

 1. **Choose widely available fonts**: Stick to common system fonts for maximum compatibility
 2. **Test on target systems**: Verify your chosen fonts are available where the plots will be viewed
 3. **Provide fallbacks**: Consider having alternative font choices for different platforms
 4. **Document requirements**: If using specific fonts, document them for other users
 5. **Use for static plots**: This feature is designed for ``create_plot()``, not interactive plots

Further Examples
----------------

For more detailed examples and test cases demonstrating the ``use_system_fonts`` parameter, see the `example notebook <https://github.com/TutteInstitute/datamapplot/blob/main/examples/example_offline_fonts.ipynb>`_ in the examples directory.

.. note::
   For interactive plots that need to work offline, see the :doc:`offline_mode` documentation which covers caching JavaScript dependencies and fonts for fully self-contained HTML outputs.