import numpy as np
import pandas as pd

import jinja2
import requests
import base64
import io
import gzip
import html
import warnings

from scipy.spatial import Delaunay
from matplotlib.colors import to_rgba

from datamapplot.medoids import medoid
from datamapplot.alpha_shapes import create_boundary_polygons, smooth_polygon

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
       
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.2.0/css/bootstrap-theme.min.css" />
    <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/font-awesome/4.6.3/css/font-awesome.min.css" />
    <script src="https://unpkg.com/deck.gl@latest/dist.min.js"></script>
    {% if inline_data %}
    <script src="https://unpkg.com/fflate@0.8.0"></script>
    {% endif %}
    <style>
        body {
          margin: 0;
          padding: 0;
          overflow: hidden;
          background: {{page_background_color}};
        }

        #deck-container {
          width: 100vw;
          height: 100vh;
        }

        #deck-container canvas {
          z-index: 1;
          background: {{page_background_color}};
        }

        .deck-tooltip {
            font-size: 0.8em;
            font-family: Helvetica, Arial, sans-serif;
            width: 25%;
        }

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
            color: {{title_font_color}};
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
        <span style="font-family:{{title_font_family}};font-size:{{title_font_size}}pt;color:{{title_font_color}}">
            {{title}}
        </span><br/>
        <span style="font-family:{{title_font_family}};font-size:{{sub_title_font_size}}pt;color:{{sub_title_font_color}}">
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
  <script type="module">
    import { ArrowLoader } from 'https://cdn.jsdelivr.net/npm/@loaders.gl/arrow@4.1.0-alpha.10/+esm'
    import { JSONLoader } from 'https://cdn.jsdelivr.net/npm/@loaders.gl/json@4.0.5/+esm'
    {% if not inline_data %}
    import { ZipLoader } from 'https://cdn.jsdelivr.net/npm/@loaders.gl/zip@4.1.0-alpha.10/+esm'
    import { CSVLoader } from 'https://cdn.jsdelivr.net/npm/@loaders.gl/csv@4.1.0-alpha.10/+esm'
    {% endif %}

    {% if inline_data %}
    const pointDataBase64 = "{{base64_point_data}}";
    const pointDataBuffer = fflate.strToU8(atob(pointDataBase64), true);
    const pointData = await loaders.parse(pointDataBuffer, ArrowLoader);
    const hoverDataBase64 = "{{base64_hover_data}}";
    const hoverDataBuffer = fflate.strToU8(atob(hoverDataBase64), true);
    const unzippedHoverData = fflate.gunzipSync(hoverDataBuffer);
    const hoverData = await loaders.parse(unzippedHoverData, ArrowLoader);
    const labelDataBase64 = "{{base64_label_data}}";
    const labelDataBuffer = fflate.strToU8(atob(labelDataBase64), true);
    const unzippedLabelData = fflate.gunzipSync(labelDataBuffer);    
    const labelData = await loaders.parse(unzippedLabelData, JSONLoader);
    {% else %}
    const pointData = await loaders.load("point_df.arrow", ArrowLoader);
    const unzippedHoverData = await loaders.load("point_hover_text_arrow.zip", ZipLoader);
    const hoverData = await loaders.parse(unzippedHoverData["point_hover_text.arrow"], ArrowLoader);
    const unzippedLabelData = await loaders.load("label_data_json.zip", ZipLoader);
    const labelData = await loaders.parse(unzippedLabelData["label_data.json"], JSONLoader);
    {% endif %}
    
    const DATA = {src: pointData.data, length: pointData.data.x.length}

    const container = document.getElementById('deck-container');
    const pointLayer = new deck.ScatterplotLayer({
        id: 'dataPointLayer',
        data: DATA,
        getPosition: (object, {index, data}) => {
            return [data.src.x[index], data.src.y[index]];
        },
        {% if point_size < 0 %}
        getRadius: (object, {index, data}) => {
            return data.src.size[index];
        },
        {% else %}
        getRadius: {{point_size}},
        {% endif %}
        getFillColor: (object, {index, data}) => {
            return [
                data.src.r[index], 
                data.src.g[index], 
                data.src.b[index],
                180
            ]
        },
        getLineColor: (object, {index, data}) => {
            return [
                data.src.r[index], 
                data.src.g[index], 
                data.src.b[index],
                32
            ]
        },       
        getLineColor: {{point_outline_color}},
        getLineWidth: {{point_line_width}},
        highlightColor: {{point_hover_color}}, 
        lineWidthMaxPixels: {{point_line_width_max_pixels}},
        lineWidthMinPixels: {{point_line_width_min_pixels}},
        radiusMaxPixels: {{point_radius_max_pixels}}, 
        radiusMinPixels: {{point_radius_min_pixels}},
        radiusUnits: "common", 
        lineWidthUnits: "common", 
        autoHighlight: true,
        pickable: true, 
        stroked: true
    });
    const labelLayer = new deck.TextLayer({
        id: "textLabelLayer",
        data: labelData,
        pickable: false,
        getPosition: d => [d.x, d.y],
        getText: d => d.label,
        getColor: {{label_text_color}},
        getSize: d => d.size,
        sizeScale: 1,
        sizeMinPixels: {{text_min_pixel_size}},
        sizeMaxPixels: {{text_max_pixel_size}},
        outlineWidth: {{text_outline_width}},
        outlineColor: {{text_outline_color}},
        getBackgroundColor: {{text_background_color}},
        getBackgroundPadding: [15, 15, 15, 15],
        background: true,
        characterSet: "auto",
        fontFamily: "{{font_family}}",
        lineHeight: {{line_spacing}},
        fontSettings: {"sdf": true},
        getTextAnchor: "middle",
        getAlignmentBaseline: "center",
        lineHeight: 0.95,
        elevation: 100,
        // CollideExtension options
        collisionEnabled: true,
        getCollisionPriority: d => d.size,
        collisionTestProps: {
          sizeScale: {{text_collision_size_scale}},
          sizeMaxPixels: {{text_max_pixel_size}} * 2,
          sizeMinPixels: {{text_min_pixel_size}} * 2
        },
        extensions: [new deck.CollisionFilterExtension()],
    });
    {% if cluster_boundary_polygons %}
    const boundaryLayer = new deck.PolygonLayer({
        data: labelData,
        stroked: true,
        filled: false,
        getLineColor: d => [d.r, d.g, d.b, d.a],
        getPolygon: d => d.polygon,
        lineWidthUnits: "common",
        getLineWidth: d => d.size * d.size,
        lineWidthScale: 5e-5,
        lineJointRounded: true,
        lineWidthMaxPixels: 4,
        lineWidthMinPixels: 0.0,
    });
    {% endif %}

    const deckgl = new deck.DeckGL({
      container: container,
      initialViewState: {
        latitude: {{data_center_y}},
        longitude: {{data_center_x}},
        zoom: {{zoom_level}}
      },
      controller: true,
      {% if cluster_boundary_polygons %}
      layers: [pointLayer, boundaryLayer, labelLayer],
      {% else %}
      layers: [pointLayer, labelLayer],
      {% endif %}
      getTooltip: {{get_tooltip}}
    });
    </script>
