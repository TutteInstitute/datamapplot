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

from pandas.api.types import is_string_dtype, is_numeric_dtype, is_datetime64_any_dtype

from datamapplot.histograms import (
    generate_bins_from_numeric_data,
    generate_bins_from_categorical_data,
    generate_bins_from_temporal_data,
)
from datamapplot.alpha_shapes import create_boundary_polygons, smooth_polygon
from datamapplot.fonts import (
    can_reach_google_fonts,
    query_google_fonts,
    GoogleAPIUnreachable,
)
from datamapplot.medoids import medoid
from datamapplot.config import ConfigManager
from datamapplot import offline_mode_caching
from datamapplot.selection_handlers import SelectionHandlerBase

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

_DECKGL_TEMPLATE_STR = (files("datamapplot") / "deckgl_template.html").read_text(
    encoding="utf-8"
)

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


def get_google_font_for_embedding(fontname, offline_mode=False, offline_font_file=None):
    if offline_mode:
        all_encoded_fonts = offline_mode_caching.load_fonts(file_path=offline_font_file)
        encoded_fonts = all_encoded_fonts.get(fontname, None)
        if encoded_fonts is not None:
            font_descriptions = [
                (
                    f"""
    @font-face {{ 
        font-family: '{fontname}'; 
        font-style: {font_data["style"]};
        font-weight: {font_data["weight"]};
        src: url(data:font/{font_data["type"]};base64,{font_data["content"]}) format('{font_data["type"]}');
        unicode-range: {font_data["unicode_range"]};
    }}"""
                    if len(font_data["unicode_range"]) > 0
                    else f"""
    @font-face {{ 
        font-family: '{fontname}'; 
        font-style: {font_data["style"]};
        font-weight: {font_data["weight"]};
        src: url(data:font/{font_data["type"]};base64,{font_data["content"]}) format('{font_data["type"]}');
    }}"""
                )
                for font_data in encoded_fonts
            ]
            return "<style>\n" + "\n".join(font_descriptions) + "\n    </style>\n"
        else:
            return ""

    if can_reach_google_fonts(timeout=10.0):
        font_links = []
        collection = query_google_fonts(fontname)
        for font in collection:
            if font.url.endswith(".ttf"):
                font_links.append(
                    f'<link rel="preload" href="{font.url}" as="font" crossorigin="anonymous" type="font/ttf" />'
                )
            elif font.url.endswith(".woff2"):
                font_links.append(
                    f'<link rel="preload" href="{font.url}" as="font" crossorigin="anonymous" type="font/woff2" />'
                )
        return "\n".join(font_links) + f"\n<style>\n{collection.content}\n</style>\n"
    else:
        return ""


