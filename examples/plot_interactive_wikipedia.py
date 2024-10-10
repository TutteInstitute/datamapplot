"""
Interactive Wikipedia
---------------------

Demonstrating interactive plotting with a Simple Wikipedia data map.

For a full size version see
https://lmcinnes.github.io/datamapplot_examples/Wikipedia_data_map_example.html
"""
import numpy as np
import datamapplot

wikipedia_data_map = np.load("wikipedia_layered_data_map.npy")
wikipedia_label_layers = []
for i in range(6):
    wikipedia_label_layers.append(
        np.load(f"wikipedia_layer{i}_cluster_labels.npy", allow_pickle=True)
    )
wikipedia_hover_text = [
    x.strip()
    for x in open(
        "wikipedia_large_hover_text.txt",
        mode="r"
    )
]
wikipedia_marker_size_array = np.load("wikipedia_marker_size_array.npy")

plot = datamapplot.create_interactive_plot(
    wikipedia_data_map,
    wikipedia_label_layers[0],
    wikipedia_label_layers[1],
    wikipedia_label_layers[3],
    wikipedia_label_layers[5],
    hover_text = wikipedia_hover_text,
    title="Map of Wikipedia",
    sub_title="Paragraphs from articles on Simple Wikipedia embedded with Cohere embed",
    logo="https://asset.brandfetch.io/idfDTLvPCK/idyv4d98RT.png",
    font_family="Marcellus SC",
    background_color="#eae6de",
    marker_size_array=wikipedia_marker_size_array,
    cluster_boundary_polygons=True,
    initial_zoom_fraction=0.99,
)
plot