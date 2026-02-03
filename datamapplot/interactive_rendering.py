import base64
import gzip
import html
import io
import os
import warnings
import zipfile
import json
import platformdirs
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import jinja2
import numpy as np
import pandas as pd
import requests
import re
from importlib_resources import files
from matplotlib.colors import to_rgba
from pathlib import Path
from rcssmin import cssmin
from rjsmin import jsmin
from scipy.spatial import Delaunay
from colorspacious import cspace_convert
from sklearn.cluster import KMeans
from collections.abc import Iterable

from pandas.api.types import is_string_dtype, is_datetime64_any_dtype
import datetime as dt

from datamapplot.histograms import (
    generate_bins_from_numeric_data,
    generate_bins_from_categorical_data,
    generate_bins_from_temporal_data,
)
from datamapplot.alpha_shapes import create_boundary_polygons, smooth_polygon
from datamapplot.edge_bundling import bundle_edges
from datamapplot.fonts import (
    can_reach_google_fonts,
    query_google_fonts,
    GoogleAPIUnreachable,
)
from datamapplot.medoids import medoid
from datamapplot.config import ConfigManager
from datamapplot import offline_mode_caching
from datamapplot.selection_handlers import SelectionHandlerBase
from datamapplot.interactive_helpers import (
    get_google_font_for_embedding,
    url_to_base64_img,
    build_colormap_data,
    default_colormap_options,
    per_layer_cluster_colormaps,
    compute_point_scaling,
    compute_label_scaling,
    get_style_config,
    get_label_text_color,
    prepare_hover_data,
    prepare_edge_bundle_data,
    prepare_histogram_data,
    prepare_colormap_data,
    encode_inline_data,
    write_offline_data,
    prepare_selection_handler,
    prepare_dynamic_tooltip,
    get_js_dependency_sources,
    get_css_dependency_sources,
    get_js_dependency_urls,
    compute_percentile_bounds,
    cmap_name_to_color_list,
    array_to_colors,
    color_sample_from_colors,
    prepare_offline_mode_data,
    prepare_fonts,
    prepare_logo,
    label_text_and_polygon_dataframes,
)
from datamapplot.widget_helpers import (
    WidgetConfig,
    VALID_LOCATIONS,
    load_widget_config_from_json,
    validate_widget_layout,
    merge_widget_configs,
    widgets_from_legacy_params,
    group_widgets_by_location,
    get_drawer_enabled,
    update_drawer_enabled_for_handlers,
    collect_widget_dependencies,
    legacy_widget_flags_from_widgets,
    collect_widget_data,
    encode_widget_data,
)
from datamapplot.widgets import (
    WidgetBase,
    SearchWidget,
    HistogramWidget,
    TopicTreeWidget,
    LegendWidget,
)

try:
    import matplotlib

    get_cmap = matplotlib.colormaps.get_cmap
except ImportError:
    from matplotlib.cm import get_cmap
from matplotlib.colors import rgb2hex

from warnings import warn

_DEFAULT_DICRETE_COLORMAPS = [
    "tab10",
    "Dark2",
    "Accent",
    "Set3",
    "Paired",
    "tab20",
    "tab20b",
    "tab20c",
    "Set1",
    "Set2",
    "Pastel1",
    "Pastel2",
]

_DEFAULT_CONTINUOUS_COLORMAPS = [
    "viridis",
    "plasma",
    "cividis",
    "YlGnBu",
    "cet_fire",
    "PuRd",
    "BuPu",
    "cet_bgy",
    "cet_CET_L7",
    "cet_CET_L17",
    "cet_gouldian",
]

_CLUSTER_LAYER_DESCRIPTORS = {
    9: [
        "Top",
        "Upper",
        "Upper-mid",
        "Upper-central",
        "Mid",
        "Lower-central",
        "Lower-mid",
        "Lower",
        "Bottom",
    ],
    8: [
        "Top",
        "Upper",
        "Upper-mid",
        "Upper-central",
        "Lower-central",
        "Lower-mid",
        "Lower",
        "Bottom",
    ],
    7: [
        "Top",
        "Upper",
        "Upper-mid",
        "Mid",
        "Lower-mid",
        "Lower",
        "Bottom",
    ],
    6: [
        "Top",
        "Upper",
        "Upper-mid",
        "Lower-mid",
        "Lower",
        "Bottom",
    ],
    5: [
        "Top",
        "Upper",
        "Mid",
        "Lower",
        "Bottom",
    ],
    4: [
        "Top" "Upper-mid",
        "Lower-mid",
        "Bottom",
    ],
    3: [
        "Upper",
        "Mid",
        "Lower",
    ],
    2: [
        "Upper",
        "Lower",
    ],
    1: ["Primary"],
}

