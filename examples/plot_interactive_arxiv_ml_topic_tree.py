"""
Interactive ArXiv ML Topic Tree
-------------------------------

Demonstrating interactive plotting with the ArXiv ML data map using a topic tree.
"""

import numpy as np
import datamapplot


arxivml_data_map = np.load("arxiv_ml_data_map.npz")["arr_0"]
arxivml_label_layers = []
for layer_num in range(5):
    arxivml_label_layers.append(
        np.load(f"arxiv_ml_layer{layer_num}_cluster_labels.npz", allow_pickle=True)[
            "arr_0"
        ]
    )
arxivml_hover_data = np.load("arxiv_ml_hover_data.npz", allow_pickle=True)["arr_0"]

plot = datamapplot.create_interactive_plot(
    arxivml_data_map,
    arxivml_label_layers[0],
    arxivml_label_layers[2],
    arxivml_label_layers[4],
    hover_text=arxivml_hover_data,
    initial_zoom_fraction=0.999,
    font_family="Playfair Display SC",
    title="ArXiv Machine Learning Landscape - With Topic Tree",
    sub_title="A data map of papers from the Machine Learning section of ArXiv",
    logo="https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/512px-ArXiv_logo_2022.svg.png",
    logo_width=128,
    on_click='window.open(`http://google.com/search?q="{hover_text}"`)',
    enable_search=True,
    darkmode=True,
    inline_data=True,
    offline_data_prefix="arxivml_gallery_topic_tree",
    enable_topic_tree=True,
    topic_tree_kwds={
        "color_bullets": True,
    },
    use_widgets=False,
)
plot.save("arxiv_ml_topic_tree.html")
plot
