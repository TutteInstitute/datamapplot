"""
ArXiv ML Word Cloud Style
-------------------------

Demonstrating the word cloud style using the ArXiv ML dataset.
"""
import datamapplot
import numpy as np
import requests
import PIL
import matplotlib.pyplot as plt
import colorcet

plt.rcParams['savefig.bbox'] = 'tight'

arxivml_data_map = np.load("arxiv_ml_data_map.npy")
arxivml_labels = np.load("arxiv_ml_cluster_labels.npy", allow_pickle=True)

arxiv_logo_response = requests.get(
    "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/320px-ArXiv_logo_2022.svg.png",
    stream=True,
    headers={'User-Agent': 'My User Agent 1.0'}
)
arxiv_logo = np.asarray(PIL.Image.open(arxiv_logo_response.raw))

fig, ax = datamapplot.create_plot(
    arxivml_data_map,
    arxivml_labels,
    title="ArXiv ML Landscape",
    sub_title="A data map of papers from the Machine Learning section of ArXiv",
    label_wrap_width=10,
    label_over_points=True,
    dynamic_label_size=True,
    max_font_size=36,
    min_font_size=4,
    min_font_weight=100,
    max_font_weight=1000,
    font_family="Roboto Condensed"
    cmap=colorcet.cm.CET_C2,
    logo=arxiv_logo,
    logo_width=0.1,
)
