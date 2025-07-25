"""
Interactive CORD-19
-------------------

Demonstrating interactive plotting with colormaps and search with the CORD-19 large data map.

For a full size version see
https://lmcinnes.github.io/datamapplot_examples/CORD19_data_map_example.html
"""
import numpy as np
import bz2
import datamapplot
import colorcet

cord19_data_map = np.load("cord19_umap_vectors.npz")["arr_0"]
cord19_label_layers = []
for i in range(6):
    cord19_label_layers.append(
        np.load(f"cord19_layer{i}_cluster_labels.npz", allow_pickle=True)["arr_0"]
    )
cord19_hover_text = [
    x.decode("utf-8").strip()
    for x in bz2.open(
        "cord19_large_hover_text.txt.bz2",
        mode="r"
    )
]
cord19_marker_size_array = np.log(1 + np.load("cord19_marker_size_array.npz")["arr_0"])

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
    sub_title="A data map of papers relating to COVID-19 and SARS-CoV-2",
    font_family="Cinzel",
    logo="https://allenai.org/newsletters/archive/2023-03-newsletter_files/927c3ca8-6c75-862c-ee5d-81703ef10a8d.png",
    logo_width=128,
    marker_size_array=cord19_marker_size_array,
    cmap=colorcet.cm.CET_C2s,
    noise_color="#aaaaaa66",
    cluster_boundary_polygons=True,
    enable_search=True,
    inline_data=False,
    offline_data_prefix="cord_gallery",
)
plot.save("cord19.html")
plot
