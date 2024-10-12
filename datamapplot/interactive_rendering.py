import base64
import gzip
import html
import io
import os
import warnings
import zipfile
import json

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

from pandas.api.types import is_string_dtype, is_numeric_dtype, is_datetime64_any_dtype

from datamapplot.histograms import (
    generate_bins_from_numeric_data,
    generate_bins_from_categorical_data,
    generate_bins_from_temporal_data,
)
from datamapplot.alpha_shapes import create_boundary_polygons, smooth_polygon
from datamapplot.medoids import medoid

_DECKGL_TEMPLATE_STR = (files("datamapplot") / "deckgl_template.html").read_text(
    encoding="utf-8"
)

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

_NOTEBOOK_NON_INLINE_WORKER = """
    const parsingWorkerBlob = new Blob([`
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
          const response = await fetch(filename, {
            headers: {Authorization: 'Token API_TOKEN'}
          });
          if (!response.ok) {
            throw new Error(\`HTTP error! status: \${response.status}\`);
          }
          const data = await response.json()
            .then(data => data.content)
            .then(base64data => decodeBase64(base64data))
            .then(buffer => DecompressBytes(buffer));
          return data;
      }
      self.onmessage = async function(event) {
        const { encodedData, JSONParse } = event.data;
        const binaryData = await decompressFile(encodedData);
        if (JSONParse) {
          const parsedData = JSON.parse(new TextDecoder("utf-8").decode(binaryData));
          self.postMessage({ data: parsedData });
        } else {
          // Send the parsed table back to the main thread
          self.postMessage({ data: binaryData });
        }
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
            for filename in re.findall(r"/(.*?_data\.zip)", self._html_str):
                print(f"Adding {filename} to bundle")
                zf.write(filename)


def get_google_font_for_embedding(fontname):
    api_fontname = fontname.replace(" ", "+")
    api_response = requests.get(
        f"https://fonts.googleapis.com/css?family={api_fontname}:black,bold,regular,light",
        timeout=10,
    )
    if api_response.ok:
        font_urls = re.findall(r"(https?://[^\)]+)", str(api_response.content))
        font_links = []
        for url in font_urls:
            if url.endswith(".ttf"):
                font_links.append(
                    f'<link rel="preload" href="{url}" as="font" crossorigin="anonymous" type="font/ttf" />'
                )
            elif url.endswith(".woff2"):
                font_links.append(
                    f'<link rel="preload" href="{url}" as="font" crossorigin="anonymous" type="font/woff2" />'
                )
        return (
            "\n".join(font_links)
            + f"\n<style>\n{api_response.content.decode()}\n</style>\n"
        )
    else:
        return ""


def _get_js_dependency_sources(
    minify, enable_search, enable_histogram, enable_lasso_selection
):
    """
    Gather the necessary JavaScript dependency files for embedding in the HTML template.

    Parameters
    ----------
    minify : bool
        Whether to minify the JS files.

    enable_search : bool
        Whether to include JS dependencies for the search functionality.

    enable_histogram: bool
        Whether to include JS dependencies for the histogram functionality.

    enable_lasso_selection: bool
        Whether to include JS dependencies for the lasso selection functionality.

    Returns
    -------
    dict
        A dictionary where keys are the names of JS files and values are their
        source content.
    """
    static_dir = Path(__file__).resolve().parent / "static" / "js"
    js_dependencies = ["datamap.js", "data_selection_manager.js"]
    js_dependencies_src = {}

    if enable_histogram:
        js_dependencies.append("d3_histogram.js")

    if enable_lasso_selection:
        js_dependencies.append("lasso_selection.js")
        js_dependencies.append("quad_tree.js")

    for js_file in js_dependencies:
        with open(static_dir / js_file, "r", encoding="utf-8") as file:
            js_src = file.read()
            js_dependencies_src[js_file] = jsmin(js_src) if minify else js_src

    return js_dependencies_src


def _get_css_dependency_sources(minify, enable_histogram, show_loading_progress):
    """
    Gather the necessary CSS dependency files for embedding in the HTML template.

    Parameters
    ----------
    minify : bool
        Whether to minify the CSS files.

    enable_histogram: bool
        Whether to include CSS dependencies for the histogram functionality.

    show_loading_progress: bool
        Whether to have progress bars for data loading.

    Returns
    -------
    dict
        A dictionary where keys are the names of CSS files and values are their
        source content.
    """
    static_dir = Path(__file__).resolve().parent / "static" / "css"
    css_dependencies = []
    css_dependencies_src = {}

    if enable_histogram:
        css_dependencies.append("d3_histogram_style.css")

    if show_loading_progress:
        css_dependencies.append("progress_bar_style.css")

    for css_file in css_dependencies:
        with open(static_dir / css_file, "r", encoding="utf-8") as file:
            css_src = file.read()
            css_dependencies_src[css_file] = cssmin(css_src) if minify else css_src

    return css_dependencies_src


def _get_js_dependency_urls(enable_histogram, selection_handler=None):
    """
    Gather the necessary JavaScript dependency URLs for embedding in the HTML template.

    Parameters
    ----------
    enable_histogram: bool
        Whether to include JS URLs for the histogram functionality.

    Returns
    -------
    list
        A list of URLs that point to the required JavaScript dependencies.
    """
    js_dependency_urls = []

    # Add common dependencies (if any)
    common_js_urls = [
        "https://unpkg.com/deck.gl@latest/dist.min.js",
        "https://unpkg.com/apache-arrow@latest/Arrow.es2015.min.js",
    ]
    js_dependency_urls.extend(common_js_urls)

    # Conditionally add dependencies based on functionality
    if enable_histogram:
        js_dependency_urls.append("https://d3js.org/d3.v6.min.js")

    if selection_handler is not None:
        js_dependency_urls.extend(selection_handler.dependencies)

    js_dependency_urls = list(set(js_dependency_urls))

    return js_dependency_urls


def compute_percentile_bounds(points, percentage=99.9):
    n_points = points.shape[0]
    n_to_select = np.int32(n_points * (percentage / 100))
    centroid = np.mean(points, axis=0)

    # Sort points by distance from centroid
    vectors = points - centroid
    distances = np.linalg.norm(vectors**2, axis=1)
    sorted_indices = np.argsort(distances)
    selected_points = points[sorted_indices[:n_to_select]]

    # Compute bounds
    xmin, ymin = np.min(selected_points, axis=0)
    xmax, ymax = np.max(selected_points, axis=0)

    x_padding = 0.01 * (xmax - xmin)
    y_padding = 0.01 * (ymax - ymin)

    return [float(xmin - x_padding), float(xmax + x_padding), float(ymin - y_padding), float(ymax + y_padding)]


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
    cluster_idx_vector = np.asarray(pd.Series(cluster_label_vector).map(label_map))

    label_locations = []
    cluster_sizes = []
    polygons = []

    for i, _ in enumerate(unique_non_noise_labels):
        cluster_mask = cluster_idx_vector == i
        cluster_points = data_map_coords[cluster_mask]
        if use_medoids:
            label_locations.append(medoid(cluster_points))
        else:
            label_locations.append(cluster_points.mean(axis=0))

        cluster_sizes.append(np.sum(cluster_mask) ** 0.25)
        if cluster_polygons:
            simplices = Delaunay(
                cluster_points, qhull_options="Qbb Qc Qz Q12 Q7"
            ).simplices
            polygons.append(
                [
                    smooth_polygon(x).tolist()
                    for x in create_boundary_polygons(
                        cluster_points, simplices, alpha=alpha
                    )
                ]
            )

    label_locations = np.asarray(label_locations)

    data = {
        "x": label_locations.T[0],
        "y": label_locations.T[1],
        "label": unique_non_noise_labels,
        "size": cluster_sizes,
    }
    if cluster_polygons:
        data["polygon"] = polygons

    return pd.DataFrame(data)


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
    darkmode=False,
    offline_data_prefix=None,
    tooltip_css=None,
    hover_text_html_template=None,
    extra_point_data=None,
    enable_search=False,
    search_field="hover_text",
    histogram_data=None,
    histogram_n_bins=20,
    histogram_group_datetime_by=None,
    histogram_range=None,
    histogram_settings={},
    on_click=None,
    selection_handler=None,
    show_loading_progress=True,
    custom_html=None,
    custom_css=None,
    custom_js=None,
    minify_deps=True,
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

    # Compute bounds for initial view
    bounds = compute_percentile_bounds(
        point_dataframe[["x", "y"]].values,
        percentage=(initial_zoom_fraction * 100),
    )

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
    enable_histogram = histogram_data is not None
    histogram_data_attr = "histogram_data_attr"
    histogram_ctx = {
        "enable_histogram": enable_histogram,
        "histogram_data_attr": histogram_data_attr,
        **histogram_settings,
    }
    enable_lasso_selection = selection_handler is not None

    point_data_cols = ["x", "y", "r", "g", "b", "a"]

    if point_size < 0:
        point_data_cols.append("size")

    # if enable_search or enable_histogram or enable_lasso_selection:
    #     point_dataframe["selected"] = np.ones(len(point_dataframe), dtype=np.uint8)
    #     point_data_cols.append("selected")

    point_data = point_dataframe[point_data_cols]

    if "hover_text" in point_dataframe.columns:
        if extra_point_data is not None:
            hover_data = pd.concat(
                [point_dataframe[["hover_text"]], extra_point_data],
                axis=1,
            )
            replacements = FormattingDict(
                **{
                    str(name): f"${{hoverData.{name}[index]}}"
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
                get_tooltip = "({index}) => hoverData.hover_text[index]"

            if on_click is not None:
                on_click = (
                    "({index, picked}, event) => { if (picked) {"
                    + on_click.format_map(replacements)
                    + " } }"
                )
        else:
            hover_data = point_dataframe[["hover_text"]].copy()
            get_tooltip = "({index}) => hoverData.hover_text[index]"

            replacements = FormattingDict(
                **{
                    str(name): f"${{hoverData.{name}[index]}}"
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
        hover_data = extra_point_data.copy()
        replacements = FormattingDict(
            **{
                str(name): f"${{hoverData.{name}[index]}}"
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

    if enable_histogram:
        if isinstance(histogram_data.dtype, pd.CategoricalDtype):
            bin_data, index_data = generate_bins_from_categorical_data(
                histogram_data, histogram_n_bins, histogram_range
            )
        elif is_string_dtype(histogram_data.dtype):
            bin_data, index_data = generate_bins_from_categorical_data(
                histogram_data, histogram_n_bins, histogram_range
            )
        elif is_datetime64_any_dtype(histogram_data.dtype):
            if histogram_group_datetime_by is not None:
                bin_data, index_data = generate_bins_from_temporal_data(
                    histogram_data, histogram_group_datetime_by, histogram_range
                )
            else:
                bin_data, index_data = generate_bins_from_numeric_data(
                    histogram_data, histogram_n_bins, histogram_range
                )
        else:
            bin_data, index_data = generate_bins_from_numeric_data(
                histogram_data, histogram_n_bins, histogram_range
            )

    if inline_data:
        buffer = io.BytesIO()
        point_data.to_feather(buffer, compression="uncompressed")
        buffer.seek(0)
        arrow_bytes = buffer.read()
        gzipped_bytes = gzip.compress(arrow_bytes)
        base64_point_data = base64.b64encode(gzipped_bytes).decode()
        json_bytes = json.dumps(hover_data.to_dict(orient="list")).encode()
        gzipped_bytes = gzip.compress(json_bytes)
        base64_hover_data = base64.b64encode(gzipped_bytes).decode()
        label_data_json = label_dataframe.to_json(orient="records")
        gzipped_label_data = gzip.compress(bytes(label_data_json, "utf-8"))
        base64_label_data = base64.b64encode(gzipped_label_data).decode()
        if enable_histogram:
            json_bytes = bin_data.to_json(
                orient="records", date_format="iso", date_unit="s"
            ).encode()
            gzipped_bytes = gzip.compress(json_bytes)
            base64_histogram_bin_data = base64.b64encode(gzipped_bytes).decode()
            buffer = io.BytesIO()
            index_data.to_frame().to_feather(buffer, compression="uncompressed")
            buffer.seek(0)
            arrow_bytes = buffer.read()
            gzipped_bytes = gzip.compress(arrow_bytes)
            base64_histogram_index_data = base64.b64encode(gzipped_bytes).decode()
        else:
            base64_histogram_bin_data = None
            base64_histogram_index_data = None
        file_prefix = None
    else:
        base64_point_data = ""
        base64_hover_data = ""
        base64_label_data = ""
        base64_histogram_bin_data = ""
        base64_histogram_index_data = ""
        file_prefix = (
            offline_data_prefix if offline_data_prefix is not None else "datamapplot"
        )
        with gzip.open(f"{file_prefix}_point_data.zip", "wb") as f:
            point_data.to_feather(f, compression="uncompressed")
        with gzip.open(f"{file_prefix}_meta_data.zip", "wb") as f:
            f.write(json.dumps(hover_data.to_dict(orient="list")).encode())
        label_data_json = label_dataframe.to_json(path_or_buf=None, orient="records")
        with gzip.open(f"{file_prefix}_label_data.zip", "wb") as f:
            f.write(bytes(label_data_json, "utf-8"))
        if enable_histogram:
            with gzip.open(f"{file_prefix}_histogram_bin_data.zip", "wb") as f:
                f.write(
                    bin_data.to_json(
                        orient="records", date_format="iso", date_unit="s"
                    ).encode()
                )
            with gzip.open(f"{file_prefix}_histogram_index_data.zip", "wb") as f:
                index_data.to_frame().to_feather(f, compression="uncompressed")

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

    # Pepare JS/CSS dependencies for embedding in the HTML template
    dependencies_ctx = {
        "js_dependency_urls": _get_js_dependency_urls(
            enable_histogram, selection_handler
        ),
        "js_dependency_srcs": _get_js_dependency_sources(
            minify_deps,
            enable_search,
            enable_histogram,
            enable_lasso_selection,
        ),
        "css_dependency_srcs": _get_css_dependency_sources(
            minify_deps, enable_histogram, show_loading_progress
        ),
    }

    template = jinja2.Template(_DECKGL_TEMPLATE_STR)
    api_fontname = font_family.replace(" ", "+")
    font_data = get_google_font_for_embedding(font_family)
    if font_data == "":
        api_fontname = None
    if tooltip_font_family is not None:
        api_tooltip_fontname = tooltip_font_family.replace(" ", "+")
        resp = requests.get(
            f"https://fonts.googleapis.com/css?family={api_tooltip_fontname}",
            timeout=30,
        )
        if not resp.ok:
            api_tooltip_fontname = None
    else:
        api_tooltip_fontname = None

    if selection_handler is not None:
        if custom_html is None:
            custom_html = selection_handler.html
        else:
            custom_html += selection_handler.html

        if custom_js is None:
            custom_js = selection_handler.javascript
        else:
            custom_js += selection_handler.javascript

        if custom_css is None:
            custom_css = selection_handler.css
        else:
            custom_css += selection_handler.css

    html_str = template.render(
        title=title if title is not None else "Interactive Data Map",
        sub_title=sub_title if sub_title is not None else "",
        google_font=api_fontname,
        google_font_data=font_data,
        google_tooltip_font=api_tooltip_fontname,
        page_background_color=page_background_color,
        search=enable_search,
        **histogram_ctx,
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
        base64_histogram_bin_data=base64_histogram_bin_data,
        base64_histogram_index_data=base64_histogram_index_data,
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
        data_bounds=bounds,
        on_click=on_click,
        enable_lasso_selection=enable_lasso_selection,
        get_tooltip=get_tooltip,
        search_field=search_field,
        show_loading_progress=show_loading_progress,
        custom_js=custom_js,
        **dependencies_ctx,
    )
    return html_str
