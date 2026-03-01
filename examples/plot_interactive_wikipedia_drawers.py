"""
Interactive Wikipedia with Drawer Layout
----------------------------------------

Demonstrating slide-out drawer functionality with the Simple Wikipedia data map.

This example shows how to:
- Place widgets in slide-out drawers
- Use the topic tree for hierarchical navigation
- Create a clean main view with tools accessible in drawers

Keyboard shortcuts:
- Ctrl + [ : Toggle left drawer
- Ctrl + ] : Toggle right drawer
- Escape : Close all drawers

For a full size version see
https://lmcinnes.github.io/datamapplot_examples/Wikipedia_data_map_example.html
"""

import numpy as np
import datamapplot
from datamapplot import TitleWidget, SearchWidget, LogoWidget, LegendWidget


# Load Wikipedia data
wikipedia_data_map = np.load("wikipedia_layered_data_map.npz")["arr_0"]
wikipedia_label_layers = []
for i in range(6):
    wikipedia_label_layers.append(
        np.load(f"wikipedia_layer{i}_cluster_labels.npz", allow_pickle=True)["arr_0"]
    )
wikipedia_hover_text = np.load("wikipedia_large_hover_text.npz", allow_pickle=True)[
    "arr_0"
]
wikipedia_marker_size_array = np.load("wikipedia_marker_size_array.npz")["arr_0"]

# Define drawer-based layout
# The main view stays clean - all tools are in drawers
#
# Widgets are created using widget classes with location parameter to control placement.
widgets = [
    # Title stays in top-left corner for visibility
    TitleWidget(
        title="Map of Wikipedia",
        sub_title="Use Ctrl+[ and Ctrl+] to access tools",
        title_font_size=28,
        location="top-left",
        order=0,
    ),
    # Logo in bottom-right corner
    LogoWidget(
        logo="https://asset.brandfetch.io/idfDTLvPCK/idyv4d98RT.png",
        logo_width=100,
        location="bottom-right",
        order=0,
    ),
    # Left drawer: Search for exploration
    SearchWidget(
        search_field="hover_text",
        location="drawer-left",
        order=0,
    ),
    # Right drawer: Legend for reference
    LegendWidget(
        location="drawer-right",
        order=0,
    ),
]

plot = datamapplot.create_interactive_plot(
    wikipedia_data_map,
    wikipedia_label_layers[0],
    wikipedia_label_layers[1],
    wikipedia_label_layers[3],
    wikipedia_label_layers[5],
    hover_text=wikipedia_hover_text,
    font_family="Marcellus SC",
    background_color="#eae6de",
    marker_size_array=wikipedia_marker_size_array,
    cluster_boundary_polygons=True,
    initial_zoom_fraction=0.99,
    widgets=widgets,
    inline_data=False,
    offline_data_prefix="wikipedia_drawers_gallery",
)
plot.save("wikipedia_drawers.html")
plot
