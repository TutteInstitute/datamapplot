"""
CORD-19
-------

CORD-19 Data map with highlights applied to some important labels
"""
import datamapplot
import numpy as np
import requests
import PIL
import matplotlib.pyplot as plt

plt.rcParams['savefig.bbox'] = 'tight'

cord19_data_map = np.load("CORD19-subset-data-map.npy")
cord19_labels = np.load("CORD19-subset-cluster_labels.npy", allow_pickle=True)

allenai_logo_response = requests.get(
    "https://allenai.org/newsletters/archive/2023-03-newsletter_files/927c3ca8-6c75-862c-ee5d-81703ef10a8d.png",
    stream=True,
)
allenai_logo = np.asarray(PIL.Image.open(allenai_logo_response.raw))

datamapplot.create_plot(
    cord19_data_map,
    cord19_labels,
    palette_hue_shift=-90,
    title="CORD-19 Data Map",
    sub_title="A data map of papers relating to COVID-19 and SARS-CoV-2",
    highlight_labels=[
        "Effects of the COVID-19 pandemic on mental health",
        "Airborne Transmission of COVID19",
        "Diagnostic Testing for SARS-CoV2",
        "Viral Diseases and Emerging Zoonoses",
        "Vaccine Acceptance",
    ],
    label_font_size=6,
    label_margin_factor=1.75,
    label_direction_bias=1.0,
    highlight_label_keywords={"fontsize": 12, "fontweight": "bold", "bbox": {"boxstyle": "circle", "pad": 0.75}},
    logo=allenai_logo,
)
plt.show()