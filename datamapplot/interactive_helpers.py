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
import re
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
    best_match = None
    best_overlap = 0
    
    for j, parent_mask in enumerate(parents):
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
