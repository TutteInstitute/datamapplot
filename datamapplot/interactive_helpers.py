"""
Helper functions for interactive data map rendering.

This module contains utilities for:
- Font embedding (Google Fonts)
- JavaScript/CSS dependency management
- Colormap processing and data conversion
- Label and polygon data preparation
- Data encoding for HTML templates
"""

import base64
import gzip
import io
import json
import os
from collections.abc import Iterable
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import numpy as np
import pandas as pd
from colorspacious import cspace_convert
from importlib_resources import files
from matplotlib.colors import rgb2hex, to_rgba
from pandas.api.types import is_datetime64_any_dtype, is_string_dtype
from rcssmin import cssmin
from rjsmin import jsmin
from scipy.spatial import Delaunay
from sklearn.cluster import KMeans
import datetime as dt

from datamapplot.alpha_shapes import create_boundary_polygons, smooth_polygon
from datamapplot.fonts import can_reach_google_fonts, query_google_fonts
from datamapplot.medoids import medoid
from datamapplot.selection_handlers import SelectionHandlerBase
from datamapplot import offline_mode_caching

try:
    import matplotlib
    get_cmap = matplotlib.colormaps.get_cmap
except ImportError:
    from matplotlib.cm import get_cmap

# Default colormaps for different data types
DEFAULT_DISCRETE_COLORMAPS = [
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

DEFAULT_CONTINUOUS_COLORMAPS = [
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

CLUSTER_LAYER_DESCRIPTORS = {
    9: ["Top", "Upper", "Upper-mid", "Upper-central", "Mid", 
        "Lower-central", "Lower-mid", "Lower", "Bottom"],
    8: ["Top", "Upper", "Upper-mid", "Upper-central", 
        "Lower-central", "Lower-mid", "Lower", "Bottom"],
    7: ["Top", "Upper", "Upper-mid", "Mid", "Lower-mid", "Lower", "Bottom"],
    6: ["Top", "Upper", "Upper-mid", "Lower-mid", "Lower", "Bottom"],
    5: ["Top", "Upper", "Mid", "Lower", "Bottom"],
    4: ["Top", "Upper-mid", "Lower-mid", "Bottom"],
    3: ["Upper", "Mid", "Lower"],
    2: ["Upper", "Lower"],
    1: ["Primary"],
}


# =============================================================================
# Font Embedding Functions
# =============================================================================

def get_google_font_for_embedding(fontname, offline_mode=False, offline_font_file=None):
    """
    Get Google Font CSS for embedding in HTML.
    
    Parameters
    ----------
    fontname : str
        Name of the Google Font to embed.
    offline_mode : bool, optional
        Whether to use offline cached fonts. Default is False.
    offline_font_file : str or Path, optional
        Path to the offline font cache file.
        
    Returns
    -------
    str
        HTML/CSS string for embedding the font.
    """
    if offline_mode:
        all_encoded_fonts = offline_mode_caching.load_fonts(file_path=offline_font_file)
        encoded_fonts = all_encoded_fonts.get(fontname, None)
        if encoded_fonts is not None:
            font_descriptions = [
                _build_font_face_css(fontname, font_data)
                for font_data in encoded_fonts
            ]
            return "<style>\n" + "\n".join(font_descriptions) + "\n    </style>\n"
        return ""

    if can_reach_google_fonts(timeout=10.0):
        font_links = []
        collection = query_google_fonts(fontname)
        for font in collection:
            if font.url.endswith(".ttf"):
                font_links.append(
                    f'<link rel="preload" href="{font.url}" as="font" '
                    f'crossorigin="anonymous" type="font/ttf" />'
                )
            elif font.url.endswith(".woff2"):
                font_links.append(
                    f'<link rel="preload" href="{font.url}" as="font" '
                    f'crossorigin="anonymous" type="font/woff2" />'
                )
        return "\n".join(font_links) + f"\n<style>\n{collection.content}\n</style>\n"
    return ""


def _build_font_face_css(fontname, font_data):
    """Build a @font-face CSS declaration from font data."""
    base_css = f"""
    @font-face {{ 
        font-family: '{fontname}'; 
        font-style: {font_data["style"]};
        font-weight: {font_data["weight"]};
        src: url(data:font/{font_data["type"]};base64,{font_data["content"]}) format('{font_data["type"]}');"""
    
    if len(font_data["unicode_range"]) > 0:
        return base_css + f"""
        unicode-range: {font_data["unicode_range"]};
    }}"""
    return base_css + "\n    }"


# =============================================================================
# JavaScript/CSS Dependency Management
# =============================================================================

def get_js_dependency_sources(
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
    enable_histogram : bool
        Whether to include JS dependencies for the histogram functionality.
    enable_lasso_selection : bool
        Whether to include JS dependencies for the lasso selection functionality.
    colormap_selector : bool
        Whether to include JS dependencies for the colormap selector functionality.
    enable_topic_tree : bool
        Whether to include JS dependencies for the topic tree functionality.
    enable_dynamic_tooltip : bool
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


def get_css_dependency_sources(
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
    enable_histogram : bool
        Whether to include CSS dependencies for the histogram functionality.
    show_loading_progress : bool
        Whether to have progress bars for data loading.
    enable_colormap_selector : bool
        Whether to include CSS dependencies for the colormap selector.
    enable_topic_tree : bool
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


def get_js_dependency_urls(
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
    enable_histogram : bool
        Whether to include JS URLs for the histogram functionality.
    enable_topic_tree : bool
        Whether to include JS URLs for the topic tree functionality.
    enable_colormaps : bool
        Whether to include JS URLs for the colormap functionality.
    selection_handler : SelectionHandlerBase or Iterable[SelectionHandlerBase], optional
        The selection handler(s) to use for managing data selection.
    cdn_url : str, optional
        The CDN URL to use for loading external JavaScript libraries.

    Returns
    -------
    list
        A list of URLs that point to the required JavaScript dependencies.
    """
    js_dependency_urls = [
        f"https://{cdn_url}/deck.gl@latest/dist.min.js",
        f"https://{cdn_url}/apache-arrow@latest/Arrow.es2015.min.js",
    ]

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
                "The selection_handler must be an instance of SelectionHandlerBase "
                "or an iterable of SelectionHandlerBase instances."
            )

    return list(set(js_dependency_urls))


# =============================================================================
# Colormap Processing Functions
# =============================================================================

def default_colormap_options(values_dict):
    """
    Generate default colormap metadata for a dictionary of value arrays.
    
    Parameters
    ----------
    values_dict : dict
        Dictionary mapping names to numpy arrays of values.
        
    Returns
    -------
    list
        List of colormap metadata dictionaries.
    """
    colormap_metadata_list = []
    continuous_cmap_counter = 0
    existing_fields = set()
    used_colormaps = set()

    for name, values in values_dict.items():
        colormap_metadata = {}
        candidate_field = name.split()[0]
        n = 0
        while candidate_field in existing_fields:
            n += 1
            candidate_field = f"{name.split()[0]}_{n}"
        colormap_metadata["field"] = candidate_field
        existing_fields.add(candidate_field)
        colormap_metadata["description"] = name

        if values.dtype.kind in ["U", "S", "O", "b"]:
            colormap_metadata["kind"] = "categorical"
            n_categories = len(np.unique(values))
            n = 0
            cmap = DEFAULT_DISCRETE_COLORMAPS[n]
            while cmap in used_colormaps or n_categories > len(get_cmap(cmap).colors):
                n += 1
                if n >= len(DEFAULT_DISCRETE_COLORMAPS):
                    n = 0
                    cmap = DEFAULT_DISCRETE_COLORMAPS[n]
                    while cmap in used_colormaps:
                        n += 1
                        cmap = DEFAULT_DISCRETE_COLORMAPS[n]
                    break
                else:
                    cmap = DEFAULT_DISCRETE_COLORMAPS[n]
            colormap_metadata["cmap"] = cmap
            used_colormaps.add(cmap)
        elif is_datetime64_any_dtype(values):
            colormap_metadata["kind"] = "datetime"
            colormap_metadata["cmap"] = DEFAULT_CONTINUOUS_COLORMAPS[continuous_cmap_counter]
            continuous_cmap_counter += 1
        else:
            colormap_metadata["kind"] = "continuous"
            colormap_metadata["cmap"] = DEFAULT_CONTINUOUS_COLORMAPS[continuous_cmap_counter]
            continuous_cmap_counter += 1

        colormap_metadata_list.append(colormap_metadata)

    return colormap_metadata_list


def cmap_name_to_color_list(cmap_name):
    """Convert a matplotlib colormap name to a list of hex colors."""
    cmap = get_cmap(cmap_name)
    if hasattr(cmap, "colors"):
        return [rgb2hex(c) for c in cmap.colors]
    return [rgb2hex(cmap(i)) for i in np.linspace(0, 1, 128)]


def array_to_colors(values, cmap_name, metadata, color_list=None):
    """
    Convert an array of values to RGBA color values.
    
    Parameters
    ----------
    values : array-like
        The values to convert to colors.
    cmap_name : str or None
        Name of the matplotlib colormap to use.
    metadata : dict
        Dictionary to store colormap metadata (modified in place).
    color_list : list, optional
        List of colors to use instead of a colormap.
        
    Returns
    -------
    np.ndarray
        Array of RGBA color values (0-255).
    """
    values = np.asarray(values)

    # Handle colormap setup
    if cmap_name is None:
        cmap = None
        assert color_list is not None
        color_list = [to_rgba(color) for color in color_list]
    else:
        cmap = get_cmap(cmap_name)

    vmin = metadata.pop("vmin", None)
    vmax = metadata.pop("vmax", None)

    def get_valid_mask(arr):
        if is_datetime64_any_dtype(arr):
            return ~pd.isna(arr)
        elif arr.dtype.kind in ["f", "i"]:
            return np.isfinite(arr)
        return ~pd.isna(arr)

    # Handle datetime values
    if is_datetime64_any_dtype(values):
        return _datetime_to_colors(values, cmap, vmin, vmax, metadata, get_valid_mask)
    elif values.dtype.kind in ["U", "S", "O", "b"]:
        return _categorical_to_colors(values, cmap, metadata, color_list, get_valid_mask)
    else:
        return _numeric_to_colors(values, cmap, vmin, vmax, metadata, get_valid_mask)


def _datetime_to_colors(values, cmap, vmin, vmax, metadata, get_valid_mask):
    """Convert datetime values to colors."""
    if cmap is None:
        raise ValueError("cmap must be provided for datetime data")

    valid_mask = get_valid_mask(values)
    if not np.any(valid_mask):
        raise ValueError("No valid datetime values found")

    valid_values = values[valid_mask]

    if not isinstance(vmin, (pd.Timestamp, np.datetime64, dt.datetime)):
        vmin = valid_values.min()
    if not isinstance(vmax, (pd.Timestamp, np.datetime64, dt.datetime)):
        vmax = valid_values.max()

    normalized_values = np.zeros_like(values, dtype=float)
    normalized_values[valid_mask] = (
        (valid_values - vmin) / (vmax - vmin) if vmin != vmax else 0.5
    )

    colors_array = np.zeros((len(values), 4))
    colors_array[valid_mask] = cmap(normalized_values[valid_mask])
    colors_array[~valid_mask] = [0, 0, 0, 0]

    metadata["valueRange"] = [
        pd.Timestamp(vmin).isoformat(),
        pd.Timestamp(vmax).isoformat(),
    ]
    metadata["kind"] = "datetime"

    return (colors_array * 255).astype(np.uint8)


def _categorical_to_colors(values, cmap, metadata, color_list, get_valid_mask):
    """Convert categorical values to colors."""
    valid_mask = get_valid_mask(values)
    if not np.any(valid_mask):
        raise ValueError("No valid string, object, or boolean values found")

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
                val: cmap(i / (len(unique_values) - 1) if len(unique_values) > 1 else 0.5)
                for i, val in enumerate(unique_values)
            }

        colors_array = np.zeros((len(values), 4))
        colors_array[valid_mask] = [value_to_color[val] for val in values[valid_mask]]
        colors_array[~valid_mask] = [0, 0, 0, 0]

        metadata["colorMapping"] = {
            str(key): rgb2hex(color) for key, color in value_to_color.items()
        }
        metadata["kind"] = "categorical"
    else:
        # Handle non-categorical string data
        if cmap:
            value_to_num = {val: i for i, val in enumerate(unique_values)}
            normalized_values = np.zeros(len(values))
            normalized_values[valid_mask] = [value_to_num[val] for val in values[valid_mask]]
            if len(unique_values) > 1:
                normalized_values = normalized_values / (len(unique_values) - 1)

            colors_array = np.zeros((len(values), 4))
            colors_array[valid_mask] = cmap(normalized_values[valid_mask])
            colors_array[~valid_mask] = [0, 0, 0, 0]
        else:
            value_to_num = {val: i % len(color_list) for i, val in enumerate(unique_values)}
            colors_array = np.zeros((len(values), 4))
            colors_array[valid_mask] = [
                color_list[value_to_num[val]] for val in values[valid_mask]
            ]
            colors_array[~valid_mask] = [0, 0, 0, 0]

        metadata["colorMapping"] = {}

    return (colors_array * 255).astype(np.uint8)


def _numeric_to_colors(values, cmap, vmin, vmax, metadata, get_valid_mask):
    """Convert numeric values to colors."""
    if cmap is None:
        raise ValueError("cmap must be provided for continuous data")

    valid_mask = get_valid_mask(values)
    if not np.any(valid_mask):
        raise ValueError("No valid numeric values found")

    valid_values = values[valid_mask]

    if not np.issubdtype(type(vmin), np.number):
        vmin = valid_values.min()
    if not np.issubdtype(type(vmax), np.number):
        vmax = valid_values.max()

    normalized_values = np.zeros_like(values, dtype=float)
    normalized_values[valid_mask] = (
        (valid_values - vmin) / (vmax - vmin) if vmin != vmax else 0.5
    )

    colors_array = np.zeros((len(values), 4))
    colors_array[valid_mask] = cmap(normalized_values[valid_mask])
    colors_array[~valid_mask] = [0, 0, 0, 0]

    metadata["valueRange"] = [float(vmin), float(vmax)]
    metadata["kind"] = "continuous"

    return (colors_array * 255).astype(np.uint8)


def color_sample_from_colors(color_array, n_swatches=5):
    """Extract representative color swatches from a color array using KMeans clustering."""
    jch_colors = cspace_convert(color_array[:, :3], "sRGB1", "JCh")
    cielab_colors = cspace_convert(jch_colors[jch_colors.T[1] > 20], "JCh", "CAM02-UCS")
    quantizer = KMeans(n_clusters=n_swatches, random_state=0, n_init=1).fit(cielab_colors)
    result = [
        rgb2hex(c)
        for c in np.clip(
            cspace_convert(quantizer.cluster_centers_, "CAM02-UCS", "sRGB1"), 0, 1
        )
    ]
    return result


def per_layer_cluster_colormaps(label_layers, label_color_map, n_swatches=5):
    """
    Generate colormap metadata and color data for hierarchical cluster layers.
    
    Parameters
    ----------
    label_layers : list
        List of label arrays, one per layer.
    label_color_map : dict
        Dictionary mapping labels to colors.
    n_swatches : int, optional
        Number of color swatches to extract.
        
    Returns
    -------
    tuple
        (metadata, colordata) where metadata is a list of dictionaries and
        colordata is a list of label arrays.
    """
    metadata = []
    colordata = []
    
    for i, layer in enumerate(label_layers[::-1]):
        color_list = pd.Series(layer).map(label_color_map).to_list()
        color_array = np.asarray([
            (to_rgba(color) if type(color) == str 
             else (color[0] / 255, color[1] / 255, color[2] / 255, 1.0))
            for color in color_list
        ])
        color_sample = color_sample_from_colors(color_array, n_swatches)
        unique_labels = np.unique(layer)
        colormap_subset = {
            label: (rgb2hex((color[0] / 255, color[1] / 255, color[2] / 255, 1.0))
                    if type(color) != str else color)
            for label, color in label_color_map.items()
            if label in unique_labels
        }
        
        descriptors = CLUSTER_LAYER_DESCRIPTORS.get(
            len(label_layers), [f"Layer-{n}" for n in range(len(label_layers))]
        )
        colormap_metadata = {
            "field": f"layer_{i}",
            "description": f"{descriptors[i]} Clusters",
            "colors": color_sample + [
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
    """
    Build colormap configuration and color data for the interactive viewer.
    
    Parameters
    ----------
    colormap_rawdata : list
        List of raw data arrays for each colormap.
    colormap_metadata : list
        List of metadata dictionaries for each colormap.
    base_colors : list
        Base cluster colors.
        
    Returns
    -------
    tuple
        (colormaps, color_df) where colormaps is a list of colormap configurations
        and color_df is a DataFrame of color values.
    """
    colormaps = [{
        "field": "none",
        "description": "Clusters",
        "colors": base_colors,
        "kind": "categorical",
    }]
    color_data = []

    for rawdata, metadata in zip(colormap_rawdata, colormap_metadata):
        cmap_colors, cmap_name = _extract_colormap_colors(metadata)
        
        colormap = {
            "field": metadata["field"],
            "description": metadata["description"],
            "colors": cmap_colors,
            "kind": metadata.get("kind", "continuous"),
            "nColors": metadata.get("n_colors", 5),
            "vmin": metadata.get("vmin", None),
            "vmax": metadata.get("vmax", None),
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
        
        color_data.append(pd.DataFrame(
            colors_array,
            columns=[
                f"{metadata['field']}_r",
                f"{metadata['field']}_g",
                f"{metadata['field']}_b",
                f"{metadata['field']}_a",
            ],
        ))

    return colormaps, pd.concat(color_data, axis=1)


def _extract_colormap_colors(metadata):
    """Extract color list and colormap name from metadata."""
    if "colors" in metadata:
        return metadata["colors"], None
    elif "cmap" in metadata:
        cmap_name = metadata["cmap"]
        return cmap_name_to_color_list(cmap_name), cmap_name
    elif "palette" in metadata:
        return metadata["palette"], None
    elif "color_mapping" in metadata:
        return list(metadata["color_mapping"].values()), None
    return [], None


# =============================================================================
# Data Bounds and Label Processing
# =============================================================================

def compute_percentile_bounds(points, percentage=99.9):
    """
    Compute bounding box that contains the specified percentage of points.
    
    Parameters
    ----------
    points : np.ndarray
        Array of (x, y) coordinates.
    percentage : float, optional
        Percentage of points to include in bounds.
        
    Returns
    -------
    list
        [xmin, xmax, ymin, ymax] bounds with padding.
    """
    n_points = points.shape[0]
    n_to_select = np.int32(n_points * (percentage / 100))
    centroid = np.mean(points, axis=0)

    vectors = points - centroid
    distances = np.linalg.norm(vectors**2, axis=1)
    sorted_indices = np.argsort(distances)
    selected_points = points[sorted_indices[:n_to_select]]

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
    labels : np.ndarray
        Label text for each point.
    data_map_coords : np.ndarray
        Data map xy coordinates for each point.
    noise_label : str, optional
        The label to represent noise. Default is "Unlabelled".
    use_medoids : bool, optional
        Whether to use cluster medoids to position labels.
    cluster_polygons : bool, optional
        Whether to build polygon cluster boundaries.
    include_zoom_bounds : bool, optional
        Whether to include the zoom boundary of a cluster.
    include_related_points : bool, optional
        Whether to include indexes of related points to each label.
    alpha : float, optional
        Display transparency for cluster polygons.
    parents : list or None, optional
        A record of the cluster hierarchy.

    Returns
    -------
    pd.DataFrame
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

    for i, label in enumerate(unique_non_noise_labels):
        cluster_mask = cluster_idx_vector == i
        cluster_points = data_map_coords[cluster_mask]

        if use_medoids:
            label_locations.append(medoid(cluster_points))
        else:
            label_locations.append(cluster_points.mean(axis=0))

        cluster_sizes.append(np.sum(cluster_mask) ** 0.25)
        
        if cluster_polygons:
            polygons.append(_compute_cluster_polygon(cluster_points, alpha))
        else:
            polygons.append(None)
            
        if include_zoom_bounds:
            points_bounds.append(_compute_label_bounds(cluster_points))
        else:
            points_bounds.append(None)
            
        if include_related_points:
            related_points.append(np.where(cluster_mask)[0].tolist())
        else:
            related_points.append(None)

        # Handle label IDs and parent tracking
        if parents is not None:
            label_id = f"{len(parents)}-{i}"
            parent_id = _find_parent_id(cluster_mask, parents)
            label_ids.append(label_id)
            parent_ids.append(parent_id)
            parents.append(cluster_mask)
        else:
            label_ids.append(None)
            parent_ids.append(None)

    label_locations = np.asarray(label_locations)
    
    df = pd.DataFrame({
        "label": unique_non_noise_labels,
        "x": label_locations[:, 0],
        "y": label_locations[:, 1],
        "size": cluster_sizes,
        "polygon": polygons,
        "bounds": points_bounds,
        "relatedPoints": related_points,
        "id": label_ids,
        "parent": parent_ids,
    })
    
    # Remove None columns
    df = df.dropna(axis=1, how="all")
    
    return df


def _compute_cluster_polygon(cluster_points, alpha):
    """Compute a smoothed boundary polygon for a cluster."""
    try:
        simplices = Delaunay(cluster_points, qhull_options="Qbb Qc Qz Q12 Q7").simplices
        boundary_polys = create_boundary_polygons(
            cluster_points, simplices, alpha=alpha
        )
        if len(boundary_polys) > 0:
            return [smooth_polygon(boundary_polys[0]).tolist()]
        return None
    except Exception:
        return None


def _compute_label_bounds(cluster_points):
    """Compute bounding box for a cluster's points."""
    xmin, ymin = np.min(cluster_points, axis=0)
    xmax, ymax = np.max(cluster_points, axis=0)
    return [float(xmin), float(xmax), float(ymin), float(ymax)]


def _find_parent_id(cluster_mask, parents):
    """Find the parent ID for a cluster based on overlap with previous layers."""
    # Handle empty or uninitialized parents list
    if not parents or len(parents) == 0:
        return None
    
    # Check if first element is empty (initial state from create_plots.py)
    if len(parents[0]) == 0:
        return None
        
    best_match = None
    best_overlap = 0
    
    for j, parent_mask in enumerate(parents):
        # Skip empty masks
        if len(parent_mask) == 0:
            continue
        overlap = np.sum(cluster_mask & parent_mask)
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = j
            
    if best_match is not None:
        layer_idx = 0
        count = 0
        for k, p in enumerate(parents):
            if k == best_match:
                return f"{layer_idx}-{count}"
            count += 1
            # Detect layer boundaries (simplified heuristic)
            
    return None


# =============================================================================
# Data Encoding Functions
# =============================================================================

def encode_data_for_html(data, compress=True):
    """
    Encode data as base64 for embedding in HTML.
    
    Parameters
    ----------
    data : bytes or str
        Data to encode.
    compress : bool, optional
        Whether to gzip compress the data.
        
    Returns
    -------
    str
        Base64-encoded string.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    
    if compress:
        data = gzip.compress(data)
    
    return base64.b64encode(data).decode("ascii")


def arrow_to_base64(df):
    """
    Convert a DataFrame to base64-encoded Arrow format.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to encode.
        
    Returns
    -------
    str
        Base64-encoded gzipped Arrow data.
    """
    import pyarrow as pa
    
    buffer = io.BytesIO()
    table = pa.Table.from_pandas(df)
    
    with pa.ipc.new_stream(buffer, table.schema) as writer:
        writer.write_table(table)
    
    return encode_data_for_html(buffer.getvalue())


def json_to_base64(data):
    """
    Convert data to base64-encoded JSON format.
    
    Parameters
    ----------
    data : any
        JSON-serializable data.
        
    Returns
    -------
    str
        Base64-encoded gzipped JSON data.
    """
    json_str = json.dumps(data)
    return encode_data_for_html(json_str)


# =============================================================================
# Utility Classes
# =============================================================================

class FormattingDict(dict):
    """A dict subclass that returns the key wrapped in braces for missing keys."""
    
    def __missing__(self, key):
        return f"{{{key}}}"


# =============================================================================
# Render HTML Helper Functions
# =============================================================================

def compute_point_scaling(point_dataframe, bounds, point_size_scale=None):
    """
    Compute point size scaling for the visualization.
    
    Parameters
    ----------
    point_dataframe : pd.DataFrame
        DataFrame containing point data with x, y coordinates.
    bounds : tuple
        Data bounds as (x_min, x_max, y_min, y_max).
    point_size_scale : float or None
        User-specified point size scale, or None for automatic.
        
    Returns
    -------
    tuple
        (magic_number, point_size, updated_point_dataframe)
    """
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
        point_dataframe = point_dataframe.copy()
        point_dataframe["size"] = magic_number * (
            point_dataframe["size"] / point_dataframe["size"].mean()
        )
        point_size = -1

    return magic_number, point_size, point_dataframe


def compute_label_scaling(label_dataframe, min_fontsize, max_fontsize):
    """
    Compute label text size scaling.
    
    Parameters
    ----------
    label_dataframe : pd.DataFrame
        DataFrame containing label data with size column.
    min_fontsize : float
        Minimum font size.
    max_fontsize : float
        Maximum font size.
        
    Returns
    -------
    pd.DataFrame
        Updated label dataframe with scaled sizes.
    """
    label_dataframe = label_dataframe.copy()
    size_range = label_dataframe["size"].max() - label_dataframe["size"].min()
    if size_range > 0:
        label_dataframe["size"] = (
            label_dataframe["size"] - label_dataframe["size"].min()
        ) * ((max_fontsize - min_fontsize) / size_range) + min_fontsize
    else:
        label_dataframe["size"] = (max_fontsize + min_fontsize) / 2.0
    return label_dataframe


def get_style_config(darkmode, text_outline_color="#eeeeeedd"):
    """
    Get style configuration based on darkmode setting.
    
    Parameters
    ----------
    darkmode : bool
        Whether darkmode is enabled.
    text_outline_color : str
        Text outline color (will be adjusted for darkmode).
        
    Returns
    -------
    dict
        Style configuration dictionary.
    """
    if darkmode and text_outline_color == "#eeeeeedd":
        text_outline_color = "#111111dd"
    
    return {
        "point_outline_color": [250, 250, 250, 128] if not darkmode else [5, 5, 5, 128],
        "text_background_color": [255, 255, 255, 64] if not darkmode else [0, 0, 0, 64],
        "title_font_color": "#000000" if not darkmode else "#ffffff",
        "sub_title_font_color": "#777777",
        "title_background": "#ffffffaa" if not darkmode else "#000000aa",
        "shadow_color": "#aaaaaa44" if not darkmode else "#00000044",
        "input_background": "#ffffffdd" if not darkmode else "#000000dd",
        "input_border": "#ddddddff" if not darkmode else "#222222ff",
        "page_background_color": "#ffffff" if not darkmode else "#000000",
        "text_outline_color": text_outline_color,
    }


def get_label_text_color(color_label_text, darkmode):
    """
    Get label text color configuration.
    
    Parameters
    ----------
    color_label_text : bool
        Whether to color label text based on cluster color.
    darkmode : bool
        Whether darkmode is enabled.
        
    Returns
    -------
    str or list
        Label text color (JS expression or RGBA list).
    """
    if color_label_text:
        return "d => [d.r, d.g, d.b]"
    else:
        return [0, 0, 0, 255] if not darkmode else [255, 255, 255, 255]


def prepare_hover_data(
    point_dataframe,
    extra_point_data,
    hover_text_html_template,
    on_click,
    topic_tree_kwds,
):
    """
    Prepare hover data and tooltip/click handlers.
    
    Parameters
    ----------
    point_dataframe : pd.DataFrame
        Point data with optional hover_text column.
    extra_point_data : pd.DataFrame or None
        Additional point metadata.
    hover_text_html_template : str or None
        HTML template for hover tooltip.
    on_click : str or None
        JavaScript click handler.
    topic_tree_kwds : dict
        Topic tree keywords.
        
    Returns
    -------
    dict
        Dictionary with hover_data, get_tooltip, on_click, and topic_tree_kwds.
    """
    topic_tree_kwds = topic_tree_kwds.copy()
    
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
    
    return {
        "hover_data": hover_data,
        "get_tooltip": get_tooltip,
        "on_click": on_click,
        "topic_tree_kwds": topic_tree_kwds,
    }


def prepare_edge_bundle_data(point_dataframe, edge_bundle_keywords):
    """
    Prepare edge bundle data for visualization.
    
    Parameters
    ----------
    point_dataframe : pd.DataFrame
        Point data with x, y, r, g, b columns.
    edge_bundle_keywords : dict
        Keywords for edge bundling algorithm.
        
    Returns
    -------
    pd.DataFrame
        Edge data with x1, y1, x2, y2, r, g, b columns.
    """
    from datamapplot.edge_bundling import bundle_edges
    
    data_map_coords = point_dataframe[["x", "y"]].values
    color_list = point_dataframe[["r", "g", "b"]].values
    lines, colors = bundle_edges(
        data_map_coords, color_list, rgb_colors=True, **edge_bundle_keywords
    )
    return pd.DataFrame({
        'x1': lines[:, 0],
        'y1': lines[:, 1],
        'x2': lines[:, 2],
        'y2': lines[:, 3],
        'r': colors[:, 0].astype(np.uint8),
        'g': colors[:, 1].astype(np.uint8),
        'b': colors[:, 2].astype(np.uint8)
    })


def prepare_histogram_data(
    histogram_data,
    histogram_n_bins,
    histogram_group_datetime_by,
    histogram_range,
):
    """
    Prepare histogram bin and index data.
    
    Parameters
    ----------
    histogram_data : pd.Series
        Data to histogram.
    histogram_n_bins : int
        Number of bins.
    histogram_group_datetime_by : str or None
        Datetime grouping unit.
    histogram_range : tuple or None
        Histogram range.
        
    Returns
    -------
    tuple
        (bin_data, index_data) DataFrames.
    """
    from datamapplot.histograms import (
        generate_bins_from_categorical_data,
        generate_bins_from_numeric_data,
        generate_bins_from_temporal_data,
    )
    
    if isinstance(histogram_data.dtype, pd.CategoricalDtype):
        return generate_bins_from_categorical_data(
            histogram_data, histogram_n_bins, histogram_range
        )
    elif is_string_dtype(histogram_data.dtype):
        return generate_bins_from_categorical_data(
            histogram_data, histogram_n_bins, histogram_range
        )
    elif is_datetime64_any_dtype(histogram_data.dtype):
        if histogram_group_datetime_by is not None:
            return generate_bins_from_temporal_data(
                histogram_data, histogram_group_datetime_by, histogram_range
            )
        else:
            return generate_bins_from_numeric_data(
                histogram_data, histogram_n_bins, histogram_range
            )
    else:
        return generate_bins_from_numeric_data(
            histogram_data, histogram_n_bins, histogram_range
        )


def prepare_colormap_data(
    point_dataframe,
    colormap_rawdata,
    colormap_metadata,
    colormaps,
    cluster_layer_colormaps,
    label_layers,
    cluster_colormap,
    noise_color,
):
    """
    Prepare colormap data for the visualization.
    
    Parameters
    ----------
    point_dataframe : pd.DataFrame
        Point data with r, g, b columns.
    colormap_rawdata : list or None
        Raw colormap data arrays.
    colormap_metadata : list or None
        Colormap metadata dictionaries.
    colormaps : dict or None
        Simple colormaps dictionary.
    cluster_layer_colormaps : bool
        Whether to use per-layer cluster colormaps.
    label_layers : list or None
        Label layer data.
    cluster_colormap : list or None
        Cluster colormap colors.
    noise_color : str
        Color for noise/unlabelled points.
        
    Returns
    -------
    tuple
        (color_metadata, color_data, enable_colormap_selector)
    """
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
        if len(cielab_colors) > 0:
            quantizer = KMeans(n_clusters=n_swatches, random_state=0, n_init=1).fit(
                cielab_colors
            )
            cluster_colors = [
                rgb2hex(c)
                for c in np.clip(
                    cspace_convert(quantizer.cluster_centers_, "CAM02-UCS", "sRGB1"), 0, 1
                )
            ]
        else:
            cluster_colors = [noise_color] * n_swatches
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
        return color_metadata, color_data, True
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
        return color_metadata, color_data, True
    else:
        return None, None, False


def encode_inline_data(
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
):
    """
    Encode data for inline HTML embedding.
    
    Parameters
    ----------
    point_data : pd.DataFrame
        Point data to encode.
    hover_data : pd.DataFrame
        Hover/metadata to encode.
    label_dataframe : pd.DataFrame
        Label data to encode.
    enable_histogram : bool
        Whether histogram is enabled.
    bin_data : pd.DataFrame or None
        Histogram bin data.
    index_data : pd.Series or None
        Histogram index data.
    enable_colormap_selector : bool
        Whether colormap selector is enabled.
    color_data : pd.DataFrame or None
        Color data.
    edge_bundle : bool
        Whether edge bundling is enabled.
    edge_data : pd.DataFrame or None
        Edge data.
        
    Returns
    -------
    dict
        Dictionary of base64-encoded data strings.
    """
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

    if edge_bundle:
        buffer = io.BytesIO()
        edge_data.to_feather(buffer, compression="uncompressed")
        buffer.seek(0)
        arrow_bytes = buffer.read()
        gzipped_bytes = gzip.compress(arrow_bytes)
        base64_edge_data = base64.b64encode(gzipped_bytes).decode()
    else:
        base64_edge_data = None

    return {
        "base64_point_data": base64_point_data,
        "base64_hover_data": base64_hover_data,
        "base64_label_data": base64_label_data,
        "base64_histogram_bin_data": base64_histogram_bin_data,
        "base64_histogram_index_data": base64_histogram_index_data,
        "base64_color_data": base64_color_data,
        "base64_edge_data": base64_edge_data,
        "file_prefix": None,
        "html_file_prefix": None,
        "n_chunks": 0,
    }


def write_offline_data(
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
):
    """
    Write data to offline files.
    
    Parameters
    ----------
    point_data : pd.DataFrame
        Point data to write.
    hover_data : pd.DataFrame
        Hover/metadata to write.
    label_dataframe : pd.DataFrame
        Label data to write.
    enable_histogram : bool
        Whether histogram is enabled.
    bin_data : pd.DataFrame or None
        Histogram bin data.
    index_data : pd.Series or None
        Histogram index data.
    enable_colormap_selector : bool
        Whether colormap selector is enabled.
    color_data : pd.DataFrame or None
        Color data.
    edge_bundle : bool
        Whether edge bundling is enabled.
    edge_data : pd.DataFrame or None
        Edge data.
    offline_data_path : str or Path or None
        Path for offline data files.
    offline_data_prefix : str or None
        Prefix for offline data files (deprecated).
    offline_data_chunk_size : int
        Chunk size for splitting data.
        
    Returns
    -------
    dict
        Dictionary with file_prefix, html_file_prefix, n_chunks, and empty base64 strings.
    """
    # Handle offline_data_path with backward compatibility
    if offline_data_path is not None:
        # Convert to Path object for easier handling
        data_path = Path(offline_data_path)

        # Create directory if it doesn't exist
        if data_path.suffix:  # If user provided a file with extension, use parent dir
            data_dir = data_path.parent
            base_name = data_path.stem
            file_prefix = str(data_path.with_suffix(""))
        else:  # User provided directory/basename
            data_dir = data_path.parent if data_path.parent != Path(".") else Path(".")
            base_name = data_path.name
            file_prefix = str(data_path)

        # Ensure directory exists
        data_dir.mkdir(parents=True, exist_ok=True)

        # For HTML references, we need just the basename
        html_file_prefix = base_name
    else:
        # Backward compatibility: use offline_data_prefix
        file_prefix = offline_data_prefix if offline_data_prefix is not None else "datamapplot"
        html_file_prefix = file_prefix

    n_chunks = (point_data.shape[0] // offline_data_chunk_size) + 1
    
    for i in range(n_chunks):
        chunk_start = i * offline_data_chunk_size
        chunk_end = min((i + 1) * offline_data_chunk_size, point_data.shape[0])
        with gzip.open(f"{file_prefix}_point_data_{i}.zip", "wb") as f:
            point_data[chunk_start:chunk_end].to_feather(f, compression="uncompressed")
        with gzip.open(f"{file_prefix}_meta_data_{i}.zip", "wb") as f:
            f.write(
                json.dumps(
                    hover_data[chunk_start:chunk_end].to_dict(orient="list")
                ).encode()
            )
        if enable_colormap_selector:
            with gzip.open(f"{file_prefix}_color_data_{i}.zip", "wb") as f:
                color_data[chunk_start:chunk_end].to_feather(f, compression="uncompressed")
    
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

    if edge_bundle:
        edge_data_json = edge_data.to_json(path_or_buf=None, orient="records")
        with gzip.open(f"{file_prefix}_edge_data.zip", "wb") as f:
            f.write(bytes(edge_data_json, "utf-8"))

    return {
        "base64_point_data": "",
        "base64_hover_data": "",
        "base64_label_data": "",
        "base64_histogram_bin_data": "",
        "base64_histogram_index_data": "",
        "base64_color_data": "",
        "base64_edge_data": "",
        "file_prefix": file_prefix,
        "html_file_prefix": html_file_prefix,
        "n_chunks": n_chunks,
    }


def prepare_selection_handler(selection_handler, custom_html, custom_js, custom_css):
    """
    Process selection handler and merge its HTML/JS/CSS with custom content.
    
    Parameters
    ----------
    selection_handler : SelectionHandlerBase or Iterable or None
        Selection handler(s) to process.
    custom_html : str or None
        Existing custom HTML.
    custom_js : str or None
        Existing custom JavaScript.
    custom_css : str or None
        Existing custom CSS.
        
    Returns
    -------
    tuple
        (custom_html, custom_js, custom_css) with handler content merged.
    """
    if selection_handler is None:
        return custom_html, custom_js, custom_css
    
    if isinstance(selection_handler, Iterable) and not isinstance(selection_handler, SelectionHandlerBase):
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
    
    return custom_html, custom_js, custom_css


def prepare_dynamic_tooltip(dynamic_tooltip):
    """
    Prepare dynamic tooltip configuration.
    
    Parameters
    ----------
    dynamic_tooltip : dict or None
        Dynamic tooltip configuration.
        
    Returns
    -------
    dict
        Tooltip configuration dictionary.
    """
    if dynamic_tooltip is not None:
        return {
            "enable_dynamic_tooltip": True,
            "tooltip_identifier_js": dynamic_tooltip.get("identifier_js", None),
            "tooltip_fetch_js": dynamic_tooltip["fetch_js"],
            "tooltip_format_js": dynamic_tooltip["format_js"],
            "tooltip_loading_js": dynamic_tooltip["loading_js"],
            "tooltip_error_js": dynamic_tooltip["error_js"],
        }
    else:
        return {
            "enable_dynamic_tooltip": False,
            "tooltip_identifier_js": None,
            "tooltip_fetch_js": None,
            "tooltip_format_js": None,
            "tooltip_loading_js": None,
            "tooltip_error_js": None,
        }


def url_to_base64_img(url):
    """
    Convert an image URL to a base64-encoded data URI.
    
    Parameters
    ----------
    url : str
        URL of the image to convert.
        
    Returns
    -------
    str or None
        Base64 data URI string, or None if conversion fails.
    """
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


# =============================================================================
# Offline Mode and Font Handling
# =============================================================================

def prepare_offline_mode_data(
    offline_mode,
    offline_mode_js_data_file,
    offline_mode_font_data_file,
):
    """
    Prepare offline mode data by loading cached JS and font files.
    
    Parameters
    ----------
    offline_mode : bool
        Whether offline mode is enabled.
    offline_mode_js_data_file : str or Path or None
        Path to the cached JS data file.
    offline_mode_font_data_file : str or Path or None
        Path to the cached font data file.
        
    Returns
    -------
    dict
        Dictionary with 'offline_mode_data' and 'offline_mode_font_data_file' keys.
    """
    import platformdirs
    from datamapplot import offline_mode_caching
    
    if not offline_mode:
        return {
            "offline_mode_data": None,
            "offline_mode_font_data_file": None,
        }
    
    if offline_mode_js_data_file is None:
        data_directory = platformdirs.user_data_dir("datamapplot")
        offline_mode_js_data_file = (
            Path(data_directory) / "datamapplot_js_encoded.json"
        )
        if not offline_mode_js_data_file.is_file():
            offline_mode_caching.cache_js_files()
        with offline_mode_js_data_file.open("r") as f:
            offline_mode_data = json.load(f)
    else:
        with open(offline_mode_js_data_file, "r") as f:
            offline_mode_data = json.load(f)

    if offline_mode_font_data_file is None:
        data_directory = platformdirs.user_data_dir("datamapplot")
        offline_mode_font_data_file = (
            Path(data_directory) / "datamapplot_fonts_encoded.json"
        )
        if not offline_mode_font_data_file.is_file():
            offline_mode_caching.cache_fonts()
    
    return {
        "offline_mode_data": offline_mode_data,
        "offline_mode_font_data_file": offline_mode_font_data_file,
    }


def prepare_fonts(
    font_family,
    tooltip_font_family,
    offline_mode,
    offline_mode_font_data_file,
):
    """
    Prepare font data for embedding in HTML.
    
    Parameters
    ----------
    font_family : str
        The main font family name.
    tooltip_font_family : str or None
        The tooltip font family name.
    offline_mode : bool
        Whether offline mode is enabled.
    offline_mode_font_data_file : str or Path or None
        Path to the cached font data file.
        
    Returns
    -------
    dict
        Dictionary with 'api_fontname', 'font_data', and 'api_tooltip_fontname' keys.
    """
    import requests
    
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
    
    return {
        "api_fontname": api_fontname,
        "font_data": font_data,
        "api_tooltip_fontname": api_tooltip_fontname,
    }


def prepare_logo(logo, offline_mode):
    """
    Prepare logo for embedding in HTML.
    
    Parameters
    ----------
    logo : str or None
        URL of the logo image.
    offline_mode : bool
        Whether offline mode is enabled.
        
    Returns
    -------
    str or None
        Processed logo URL or base64 data URI.
        
    Raises
    ------
    ValueError
        If logo URL has no scheme.
    """
    if logo is None:
        return None
    
    scheme = urlparse(logo).scheme
    if not scheme:
        raise ValueError(
            f"No scheme supplied for logo URL. Perhaps you meant https://{logo}?"
        )
    elif offline_mode or scheme == "file":
        # Store the image inline as a base64 URI.
        return url_to_base64_img(logo)
    
    return logo

