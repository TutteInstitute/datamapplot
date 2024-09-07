import base64
import gzip
import html
import io
import os
import warnings
import zipfile

import jinja2
import numpy as np
import pandas as pd
import requests
from importlib_resources import files
from matplotlib.colors import to_rgba
from pathlib import Path
from rcssmin import cssmin
from rjsmin import jsmin
from scipy.spatial import Delaunay

from datamapplot.alpha_shapes import create_boundary_polygons, smooth_polygon
from datamapplot.medoids import medoid

_DECKGL_TEMPLATE_STR = (
    files("datamapplot") / "deckgl_template.html"
).read_text(encoding='utf-8')

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
        with open(filename, "w+", encoding="utf-8") as f:
            f.write(self._html_str)

def _get_js_dependency_sources(minify, enable_search, enable_histogram):
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

    Returns
    -------
    dict
        A dictionary where keys are the names of JS files and values are their 
        source content.
    """
    static_dir = Path(__file__).resolve().parent / "static" / "js"
    js_dependencies = []
    js_dependencies_src = {}
    
    if enable_search or enable_histogram:
        js_dependencies.append("data_selection_manager.js")
        
    if enable_histogram:        
        js_dependencies.append("d3_histogram.js")

    for js_file in js_dependencies:
        with open(static_dir / js_file, 'r', encoding='utf-8') as file:
            js_src = file.read()
            js_dependencies_src[js_file] = jsmin(js_src) if minify else js_src
    
    return js_dependencies_src

def _get_css_dependency_sources(minify, enable_histogram):
    """
    Gather the necessary CSS dependency files for embedding in the HTML template.

    Parameters
    ----------
    minify : bool
        Whether to minify the CSS files.

    enable_histogram: bool
        Whether to include CSS dependencies for the histogram functionality.
        
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
        
    for css_file in css_dependencies:
        with open(static_dir / css_file, 'r', encoding='utf-8') as file:
            css_src = file.read()
            css_dependencies_src[css_file] = cssmin(css_src) if minify else css_src

    return css_dependencies_src

def _get_js_dependency_urls(enable_histogram):
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
        "https://unpkg.com/apache-arrow@latest/Arrow.es2015.min.js"
    ]
    js_dependency_urls.extend(common_js_urls)
    
    # Conditionally add dependencies based on functionality
    if enable_histogram:
        js_dependency_urls.append("https://cdnjs.cloudflare.com/ajax/libs/d3/6.5.0/d3.min.js")

    return js_dependency_urls

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
    histogram_data=None,
    histogram_link_selection=True,
    histogram_settings={},
    on_click=None,
    selection_handler=None,
    custom_html=None,
    custom_css=None,
    custom_js=None,
    minify_deps=True
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

    histogram_data: list, pandas.Series, or None (optional, default=None)
        The data used to generate a histogram. The histogram data can be passed as a list or 
        Pandas Series; if `None`, the histogram is disabled. The length of the list or Series
        must match the number of rows in `point_dataframe`. The values within the list or Series 
        must be of type unsigned integer, signed integer, floating-point number, string, or a
        date string in the format `YYYY-MM-DD`.

    histogram_link_selection: bool (optional, default=True)
        Whether to link the selection in the histogram to the selection in the data map from
        search. Since selection rendering on the histogram scales poorly with dataset size it
        can be beneficial to disable the selection linking for large datasets.
    
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
    enable_histogram = histogram_data is not None
    histogram_data_attr = "histogram_data_attr"
    histogram_ctx = { 
        "enable_histogram": enable_histogram, 
        "histogram_data_attr": histogram_data_attr,
        "histogram_link_selection": histogram_link_selection,
        **histogram_settings 
    }
    
    point_data_cols = ["x", "y", "r", "g", "b", "a"]
    
    if point_size < 0:
        point_data_cols.append("size")
        
    if enable_search or enable_histogram:
        point_dataframe["selected"] = np.ones(len(point_dataframe), dtype=np.uint8)
        point_data_cols.append("selected")
        
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
        hover_data[histogram_data_attr] = histogram_data


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
        buffer = io.BytesIO()
        hover_data.to_feather(buffer, compression="uncompressed")
        buffer.seek(0)
        with gzip.open(f"{file_prefix}_point_hover_data.zip", "wb") as f:
            f.write(buffer.read())
        label_data_json = label_dataframe.to_json(path_or_buf=None, orient="records")
        with gzip.open(f"{file_prefix}_label_data.zip", "wb") as f:
            f.write(bytes(label_data_json, "utf-8"))


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
        "js_dependency_urls": _get_js_dependency_urls(enable_histogram),
        "js_dependency_srcs": _get_js_dependency_sources(minify_deps, enable_search, enable_histogram),
        "css_dependency_srcs": _get_css_dependency_sources(minify_deps, enable_histogram)
    }

    template = jinja2.Template(_DECKGL_TEMPLATE_STR)
    api_fontname = font_family.replace(" ", "+")
    resp = requests.get(
        f"https://fonts.googleapis.com/css?family={api_fontname}",
        timeout=300,
    )
    if not resp.ok:
        api_fontname = None
    if tooltip_font_family is not None:
        api_tooltip_fontname = tooltip_font_family.replace(" ", "+")
        resp = requests.get(
            f"https://fonts.googleapis.com/css?family={api_tooltip_fontname}",
            timeout=300,
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
        enable_selection=selection_handler is not None,
        get_tooltip=get_tooltip,
        search_field=search_field,
        custom_js=custom_js,
        **dependencies_ctx
    )
    return html_str
