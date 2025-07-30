"""
Interactive Custom CORD-19
--------------------------

Demonstrating interactive plotting and what can be achieved with the extra options available
via ``custom_html``, ``custom_css`` and ``custom_js`` to construct a clickable legend for
selecting subsets of data based on the field of research (click on the colour swatches
in the legend to select a specific field).

For a full size version see
https://lmcinnes.github.io/datamapplot_examples/CORD19_customised_example.html
"""

import bz2

import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.colors import rgb2hex

import datamapplot

cord19_data_map = np.load("cord19_umap_vectors.npy")
cord19_label_layers = []
for i in range(6):
    cord19_label_layers.append(
        np.load(f"cord19_layer{i}_cluster_labels.npy", allow_pickle=True)
    )
cord19_hover_text = [
    x.decode("utf-8").strip()
    for x in bz2.open("cord19_large_hover_text.txt.bz2", mode="r")
]

color_mapping = {}
color_mapping["Medicine"] = "#bbbbbb"
for key, color in zip(
    ("Biology", "Chemistry", "Physics"), sns.color_palette("YlOrRd_r", 3)
):
    color_mapping[key] = rgb2hex(color)
for key, color in zip(
    ("Business", "Economics", "Political Science"), sns.color_palette("BuPu_r", 3)
):
    color_mapping[key] = rgb2hex(color)
for key, color in zip(
    ("Psychology", "Sociology", "Geography", "History"),
    sns.color_palette("YlGnBu_r", 4),
):
    color_mapping[key] = rgb2hex(color)
for key, color in zip(
    ("Computer Science", "Engineering", "Mathematics"),
    sns.color_palette("light:teal_r", 4)[:-1],
):
    color_mapping[key] = rgb2hex(color)
for key, color in zip(
    ("Environmental Science", "Geology", "Materials Science"),
    sns.color_palette("pink", 3),
):
    color_mapping[key] = rgb2hex(color)
for key, color in zip(("Art", "Philosophy", "Unknown"), sns.color_palette("bone", 3)):
    color_mapping[key] = rgb2hex(color)

cord19_extra_data = pd.read_feather("cord19_extra_data.arrow")
cord19_extra_data["color"] = cord19_extra_data.primary_field.map(color_mapping)
marker_color_array = cord19_extra_data.primary_field.map(color_mapping)
marker_size_array = np.log(1 + cord19_extra_data.citation_count.values)

# Add custom CSS to style the legend element we will add to the plot
custom_css = """
.row {
    display : flex;
    align-items : center;
}
.box {
    height:10px;
    width:10px;
    border-radius:2px;
    margin-right:5px;
    padding:0px 0 1px 0;
    text-align:center;
    color: white;
    font-size: 14px;
}
#legend {
    position: absolute;
    top: 0;
    right: 0;
}
#title-container {
    max-width: 75%;
}
"""
# Construct HTML for the legend
custom_html = """
<div id="legend" class="container-box">
"""
for field, color in color_mapping.items():
    custom_html += f'    <div class="row"><div id="{field}" class="box" style="background-color:{color};"></div>{field}</div>\n'
custom_html += "</div>\n"

# Create a custom tooltip, highlighting the field of research and citation count
badge_css = """
    border-radius:6px; 
    width:fit-content; 
    max-width:75%; 
    margin:2px; 
    padding: 2px 10px 2px 10px; 
    font-size: 10pt;
"""
hover_text_template = f"""
<div>
    <div style="font-size:12pt;padding:2px;">{{hover_text}}</div>
    <div style="background-color:{{color}};color:#fff;{badge_css}">{{primary_field}}</div>
    <div style="background-color:#eeeeeeff;{badge_css}">citation count: {{citation_count}}</div>
</div>
"""

# Add custom javascript to make the legend interactive/clickable,
# and interact with search selection
custom_js = """
const legend = document.getElementById("legend");
const selectedPrimaryFields = new Set();

legend.addEventListener('click', function (event) {
    const selectedField = event.srcElement.id;

    if (selectedField) {
        if (selectedPrimaryFields.has(selectedField)) {
            selectedPrimaryFields.delete(selectedField);
            event.srcElement.innerHTML = "";
        } else {
            selectedPrimaryFields.add(selectedField);
            event.srcElement.innerHTML = "✓";
        }
    }
    const selectedIndices = [];
    datamap.metaData.primary_field.forEach((field, i) => {
        if (selectedPrimaryFields.has(field)) {
            selectedIndices.push(i);
        }
    });
    datamap.addSelection(selectedIndices, "legend");
});
"""

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
    sub_title="A data map of papers relating to COVID-19",
    font_family="Cinzel",
    logo="https://allenai.org/newsletters/archive/2023-03-newsletter_files/927c3ca8-6c75-862c-ee5d-81703ef10a8d.png",
    logo_width=128,
    color_label_text=False,
    marker_size_array=marker_size_array,
    marker_color_array=marker_color_array,
    point_radius_max_pixels=16,
    text_outline_width=4,
    text_min_pixel_size=16,
    text_max_pixel_size=48,
    min_fontsize=16,
    max_fontsize=32,
    noise_color="#aaaaaa44",
    cluster_boundary_polygons=True,
    color_cluster_boundaries=False,
    extra_point_data=cord19_extra_data,
    hover_text_html_template=hover_text_template,
    on_click='window.open(`http://google.com/search?q="{hover_text}"`)',
    enable_search=True,
    custom_css=custom_css,
    custom_html=custom_html,
    custom_js=custom_js,
    inline_data=False,
    offline_data_prefix="custom_cord_gallery",
)
plot
