Theming Widgets
===============

An interactive plot is more than the map itself: titles, search boxes, legends,
histograms, topic trees and all the other widgets sit on top of it. DataMapPlot
tries to make all of these look like they belong together, and like they belong
with your plot. That means the widgets pick up the font you chose for the plot,
switch between light and dark along with it, and share a common look: soft
translucent panels, quiet neutral controls, and a single accent colour for
whatever is selected or active.

Most of the time that is all you need to know, since the widgets will simply
follow your plot. If you want something a little different, though, the whole
look is controlled by a small set of theme settings that you can adjust with the
``widget_theme`` parameter. This guide will walk you through how widgets get
their look, how to adjust it, and how to use the same theme in your own custom
CSS and widgets.

How Widgets Get Their Look
--------------------------

Every widget draws its colours, fonts and sizes from a shared *widget theme*.
DataMapPlot builds the theme from the settings of your plot:

* the font comes from ``font_family``;
* the text, panel and input colours come from ``darkmode``;
* everything else (panel corners, control borders, the accent colour and so on)
  has a sensible default.

Because the widgets share one theme, they all change together. Let's see that in
action with a plot that has a few widgets:

.. code:: python

    import datamapplot

    plot = datamapplot.create_interactive_plot(
        data_map_coords,
        labels,
        hover_text=hover_text,
        title="My Data Map",
        sub_title="A map of some interesting data",
        enable_search=True,
        font_family="Playfair Display",
        darkmode=True,
    )

The title, subtitle and search box are all set in Playfair Display, and since we
asked for ``darkmode`` they all switch to light text on dark panels. There was
no need to tell each widget about the font or the dark mode; they follow the
plot.

Widget Fonts
------------

By default every widget uses the plot's ``font_family``, the same font as the
cluster labels on the map. That includes the title, the search box, the topic
tree, legends, buttons and even the text annotations you add with the
:class:`~datamapplot.AnnotationWidget`.

If you would like a particular widget in a different font you can usually say so
when you create it. For example, a title in a display font over a map labelled in
something plainer:

.. code:: python

    plot = datamapplot.create_interactive_plot(
        data_map_coords,
        labels,
        font_family="Roboto",
        widgets=[
            datamapplot.TitleWidget(
                title="My Data Map",
                title_font_family="Cinzel",
            ),
            datamapplot.SearchWidget(),
        ],
    )

To put *all* the widgets in a different font from the map labels, set the
``font_family`` of the widget theme instead (see
:ref:`Adjusting the Widget Theme` below). DataMapPlot will fetch any Google
Font you name, just as it does for ``font_family``.

Widgets in Light and Dark Mode
------------------------------

Widgets follow the plot's ``darkmode`` setting: with ``darkmode=True`` the
panels are dark, and the text is light. The panels are slightly lighter than a
black background, so they stand out from the map behind them.

.. note::

    Earlier versions of DataMapPlot asked you to pass ``darkmode=True`` to some
    widgets (such as :class:`~datamapplot.TitleWidget`) as well as to the plot.
    That is no longer needed: passing ``darkmode`` to a widget now has no effect
    and gives a warning, and will be removed in a future release.

Adjusting the Widget Theme
--------------------------

To change the look of the widgets, pass ``widget_theme`` to
``create_interactive_plot``. It is a dictionary of theme settings; any setting
you leave out keeps its default. Let's give a plot a red accent colour (used for
selected and active controls) and squarer corners:

.. code:: python

    plot = datamapplot.create_interactive_plot(
        data_map_coords,
        labels,
        enable_search=True,
        histogram_data=publication_dates,
        widget_theme={
            "accent_color": "#e15759",
            "panel_radius": "6px",
            "control_radius": "4px",
        },
    )

The values are CSS values, so anything that CSS accepts for that kind of setting
will work: colours as hex codes, ``rgb(...)`` or names, sizes in ``px`` or ``em``,
and so on. If you misspell a setting DataMapPlot will raise an error listing the
valid ones, rather than silently ignoring it.

