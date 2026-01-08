"""
Interactive CORD-19 with Histogram
----------------------------------

Demonstrating interactive plotting with a histogram for filtering by publication date.
The histogram allows users to select a time range and see the corresponding papers
highlighted on the data map.

For a full size version see
https://lmcinnes.github.io/datamapplot_examples/CORD19_data_map_example.html
"""

import numpy as np
import pandas as pd
import datamapplot
import colorcet

# Load the CORD19 data
cord19_data_map = np.load("cord19_umap_vectors.npz")["arr_0"]
cord19_label_layers = []
for i in range(6):
    cord19_label_layers.append(
        np.load(f"cord19_layer{i}_cluster_labels.npz", allow_pickle=True)["arr_0"]
    )
cord19_hover_text = np.load("cord19_large_hover_text.npz", allow_pickle=True)["arr_0"]
cord19_marker_size_array = np.log(1 + np.load("cord19_marker_size_array.npz")["arr_0"])

# Load publication dates for histogram
# The dates file matches the large CORD19 dataset (517229 points)
publication_dates = np.load("CORD19-subset-publish-dates.npz", allow_pickle=True)[
    "arr_0"
]
publication_dates = pd.Series(publication_dates)

# Create the interactive plot with histogram
plot = datamapplot.create_interactive_plot(
    cord19_data_map,
    cord19_label_layers[0],
    cord19_label_layers[1],
    cord19_label_layers[2],
    cord19_label_layers[3],
    cord19_label_layers[4],
    cord19_label_layers[5],
    hover_text=cord19_hover_text,
    initial_zoom_fraction=0.99,
    title="CORD-19 Data Map",
    sub_title="A data map of papers relating to COVID-19 and SARS-CoV-2 with publication date histogram",
    font_family="Cinzel",
    logo="https://allenai.org/newsletters/archive/2023-03-newsletter_files/927c3ca8-6c75-862c-ee5d-81703ef10a8d.png",
    logo_width=128,
    marker_size_array=cord19_marker_size_array,
    cmap=colorcet.cm.CET_C2s,
    noise_color="#aaaaaa66",
    cluster_boundary_polygons=True,
    enable_search=True,
    # Histogram configuration
    histogram_data=publication_dates,
    histogram_group_datetime_by="month",
    histogram_n_bins=50,
    histogram_settings={
        "histogram_title": "Publication Date",
        "histogram_bin_fill_color": "#6290C3",
        "histogram_bin_selected_fill_color": "#2EBFA5",
    },
    inline_data=True,
    offline_data_prefix="cord_histogram_gallery",
)
plot.save("cord19_histogram.html")
plot
