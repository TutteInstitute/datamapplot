"""
ArXiv ML
--------

Demonstrating some custom styles that can be used with the ArXiv ML data map
"""
import datamapplot
import numpy as np
import requests
import PIL
import matplotlib.pyplot as plt

plt.rcParams['savefig.bbox'] = 'tight'

arxivml_data_map = np.load("arxiv_ml_data_map.npz")["arr_0"]
arxivml_labels = np.load("arxiv_ml_cluster_labels.npz", allow_pickle=True)["arr_0"]

arxiv_logo_response = requests.get(
    "https://upload.wikimedia.org/wikipedia/commons/7/7a/ArXiv_logo_2022.png",
    stream=True,
    headers={'User-Agent': 'My User Agent 1.0'}
)
arxiv_logo = np.asarray(PIL.Image.open(arxiv_logo_response.raw).convert("RGBA"))

fig, ax = datamapplot.create_plot(
    arxivml_data_map,
    arxivml_labels,
    title="ArXiv ML Landscape",
    sub_title="A data map of papers from the Machine Learning section of ArXiv",
    logo=arxiv_logo,
    font_family="Playfair Display SC",
    label_linespacing=1.25,
    label_font_size=8,
    title_keywords={"fontsize":45.65, "fontfamily":"Playfair Display SC Black"},
    label_margin_factor=1.0,
    darkmode=True
)
fig.savefig("plot_arxiv_ml.png", bbox_inches="tight")
plt.show()