def _get_js_dependency_sources(
    minify,
    enable_search,
    enable_histogram,
    enable_lasso_selection,
    colormap_selector,
    enable_topic_tree,
    enable_dynamic_tooltip,
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

    enable_topic_tree: bool
        Whether to include JS dependencies for the topic tree functionality.

    enable_dynamic_tooltip: bool
        Whether to include JS dependencies for the API tooltip functionality.

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

    if colormap_selector:
        js_dependencies.append("colormap_selector.js")

    if enable_topic_tree:
        js_dependencies.append("topic_tree.js")

    if enable_dynamic_tooltip:
        js_dependencies.append("dynamic_tooltip.js")

    for js_file in js_dependencies:
        with open(static_dir / js_file, "r", encoding="utf-8") as file:
            js_src = file.read()
            js_dependencies_src[js_file] = jsmin(js_src) if minify else js_src

    return js_dependencies_src


def _get_css_dependency_sources(
    minify,
    enable_histogram,
    show_loading_progress,
    enable_colormap_selector,
    enable_topic_tree,
):
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

    enable_topic_tree: bool
        Whether to include CSS dependencies for the table of contents functionality.

    Returns
    -------
    dict
        A dictionary where keys are the names of CSS files and values are their
        source content.
    """
    static_dir = Path(__file__).resolve().parent / "static" / "css"
    css_dependencies = ["containers_and_stacks.css"]
    css_dependencies_src = {}

    if enable_histogram:
        css_dependencies.append("d3_histogram_style.css")

    if show_loading_progress:
        css_dependencies.append("progress_bar_style.css")

    if enable_colormap_selector:
        css_dependencies.append("colormap_selector_style.css")

    if enable_topic_tree:
        css_dependencies.append("topic_tree_style.css")

    for css_file in css_dependencies:
        with open(static_dir / css_file, "r", encoding="utf-8") as file:
            css_src = file.read()
            css_dependencies_src[css_file] = cssmin(css_src) if minify else css_src

    return css_dependencies_src


def _get_js_dependency_urls(
    enable_histogram,
    enable_topic_tree,
    enable_colormaps,
    selection_handler=None,
    cdn_url="unpkg.com",
):
    """
    Gather the necessary JavaScript dependency URLs for embedding in the HTML template.

    Parameters
    ----------
    enable_histogram: bool
        Whether to include JS URLs for the histogram functionality.

    enable_topic_tree: bool
        Whether to include JS URLs for the topic tree functionality.

    enable_colormaps: bool
        Whether to include JS URLs for the colormap functionality.

    selection_handler: SelectionHandlerBase or Iterable[SelectionHandlerBase], optional
        The selection handler(s) to use for managing data selection.

    cdn_url: str, optional
        The CDN URL to use for loading external JavaScript libraries.

    Returns
    -------
    list
        A list of URLs that point to the required JavaScript dependencies.
    """
    js_dependency_urls = []

    # Add common dependencies (if any)
    common_js_urls = [
        f"https://{cdn_url}/deck.gl@latest/dist.min.js",
        f"https://{cdn_url}/apache-arrow@latest/Arrow.es2015.min.js",
    ]
    js_dependency_urls.extend(common_js_urls)

    # Conditionally add dependencies based on functionality
    if enable_histogram or enable_colormaps:
        js_dependency_urls.append(f"https://{cdn_url}/d3@latest/dist/d3.min.js")

    if enable_topic_tree:
        js_dependency_urls.append(f"https://{cdn_url}/jquery@3.7.1/dist/jquery.min.js")

    if selection_handler is not None:
        if isinstance(selection_handler, Iterable):
            for handler in selection_handler:
                js_dependency_urls.extend(handler.dependencies)
        elif isinstance(selection_handler, SelectionHandlerBase):
            js_dependency_urls.extend(selection_handler.dependencies)
        else:
            raise ValueError(
                "The selection_handler must be an instance of SelectionHandlerBase or an iterable of SelectionHandlerBase instances."
            )

    js_dependency_urls = list(set(js_dependency_urls))

    return js_dependency_urls


def default_colormap_options(values_dict):

    colormap_metadata_list = []
    continuous_cmap_counter = 0
    existing_fields = set([])
    used_colormaps = set([])

    for name, values in values_dict.items():
        colormap_metadata = {}
        candidate_field = name.split()[0]
        n = 0
        while candidate_field in existing_fields:
            n += 1
            candidate_field = f"{name.split()[0]}_{n}"
        colormap_metadata["field"] = candidate_field
        colormap_metadata["description"] = name

        if values.dtype.kind in ["U", "S", "O"]:
            colormap_metadata["kind"] = "categorical"
            n_categories = len(np.unique(values))
            n = 0
            cmap = _DEFAULT_DICRETE_COLORMAPS[n]
            while cmap in used_colormaps or n_categories > len(get_cmap(cmap).colors):
                n += 1
                if n >= len(_DEFAULT_DICRETE_COLORMAPS):
                    n = 0
                    cmap = _DEFAULT_DICRETE_COLORMAPS[n]
                    while cmap in used_colormaps:
                        n += 1
                        cmap = _DEFAULT_DICRETE_COLORMAPS[n]
                    break
                else:
                    cmap = _DEFAULT_DICRETE_COLORMAPS[n]
            colormap_metadata["cmap"] = cmap
            used_colormaps.add(cmap)
        elif pd.api.types.is_datetime64_any_dtype(values):
            colormap_metadata["kind"] = "datetime"
            colormap_metadata["cmap"] = _DEFAULT_CONTINUOUS_COLORMAPS[
                continuous_cmap_counter
            ]
            continuous_cmap_counter += 1
        else:
            colormap_metadata["kind"] = "continuous"
            colormap_metadata["cmap"] = _DEFAULT_CONTINUOUS_COLORMAPS[
                continuous_cmap_counter
            ]
            continuous_cmap_counter += 1

        colormap_metadata_list.append(colormap_metadata)

    return colormap_metadata_list


def cmap_name_to_color_list(cmap_name):
    cmap = get_cmap(cmap_name)
    if hasattr(cmap, "colors"):
        result = [rgb2hex(c) for c in cmap.colors]
    else:
        result = [rgb2hex(cmap(i)) for i in np.linspace(0, 1, 128)]
    return result


def array_to_colors(values, cmap_name, metadata, color_list=None):
    values = np.asarray(values)

    # Handle colormap setup
    if cmap_name is None:
        cmap = None
        assert color_list is not None
        color_list = [to_rgba(color) for color in color_list]
    else:
        cmap = get_cmap(cmap_name)

    # Function to get finite/non-null mask
    def get_valid_mask(arr):
        if pd.api.types.is_datetime64_any_dtype(arr):
            return ~pd.isna(arr)
        elif arr.dtype.kind in ["f", "i"]:
            return np.isfinite(arr)
        else:
            return ~pd.isna(arr)

    # Handle datetime values
    if pd.api.types.is_datetime64_any_dtype(values):
        if cmap is None:
            raise ValueError("cmap must be provided for datetime data")

        valid_mask = get_valid_mask(values)
        if not np.any(valid_mask):
            raise ValueError("No valid datetime values found")

        valid_values = values[valid_mask]
        vmin, vmax = valid_values.min(), valid_values.max()

        # Convert to float for normalization
        normalized_values = np.zeros_like(values, dtype=float)
        normalized_values[valid_mask] = (
            (valid_values - vmin) / (vmax - vmin) if vmin != vmax else 0.5
        )

        colors_array = np.zeros((len(values), 4))
        colors_array[valid_mask] = cmap(normalized_values[valid_mask])
        colors_array[~valid_mask] = [0, 0, 0, 0]  # Transparent for invalid values

        # Store datetime range as ISO format strings
        metadata["valueRange"] = [
            pd.Timestamp(vmin).isoformat(),
            pd.Timestamp(vmax).isoformat(),
        ]
        metadata["kind"] = "datetime"

    elif values.dtype.kind in ["U", "S", "O"]:  # String or object type
        valid_mask = get_valid_mask(values)
        if not np.any(valid_mask):
            raise ValueError("No valid string values found")

        # Get unique valid values
        unique_values = np.unique(values[valid_mask])

        if cmap:
            n_colors = len(cmap.colors) if hasattr(cmap, "colors") else 256
        else:
            n_colors = len(color_list)

        if n_colors <= 20 or metadata.get("kind") == "categorical":
            # Handle categorical data
            if cmap is None and color_list:
                value_to_color = {
                    val: color_list[i % n_colors] for i, val in enumerate(unique_values)
                }
            else:
                value_to_color = {
                    val: cmap(
                        i / (len(unique_values) - 1) if len(unique_values) > 1 else 0.5
                    )
                    for i, val in enumerate(unique_values)
                }

            colors_array = np.zeros((len(values), 4))
            colors_array[valid_mask] = [
                value_to_color[val] for val in values[valid_mask]
            ]
            colors_array[~valid_mask] = [0, 0, 0, 0]  # Transparent for invalid values

            metadata["colorMapping"] = {
                str(key): rgb2hex(color) for key, color in value_to_color.items()
            }
            metadata["kind"] = "categorical"

        else:
            # Handle non-categorical string data
            if cmap:
                value_to_num = {val: i for i, val in enumerate(unique_values)}
                normalized_values = np.zeros(len(values))
                normalized_values[valid_mask] = [
                    value_to_num[val] for val in values[valid_mask]
                ]
                if len(unique_values) > 1:
                    normalized_values = normalized_values / (len(unique_values) - 1)

                colors_array = np.zeros((len(values), 4))
                colors_array[valid_mask] = cmap(normalized_values[valid_mask])
                colors_array[~valid_mask] = [0, 0, 0, 0]
            else:
                value_to_num = {
                    val: i % len(color_list) for i, val in enumerate(unique_values)
                }
                colors_array = np.zeros((len(values), 4))
                colors_array[valid_mask] = [
                    color_list[value_to_num[val]] for val in values[valid_mask]
                ]
                colors_array[~valid_mask] = [0, 0, 0, 0]

            metadata["colorMapping"] = {}

    else:  # Numeric data
        if cmap is None:
            raise ValueError("cmap must be provided for continuous data")

        valid_mask = get_valid_mask(values)
        if not np.any(valid_mask):
            raise ValueError("No valid numeric values found")

        valid_values = values[valid_mask]
        vmin, vmax = valid_values.min(), valid_values.max()

        normalized_values = np.zeros_like(values, dtype=float)
        normalized_values[valid_mask] = (
            (valid_values - vmin) / (vmax - vmin) if vmin != vmax else 0.5
        )

        colors_array = np.zeros((len(values), 4))
        colors_array[valid_mask] = cmap(normalized_values[valid_mask])
        colors_array[~valid_mask] = [0, 0, 0, 0]  # Transparent for invalid values

        metadata["valueRange"] = [float(vmin), float(vmax)]
        metadata["kind"] = "continuous"

    return (colors_array * 255).astype(np.uint8)


def color_sample_from_colors(color_array, n_swatches=5):
    jch_colors = cspace_convert(color_array[:, :3], "sRGB1", "JCh")
    cielab_colors = cspace_convert(jch_colors[jch_colors.T[1] > 20], "JCh", "CAM02-UCS")
    quantizer = KMeans(n_clusters=n_swatches, random_state=0, n_init=1).fit(
        cielab_colors
    )
    result = [
        rgb2hex(c)
        for c in np.clip(
            cspace_convert(quantizer.cluster_centers_, "CAM02-UCS", "sRGB1"), 0, 1
        )
    ]
    return result


def per_layer_cluster_colormaps(label_layers, label_color_map, n_swatches=5):
    metadata = []
    colordata = []
    for i, layer in enumerate(label_layers[::-1]):
        color_list = pd.Series(layer).map(label_color_map).to_list()
        color_array = np.asarray(
            [
                (
                    to_rgba(color)
                    if type(color) == str
                    else (color[0] / 255, color[1] / 255, color[2] / 255, 1.0)
                )
                for color in color_list
            ]
        )
        color_sample = color_sample_from_colors(color_array, n_swatches)
        unique_labels = np.unique(layer)
        colormap_subset = {
            label: (
                rgb2hex((color[0] / 255, color[1] / 255, color[2] / 255, 1.0))
                if type(color) != str
                else color
            )
            for label, color in label_color_map.items()
            if label in unique_labels
        }
        descriptors = _CLUSTER_LAYER_DESCRIPTORS.get(
            len(label_layers), [f"Layer-{n}" for n in range(len(label_layers))]
        )
        colormap_metadata = {
            "field": f"layer_{i}",
            "description": f"{descriptors[i]} Clusters",
            "colors": color_sample
            + [
                color for color in colormap_subset.values() if color not in color_sample
            ],
            "kind": "categorical",
            "color_mapping": colormap_subset,
        }
        if len(unique_labels) <= 25:
            colormap_metadata["show_legend"] = True
        else:
            colormap_metadata["show_legend"] = False
        colordata.append(layer)
        metadata.append(colormap_metadata)

    return metadata, colordata


def build_colormap_data(colormap_rawdata, colormap_metadata, base_colors):
    base_colors_sample = base_colors
    colormaps = [
        {
            "field": "none",
            "description": "Clusters",
            "colors": base_colors_sample,
            "kind": "categorical",
        }
    ]
    color_data = []

    for rawdata, metadata in zip(colormap_rawdata, colormap_metadata):
        if "colors" in metadata:
            cmap_colors = metadata["colors"]
        elif "cmap" in metadata:
            cmap_name = metadata["cmap"]
            cmap_colors = cmap_name_to_color_list(cmap_name)
        elif "palette" in metadata:
            cmap_colors = metadata["palette"]
            cmap_name = None
        elif "color_mapping" in metadata:
            cmap_colors = list(metadata["color_mapping"].values())
            cmap_name = None
        else:
            cmap_colors = []
        colormap = {
            "field": metadata["field"],
            "description": metadata["description"],
            "colors": cmap_colors,
            "kind": metadata.get("kind", "continuous"),
            "nColors": metadata.get("n_colors", 5),
        }
        if "show_legend" in metadata:
            colormap["showLegend"] = metadata["show_legend"]
        colormaps.append(colormap)
        if "color_mapping" in metadata:
            colormap["colorMapping"] = metadata["color_mapping"]
            colormap["kind"] = "categorical"
            colors_array = (
                np.array([to_rgba(metadata["color_mapping"][val]) for val in rawdata])
                * 255
            ).astype(np.uint8)
        else:
            colors_array = array_to_colors(rawdata, cmap_name, colormap, cmap_colors)
        color_data.append(
            pd.DataFrame(
                colors_array,
                columns=[
                    f"{metadata['field']}_r",
                    f"{metadata['field']}_g",
                    f"{metadata['field']}_b",
                    f"{metadata['field']}_a",
                ],
            )
        )

    return colormaps, pd.concat(color_data, axis=1)


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

    return [
        float(xmin - x_padding),
        float(xmax + x_padding),
        float(ymin - y_padding),
        float(ymax + y_padding),
    ]


def label_text_and_polygon_dataframes(
    labels,
    data_map_coords,
    noise_label="Unlabelled",
    use_medoids=False,
    cluster_polygons=False,
    include_zoom_bounds=False,
    include_related_points=False,
    alpha=0.05,
    parents=None,
):
    """
    Build the necessary label data, including cluster polygon bounds.

    Parameters
    ----------
    labels: np.array
        Label text for each point

    data_map_coords: np.array
        Data map xy coordinates for each point

    noise_label: str="Unlabelled"
        The label to represent noise as used in labels.

    use_medoids: bool (optional, default=False)
        Whether to use cluster medoids to position labels.
        Otherwise, the mean position of the cluster points is used.

    cluster_polygons: bool (optional, default=False)
        Whether to build polygon cluster boundaries.

    include_zoom_bounds: bool (optional, default=False)
        Whether to include the zoom boundary of a cluster associated with a label.
        Normally used when displaying a topic tree.

    include_related_points: bool (optional, default=False)
        Whether to include indexes of related points to each label.
        Normally used when displaying a topic tree with on_click functionality.

    alpha: float (optional, default=0.05)
        Display transparency for cluster polygons.

    parents: list or None (optional, default=None)
        A record of the cluster heirarchy. This will be edited to include this layer's values.

    Returns
    -------
    dataframe
        A dataframe containing relevant information for each label.
    """
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
    related_points = []
    points_bounds = []
    label_ids = []
    parent_ids = []

    for i, l in enumerate(unique_non_noise_labels):
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
        if include_related_points:
            related_points.append(np.where(cluster_mask))
        if include_zoom_bounds:
            points_bounds.append(compute_percentile_bounds(cluster_points))
        if parents is not None:
            if len(parents[0]):
                # Get the provenance (cluster membership at different heirarchical layers).
                # This should be consistent.(?? could break with different topic naming ??)
                p = (
                    ["base"]
                    + list(
                        np.median(parents[0][:, cluster_mask], axis=1)
                        .astype(int)
                        .astype(str)
                    )
                    + [str(i)]
                )
                label_ids.append("_".join(p))
                parent_ids.append("_".join(p[:-1]))
            else:
                label_ids.append(f"base_{i}")
                parent_ids.append("base")

    if parents is not None:
        # do the same for unlabeled points, noting that not all unlabeled
        # points at this level have the same parent.
        unlabeled_mask = cluster_idx_vector == -1

        # At the top level, we don't need to wory about unlabeled points having
        # different parents.
        if len(parents[0]):
            parent_masks = [
                (parents[0][-1] == parent) for parent in np.unique(parents[0][-1])
            ]
        else:
            parent_masks = [unlabeled_mask]

        # Iterate over possible parents
        for parent_mask in parent_masks:
            cluster_mask = unlabeled_mask & parent_mask

            if np.sum(cluster_mask) > 2:
                cluster_points = data_map_coords[cluster_mask]
                label_locations.append(cluster_points.mean(axis=0))
                cluster_sizes.append(None)
                polygons.append(None)
                unique_non_noise_labels.append(noise_label)
                if include_related_points:
                    related_points.append(np.where(cluster_mask))
                if include_zoom_bounds:
                    points_bounds.append(compute_percentile_bounds(cluster_points))
                if len(parents[0]):
                    # Get the provenance.
                    # This should be consistent.(??)
                    p = (
                        ["base"]
                        + list(
                            np.median(parents[0][:, cluster_mask], axis=1)
                            .astype(int)
                            .astype(str)
                        )
                        + ["-1"]
                    )
                    label_ids.append("_".join(p))
                    parent_ids.append("_".join(p[:-1]))
                else:
                    label_ids.append("base_-1")
                    parent_ids.append("base")

    if parents is not None:
        # parents is mutable, add on the currend cluster idx_vector.
        #
        if len(parents[0]):
            parents[0] = np.vstack((parents[0], cluster_idx_vector))
        else:
            parents[0] = np.vstack((cluster_idx_vector,))

    label_locations = np.asarray(label_locations)

    data = {
        "x": label_locations.T[0],
        "y": label_locations.T[1],
        "label": unique_non_noise_labels,
        "size": cluster_sizes,
    }
    if cluster_polygons:
        data["polygon"] = polygons
    # Points are far too heavyweight for large datasets
    # We can use a different more efficient data-structure later
    # if we require this information for selection etc.
    if include_related_points:
        data["points"] = related_points
    if parents is not None:
        data["id"] = label_ids
        data["parent"] = parent_ids
        if include_zoom_bounds:
            data["bounds"] = points_bounds
    return pd.DataFrame(data)


def url_to_base64_img(url):
    try:
        # Download the image.
        # The requests library doesn't support the file scheme so use urllib.
        with urlopen(url, timeout=10) as response:
            data = response.read()
            content_type = response.info().get_content_type()
    except HTTPError as e:
        print(f"Error downloading image: HTTP error {e.code} {e.reason}")
        return None
    except URLError as e:
        print(f"Error downloading image: Network error {e.reason}")
        return None

    # Determine the image type from the response content type.
    if not content_type.startswith("image/"):
        print(f"URL {url} has content type {content_type} not image")
        return None

    # Convert the image data to base64.
    image_data = base64.b64encode(data).decode("utf-8")

    # Create the complete data URI.
    return f"data:{content_type};base64,{image_data}"


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
    n_points = point_dataframe.shape[0]
    if point_size_scale is not None:
        magic_number = point_size_scale / 100.0
    else:
        width = bounds[1] - bounds[0]
        height = bounds[3] - bounds[2]
        size_scale = np.sqrt(width * height)
        scaling = size_scale / 25.0
        magic_number = scaling * np.clip(32 * 4 ** (-np.log10(n_points)), 0.005, 0.1)

    if "size" not in point_dataframe.columns:
        point_size = magic_number
    else:
        point_dataframe["size"] = magic_number * (
            point_dataframe["size"] / point_dataframe["size"].mean()
        )
        point_size = -1

    if darkmode and text_outline_color == "#eeeeeedd":
        text_outline_color = "#111111dd"

    if background_image is not None:
        if background_image_bounds is None:
            background_image_bounds = [
                point_dataframe["x"].min(),
                point_dataframe["y"].min(),
                point_dataframe["x"].max(),
                point_dataframe["y"].max(),
            ]

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

    if "hover_text" in point_dataframe.columns:
        if extra_point_data is not None:
            assert extra_point_data.shape[0] == point_dataframe.shape[0], (
                "If `extra_point_data` is provided, it must have the same number of rows as "
                "`point_dataframe`."
            )
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
                    '({index, picked, layer}) => picked ? {"html": `'
                    + hover_text_html_template.format_map(replacements)
                    + "`} : null"
                )
            else:
                get_tooltip = "({index}) => hoverData.hover_text[index]"

            if on_click is not None:
                on_click = (
                    "({index, picked, layer}, event) => { if (picked) {"
                    + on_click.format_map(replacements)
                    + " } }"
                )

            if (
                "button_on_click" in topic_tree_kwds
                and topic_tree_kwds["button_on_click"] is not None
            ):
                topic_tree_replacements = FormattingDict(
                    **{
                        str(name): f"label.points[0].map(x=>datamap.metaData.{name}[x])"
                        for name in hover_data.columns
                    }
                )
                topic_tree_kwds["button_on_click"] = topic_tree_kwds[
                    "button_on_click"
                ].format_map(topic_tree_replacements)
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
                    "({index, picked, layer}, event) => { if (picked) {"
                    + on_click.format_map(replacements)
                    + " } }"
                )
            if (
                "button_on_click" in topic_tree_kwds
                and topic_tree_kwds["button_on_click"] is not None
            ):
                topic_tree_replacements = FormattingDict(
                    **{
                        str(name): f"label.points[0].map(x=>datamap.metaData.{name}[x])"
                        for name in hover_data.columns
                    }
                )
                topic_tree_kwds["button_on_click"] = topic_tree_kwds[
                    "button_on_click"
                ].format_map(topic_tree_replacements)

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
                '({index, picked, layer}) => picked ? {"html": `'
                + hover_text_html_template.format_map(replacements)
                + "`} : null"
            )
        else:
            get_tooltip = "null"

        if on_click is not None:
            on_click = (
                "({index, picked, layer}, event) => { if (picked) {"
                + on_click.format_map(replacements)
                + " } }"
            )
        if (
            "button_on_click" in topic_tree_kwds
            and topic_tree_kwds["button_on_click"] is not None
        ):
            topic_tree_replacements = FormattingDict(
                **{
                    str(name): f"label.points[0].map(x=>datamap.metaData.{name}[x])"
                    for name in hover_data.columns
                }
            )
            topic_tree_kwds["button_on_click"] = topic_tree_kwds[
                "button_on_click"
            ].format_map(topic_tree_replacements)
    else:
        hover_data = pd.DataFrame(columns=("hover_text",))
        get_tooltip = "null"

    # Histogram
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

    if colormap_rawdata is not None and colormap_metadata is not None:
        jch_colors = cspace_convert(
            point_dataframe[["r", "g", "b"]].values / 255, "sRGB1", "JCh"
        )
        cielab_colors = cspace_convert(
            jch_colors[jch_colors.T[1] > 20], "JCh", "CAM02-UCS"
        )
        n_swatches = (
            np.max([colormap.get("n_colors", 5) for colormap in colormap_metadata])
            if len(colormap_metadata) > 0
            else 5
        )
        quantizer = KMeans(n_clusters=n_swatches, random_state=0, n_init=1).fit(
            cielab_colors
        )
        cluster_colors = [
            rgb2hex(c)
            for c in np.clip(
                cspace_convert(quantizer.cluster_centers_, "CAM02-UCS", "sRGB1"), 0, 1
            )
        ]
        if cluster_layer_colormaps:
            if label_layers is None or cluster_colormap is None:
                raise ValueError(
                    "If using cluster_layer_colormaps label_layers and cluster_colormap must be provided"
                )
            layer_color_metadata, layer_color_data = per_layer_cluster_colormaps(
                label_layers, cluster_colormap, n_swatches
            )
            colormap_metadata[0:0] = layer_color_metadata
            colormap_rawdata[0:0] = layer_color_data
        color_metadata, color_data = build_colormap_data(
            colormap_rawdata, colormap_metadata, cluster_colors
        )
        enable_colormap_selector = True
    elif colormaps is not None:
        colormap_metadata = default_colormap_options(colormaps)
        colormap_rawdata = list(colormaps.values())
        cielab_colors = cspace_convert(
            point_dataframe[["r", "g", "b"]].values / 255, "sRGB1", "CAM02-UCS"
        )
        quantizer = KMeans(n_clusters=5, random_state=0, n_init=1).fit(cielab_colors)
        cluster_colors = [
            rgb2hex(c)
            for c in np.clip(
                cspace_convert(quantizer.cluster_centers_, "CAM02-UCS", "sRGB1"), 0, 1
            )
        ]
        if cluster_layer_colormaps:
            if label_layers is None or cluster_colormap is None:
                raise ValueError(
                    "If using cluster_layer_colormaps label_layers and cluster_colormap must be provided"
                )
            layer_color_metadata, layer_color_data = per_layer_cluster_colormaps(
                label_layers, cluster_colormap, 5
            )
            colormap_metadata[0:0] = layer_color_metadata
            colormap_rawdata[0:0] = layer_color_data
        color_metadata, color_data = build_colormap_data(
            colormap_rawdata, colormap_metadata, cluster_colors
        )
        enable_colormap_selector = True
    else:
        color_metadata = None
        color_data = None
        enable_colormap_selector = False

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

        if enable_colormap_selector:
            buffer = io.BytesIO()
            color_data.to_feather(buffer, compression="uncompressed")
            buffer.seek(0)
            arrow_bytes = buffer.read()
            gzipped_bytes = gzip.compress(arrow_bytes)
            base64_color_data = base64.b64encode(gzipped_bytes).decode()
        else:
            base64_color_data = None

        file_prefix = None
        html_file_prefix = None
        n_chunks = 0
    else:
        base64_point_data = ""
        base64_hover_data = ""
        base64_label_data = ""
        base64_histogram_bin_data = ""
        base64_histogram_index_data = ""
        base64_color_data = ""

        # Handle offline_data_path with backward compatibility
        if offline_data_path is not None:
            # Convert to Path object for easier handling
            data_path = Path(offline_data_path)

            # Create directory if it doesn't exist
            if (
                data_path.suffix
            ):  # If user provided a file with extension, use parent dir
                data_dir = data_path.parent
                base_name = data_path.stem
                file_prefix = str(data_path.with_suffix(""))
            else:  # User provided directory/basename
                data_dir = (
                    data_path.parent if data_path.parent != Path(".") else Path(".")
                )
                base_name = data_path.name
                file_prefix = str(data_path)

            # Ensure directory exists
            data_dir.mkdir(parents=True, exist_ok=True)

            # For HTML references, we need just the basename
            html_file_prefix = base_name
        else:
            # Backward compatibility: use offline_data_prefix
            file_prefix = (
                offline_data_prefix
                if offline_data_prefix is not None
                else "datamapplot"
            )
            html_file_prefix = file_prefix
        n_chunks = (point_data.shape[0] // offline_data_chunk_size) + 1
        for i in range(n_chunks):
            chunk_start = i * offline_data_chunk_size
            chunk_end = min((i + 1) * offline_data_chunk_size, point_data.shape[0])
            with gzip.open(f"{file_prefix}_point_data_{i}.zip", "wb") as f:
                point_data[chunk_start:chunk_end].to_feather(
                    f, compression="uncompressed"
                )
            with gzip.open(f"{file_prefix}_meta_data_{i}.zip", "wb") as f:
                f.write(
                    json.dumps(
                        hover_data[chunk_start:chunk_end].to_dict(orient="list")
                    ).encode()
                )
            if enable_colormap_selector:
                with gzip.open(f"{file_prefix}_color_data_{i}.zip", "wb") as f:
                    color_data[chunk_start:chunk_end].to_feather(
                        f, compression="uncompressed"
                    )
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

    if dynamic_tooltip is not None:
        enable_dynamic_tooltip = True
        tooltip_identifier_js = dynamic_tooltip["identifier_js"]
        tooltip_fetch_js = dynamic_tooltip["fetch_js"]
        tooltip_format_js = dynamic_tooltip["format_js"]
        tooltip_loading_js = dynamic_tooltip["loading_js"]
        tooltip_error_js = dynamic_tooltip["error_js"]
    else:
        enable_dynamic_tooltip = False
        tooltip_identifier_js = None
        tooltip_fetch_js = None
        tooltip_format_js = None
        tooltip_loading_js = None
        tooltip_error_js = None

    if background_color is None:
        page_background_color = "#ffffff" if not darkmode else "#000000"
    else:
        page_background_color = background_color

    # Pepare JS/CSS dependencies for embedding in the HTML template
    dependencies_ctx = {
        "js_dependency_urls": _get_js_dependency_urls(
            enable_histogram,
            enable_topic_tree,
            enable_colormap_selector,
            selection_handler,
            cdn_url=cdn_url,
        ),
        "js_dependency_srcs": _get_js_dependency_sources(
            minify_deps,
            enable_search,
            enable_histogram,
            enable_lasso_selection,
            enable_colormap_selector,
            enable_topic_tree,
            enable_dynamic_tooltip,
        ),
        "css_dependency_srcs": _get_css_dependency_sources(
            minify_deps,
            enable_histogram,
            show_loading_progress,
            enable_colormap_selector,
            enable_topic_tree,
        ),
    }

    template = jinja2.Template(_DECKGL_TEMPLATE_STR)

    if logo is not None:
        scheme = urlparse(logo).scheme
        if not scheme:
            # HTML will think logo is a relative path and fail to load it.
            raise ValueError(
                (
                    "No scheme supplied for logo URL. "
                    f"Perhaps you meant https://{logo}?"
                )
            )
        elif offline_mode or scheme == "file":
            # Store the image inline as a base64 URI.
            logo = url_to_base64_img(logo)

    if offline_mode:
        if offline_mode_js_data_file is None:
            data_directory = platformdirs.user_data_dir("datamapplot")
            offline_mode_js_data_file = (
                Path(data_directory) / "datamapplot_js_encoded.json"
            )
            if not offline_mode_js_data_file.is_file():
                offline_mode_caching.cache_js_files()
            offline_mode_data = json.load(offline_mode_js_data_file.open("r"))
        else:
            offline_mode_data = json.load(open(offline_mode_js_data_file, "r"))

        if offline_mode_font_data_file is None:
            data_directory = platformdirs.user_data_dir("datamapplot")
            offline_mode_font_data_file = (
                Path(data_directory) / "datamapplot_fonts_encoded.json"
            )
            if not offline_mode_font_data_file.is_file():
                offline_mode_caching.cache_fonts()
    else:
        offline_mode_data = None

    api_fontname = font_family.replace(" ", "+")
    font_data = get_google_font_for_embedding(
        font_family,
        offline_mode=offline_mode,
        offline_font_file=offline_mode_font_data_file if offline_mode else None,
    )
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
        if isinstance(selection_handler, Iterable):
            for handler in selection_handler:
                if custom_html is None:
                    custom_html = handler.html
                else:
                    custom_html += handler.html

                if custom_js is None:
                    custom_js = handler.javascript
                else:
                    custom_js += handler.javascript

                if custom_css is None:
                    custom_css = handler.css
                else:
                    custom_css += handler.css
        elif isinstance(selection_handler, SelectionHandlerBase):
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
        else:
            raise ValueError(
                "selection_handler must be an instance of SelectionHandlerBase or an iterable of SelectionHandlerBase instances"
            )

    html_str = template.render(
        title=title if title is not None else "Interactive Data Map",
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
        base64_color_data=base64_color_data,
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
        custom_js=custom_js,
        offline_mode=offline_mode,
        offline_mode_data=offline_mode_data,
        splash_warning=splash_warning,
        enable_api_tooltip=enable_dynamic_tooltip,
        tooltip_identifier_js=tooltip_identifier_js,
        tooltip_fetch_js=tooltip_fetch_js,
        tooltip_format_js=tooltip_format_js,
        tooltip_loading_js=tooltip_loading_js,
        tooltip_error_js=tooltip_error_js,
        **dependencies_ctx,
    )
    return html_str
