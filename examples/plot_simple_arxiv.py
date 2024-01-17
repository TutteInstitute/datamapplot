"""
Simple ArXiv ML
---------------

Demonstrating some arrow and font styles that can be used with the ArXiv ML data map
"""
import datamapplot
import numpy as np
import requests
import PIL
import matplotlib.font_manager
import matplotlib.pyplot as plt
from tempfile import NamedTemporaryFile
import re
import colorcet

plt.rcParams['savefig.bbox'] = 'tight'

def get_google_font(fontname):
    api_fontname = fontname.replace(' ', '+')
    api_response = resp = requests.get(
        f"https://fonts.googleapis.com/css?family={api_fontname}:black,bold,regular,light"
    )
    font_urls = re.findall(r'(https?://[^\)]+)', str(api_response.content))
    for font_url in font_urls:
        font_data = requests.get(font_url)
        f = NamedTemporaryFile(delete=False, suffix='.ttf')
        f.write(font_data.content)
        f.close()
        matplotlib.font_manager.fontManager.addfont(f.name)

arxivml_data_map = np.load("arxiv_ml_data_map.npy")
arxivml_labels = np.load("arxiv_ml_simplified_cluster_labels.npy", allow_pickle=True)

arxiv_logo_response = requests.get(
    "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/320px-ArXiv_logo_2022.svg.png",
    stream=True,
    headers={'User-Agent': 'My User Agent 1.0'}
)
arxiv_logo = np.asarray(PIL.Image.open(arxiv_logo_response.raw))
get_google_font("Great Vibes")
get_google_font("Montserrat")

fig, ax = datamapplot.create_plot(
    arxivml_data_map,
    arxivml_labels,
    title="ArXiv ML Landscape",
    sub_title="A data map of papers from the Machine Learning section of ArXiv",
    logo=arxiv_logo,
    fontfamily="Montserrat Thin",
    label_font_size=9.5,
    label_margin_factor=1.0,
    arrowprops={
        "arrowstyle": "wedge", "connectionstyle": "arc3,rad=0.3", "linewidth": 0.25, "ec": "#4f3e2d"
    },
    title_keywords={"fontfamily":"Montserrat Thin", "fontweight":"black", "fontsize":36},
    sub_title_keywords={"fontfamily":"Montserrat Thin", "fontsize":22},
    glow_keywords={"n_levels":16, "kernel":"exponential", "kernel_bandwidth":0.2},
    cmap=colorcet.cm.CET_L9,
)
fig.savefig("plot_simple_arxiv.png", bbox_inches="tight")
plt.show()