"""
Wikipedia
---------

Demonstrating some style options with the Simple-Wikipedia Data map
"""

import matplotlib.pyplot as plt
import numpy as np
import PIL
import requests

import datamapplot

plt.rcParams["savefig.bbox"] = "tight"

wikipedia_data_map = np.load("Wikipedia-data_map.npy")
wikipedia_labels = np.load("Wikipedia-cluster_labels.npy", allow_pickle=True)

cohere_logo_response = requests.get(
    "https://asset.brandfetch.io/idfDTLvPCK/idyv4d98RT.png",
    stream=True,
)
cohere_logo = np.asarray(PIL.Image.open(cohere_logo_response.raw))

fig, ax = datamapplot.create_plot(
    wikipedia_data_map,
    wikipedia_labels,
    title="Map of Wikipedia",
    sub_title="Paragraphs from articles on Simple Wikipedia embedded with Cohere embed",
    logo=cohere_logo,
    logo_width=0.28,
    use_medoids=True,
    arrowprops={
        "arrowstyle": "wedge,tail_width=0.85,shrink_factor=0.15",
        "linewidth": 0.4,
        "fc": "#33333377",
        "ec": "#333333aa",
    },
    font_family="Marcellus SC",
    label_linespacing=1.25,
    label_direction_bias=1.25,
    title_keywords={"fontsize": 62.5},
)
ax.set(facecolor="#eae6de")
fig.savefig("plot_wikipedia.png", bbox_inches="tight")
plt.show()
