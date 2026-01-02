"""
Interactive CORD-19 with Word Cloud Selection
----------------------------------------------

Demonstrating interactive plotting with a selection handler that generates
word clouds from selected points. Use the lasso selection tool to select
a region of the map and see a word cloud generated from the paper titles
in that region.

For a full size version see
https://lmcinnes.github.io/datamapplot_examples/CORD19_data_map_example.html
"""
import numpy as np
import datamapplot
import colorcet
from datamapplot.selection_handlers import WordCloud

# Load the CORD19 data
cord19_data_map = np.load("cord19_umap_vectors.npz")["arr_0"]
cord19_label_layers = []
for i in range(6):
    cord19_label_layers.append(
        np.load(f"cord19_layer{i}_cluster_labels.npz", allow_pickle=True)["arr_0"]
    )
cord19_hover_text = np.load("cord19_large_hover_text.npz", allow_pickle=True)["arr_0"]
cord19_marker_size_array = np.log(1 + np.load("cord19_marker_size_array.npz")["arr_0"])

# Create a WordCloud selection handler
# When users lasso-select points, a word cloud will be generated from their titles
word_cloud_handler = WordCloud(
    n_words=100,
    width=400,
    height=400,
    font_family="Cinzel",
    n_rotations=3,  # Allow some rotation for visual interest
    color_scale="YlGnBu",
    location="bottom-right",
    use_idf=True,  # Use TF-IDF weighting for better keyword extraction
)

# Create the interactive plot with word cloud selection handler
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
    sub_title="Select a region to generate a word cloud from paper titles",
    font_family="Cinzel",
    logo="https://allenai.org/newsletters/archive/2023-03-newsletter_files/927c3ca8-6c75-862c-ee5d-81703ef10a8d.png",
    logo_width=128,
    marker_size_array=cord19_marker_size_array,
    cmap=colorcet.cm.CET_C2s,
    noise_color="#aaaaaa66",
    cluster_boundary_polygons=True,
    enable_search=True,
    # Selection handler for word clouds
    selection_handler=word_cloud_handler,
    inline_data=False,
    offline_data_prefix="cord_wordcloud_gallery",
)
plot.save("cord19_wordcloud.html")
plot
