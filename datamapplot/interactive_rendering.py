import numpy as np
import pandas as pd
import pydeck as pdk

import json
import jinja2
import requests
import textwrap

from scipy.spatial import Delaunay
from matplotlib.colors import to_rgb, to_rgba

from datamapplot.medoids import medoid
from datamapplot.alpha_shapes import create_boundary_polygons
from datamapplot.palette_handling import (
    palette_from_cmap_and_datamap,
    palette_from_datamap,
    pastel_palette,
    deep_palette,
)

_DECKGL_TEMPLATE_STR = """
<!DOCTYPE html>
<html>
  <head>
    <meta http-equiv="content-type" content="text/html; charset=UTF-8" />
    <title>{{title}}</title>
    {% if google_font %}
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family={{google_font}}&display=swap" rel="stylesheet">
    {% endif %}
    {% if google_maps_key %}
    <script src="https://maps.googleapis.com/maps/api/js?key={{google_maps_key}}&libraries=places"></script>
    {% else %}
    <script src="https://api.tiles.mapbox.com/mapbox-gl-js/v1.13.0/mapbox-gl.js"></script>
    {% endif %}
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.2.0/css/bootstrap-theme.min.css" />
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/font-awesome/4.6.3/css/font-awesome.min.css" />
    {{ deckgl_jupyter_widget_bundle }}
    <script src="https://unpkg.com/@deck.gl/extensions@8.9.33/dist.min.js"></script> 
    {%if load_data %}

    {% endif %}
    <style>
    {{ css_text }}
    #title-container {
        position: absolute;
        top: 0;
        left: 0;
        margin: 16px;
        padding: 12px;
        border-radius: 16px;
        line-height: 0.95;
        z-index: 2;
        font-family: {{title_font_family}};
        background: {{title_background}};
      }
      {% if logo %}
            #logo-container {
        position: absolute;
        bottom: 0;
        right: 0;
        margin: 16px;
        padding: 12px;
        border-radius: 16px;
        z-index: 2;
        background: {{title_background}};
     }
      img {
        display: block;
        margin-left: auto;
        margin-right: auto;
      }
      {% endif %}
    </style>
  </head>
  <body>
    {% if use_title %}
    <div id="title-container">
        <span style="font-family:{{title_font_family}};font-size:{{title_font_size}}pt;color:{{title_color}}">
            {{title}}
        </span><br/>
        <span style="font-family:{{title_font_family}};font-size:{{sub_title_font_size}}pt;color:#777777">
            {{sub_title}}
        </span>
    </div>
    {% endif %}
    {% if logo %}
    <div id="logo-container">
      <img src={{logo}} style="width:{{logo_width}}px">
    </div>
    {% endif %}
    <div id="deck-container">
    </div>
  </body>
  <script>
    {%if load_data %}
    const data = await load({{arrow_filename}}, ArrowLoader);
    {% endif %}
    const container = document.getElementById('deck-container');
    const jsonInput = {{json_input}};
    const tooltip = {{tooltip}};
    const customLibraries = null;
    const configuration =  {
        classes: Object.assign({}, deck)
    };

    const deckInstance = createDeck({
      container,
      jsonInput,
      tooltip,
      customLibraries,
      configuration
    });

  </script>
</html>
"""


def label_text_and_polygon_dataframes(
    labels,
    data_map_coords,
    noise_label="Unlabelled",
    use_medoids=False,
    label_wrap_width=16,
    cluster_polygons=False,
    alpha=0.05,
):
    cluster_label_vector = np.asarray(labels)
    unique_non_noise_labels = [
        label for label in np.unique(cluster_label_vector) if label != noise_label
    ]
    label_locations = []
    cluster_sizes = []
    polygons = []

    for l in unique_non_noise_labels:
        cluster_mask = cluster_label_vector == l
        cluster_points = data_map_coords[cluster_mask]
        if use_medoids:
            label_locations.append(medoid(cluster_points))
        else:
            label_locations.append(cluster_points.mean(axis=0))

        cluster_sizes.append(np.sum(cluster_mask) ** 0.25)
        if cluster_polygons:
            simplices = Delaunay(cluster_points).simplices
            polygons.append(
                [
                    x.tolist()
                    for x in create_boundary_polygons(
                        cluster_points, simplices, alpha=alpha
                    )
                ]
            )

    label_locations = np.asarray(label_locations)

    if cluster_polygons:
        return pd.DataFrame(
            {
                "x": label_locations.T[0],
                "y": label_locations.T[1],
                "label": unique_non_noise_labels,
                "size": cluster_sizes,
                "polygon": polygons,
            }
        )
    else:
        return pd.DataFrame(
            {
                "x": label_locations.T[0],
                "y": label_locations.T[1],
                "label": unique_non_noise_labels,
                "size": cluster_sizes,
            }
        )