Widget Theme Settings
~~~~~~~~~~~~~~~~~~~~~

These are the settings you can adjust, with their defaults in light and dark
mode:

.. list-table::
   :header-rows: 1
   :widths: 25 30 45

   * - Setting
     - Default
     - Used for
   * - ``font_family``
     - the plot's ``font_family``
     - All widget text
   * - ``text_color``
     - ``#000000`` / ``#ffffff``
     - Widget text
   * - ``text_muted_color``
     - ``#777777``
     - Subtitles, labels and secondary text
   * - ``panel_background``
     - ``#ffffffaa`` / ``#1c1c1ccc``
     - Widget panels
   * - ``panel_background_opaque``
     - as ``panel_background``, with alpha ``ee``
     - Drawers, dropdowns and tooltips
   * - ``panel_blur``
     - ``3px``
     - Blur of the map behind panels
   * - ``panel_shadow``
     - ``2px 3px 10px #aaaaaa44`` / ``... #00000044``
     - Panel shadows
   * - ``panel_radius``
     - ``16px``
     - Panel corners
   * - ``panel_padding``
     - ``12px``
     - Space inside panels
   * - ``panel_margin``
     - ``8px 16px``
     - Space around panels
   * - ``input_background``
     - ``#ffffffdd`` / ``#000000dd``
     - Text inputs and selects
   * - ``input_border``
     - ``2px inset #77777744``
     - Text inputs and selects
   * - ``input_focus_border``
     - ``2px inset #555555``
     - Text inputs and selects being edited
   * - ``control_border``
     - ``1px solid #aaaaaa77``
     - Buttons, dropdowns and list items
   * - ``control_radius``
     - ``8px``
     - Corners of buttons, inputs and dropdowns
   * - ``hover_background``
     - ``#77777744``
     - Controls under the mouse pointer
   * - ``divider``
     - ``1px solid #aaaaaa44``
     - Lines under headings and between rows
   * - ``accent_color``
     - ``#3ba5e7``
     - Selected and active controls, checkboxes and sliders
   * - ``accent_text_color``
     - ``#ffffff``
     - Text on the accent colour
   * - ``danger_color``
     - ``#e15759``
     - Clear and delete actions, and errors
   * - ``heading_weight``
     - ``600``
     - Widget headings
   * - ``small_font_size``
     - ``0.8em``
     - Small text, such as labels and buttons

If you change ``panel_background`` but not ``panel_background_opaque``, the
opaque version follows your new panel colour, so drawers and dropdowns still
match the panels.

Using the Theme in Custom CSS
-----------------------------

Each theme setting is also available as a CSS custom property, named ``--dmp-``
followed by the setting with dashes instead of underscores: ``accent_color`` is
``var(--dmp-accent-color)``, ``panel_radius`` is ``var(--dmp-panel-radius)``, and
so on. That makes it easy for your own additions to match the widgets, in light
and dark mode alike. For example, some ``custom_css`` for a custom selection
handler panel:

.. code:: python

    custom_css = """
    #my-panel button {
        border: var(--dmp-control-border);
        border-radius: var(--dmp-control-radius);
        background: transparent;
        color: inherit;
    }
    #my-panel button.active {
        background: var(--dmp-accent-color);
        color: var(--dmp-accent-text-color);
    }
    """

Give your own panels the ``container-box`` class and they will get the shared
panel look (background, blur, corners, padding and shadow) too.

Widgets by Default
------------------

As of version 0.8, DataMapPlot builds the interface of every interactive plot
from widgets. The familiar parameters such as ``title``, ``enable_search``,
``enable_topic_tree``, ``histogram_data``, ``colormaps`` and ``logo`` still work
exactly as before: behind the scenes they are converted into the equivalent
widgets, which means they also follow the widget theme. You can find more about
placing widgets yourself in :doc:`widgets_and_layout`.

The old way of rendering the interface without widgets is still available with
``use_widgets=False``, but it is deprecated and will be removed in a future
release.
