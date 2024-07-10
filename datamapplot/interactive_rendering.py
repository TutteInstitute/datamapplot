import numpy as np
import pandas as pd

import jinja2
import requests
import base64
import io
import gzip
import html
import warnings
import zipfile
import os

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
    {% if google_tooltip_font %}
    <link href="https://fonts.googleapis.com/css2?family={{google_tooltip_font}}&display=swap" rel="stylesheet">
    {% endif %}
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
            {{tooltip_css}}
        }
        
        #loading {
            width: 100%;
            height: 100%;
            top: 0px;
            left: 0px;
            position: absolute;
            display: block; 
            z-index: 99
        }

        #loading-image {
            position: absolute;
            top: 45%;
            left: 47.5%;
            z-index: 100
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
            box-shadow: 2px 3px 10px {{shadow_color}};
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
            box-shadow: 2px 3px 10px {{shadow_color}};
        }
        img {
            display: block;
            margin-left: auto;
            margin-right: auto;
        }
        {% endif %}
        {% if search %}
        #search-container{
            position: absolute;
            left: -16px;
            margin: 16px;
            padding: 12px;
            border-radius: 16px;
            z-index: 2;
            font-family: {{font_family}};
            color: {{title_font_color}};
            background: {{title_background}};
            width: fit-content;
            box-shadow: 2px 3px 10px {{shadow_color}};
        }
        input {
            margin: 2px;
            padding: 4px;
            border-radius: 8px;
            color: {{title_font_color}};
            background: {{input_background}};
            border: 1px solid {{input_border}};
            transition: 0.5s;
            outline: none;
        }
        input:focus {
          border: 2px solid #555;
        }
        {% endif %}
        {% if custom_css %}
        {{custom_css}}
        {% endif %}
    </style>
  </head>
  <body>
    <div id="loading">
        <img id="loading-image" src="https://i.gifer.com/ZKZg.gif" alt="Loading..." width="5%"/>
    </div>
    {% if use_title %}
    <div id="title-container">
        <span style="font-family:{{title_font_family}};font-size:{{title_font_size}}pt;color:{{title_font_color}}">
            {{title}}
        </span><br/>
        <span style="font-family:{{title_font_family}};font-size:{{sub_title_font_size}}pt;color:{{sub_title_font_color}}">
            {{sub_title}}
        </span>
        {% if search %}
        <div id="search-container">
            <input autocomplete="off" type="search" id="search" placeholder="🔍">
        </div>
        {% endif %}
    </div>
    {% elif search %}
    <div id="search-container" style="left:0 !important">
        <input autocomplete="off" type="search" id="search" placeholder="🔍">
    </div>
    {% endif %}
    {% if logo %}
    <div id="logo-container">
      <img src={{logo}} style="width:{{logo_width}}px">
    </div>
    {% endif %}
    <div id="deck-container">
    </div>
    {% if custom_html %}
    {{custom_html}}
    {% endif %}
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
    const pointData = await loaders.load("{{file_prefix}}_point_df.arrow", ArrowLoader);
    const unzippedHoverData = await loaders.load("{{file_prefix}}_point_hover_data.zip", ZipLoader);
    const hoverData = await loaders.parse(unzippedHoverData["point_hover_data.arrow"], ArrowLoader);
    const unzippedLabelData = await loaders.load("{{file_prefix}}_label_data.zip", ZipLoader);
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
                data.src.a[index],
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
        fontWeight: {{font_weight}},
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
        lineWidthScale: {{cluster_boundary_line_width}} * 5e-5,
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
      {% if on_click %}
      onClick: {{on_click}},
      {% endif %}
      getTooltip: {{get_tooltip}}
    });
    
    document.getElementById("loading").style.display = "none";
        
    {% if search %}
        function selectPoints(item, conditional) {
        var layerId;
        if (item) {
            for (var i = 0; i < DATA.length; i++) {
                if (conditional(i)) {
                    DATA.src.selected[i] = 1;
                } else {
                    DATA.src.selected[i] = 0;
                }
            }
            layerId = 'selectedPointLayer' + item;
        } else {
            for (var i = 0; i < DATA.length; i++) {
                DATA.src.selected[i] = 1;
            }
            layerId = 'dataPointLayer';
        }
        const selectedPointLayer = pointLayer.clone(
            {
                id: layerId,
                data: DATA,
                getFilterValue: (object, {index, data}) => data.src.selected[index],
                filterRange: [1, 2],
                extensions: [new deck.DataFilterExtension({filterSize: 1})]
            }
        );
        deckgl.setProps(
            {layers: 
                [selectedPointLayer].concat(deckgl.props.layers.slice(1,))
            }
        );
    }
    
    const search = document.getElementById("search");
    search.addEventListener("input", (event) => {
            const search_term = event.target.value.toLowerCase();
            selectPoints(search_term, (i) => hoverData.data.{{search_field}}[i].toLowerCase().includes(search_term));
        }
    );
    {% endif %}
    {% if custom_js %}
    {{custom_js}}
    {% endif %}
    </script>