cfg = ConfigManager()

_TOPIC_TREE_DEFAULT_KWDS = {
    "title": "Topic Tree",
    "font_size": "12pt",
    "max_width": "30vw",
    "max_height": "42vh",
    "color_bullets": False,
    "button_on_click": None,
    "button_icon": "&#128194",
}

# Legacy template - loaded directly as a string
_DECKGL_TEMPLATE_STR = (files("datamapplot") / "deckgl_template.html").read_text(
    encoding="utf-8"
)

# Template directories for modular template support
_TEMPLATE_DIRS = [
    str(files("datamapplot") / "templates"),  # New modular templates
    str(files("datamapplot")),  # Legacy template location
]


def _get_jinja_env():
    """Get a Jinja2 Environment configured with template directories.

    This enables using {% include %} directives in templates.
    """
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(_TEMPLATE_DIRS),
        autoescape=False,
    )


def _get_template(use_modular=False):
    """Get the appropriate Jinja2 template.

    Parameters
    ----------
    use_modular : bool
        If True, use the new modular template with includes.
        If False, use the legacy single-file template.

    Returns
    -------
    jinja2.Template
        The configured template object.
    """
    if use_modular:
        env = _get_jinja_env()
        return env.get_template("deckgl_template.html.jinja2")
    else:
        return jinja2.Template(_DECKGL_TEMPLATE_STR)


_TOOL_TIP_CSS = """
            font-size: 0.8em;
            font-family: {{title_font_family}};
            font-weight: {{title_font_weight}};
            color: {{title_font_color}} !important;
            background-color: {{title_background[:-2] + "ee"}} !important;
            border-radius: 12px;
            backdrop-filter: blur(6px);
            box-shadow: 2px 3px 10px {{shadow_color}};
            max-width: 25%;
"""