</html>
"""


class FormattingDict(dict):
    def __missing__(self, key):
        return f"{{{key}}}"


class InteractiveFigure:
    """A simple class to hold interactive plot outputs. This allows for
    and object with a `_repr_html_` to display in notebooks.

    The actual content of the plot is HTML, and the `save` method can
    be used to save the results to an HTML file while can then be shared.
    """

    def __init__(self, html_str, width="100%", height=800):
        self._html_str = html_str
        self.width = width
        self.height = height

    def __repr__(self):
        return f"<InteractiveFigure width={self.width} height={self.height}>"

    def __str__(self):
        return self._html_str

    def _repr_html_(self):
        src_doc = html.escape(self._html_str)
        iframe = f"""
            <iframe
                width={self.width}
                height={self.height}
                frameborder="0"
                srcdoc="{src_doc}"
            ></iframe>
        """
        from IPython.display import HTML

        with warnings.catch_warnings():
            msg = "Consider using IPython.display.IFrame instead"
            warnings.filterwarnings("ignore", message=msg)

            html_obj = HTML(iframe)
            return getattr(html_obj, "data", "")

    def save(self, filename):
        """Save an interactive firgure to the HTML file with name `filename`"""
        with open(filename, "w+") as f:
            f.write(self._html_str)


def label_text_and_polygon_dataframes(
    labels,
    data_map_coords,
    noise_label="Unlabelled",
    use_medoids=False,
    cluster_polygons=False,
    alpha=0.05,
):
    cluster_label_vector = np.asarray(labels)
    unique_non_noise_labels = [
        label for label in np.unique(cluster_label_vector) if label != noise_label
    ]
    label_map = {n: i for i, n in enumerate(unique_non_noise_labels)}
    label_map[noise_label] = -1
    label_unmap = {i: n for n, i in label_map.items()}
    cluster_idx_vector = np.asarray(pd.Series(cluster_label_vector).map(label_map))

    label_locations = []
    cluster_sizes = []
    polygons = []

    for i, l in enumerate(unique_non_noise_labels):
        cluster_mask = cluster_idx_vector == i
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
                    smooth_polygon(x).tolist()
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


def render_html(
    point_dataframe,
    label_dataframe,
    inline_data=True,
    title=None,
    sub_title=None,
    title_font_size=36,
    sub_title_font_size=18,
    text_collision_size_scale=3,
    text_min_pixel_size=12,
    text_max_pixel_size=36,
    font_family="arial",
    logo=None,
    logo_width=256,
    color_label_text=True,
    line_spacing=0.95,
    min_fontsize=12,
    max_fontsize=24,
    text_outline_width=8,
    text_outline_color="#eeeeeedd",
    point_hover_color="#aa0000bb",
    point_radius_min_pixels=0.01,
    point_radius_max_pixels=24,
    point_line_width_min_pixels=0.1,
    point_line_width_max_pixels=8,
    point_line_width=0.001,
    darkmode=False,
    hover_text_html_template=None,
    extra_point_data=None,
):
    """Given data about points, and data about labels, render to an HTML file
    using Deck.GL to provide an interactive plot that can be zoomed, panned
    and explored.

    Parameters
    ----------
    point_dataframe: pandas.DataFrame
        A Dataframe containing point information for rendering. At a minimum this
        should include columns `"x"`, `"y"`, `"r"`, `"g"`, `"b"` and `"a"` that
        provide the x,y position and r,g,b color for each point. Note that r,g,b,a
        values should be uint8 values.

    label_dataframe: pandas.DataFrame
        A Dataframe containing information about labels, and optionally bounding
        polygons, of clusters. At a minimum this should include columns
        `"x"`, `"y"`, `"r"`, `"g"`, `"b"` and `"a"` that provide the x,y position
        and r,g,b colour of the label.

    inline_data: bool (optional, default=True)
        Whether to include data inline in the HTML file (compressed and base64 encoded)
        of whether to write data to separate files that will then be referenced by the
        HTML file -- in the latter case you will need to ensure all the files are
        co-located and served over an http server or similar. Inline is the best
        default choice for easy portability and simplicity, but can result in very
        large file sizes.

    title: str or None (optional, default=None)
        A title for the plot, to be placed in the top left corner. The title should be
        brief and to the point. More detail can be provided in the sub_title if required.

    sub_title: str or None (optional, default=None)
        A sub_title for the plot, to be placed in the top left corner.

    title_font_size: int (optional, default=36)
        The font-size of the title in points.

    sub_title_font_size: int (optional, default=18)
        The font-size of the sub-title in points.

    text_collision_size_scale: float (optional, default=3.0)
        How to scale text labels for the purpose of collision detection to determine
        which labels to display.

    text_min_pixel_size: float (optional, default=12.0)
    text_max_pixel_size: float (optional, default=36.0)
    font_family: str (optional, default="arial")
    logo: str or None (optional, default=None)
    logo_width: int (optional, default=256)
    color_label_text: bool (optional, default=True)
    line_spacing: float (optional, default=0.95)
    min_fontsize: float (optional, default=12)
    max_fontsize: float (optional, default=24)
    text_outline_width: float (optional, default=8)
    text_outline_color: str (optional, default="#eeeeeedd")
    point_hover_color: str (optional, default="#aa0000bb")
    point_radius_min_pixels: float (optional, default=0.01)
    point_radius_max_pixels: float (optional, default=24)
    point_line_width_min_pixels: float (optional, default=0.1)
    point_line_width_max_pixels: float (optional, default=8)
    point_line_width: float (optional, default=0.001)
    darkmode: bool (optional, default=False)
    hover_text_html_template: str or None (optional, default=None)
    extra_point_data: pandas.DataFrame or None (optional, default=None)

    Returns
    -------
    interactive_plot: InteractiveFigure
        An interactive figure with hover, pan, and zoom. This will display natively
        in a notebook, and can be saved to an HTML file via the `save` method.
    """
    # Compute point scaling
    n_points = point_dataframe.shape[0]
    magic_number = np.clip(32 * 4 ** (-np.log10(n_points)), 0.005, 4)
    if "size" not in point_dataframe.columns:
        point_size = magic_number
    else:
        point_dataframe["size"] = magic_number * (
            point_dataframe["size"] / point_dataframe["size"].median()
        )
        point_size = -1

    # Compute zoom level and initial view location
    data_width = point_dataframe.x.max() - point_dataframe.x.min()
    data_height = point_dataframe.y.max() - point_dataframe.y.min()
    data_center = point_dataframe[["x", "y"]].values.mean(axis=0)

    spread = max(data_width, data_height)
    if spread < (360.0 * np.power(2.0, -20)):
        zoom_level = 21
    else:
        zoom_level = max(1, np.log2(360.0) - np.log2(spread))

    if darkmode and text_outline_color == "#eeeeeedd":
        text_outline_color = "#111111dd"

    point_outline_color = [250, 250, 250, 128] if not darkmode else [5, 5, 5, 128]
    text_background_color = [255, 255, 255, 64] if not darkmode else [0, 0, 0, 64]
    if color_label_text:
        label_text_color = "d => [d.r, d.g, d.b]"
    else:
        label_text_color = [0, 0, 0, 255] if not darkmode else [255, 255, 255, 255]

    # Compute text scaling
    size_range = label_dataframe["size"].max() - label_dataframe["size"].min()
    label_dataframe["size"] = (
        label_dataframe["size"] - label_dataframe["size"].min()
    ) * ((max_fontsize - min_fontsize) / size_range) + min_fontsize

    # Prep data for inlining or storage
    if point_size < 0:
        point_data = point_dataframe[["x", "y", "r", "g", "b", "a", "size"]]
    else:
        point_data = point_dataframe[["x", "y", "r", "g", "b", "a"]]

    if "hover_text" in point_dataframe.columns:
        if extra_point_data is not None and hover_text_html_template is not None:
            hover_data = pd.concat(
                [point_dataframe[["hover_text"]], extra_point_data],
                axis=1,
            )
            replacements = FormattingDict(
                **{
                    str(name): f"${{hoverData.data.{name}[index]}}"
                    for name in hover_data.columns
                }
            )
            get_tooltip = (
                '({index, picked}) => picked ? {"html": `'
                + hover_text_html_template.format_map(replacements)
                + "`} : null"
            )
        else:
            hover_data = point_dataframe[["hover_text"]]
            get_tooltip = "({index}) => hoverData.data.hover_text[index]"
    else:
        hover_data = pd.Dataframe()
        get_tooltip = "null"

    if inline_data:
        buffer = io.BytesIO()
        point_data.to_feather(buffer, compression="uncompressed")
        buffer.seek(0)
        base64_point_data = base64.b64encode(buffer.read()).decode()
        buffer = io.BytesIO()
        hover_data.to_feather(buffer, compression="uncompressed")
        buffer.seek(0)
        arrow_bytes = buffer.read()
        gzipped_bytes = gzip.compress(arrow_bytes)
        base64_hover_data = base64.b64encode(gzipped_bytes).decode()
        label_data_json = label_dataframe.to_json(orient="records")
        gzipped_label_data = gzip.compress(bytes(label_data_json, "utf-8"))
        base64_label_data = base64.b64encode(gzipped_label_data).decode()
    else:
        base64_point_data = ""
        base64_hover_data = ""
        base64_label_data = ""
        point_data.to_feather("point_df.arrow", compression="uncompressed")
        hover_data.to_csv("point_hover_text.zip", index=False, columns=("hover_text",))
        label_dataframe.to_json("label_data.json", orient="records")

    title_font_color = "#000000" if not darkmode else "#ffffff"
    sub_title_font_color = "#777777"
    title_background = "#ffffffaa" if not darkmode else "#000000aa"

    template = jinja2.Template(_DECKGL_TEMPLATE_STR)
    api_fontname = font_family.replace(" ", "+")
    resp = requests.get(f"https://fonts.googleapis.com/css?family={api_fontname}")

    if resp.ok:
        html_str = template.render(
            title=title if title is not None else "Interactive Data Map",
            sub_title=sub_title if sub_title is not None else "",
            google_font=api_fontname,
            page_background_color="#ffffff" if not darkmode else "#000000",
            title_font_family=font_family,
            title_font_color=title_font_color,
            title_background=title_background,
            use_title=title is not None,
            title_font_size=title_font_size,
            sub_title_font_sizee=sub_title_font_size,
            sub_title_font_color=sub_title_font_color,
            logo=logo,
            logo_width=logo_width,
            inline_data=inline_data,
            base64_point_data=base64_point_data,
            base64_hover_data=base64_hover_data,
            base64_label_data=base64_label_data,
            point_size=point_size,
            point_outline_color=point_outline_color,
            point_line_width=point_line_width,
            point_hover_color=[int(c * 255) for c in to_rgba(point_hover_color)],
            point_line_width_max_pixels=point_line_width_max_pixels,
            point_line_width_min_pixels=point_line_width_min_pixels,
            point_radius_max_pixels=point_radius_max_pixels,
            point_radius_min_pixels=point_radius_min_pixels,
            label_text_color=label_text_color,
            line_spacing=line_spacing,
            text_min_pixel_size=text_min_pixel_size,
            text_max_pixel_size=text_max_pixel_size,
            text_outline_width=text_outline_width,
            text_outline_color=[int(c * 255) for c in to_rgba(text_outline_color)],
            text_background_color=text_background_color,
            font_family=font_family,
            text_collision_size_scale=text_collision_size_scale,
            cluster_boundary_polygons="polygon" in label_dataframe.columns,
            zoom_level=zoom_level,
            data_center_x=data_center[0],
            data_center_y=data_center[1],
            get_tooltip=get_tooltip,
        )
    else:
        html_str = template.render(
            title=title if title is not None else "Interactive Data Map",
            sub_title=sub_title if sub_title is not None else "",
            page_background_color=title_background,
            title_font_family=font_family,
            title_font_color=title_font_color,
            title_background=title_background,
            use_title=title is not None,
            title_font_size=title_font_size,
            sub_title_font_sizee=sub_title_font_size,
            sub_title_font_color=sub_title_font_color,
            logo=logo,
            logo_width=logo_width,
            inline_data=inline_data,
            base64_point_data=base64_point_data,
            base64_hover_data=base64_hover_data,
            base64_label_data=base64_label_data,
            point_size=point_size,
            point_outline_color=point_outline_color,
            point_line_width=point_line_width,
            point_hover_color=[int(c * 255) for c in to_rgba(point_hover_color)],
            point_line_width_max_pixels=point_line_width_max_pixels,
            point_line_width_min_pixels=point_line_width_min_pixels,
            point_radius_max_pixels=point_radius_max_pixels,
            point_radius_min_pixels=point_radius_min_pixels,
            label_text_color=label_text_color,
            line_spacing=line_spacing,
            text_min_pixel_size=text_min_pixel_size,
            text_max_pixel_size=text_max_pixel_size,
            text_outline_width=text_outline_width,
            text_outline_color=[int(c * 255) for c in to_rgba(text_outline_color)],
            text_background_color=text_background_color,
            font_family=font_family,
            text_collision_size_scale=text_collision_size_scale,
            cluster_boundary_polygons="polygon" in label_dataframe.columns,
            zoom_level=zoom_level,
            data_center_x=data_center[0],
            data_center_y=data_center[1],
            get_tooltip=get_tooltip,
        )
    return html_str
