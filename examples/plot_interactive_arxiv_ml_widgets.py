"""
Interactive ArXiv ML with Custom Widget Layout
----------------------------------------------

Demonstrating the widget system with custom widget placement using
the ArXiv ML data map.

This example shows how to:
- Use widget classes to create custom layouts
- Place widgets in corners and drawers
- Create a custom layout for data exploration

For a full size version see
https://lmcinnes.github.io/datamapplot_examples/ArXiv_data_map_example.html
"""

import numpy as np
import datamapplot
from datamapplot import TitleWidget, SearchWidget, LogoWidget


# Load the data
arxivml_data_map = np.load("arxiv_ml_data_map.npz")["arr_0"]
arxivml_label_layers = []
for layer_num in range(5):
    arxivml_label_layers.append(
        np.load(f"arxiv_ml_layer{layer_num}_cluster_labels.npz", allow_pickle=True)[
            "arr_0"
        ]
    )
arxivml_hover_data = np.load("arxiv_ml_hover_data.npz", allow_pickle=True)["arr_0"]

# Define custom widget layout
# - Title in top-left corner
# - Search in left drawer (accessible via Ctrl+[ or clicking left edge)
# - Logo in bottom-right corner
#
# Widgets are created using widget classes with location parameter to control placement.
# Note: darkmode=True should be passed to widgets that need to adapt their colors.
widgets = [
    TitleWidget(
        title="ArXiv ML Landscape",
        sub_title="Explore ML papers with custom widget layout",
        title_font_size=32,
        location="top-left",
        order=0,
        darkmode=True,  # Match the plot's darkmode setting
    ),
    SearchWidget(
        search_field="hover_text",
        location="drawer-left",
        order=0,
    ),
    LogoWidget(
        logo="https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/512px-ArXiv_logo_2022.svg.png",
        logo_width=128,
        location="bottom-right",
        order=0,
    ),
]

plot = datamapplot.create_interactive_plot(
    arxivml_data_map,
    arxivml_label_layers[0],
    arxivml_label_layers[2],
    arxivml_label_layers[4],
    hover_text=arxivml_hover_data,
    initial_zoom_fraction=0.999,
    font_family="Playfair Display SC",
    on_click='window.open(`http://google.com/search?q="{hover_text}"`)',
    darkmode=True,
    widgets=widgets,
    inline_data=True,
    offline_data_prefix="arxivml_widgets_gallery",
)
plot.save("arxiv_ml_widgets.html")
plot