_NOTEBOOK_NON_INLINE_WORKER = """
    const parsingWorkerBlob = new Blob([`
      self.onmessage = async function(event) {
        const { encodedData, JSONParse } = event.data;
        async function DecompressBytes(bytes) {
            const blob = new Blob([bytes]);
            const decompressedStream = blob.stream().pipeThrough(
                new DecompressionStream("gzip")
            );
            const arr = await new Response(decompressedStream).arrayBuffer()
            return new Uint8Array(arr);
        }
        async function decodeBase64(base64) {
            return Uint8Array.from(atob(base64), c => c.charCodeAt(0));
        }
        async function decompressFile(filename) {
          try {
            const response = await fetch(filename, {
              headers: {Authorization: 'Token API_TOKEN'}
            });
            if (!response.ok) {
              throw new Error(\\`HTTP error! status: \\${response.status}. Failed to fetch: \\${filename}\\`);
            }
            const decompressedData = await response.json()
              .then(data => data.content)
              .then(base64data => decodeBase64(base64data))
              .then(buffer => DecompressBytes(buffer));
            return decompressedData;
          } catch (error) {
            console.error('Decompression failed:', error);
            throw error;
          }
        }
        let processedCount = 0;
        const decodedData = encodedData.map(async (file, i) => {
          const binaryData = await decompressFile(file);
          processedCount += 1;
          self.postMessage({ type: "progress", progress: Math.round(((processedCount) / encodedData.length) * 95) });

          if (JSONParse) {
            const parsedData = JSON.parse(new TextDecoder("utf-8").decode(binaryData));
            return { chunkIndex: i, chunkData: parsedData };
          } else {
            return { chunkIndex: i, chunkData: binaryData };
          }
        });
        self.postMessage({ type: "data", data: await Promise.all(decodedData) });
      }
    `], { type: 'application/javascript' });
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

    def __init__(self, html_str, width="100%", height=800, api_token=None):
        self._html_str = html_str
        self.width = width
        self.height = height
        self.api_token = api_token or os.environ.get("JUPYTERHUB_API_TOKEN", None)

    def __repr__(self):
        return f"<InteractiveFigure width={self.width} height={self.height}>"

    def __str__(self):
        return self._html_str

    def _repr_html_(self):
        if "originURL" in self._html_str:
            # If we are google colab non inline data won't work
            try:
                import google.colab

                warn(
                    "You are using `inline_data=False` from within google colab. Due to how colab handles files this will not function correctly."
                )
            except:
                pass
            # We need to redirect the fetch to use the jupyter API endpoint
            # for use in a notebook...
            jupyter_html_str = self._html_str.replace(
                "originURL = self.location.origin + directoryPath;",
                "originURL = document.baseURI.substring(0, document.baseURI.lastIndexOf('/')).replace(/(notebooks|lab.*tree)/, 'api/contents');",
            )
            jupyter_html_str = re.sub(
                r"const parsingWorkerBlob.*?\'application/javascript\' \}\);",
                _NOTEBOOK_NON_INLINE_WORKER,
                jupyter_html_str,
                flags=re.DOTALL,
            )
            if self.api_token is not None:
                jupyter_html_str = jupyter_html_str.replace(
                    "headers: {Authorization: 'Token API_TOKEN'}",
                    f"headers: {{Authorization: 'Token {self.api_token}'}}",
                )
            else:
                jupyter_html_str = jupyter_html_str.replace(
                    "headers: {Authorization    : 'Token API_TOKEN'}", ""
                )
            src_doc = html.escape(jupyter_html_str)
        else:
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
        with open(filename, "w+", encoding="utf-8") as f:
            f.write(self._html_str)

    def save_bundle(self, filename):
        """Save an interactive figure to a zip file with name `filename`"""
        with zipfile.ZipFile(filename, "w") as zf:
            zf.writestr("index.html", self._html_str)
            for filename in re.findall(r"/(.*?_data(?:_\d+)?\.zip)", self._html_str):
                print(f"Adding {filename} to bundle")
                zf.write(filename)


@cfg.complete(unconfigurable={"point_dataframe", "label_dataframe"})
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
    font_weight=600,
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
    point_line_width_min_pixels=0.001,
    point_line_width_max_pixels=3,
    point_line_width=0.001,
    cluster_boundary_line_width=1,
    initial_zoom_fraction=0.999,
    background_color=None,
    background_image=None,
    background_image_bounds=None,
    darkmode=False,
    edge_bundle=False,
    edge_bundle_keywords={
        "n_neighbors": 10,
        "sample_size": None,
        "color_map_nn": 100,
        "hammer_bundle_kwargs": {"use_dask": False},
    },
    edge_width=0.2,
    offline_data_prefix=None,
    offline_data_path=None,
    offline_data_chunk_size=500_000,
    tooltip_css=None,
    hover_text_html_template=None,
    dynamic_tooltip=None,
    extra_point_data=None,
    enable_search=False,
    search_field="hover_text",
    histogram_data=None,
    histogram_enable_click_persistence=False,
    histogram_n_bins=20,
    histogram_group_datetime_by=None,
    histogram_range=None,
    histogram_settings={},
    on_click=None,
    selection_handler=None,
    colormaps=None,
    colormap_rawdata=None,
    colormap_metadata=None,
    cluster_layer_colormaps=False,
    label_layers=None,
    cluster_colormap=None,
    enable_topic_tree=False,
    topic_tree_kwds={},
    show_loading_progress=True,
    custom_html=None,
    custom_css=None,
    custom_js=None,
    minify_deps=True,
    cdn_url="unpkg.com",
    offline_mode=False,
    offline_mode_js_data_file=None,
    offline_mode_font_data_file=None,
    splash_warning=None,
    noise_color="#999999",
    noise_label="Unlabelled",
    widgets=None,
    widget_layout=None,
    default_widget_config=None,
    use_widgets=None,
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

    font_weight: str or int (optional, default=600)
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
        a URL to the image with an http, https, or file scheme.

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

    point_line_width_min_pixels: float (optional, default=0.001)
        The minimum pixel width of the outline around points.

    point_line_width_max_pixels: float (optional, default=3)
        The maximum pixel width of the outline around points.

    point_line_width: float (optional, default=0.001)
        The absolute line-width in common coordinates of the outline around points.

    cluster_boundary_line_width: float (optional, default=1.0)
        The linewidth to use for cluster boundaries. Note that cluster boundaries scale with respect
        to cluster size, so this is a scaling factor applied over this.

    initial_zoom_fraction: float (optional, default=1.0)
        The fraction of of data that should be visible in the initial zoom lavel state. Sometimes
        data maps can have extreme outliers, and lowering this value to prune those out can result
        in a more useful initial view.

    background_color: str or None (optional, default=None)
        A background colour (as a hex-string) for the data map. If ``None`` a background
        colour will be chosen automatically based on whether ``darkmode`` is set.

    background_image: str or None (optional, default=None)
        A background image to use for the data map. If ``None`` no background image will be used.
        The image should be a URL to the image.

    background_image_bounds: list or None (optional, default=None)
        The bounds of the background image. If ``None`` the image will be scaled to fit the
        data map. If a list of four values is provided then the image will be scaled to fit
        within those bounds.

    darkmode: bool (optional, default=False)
        Whether to use darkmode.

    edge_bundle: bool (optional, default=False)
        Whether to include edges in the data map.

    edge_bundle_keywords: dict (optional, default={...})
        A dictionary of keywords to use for edge bundling, passed to the edge bundling algorithm.

    edge_width: float (optional, default=0.2)
        The width of the edges in the data map.

    offline_data_prefix: str or None (optional, default=None)
        If ``inline_data=False`` a number of data files will be created storing data for
        the plot and referenced by the HTML file produced. If not none then this will provide
        a prefix on the filename of all the files created. Deprecated in favor of
        ``offline_data_path``.

    offline_data_path: str, pathlib.Path, or None (optional, default=None)
        If ``inline_data=False``, this specifies the path (including directory) where data
        files will be saved. Can be a string path or pathlib.Path object. The directory
        will be created if it doesn't exist. If not specified, falls back to
        ``offline_data_prefix`` behavior for backward compatibility.

    tooltip_css: str or None (optional, default=None)
        Custom CSS used to fine the properties of the tooltip. If ``None`` a default
        CSS style will be used. This should simply be the required CSS directives
        specific to the tooltip.

    hover_text_html_template: str or None (optional, default=None)
        An html template allowing fine grained control of what is displayed in the
        hover tooltip. This should be HTML with placeholders of the form ``{hover_text}``
        for the supplied hover text and ``{column_name}`` for columns from
        ``extra_point_data`` (see below).

    dynamic_tooltip: dict[str, str] or None (optional, default=None)
        A dictionary with keys: fetch_js, format_js, loading_js, error_js mapping to JavaScript
        functions that are passed to DynamicTooltipManager and define the behavior of the tooltip.

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

    histogram_data: list, pandas.Series, or None (optional, default=None)
        The data used to generate a histogram. The histogram data can be passed as a list or
        Pandas Series; if `None`, the histogram is disabled. The length of the list or Series
        must match the number of rows in `point_dataframe`. The values within the list or Series
        must be of type unsigned integer, signed integer, floating-point number, string, or a
        date string in the format `YYYY-MM-DD`.

    histogram_n_bins: int (optional, default=20)
        The number of bins in the histogram. It is the maximum number of bins if binning categorical
        data. If the number of unique values in the data is less than or equal to `histogram_n_bins`,
        the number of bins will be the number of unique values.

    histogram_group_datetime_by: str or None (optional, default=None)
        The time unit to group the datetime data by. If `None`, the datetime data will not be
        grouped. The time unit can be one of the following: `year`, `quarter`, `month`, `week`,
        `day`, `hour`, `minute`, or `second`.

    histogram_range: tuple or None (optional, default=None)
        The range of the histogram. If `None`, the range is automatically determined from the
        histogram data. If a tuple, it should contain two values representing the minimum and
        maximum values of the histogram.

    histogram_settings: dict or None (optional, default={})
        A dictionary containing custom settings for the histogram, if enabled. If
        `histogram_data` is provided, this dictionary allows you to customize the
        appearance of the histogram. The dictionary can include the following keys:

        - "histogram_width": str
            The width of the histogram in pixels.
        - "histogram_height": str
            The height of the histogram in pixels.
        - "histogram_bin_count": int
            The number of bins in the histogram.
        - "histogram_title": str
            The title of the histogram.
        - "histogram_bin_fill_color": str
            The fill HEX color of the histogram bins (e.g. `#6290C3`).
        - "histogram_bin_selected_fill_color": str
            The fill HEX color of the selected histogram bins (e.g. `#2EBFA5`).
        - "histogram_bin_unselected_fill_color": str
            The fill HEX color of the unselected histogram bins (e.g. `#9E9E9E`).
        - "histogram_bin_context_fill_color": str
            The fill HEX color of the contextual bins in the histogram (e.g. `#E6E6E6`).
        - "histogram_log_scale": bool
            Whether to use a log scale for y-axis of the histogram.

    on_click: str or None (optional, default=None)
        A javascript action to be taken if a point in the data map is clicked. The javascript
        can reference ``{hover_text}`` or columns from ``extra_point_data``. For example one
        could provide ``"window.open(`http://google.com/search?q=\"{hover_text}\"`)"`` to
        open a new window with a google search for the hover_text of the clicked point.

    selection_handler: instance of datamapplot.selection_handlers.SelectionHandlerBase or None (optional, default=None)
        A selection handler to be used to handle selections in the data map. If None, the
        interactive selection will not be enabled. If a selection handler is provided, the
        selection handler will be used to determine how to react to selections made on the
        data map. Selection handlers can be found in the `datamapplot.selection_handlers`
        module, or custom selection handlers can be created by subclassing the `SelectionHandlerBase`
        class.

    colormaps: dict or None (optional, default=None)
        A dictionary containing information about the colormaps to use for the data map. The
        dictionary should bey keyed by a descriptive name for the field, and the value should
        be an array of values to use for colouring the field. Datamapplot will try to infer
        data-types and suitable colormaps for the fields. If you need more control you
        should instead use ``colormap_rawdata`` and ``colormap_metadata`` which allow you to
        specify more detailed information about the colormaps to use.

    colormap_rawdata: list of numpy.ndarray or None (optional, default=None)
        A list of numpy arrays containing the raw data to be used for the colormap. Each array
        should be the same length as the number of points in the data map. If None, the colormap
        will not be enabled.

    colormap_metadata: list of dict or None (optional, default=None)
        A list of dictionaries containing metadata about the colormap. Each dictionary should
        contain the following keys: "field" (str), "description" (str), and "cmap" (str). If None,
        the colormap will not be enabled. The field should a short (one word) name for the metadata
        field, the description should be a longer description of the field, and the cmap should be
        the name of the colormap to use, and must be available in matplotlib colormap registry.

    cluster_layer_colormaps: bool (optional, default=False)
        Whether to use per-layer cluster colormaps. If True, a separate colormap in the colormaps
        dropdown will be created for each layer of the label data. This is useful when the label
        data is split into multiple layers, and you would like users to be able to select
        individual clustering resolutions to colour by.

    enable_topic_tree: bool (optional, default=False)
        Whether to enable a topic tree that highlights label heirarchy and aids navigation in
        the datamap.

    topic_tree_kwds: dict (optional, default={"title":"Topic Tree", "font_size":"12pt", "max_width":"30vw", "max_height":"42vh", "color_bullets":False, "button_on_click":None, "button_icon":"&#128194"})
        A dictionary containing custom settings for the topic tree. The dictionary can include
        the following keys:
          * "title": str
                The title of the topic tree.
          * "font_size": str
                The font size of the topic tree.
          * "max_width": str
                The max width of the topic tree.
          * "max_height": str
                The max height of the topic tree.
          * "color_bullets": bool
                Whether to use cluster colors for the bullets.
          * "button_on_click": str or None
                An optional javascript action to be taken if a button in the topic tree is selected.
                If None, there will be no buttons, otherwise they will be added with the "button_icon" setting.
                Each button will be related to a label, and can access the points related to that label.
                This javascript can reference ``{hover_text}`` or columns from ``extra_point_data``, at which
                point an array is built with those values for each point that the label describes.
                For example one could provide ``"console.log({hover_text})"`` to log the hover_text of all
                points related to the label.
          * "button_icon": str
                The text to appear on the topic tree buttons.
                These buttons do not appear unless "button_on_click" is defined.

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

    minify_deps: bool (optional, default=True)
        Whether to minify the JavaScript and CSS dependency files before embedding in the HTML template.

    cdn_url: str (optional, default="unpkg.com")
        The URL of the CDN to use for fetching JavaScript dependencies.

    offline_mode: bool (optional, default=False)
        Whether to use offline mode for embedding data and fonts in the HTML template. If True,
        the data and font files will be embedded in the HTML template as base64 encoded strings.

    offline_mode_js_data_file: str or None (optional, default=None)
        The name of the JavaScript data file to be embedded in the HTML template in offline mode.
        If None a default location used by dmp_offline_cache will be used, and if the file
        doesn't exist it will be created.

    offline_mode_font_data_file: str or None (optional, default=None)
        The name of the font data file to be embedded in the HTML template in offline mode.
        If None a default location used by dmp_offline_cache will be used, and if the file
        doesn't exist it will be created.

    cluster_colormap: list of str or None (optional, default=None)
        The colormap to use for cluster colors; if None we try to infer this from point data.

    splash_warning: str or None (optional, default=None)
        A warning message to be displayed in a splash screen when the plot is first loaded. This
        can be used to used to warn users about the volume of data, or the nature of the data,
        or to provide other information that might be useful to the user. This will only be active
        for ``inline_data=False`` and will be displayed before data is loaded, and data loading
        will not proceed until the user has dismissed the warning.

    Returns
    -------
    interactive_plot: InteractiveFigure
        An interactive figure with hover, pan, and zoom. This will display natively
        in a notebook, and can be saved to an HTML file via the `save` method.
    """
    # Compute bounds for initial view
    bounds = compute_percentile_bounds(
        point_dataframe[["x", "y"]].values,
        percentage=(initial_zoom_fraction * 100),
    )

    # Compute point scaling
    magic_number, point_size, point_dataframe = compute_point_scaling(
        point_dataframe, bounds, point_size_scale
    )

    # Get style configuration
    style_config = get_style_config(darkmode, text_outline_color)
    text_outline_color = style_config["text_outline_color"]
    point_outline_color = style_config["point_outline_color"]
    text_background_color = style_config["text_background_color"]

    # Handle background image bounds
    if background_image is not None:
        if background_image_bounds is None:
            background_image_bounds = [
                point_dataframe["x"].min(),
                point_dataframe["y"].min(),
                point_dataframe["x"].max(),
                point_dataframe["y"].max(),
            ]

    # Get label text color
    label_text_color = get_label_text_color(color_label_text, darkmode)

    # Compute label text scaling
    label_dataframe = compute_label_scaling(label_dataframe, min_fontsize, max_fontsize)

    # Prep data for inlining or storage
    enable_histogram = histogram_data is not None
    histogram_data_attr = "histogram_data_attr"
    histogram_ctx = {
        "enable_histogram": enable_histogram,
        "histogram_data_attr": histogram_data_attr,
        "histogram_enable_click_persistence": histogram_enable_click_persistence,
        **histogram_settings,
    }
    enable_lasso_selection = selection_handler is not None

    point_data_cols = ["x", "y", "r", "g", "b", "a"]

    if point_size < 0:
        point_data_cols.append("size")

    # if enable_search or enable_histogram or enable_lasso_selection:
    #     point_dataframe["selected"] = np.ones(len(point_dataframe), dtype=np.uint8)
    #     point_data_cols.append("selected")

    # Point data, hover text, and on click formatting
    point_data = point_dataframe[point_data_cols]

    # Prepare hover data and tooltip/click handlers
    hover_result = prepare_hover_data(
        point_dataframe,
        extra_point_data,
        hover_text_html_template,
        on_click,
        topic_tree_kwds,
    )
    hover_data = hover_result["hover_data"]
    get_tooltip = hover_result["get_tooltip"]
    on_click = hover_result["on_click"]
    topic_tree_kwds = hover_result["topic_tree_kwds"]

    # Prepare edge bundle data
    if edge_bundle:
        edge_data = prepare_edge_bundle_data(point_dataframe, edge_bundle_keywords)
    else:
        edge_data = None

    # Prepare histogram data
    if enable_histogram:
        bin_data, index_data = prepare_histogram_data(
            histogram_data,
            histogram_n_bins,
            histogram_group_datetime_by,
            histogram_range,
        )
    else:
        bin_data, index_data = None, None

    # Prepare colormap data
    color_metadata, color_data, enable_colormap_selector = prepare_colormap_data(
        point_dataframe,
        colormap_rawdata,
        colormap_metadata,
        colormaps,
        cluster_layer_colormaps,
        label_layers,
        cluster_colormap,
        noise_color,
    )

    # Encode data for inline HTML or write to offline files
    if inline_data:
        data_encoding = encode_inline_data(
            point_data,
            hover_data,
            label_dataframe,
            enable_histogram,
            bin_data,
            index_data,
            enable_colormap_selector,
            color_data,
            edge_bundle,
            edge_data,
        )
    else:
        data_encoding = write_offline_data(
            point_data,
            hover_data,
            label_dataframe,
            enable_histogram,
            bin_data,
            index_data,
            enable_colormap_selector,
            color_data,
            edge_bundle,
            edge_data,
            offline_data_path,
            offline_data_prefix,
            offline_data_chunk_size,
        )

    base64_point_data = data_encoding["base64_point_data"]
    base64_hover_data = data_encoding["base64_hover_data"]
    base64_label_data = data_encoding["base64_label_data"]
    base64_histogram_bin_data = data_encoding["base64_histogram_bin_data"]
    base64_histogram_index_data = data_encoding["base64_histogram_index_data"]
    base64_color_data = data_encoding["base64_color_data"]
    base64_edge_data = data_encoding["base64_edge_data"]
    file_prefix = data_encoding["file_prefix"]
    html_file_prefix = data_encoding["html_file_prefix"]
    n_chunks = data_encoding["n_chunks"]

    # Style configuration
    title_font_color = style_config["title_font_color"]
    sub_title_font_color = style_config["sub_title_font_color"]
    title_background = style_config["title_background"]
    shadow_color = style_config["shadow_color"]
    input_background = style_config["input_background"]
    input_border = style_config["input_border"]
    page_background_color = (
        background_color
        if background_color is not None
        else style_config["page_background_color"]
    )
    topic_tree_kwds = {**_TOPIC_TREE_DEFAULT_KWDS, **topic_tree_kwds}

    if tooltip_css is None:
        tooltip_css_template = jinja2.Template(_TOOL_TIP_CSS)
        tooltip_css = tooltip_css_template.render(
            title_font_family=tooltip_font_family or font_family,
            title_font_color=title_font_color,
            title_font_weight=tooltip_font_weight,
            title_background=title_background,
            shadow_color=shadow_color,
        )

    # Prepare dynamic tooltip configuration
    dynamic_tooltip_config = prepare_dynamic_tooltip(dynamic_tooltip)
    enable_dynamic_tooltip = dynamic_tooltip_config["enable_dynamic_tooltip"]
    tooltip_identifier_js = dynamic_tooltip_config["tooltip_identifier_js"]
    tooltip_fetch_js = dynamic_tooltip_config["tooltip_fetch_js"]
    tooltip_format_js = dynamic_tooltip_config["tooltip_format_js"]
    tooltip_loading_js = dynamic_tooltip_config["tooltip_loading_js"]
    tooltip_error_js = dynamic_tooltip_config["tooltip_error_js"]

    # ==========================================================================
    # Widget System Processing
    # ==========================================================================

    # Determine if we should use the new widget system
    # use_widgets=None means auto-detect: use widgets if widgets param is provided
    # use_widgets=True forces widget system even with legacy params
    # use_widgets=False forces legacy system
    use_widget_system = use_widgets
    if use_widget_system is None:
        use_widget_system = widgets is not None

    # Initialize widget containers
    widgets_by_location = {loc: [] for loc in VALID_LOCATIONS}
    drawer_enabled = {"left": False, "right": False}
    widget_css = ""
    widget_js = ""
    encoded_widget_data = {}  # Initialize for both paths

    if use_widget_system:
        # Load default widget config from file if provided
        default_config = None
        if default_widget_config is not None:
            if isinstance(default_widget_config, (str, Path)):
                default_config = load_widget_config_from_json(default_widget_config)
            elif isinstance(default_widget_config, dict):
                default_config = validate_widget_layout(default_widget_config)

        # Validate user widget layout if provided
        user_layout = None
        if widget_layout is not None:
            user_layout = validate_widget_layout(widget_layout)

        # Merge configurations
        merged_layout = merge_widget_configs(default_config, user_layout)

        # Collect widgets - either from explicit widgets param or from legacy params
        all_widgets = []
        if widgets is not None:
            if isinstance(widgets, WidgetBase):
                all_widgets = [widgets]
            elif isinstance(widgets, Iterable):
                all_widgets = list(widgets)
        else:
            # Convert legacy parameters to widgets
            all_widgets = widgets_from_legacy_params(
                title=title,
                sub_title=sub_title,
                font_family=font_family,
                title_font_size=title_font_size,
                sub_title_font_size=sub_title_font_size,
                font_weight=font_weight,
                title_font_color=title_font_color,
                sub_title_font_color=sub_title_font_color,
                enable_search=enable_search,
                search_field=search_field,
                enable_topic_tree=enable_topic_tree,
                topic_tree_kwds=topic_tree_kwds,
                histogram_data=histogram_data,
                histogram_settings=histogram_settings,
                histogram_n_bins=histogram_n_bins,
                colormaps=colormaps,
                colormap_rawdata=colormap_rawdata,
                colormap_metadata=color_metadata,
                cluster_layer_colormaps=cluster_layer_colormaps,
                logo=logo,
                logo_width=logo_width,
            )

        # Group widgets by location, applying layout overrides
        widgets_by_location = group_widgets_by_location(all_widgets, merged_layout)

        # Determine which drawers should be enabled
        drawer_enabled = get_drawer_enabled(widgets_by_location)

        # Update drawer enablement for selection handlers
        drawer_enabled = update_drawer_enabled_for_handlers(
            drawer_enabled, selection_handler
        )

        # Collect widget CSS and JS
        for widget in all_widgets:
            if widget.css:
                widget_css += widget.css + "\n"
            if widget.javascript:
                widget_js += widget.javascript + "\n"

        # Collect widget dependencies
        widget_deps = collect_widget_dependencies(all_widgets)

        # Legacy widget flags
        (
            enable_search,
            enable_histogram,
            enable_topic_tree,
            search_field,
            histogram_ctx,
            topic_tree_kwds,
        ) = legacy_widget_flags_from_widgets(all_widgets)

        # Collect and encode widget data for template
        raw_widget_data = collect_widget_data(all_widgets)
        encoded_widget_data = encode_widget_data(raw_widget_data, len(point_data))

    # Determine if drawers are enabled (for dependency loading)
    enable_drawers = drawer_enabled["left"] or drawer_enabled["right"]

    # Pepare JS/CSS dependencies for embedding in the HTML template
    dependencies_ctx = {
        "js_dependency_urls": get_js_dependency_urls(
            enable_histogram,
            enable_topic_tree,
            enable_colormap_selector,
            selection_handler,
            cdn_url=cdn_url,
        ),
        "js_dependency_srcs": get_js_dependency_sources(
            minify_deps,
            enable_search,
            enable_histogram,
            enable_lasso_selection,
            enable_colormap_selector,
            enable_topic_tree,
            enable_dynamic_tooltip,
            enable_drawers=enable_drawers,
        ),
        "css_dependency_srcs": get_css_dependency_sources(
            minify_deps,
            enable_histogram,
            show_loading_progress,
            enable_colormap_selector,
            enable_topic_tree,
            enable_drawers=enable_drawers,
        ),
    }

    # Use modular template with includes
    template = _get_template(use_modular=True)

    # Prepare logo
    logo = prepare_logo(logo, offline_mode)

    # Prepare offline mode data
    offline_result = prepare_offline_mode_data(
        offline_mode,
        offline_mode_js_data_file,
        offline_mode_font_data_file,
    )
    offline_mode_data = offline_result["offline_mode_data"]
    offline_mode_font_data_file = offline_result["offline_mode_font_data_file"]

    # Prepare fonts
    font_result = prepare_fonts(
        font_family,
        tooltip_font_family,
        offline_mode,
        offline_mode_font_data_file,
    )
    api_fontname = font_result["api_fontname"]
    font_data = font_result["font_data"]
    api_tooltip_fontname = font_result["api_tooltip_fontname"]

    # Process selection handler(s)
    custom_html, custom_js, custom_css = prepare_selection_handler(
        selection_handler, custom_html, custom_js, custom_css
    )

    html_str = template.render(
        title=title,  # if title is not None else "Interactive Data Map",
        sub_title=sub_title if sub_title is not None else "",
        google_font=api_fontname,
        google_font_data=font_data,
        google_tooltip_font=api_tooltip_fontname,
        page_background_color=page_background_color,
        search=enable_search,
        enable_topic_tree=enable_topic_tree,
        **{
            f"topic_tree_{key}": json.dumps(value)
            for key, value in topic_tree_kwds.items()
        },
        **histogram_ctx,
        enable_colormap_selector=enable_colormap_selector,
        colormap_metadata=json.dumps(color_metadata),
        title_font_family=font_family,
        title_font_color=title_font_color,
        title_background=title_background,
        tooltip_css=tooltip_css,
        shadow_color=shadow_color,
        input_background=input_background,
        input_border=input_border,
        custom_css=(custom_css or "") + "\n" + widget_css,
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
        base64_histogram_bin_data=base64_histogram_bin_data,
        base64_histogram_index_data=base64_histogram_index_data,
        base64_color_data=base64_color_data,
        edge_bundle=edge_bundle,
        base64_edge_data=base64_edge_data,
        edge_width=edge_width,
        file_prefix=html_file_prefix,
        point_size=point_size,
        point_outline_color=point_outline_color,
        point_line_width=point_line_width,
        point_hover_color=[int(c * 255) for c in to_rgba(point_hover_color)],
        point_line_width_max_pixels=point_line_width_max_pixels,
        point_line_width_min_pixels=point_line_width_min_pixels,
        point_radius_max_pixels=point_radius_max_pixels,
        point_radius_min_pixels=point_radius_min_pixels,
        label_text_color=label_text_color,
        noise_label=noise_label,
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
        data_bounds=bounds,
        n_data_chunks=n_chunks,
        on_click=on_click,
        enable_lasso_selection=enable_lasso_selection,
        get_tooltip=get_tooltip,
        search_field=search_field,
        show_loading_progress=show_loading_progress,
        background_image=background_image,
        background_image_bounds=background_image_bounds,
        custom_js=(custom_js or "") + "\n" + widget_js,
        offline_mode=offline_mode,
        offline_mode_data=offline_mode_data,
        splash_warning=splash_warning,
        enable_api_tooltip=enable_dynamic_tooltip,
        tooltip_identifier_js=tooltip_identifier_js,
        tooltip_fetch_js=tooltip_fetch_js,
        tooltip_format_js=tooltip_format_js,
        tooltip_loading_js=tooltip_loading_js,
        tooltip_error_js=tooltip_error_js,
        # Widget system context
        use_widget_system=use_widget_system,
        widgets_by_location=widgets_by_location,
        drawer_enabled=drawer_enabled,
        enable_drawers=enable_drawers,
        darkmode=darkmode,
        widget_data=encoded_widget_data,
        **dependencies_ctx,
    )
    return html_str
