"""
CORD-19
-------

CORD-19 Data map with highlights applied to some important labels
"""
import datamapplot
import numpy as np
import requests
import PIL
import matplotlib.font_manager
import matplotlib.pyplot as plt
from tempfile import NamedTemporaryFile
import re
import pandas as pd

plt.rcParams['savefig.bbox'] = 'tight'

cord19_data_map = np.load("CORD19-subset-data-map.npy")
cord19_labels = np.load("CORD19-subset-cluster_labels.npy", allow_pickle=True)

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

# Prune labels down slightly
label_counts = pd.Series(cord19_labels).value_counts()
small_clusters = label_counts[label_counts <= 700].index
for label in small_clusters:
    cord19_labels[cord19_labels == label] = "Unlabelled"

allenai_logo_response = requests.get(
    "https://allenai.org/newsletters/archive/2023-03-newsletter_files/927c3ca8-6c75-862c-ee5d-81703ef10a8d.png",
    stream=True,
)
allenai_logo = np.asarray(PIL.Image.open(allenai_logo_response.raw))

get_google_font("Cinzel")

fig, ax = datamapplot.create_plot(
    cord19_data_map,
    cord19_labels,
    palette_hue_shift=-90,
    title="CORD-19 Data Map",
    sub_title="A data map of papers relating to COVID-19 and SARS-CoV-2",
    highlight_labels=[
        "Effects of the COVID-19 pandemic on mental health",
        "Airborne Transmission of COVID19",
        "COVID19 Diagnosis",
        "Viral Diseases and Emerging Zoonoses",
        "Vaccine Acceptance",
    ],
    fontfamily="Cinzel",
    label_font_size=7,
    label_linespacing=1.25,
    label_margin_factor=1.5,
    label_direction_bias=1.0,
    highlight_label_keywords={"fontsize": 11, "fontweight": "bold", "bbox": {"boxstyle": "circle", "pad": 0.75}},
    title_keywords={"fontsize": 28},
    logo=allenai_logo,
)
fig.savefig("plot_cord19.png", bbox_inches="tight")
plt.show()