def deck_from_dataframes(
    point_dataframe,
    label_dataframe,
    font_family="arial",
    line_spacing=0.75,
    min_fontsize=12,
    max_fontsize=24,
    text_outline_width=8,
    text_min_pixel_size=8,
    text_max_pixel_size=36,
    text_outline_color="#eeeeeedd",
    point_hover_color="#aa0000",
    point_radius_min_pixels=0.01,
    point_radius_max_pixels=24,
    point_line_width_min_pixels=0.1,
    point_line_width_max_pizels=8,
    point_line_width=32,
    color_label_text=True,
    darkmode=False,
):
    views = [pdk.View(type="OrthographicView", controller=True)]
    # Compute point scaling
    n_points = point_dataframe.shape[0]
    magic_number = np.clip(32 * 4 ** (-np.log10(n_points)), 0.005, 4)
    if "size" not in point_dataframe.columns:
        point_size = magic_number
    else:
        point_dataframe["size"] = magic_number * (
            point_dataframe["size"] / point_dataframe["size"].median()
        )
        point_size = "size"

    if darkmode and text_outline_color == "#eeeeeedd":
        text_outline_color = "#111111dd"
    documents_layer = pdk.Layer(
        "ScatterplotLayer",
        point_dataframe,
        coordinate_system=None,
        get_position=["x", "y"],
        get_fill_color="color",
        get_radius=point_size,
        radius_units="'common'",
        line_width_unit="'common'",
        stroked=True,
        get_line_color=[250, 250, 250, 128] if not darkmode else [5, 5, 5, 128],
        get_line_width=point_line_width,
        line_width_min_pixels=point_line_width_min_pixels,
        line_width_max_pixels=point_line_width_max_pizels,
        radius_min_pixels=point_radius_min_pixels,
        radius_max_pixels=point_radius_max_pixels,
        pickable=True,
        auto_highlight=True,
        highlight_color=[int(c * 255) for c in to_rgba(point_hover_color)],
    )
    # Compute text scaling
    size_range = label_dataframe["size"].max() - label_dataframe["size"].min()
    label_dataframe["size"] = (
        label_dataframe["size"] - label_dataframe["size"].min()
    ) * ((max_fontsize - min_fontsize) / size_range) + min_fontsize

    # Text color depending on color_label_text and darkmode
    if color_label_text:
        label_text_color = ["r", "g", "b"]
    else:
        if darkmode:
            label_text_color = [255, 255, 255]
        else:
            label_text_color = [0, 0, 0]

    labels_layer = pdk.Layer(
        "TextLayer",
        label_dataframe,
        pickable=False,
        get_position=["x", "y"],
        get_text="label",
        get_color=label_text_color,
        get_size="size",
        size_scale=1,
        size_min_pixels=text_min_pixel_size,
        size_max_pixels=text_max_pixel_size,
        outline_width=text_outline_width,
        outline_color=[int(c * 255) for c in to_rgba(text_outline_color)],
        get_background_color=[255, 255, 255, 64] if not darkmode else [0, 0, 0, 64],
        background=True,
        font_family=pdk.types.String(font_family),
        font_settings={"sdf": True},
        get_text_anchor=pdk.types.String("middle"),
        get_alignment_baseline=pdk.types.String("center"),
        line_height=line_spacing,
        elevation=100,
    )
    layers = [documents_layer, labels_layer]
    if "polygon" in label_dataframe.columns:
        boundary_layer = pdk.Layer(
            "PolygonLayer",
            label_dataframe,
            stroked=True,
            filled=False,
            get_line_color=["r", "g", "b", "a"],
            get_polygon="polygon",
            lineWidthUnits="'common'",
            get_line_width="size * size",
            line_width_scale=5e-5,
            line_joint_rounded=True,
            line_width_max_pixels=4,
            line_width_min_pixels=0.0,
        )
        layers.append(boundary_layer)

    deck = pdk.Deck(
        layers=layers,
        map_style="light",
        initial_view_state={"latitude": 0, "longitude": 0, "zoom": 4},
        map_provider=None,
        width=800,
        height=800,
        tooltip={
            "html": "{hover_text}",
        },
    )
    return deck