</html>
"""

_TOOL_TIP_CSS = """
            font-size: 0.8em;
            font-family: {{title_font_family}};
            font-weight: {{title_font_weight}};
            color: {{title_font_color}} !important;
            background-color: {{title_background}} !important;
            border-radius: 12px;
            box-shadow: 2px 3px 10px {{shadow_color}};
            max-width: 25%;
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
    text_min_pixel_size=18,
    text_max_pixel_size=36,
    font_family="Roboto",
    font_weight=900,
    tooltip_font_family=None,
    tooltip_font_weight=300,
    logo=None,
    logo_width=256,
    color_label_text=True,
    line_spacing=0.95,
    min_fontsize=18,
    max_fontsize=28,
    text_outline_width=8,
    text_outline_color="#eeeeeedd",
    point_size_scale=None,
    point_hover_color="#aa0000bb",
    point_radius_min_pixels=0.01,
    point_radius_max_pixels=24,
    point_line_width_min_pixels=0.1,
    point_line_width_max_pixels=8,
    point_line_width=0.001,
    cluster_boundary_line_width=1,
    initial_zoom_fraction=1.0,
    background_color=None,
    darkmode=False,
    offline_data_prefix=None,
    tooltip_css=None,
    hover_text_html_template=None,
    extra_point_data=None,
    enable_search=False,
    search_field="hover_text",
    on_click=None,
    custom_html=None,
    custom_css=None,
    custom_js=None,
    alpha=180 / 255,
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
        The minimum pixel size of label text. If text would be smaller than this in size
        then render the text to be at least this size.

    text_max_pixel_size: float (optional, default=36.0)
        The maximum pixel size of label text. If text would be larger than this in size
        then render the text to be at most this size.

    font_family: str (optional, default="Roboto")
        The font family to use for label text and titles. If the font family is a
        google font then the required google font api handling will automatically
        make the font available, so any google font family is acceptable.

    font_weight: str or int (optional, default=900)
        The font weight to use for the text labels within the plot. Either weight
        specification such as "thin", "normal", or "bold" or an integer value
        between 0 (ultra-thin) and 1000 (ultra-black).

    tooltip_font_family: str (optional default="Roboto")
        The font family to use in tooltips/hover text. If the font family is a
        google font then the required google font api handling will automatically
        make the font available, so any google font family is acceptable.

    tooltip_font_weight: str or int (optional, default=400)
        The font weight to use for the tooltip /hover text within the plot. Either weight
        specification such as "thin", "normal", or "bold" or an integer value
        between 0 (ultra-thin) and 1000 (ultra-black).

    logo: str or None (optional, default=None)
        A logo image to include in the bottom right corner of the map. This should be
        a URL to the image.

    logo_width: int (optional, default=256)
        The width, in pixels, of the logo to be included in the bottom right corner.
        The logo will retain it's aspect ratio, so choose the width accordingly.

    color_label_text: bool (optional, default=True)
        Whether the text labels for clusters should be coloured or not. If set to False
        the labels will be either black or white depending on whether ``darkmode`` is set.

    line_spacing: float (optional, default=0.95)
        Line height spacing in label text.

    min_fontsize: float (optional, default=12)
        The minimum font size (in points) of label text. In general label text is scaled
        based on the size of the cluster the label if for; this will set the minimum
        value for that scaling.

    max_fontsize: float (optional, default=24)
        The maximum font size (in points) of label text. In general label text is scaled
        based on the size of the cluster the label if for; this will set the maximum
        value for that scaling.

    text_outline_width: float (optional, default=8)
        The size of the outline around the label text. The outline, in a contrasting
        colour, can make text more readable against the map background. Choosing larger
        sizes can help if text is less legible.

    text_outline_color: str (optional, default="#eeeeeedd")
        The colour of the outline around the label text. The outline should be a
        contrasting colour to the colour of the label text. By default this is white
        when ``darkmode`` is ``False`` and black when ``darkmode`` is ``True``.

    point_size_scale: float or None (optional, default=None)
        The size scale of points. If None the size scale will be determined from the data.

    point_hover_color: str (optional, default="#aa0000bb")
        The colour of the highlighted point a user is hovering over.

    point_radius_min_pixels: float (optional, default=0.01)
        The minimum number of pixels in radius of the points in the map; if zoomed out
        enough that a point would be smaller than this, it is instead rendered at this radius.
        This allows points to remain visible when zoomed out.

    point_radius_max_pixels: float (optional, default=24)
        The maximum number of pixels in radius of the points in the map; if zoomed in
        enough that a point would be larger than this, it is instead rendered at this radius.
        This allows zooming in to differentiate points that are otherwise overtop of one
         another.

    point_line_width_min_pixels: float (optional, default=0.1)
        The minimum pixel width of the outline around points.

    point_line_width_max_pixels: float (optional, default=8)
        The maximum pixel width of the outline around points.

    point_line_width: float (optional, default=0.001)
        The absolute line-width in common coordinates of the outline around points.

    cluster_boundary_line_width: float (optional, default=1.0)
        The linewidth to use for cluster boundaries. Note that cluster boundaries scale with respect
        to cluster size, so this is a scaling factor applied over this.

    initial_zoom_fraction: float (optional, default=1.0)
        The fraction of the total zoom (containing allm the data) to start the
        map in. A lower value will initialize the plot zoomed in, while values
        larger than 1.0 will result in the initial start point being zoomed out.

    background_color: str or None (optional, default=None)
        A background colour (as a hex-string) for the data map. If ``None`` a background
        colour will be chosen automatically based on whether ``darkmode`` is set.

    darkmode: bool (optional, default=False)
        Whether to use darkmode.

    offline_data_prefix: str or None (optional, default=None)
        If ``inline_data=False`` a number of data files will be created storing data for
        the plot and referenced by the HTML file produced. If not none then this will provide
        a prefix on the filename of all the files created.

    tooltip_css: str or None (optional, default=None)
        Custom CSS used to fine the properties of the tooltip. If ``None`` a default
        CSS style will be used. This should simply be the required CSS directives
        specific to the tooltip.

    hover_text_html_template: str or None (optional, default=None)
        An html template allowing fine grained control of what is displayed in the
        hover tooltip. This should be HTML with placeholders of the form ``{hover_text}``
        for the supplied hover text and ``{column_name}`` for columns from
        ``extra_point_data`` (see below).

    extra_point_data: pandas.DataFrame or None (optional, default=None)
        A dataframe of extra information about points. This should be a dataframe with
        one row per point. The information in this dataframe can be referenced by column-name
        by either ``hover_text_html_template`` or ``on_click`` for use in tooltips
        or on-click actions.

    enable_search: bool (optional, default=False)
        Whether to enable a text search that can highlight points with hover_text that
        include the given search string.

    search_field: str (optional, default="hover_text")
        If ``enable_search`` is ``True`` and ``extra_point_data`` is not ``None``, then search
        this column of the ``extra_point_data`` dataframe, or use hover_text if set to
        ``"hover_text"``.

    on_click: str or None (optional, default=None)
        A javascript action to be taken if a point in the data map is clicked. The javascript
        can reference ``{hover_text}`` or columns from ``extra_point_data``. For example one
        could provide ``"window.open(`http://google.com/search?q=\"{hover_text}\"`)"`` to
        open a new window with a google search for the hover_text of the clicked point.

    custom_css: str or None (optional, default=None)
        A string of custom CSS code to be added to the style header of the output HTML. This
        can be used to provide custom styling of other features of the output HTML as required.

    custom_html: str or None (optional, default=None)
        A string of custom HTML to be added to the body of the output HTML. This can be used to
        add other custom elements to the interactive plot, including elements that can be
        interacted with via the ``on_click`` action for example.

    custom_js: str or None (optional, default=None)
        A string of custom Javascript code that is to be added after the code for rendering
        the scatterplot. This can include code to interact with the plot which is stored
        as ``deckgl``.

    Returns
    -------
    interactive_plot: InteractiveFigure
        An interactive figure with hover, pan, and zoom. This will display natively
        in a notebook, and can be saved to an HTML file via the `save` method.
    """
    # Compute point scaling
    n_points = point_dataframe.shape[0]
    if point_size_scale is not None:
        magic_number = point_size_scale / 100.0
    else:
        magic_number = np.clip(32 * 4 ** (-np.log10(n_points)), 0.005, 0.1)

    if "size" not in point_dataframe.columns:
        point_size = magic_number
    else:
        point_dataframe["size"] = magic_number * (
            point_dataframe["size"] / point_dataframe["size"].mean()
        )
        point_size = -1

    # Compute zoom level and initial view location
    data_width = point_dataframe.x.max() - point_dataframe.x.min()
    data_height = point_dataframe.y.max() - point_dataframe.y.min()
    data_center = point_dataframe[["x", "y"]].values.mean(axis=0)

    spread = max(data_width, data_height) * initial_zoom_fraction
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
    if size_range > 0:
        label_dataframe["size"] = (
            label_dataframe["size"] - label_dataframe["size"].min()
        ) * ((max_fontsize - min_fontsize) / size_range) + min_fontsize
    else:
        label_dataframe["size"] = (max_fontsize + min_fontsize) / 2.0

    # Prep data for inlining or storage
    if enable_search:
        point_dataframe["selected"] = np.ones(len(point_dataframe), dtype=np.uint8)
        if point_size < 0:
            point_data = point_dataframe[
                ["x", "y", "r", "g", "b", "a", "size", "selected"]
            ]
        else:
            point_data = point_dataframe[["x", "y", "r", "g", "b", "a", "selected"]]
    else:
        if point_size < 0:
            point_data = point_dataframe[["x", "y", "r", "g", "b", "a", "size"]]
        else:
            point_data = point_dataframe[["x", "y", "r", "g", "b", "a"]]

    if "hover_text" in point_dataframe.columns:
        if extra_point_data is not None:
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
            if hover_text_html_template is not None:
                get_tooltip = (
                    '({index, picked}) => picked ? {"html": `'
                    + hover_text_html_template.format_map(replacements)
                    + "`} : null"
                )
            else:
                get_tooltip = "({index}) => hoverData.data.hover_text[index]"

            if on_click is not None:
                on_click = (
                    "({index, picked}, event) => { if (picked) {"
                    + on_click.format_map(replacements)
                    + " } }"
                )
        else:
            hover_data = point_dataframe[["hover_text"]]
            get_tooltip = "({index}) => hoverData.data.hover_text[index]"

            replacements = FormattingDict(
                **{
                    str(name): f"${{hoverData.data.{name}[index]}}"
                    for name in hover_data.columns
                }
            )

            if on_click is not None:
                on_click = (
                    "({index, picked}, event) => { if (picked) {"
                    + on_click.format_map(replacements)
                    + " } }"
                )
    elif extra_point_data is not None:
        hover_data = extra_point_data
        replacements = FormattingDict(
            **{
                str(name): f"${{hoverData.data.{name}[index]}}"
                for name in hover_data.columns
            }
        )
        if hover_text_html_template is not None:
            get_tooltip = (
                '({index, picked}) => picked ? {"html": `'
                + hover_text_html_template.format_map(replacements)
                + "`} : null"
            )
        else:
            get_tooltip = "null"

        if on_click is not None:
            on_click = (
                "({index, picked}, event) => { if (picked) {"
                + on_click.format_map(replacements)
                + " } }"
            )
    else:
        hover_data = pd.DataFrame(columns=("hover_text",))
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
        file_prefix = None
    else:
        base64_point_data = ""
        base64_hover_data = ""
        base64_label_data = ""
        file_prefix = (
            offline_data_prefix if offline_data_prefix is not None else "datamapplot"
        )
        point_data.to_feather(
            f"{file_prefix}_point_df.arrow", compression="uncompressed"
        )
        hover_data.to_feather("point_hover_data.arrow", compression="uncompressed")
        with zipfile.ZipFile(
            f"{file_prefix}_point_hover_data.zip",
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as f:
            f.write("point_hover_data.arrow")
        os.remove("point_hover_data.arrow")
        label_dataframe.to_json("label_data.json", orient="records")
        with zipfile.ZipFile(
            f"{file_prefix}_label_data.zip",
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as f:
            f.write("label_data.json")
        os.remove("label_data.json")

    title_font_color = "#000000" if not darkmode else "#ffffff"
    sub_title_font_color = "#777777"
    title_background = "#ffffffaa" if not darkmode else "#000000aa"
    shadow_color = "#aaaaaa44" if not darkmode else "#00000044"
    input_background = "#ffffffdd" if not darkmode else "#000000dd"
    input_border = "#ddddddff" if not darkmode else "222222ff"

    if tooltip_css is None:
        tooltip_css_template = jinja2.Template(_TOOL_TIP_CSS)
        tooltip_css = tooltip_css_template.render(
            title_font_family=tooltip_font_family or font_family,
            title_font_color=title_font_color,
            title_font_weight=tooltip_font_weight,
            title_background=title_background,
            shadow_color=shadow_color,
        )

    if background_color is None:
        page_background_color = "#ffffff" if not darkmode else "#000000"
    else:
        page_background_color = background_color

    template = jinja2.Template(_DECKGL_TEMPLATE_STR)
    api_fontname = font_family.replace(" ", "+")
    resp = requests.get(f"https://fonts.googleapis.com/css?family={api_fontname}")
    if not resp.ok:
        api_fontname = None
    if tooltip_font_family is not None:
        api_tooltip_fontname = tooltip_font_family.replace(" ", "+")
        resp = requests.get(
            f"https://fonts.googleapis.com/css?family={api_tooltip_fontname}"
        )
        if not resp.ok:
            api_tooltip_fontname = None
    else:
        api_tooltip_fontname = None

    html_str = template.render(
        title=title if title is not None else "Interactive Data Map",
        sub_title=sub_title if sub_title is not None else "",
        google_font=api_fontname,
        google_tooltip_font=api_tooltip_fontname,
        page_background_color=page_background_color,
        search=enable_search,
        title_font_family=font_family,
        title_font_color=title_font_color,
        title_background=title_background,
        tooltip_css=tooltip_css,
        shadow_color=shadow_color,
        input_background=input_background,
        input_border=input_border,
        custom_css=custom_css,
        use_title=title is not None,
        title_font_size=title_font_size,
        sub_title_font_size=sub_title_font_size,
        sub_title_font_color=sub_title_font_color,
        logo=logo,
        logo_width=logo_width,
        custom_html=custom_html,
        inline_data=inline_data,
        base64_point_data=base64_point_data,
        base64_hover_data=base64_hover_data,
        base64_label_data=base64_label_data,
        file_prefix=file_prefix,
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
        font_weight=font_weight,
        text_collision_size_scale=text_collision_size_scale,
        cluster_boundary_polygons="polygon" in label_dataframe.columns,
        cluster_boundary_line_width=cluster_boundary_line_width,
        zoom_level=zoom_level,
        data_center_x=data_center[0],
        data_center_y=data_center[1],
        on_click=on_click,
        get_tooltip=get_tooltip,
        search_field=search_field,
        custom_js=custom_js,
    )
    return html_str
