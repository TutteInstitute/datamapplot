"""
Wikipedia
---------

Demonstrating some style options with the Simple-Wikipedia Data map
"""
import datamapplot
import numpy as np
import requests
import PIL
import matplotlib.font_manager
import matplotlib.pyplot as plt
from tempfile import NamedTemporaryFile
import re

plt.rcParams['savefig.bbox'] = 'tight'

def get_google_font(fontname):
    api_fontname = fontname.replace(' ', '+')
    api_response = requests.get(
        f"https://fonts.googleapis.com/css?family={api_fontname}:black,bold,regular,light"
    )
    font_urls = re.findall(r'(https?://[^\)]+)', str(api_response.content))
    for font_url in font_urls:
        font_data = requests.get(font_url)
        f = NamedTemporaryFile(delete=False, suffix='.ttf')
        f.write(font_data.content)
        f.close()
        matplotlib.font_manager.fontManager.addfont(f.name)

wikipedia_data_map = np.load("Wikipedia-data_map.npy")
wikipedia_labels = np.load("Wikipedia-cluster_labels.npy", allow_pickle=True)

cohere_logo_response = requests.get(
    "https://asset.brandfetch.io/idfDTLvPCK/idyv4d98RT.png",
    stream=True,
)
cohere_logo = np.asarray(PIL.Image.open(cohere_logo_response.raw))

get_google_font("Marcellus SC")

fig, ax = datamapplot.create_plot(
    wikipedia_data_map,
    wikipedia_labels,
    title="Map of Wikipedia",
    sub_title="Paragraphs from articles on Simple Wikipedia embedded with Cohere embed",
    logo=cohere_logo,
    logo_width=0.28,
    use_medoids=True,
    arrowprops={"arrowstyle": "wedge,tail_width=0.85,shrink_factor=0.15", "linewidth": 0.4, "fc": "#33333377", "ec": "#333333aa"},
    fontfamily="Marcellus SC",
    label_linespacing=1.25,
    label_direction_bias=1.25,
    title_keywords={"fontsize":62.5}
)
ax.set(facecolor="#eae6de")
fig.savefig("plot_wikipedia.png", bbox_inches="tight")
plt.show()