def render_deck_to_html(
    deck,
    title=None,
    sub_title=None,
    title_font_size=36,
    sub_title_font_size=18,
    text_collision_size_scale=2,
    text_min_pixel_size=8,
    text_max_pixel_size=36,
    font_family="arial",
    logo=None,
    logo_width=256,
    darkmode=False,
):
    pdk.io.html.DECKGL_SEMVER = "8.9.*"
    pdk.io.html.CDN_URL = (
        "https://cdn.jsdelivr.net/npm/@deck.gl/jupyter-widget@{}/dist/index.js".format(
            pdk.io.html.DECKGL_SEMVER
        )
    )
    template = jinja2.Template(_DECKGL_TEMPLATE_STR)
    deck_json = deck.to_json()
    dict_deck_json = json.loads(deck_json)
    dict_deck_json["layers"][1]["extensions"] = [{"@@type": "CollisionFilterExtension"}]
    dict_deck_json["layers"][1]["getCollisionPriority"] = "@@=size"
    dict_deck_json["layers"][1]["collisionTestProps"] = {
        "sizeScale": text_collision_size_scale,
        "sizeMinPixels": text_min_pixel_size * 1.5,
        "sizeMaxPixels": text_max_pixel_size * 1.5,
    }
    deck_json = json.dumps(dict_deck_json)
    css_template = pdk.io.html.j2_env.get_template("style.j2")
    css_str = css_template.render(
        css_background_color="#ffffff" if not darkmode else "#000000"
    )
    api_fontname = font_family.replace(" ", "+")
    resp = requests.get(f"https://fonts.googleapis.com/css?family={api_fontname}")
    title_color = "#000000" if not darkmode else "#ffffff"
    title_background = "#ffffffaa" if not darkmode else "#000000aa"
    if resp.ok:
        html_str = template.render(
            json_input=deck_json,
            deckgl_jupyter_widget_bundle=pdk.io.html.cdn_picker(offline=False),
            tooltip=pdk.io.html.convert_js_bool(deck._tooltip),
            css_text=css_str,
            title=title if title is not None else "Interactive Data Map",
            sub_title=sub_title if sub_title is not None else "",
            use_title=title is not None,
            title_font_size=title_font_size,
            title_font_family=font_family,
            sub_title_font_size=sub_title_font_size,
            google_font=api_fontname,
            title_color=title_color,
            title_background=title_background,
            logo=logo,
            logo_width=logo_width,
        )
    else:
        html_str = template.render(
            json_input=deck_json,
            deckgl_jupyter_widget_bundle=pdk.io.html.cdn_picker(offline=False),
            tooltip=pdk.io.html.convert_js_bool(deck._tooltip),
            css_text=css_str,
            title=title if title is not None else "Interactive Data Map",
            sub_title=sub_title if sub_title is not None else "",
            use_title=title is not None,
            title_font_size=title_font_size,
            title_font_family=font_family,
            sub_title_font_size=sub_title_font_size,
            title_color=title_color,
            title_background=title_background,
            logo=logo,
            logo_width=logo_width,
        )
    return html_str


def render_deck(
    point_dataframe,
    label_dataframe,
    font_family="arial",
    line_spacing=0.75,
    min_fontsize=12,
    max_fontsize=24,
    text_outline_width=8,
    text_min_pixel_size=8,
    text_max_pixel_size=36,
    text_collision_size_scale=1,
    text_outline_color="#eeeeeedd",
    point_hover_color="#aa0000",
    point_radius_min_pixels=0.01,
    point_radius_max_pixels=24,
    point_line_width_min_pixels=0.1,
    point_line_width_max_pizels=8,
    point_line_width=32,
    title=None,
    sub_title=None,
    title_font_size=36,
    sub_title_font_size=18,
    logo=None,
    logo_width=256,
    color_label_text=True,
    darkmode=False,
):
    deck = deck_from_dataframes(
        point_dataframe,
        label_dataframe,
        font_family=font_family,
        line_spacing=line_spacing,
        min_fontsize=min_fontsize,
        max_fontsize=max_fontsize,
        text_outline_width=text_outline_width,
        text_min_pixel_size=text_min_pixel_size,
        text_max_pixel_size=text_max_pixel_size,
        text_outline_color=text_outline_color,
        point_hover_color=point_hover_color,
        point_radius_min_pixels=point_radius_min_pixels,
        point_radius_max_pixels=point_radius_max_pixels,
        point_line_width_min_pixels=point_line_width_min_pixels,
        point_line_width_max_pizels=point_line_width_max_pizels,
        point_line_width=point_line_width,
        color_label_text=color_label_text,
        darkmode=darkmode,
    )

    html_str = render_deck_to_html(
        deck,
        title=title,
        sub_title=sub_title,
        title_font_size=title_font_size,
        sub_title_font_size=sub_title_font_size,
        text_min_pixel_size=text_min_pixel_size,
        text_max_pixel_size=text_max_pixel_size,
        text_collision_size_scale=text_collision_size_scale,
        font_family=font_family,
        logo=logo,
        logo_width=logo_width,
        darkmode=darkmode,
    )
    return html_str
