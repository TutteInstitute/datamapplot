"""
Helper functions for widget configuration and management.

This module provides utilities for creating, configuring, and managing widgets
in the DataMapPlot interactive visualization system.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

from datamapplot.widgets import (
    WidgetBase,
    TitleWidget,
    SearchWidget,
    TopicTreeWidget,
    HistogramWidget,
    ColormapSelectorWidget,
    LegendWidget,
    LogoWidget,
)


# Valid widget locations
VALID_LOCATIONS = [
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
    "drawer-left",
    "drawer-right",
    "drawer-bottom",
]


@dataclass
class WidgetConfig:
    """Configuration for widget placement and behavior.

    Attributes
    ----------
    widget_id : str
        Unique identifier for the widget

    location : str
        Location where widget should be placed. One of VALID_LOCATIONS.

    order : int
        Stacking order within location (lower = first)

    visible : bool
        Whether widget is visible by default

    collapsible : bool
        Whether widget can be collapsed by user

    custom_params : dict
        Additional custom parameters for the widget
    """

    widget_id: str
    location: str = "top-left"
    order: int = 0
    visible: bool = True
    collapsible: bool = False
    custom_params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.location not in VALID_LOCATIONS:
            raise ValueError(
                f"Invalid location '{self.location}'. "
                f"Must be one of: {', '.join(VALID_LOCATIONS)}"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


def load_widget_config_from_json(path: Union[str, Path]) -> Dict[str, WidgetConfig]:
    """Load widget configuration from a JSON file.

    The JSON file should have widget IDs as keys and configuration dicts as values:

    .. code-block:: json

        {
            "title": {
                "location": "top-left",
                "order": 0,
                "visible": true
            },
            "histogram": {
                "location": "drawer-left",
                "order": 0,
                "collapsible": true
            }
        }

    Parameters
    ----------
    path : str or Path
        Path to the JSON configuration file

    Returns
    -------
    dict
        Dictionary mapping widget_id to WidgetConfig objects

    Raises
    ------
    FileNotFoundError
        If the configuration file doesn't exist
    ValueError
        If the JSON is invalid or contains invalid configurations
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Widget configuration file not found: {path}")

    with open(path, "r") as f:
        config_dict = json.load(f)

    configs = {}
    for widget_id, config in config_dict.items():
        if isinstance(config, dict):
            config["widget_id"] = widget_id
            configs[widget_id] = WidgetConfig(**config)
        else:
            raise ValueError(
                f"Invalid configuration for widget '{widget_id}': "
                f"expected dict, got {type(config)}"
            )

    return configs


def validate_widget_layout(
    layout: Dict[str, Union[WidgetConfig, Dict[str, Any]]],
) -> Dict[str, WidgetConfig]:
    """Validate and normalize a widget layout configuration.

    Parameters
    ----------
    layout : dict
        Dictionary mapping widget IDs to WidgetConfig objects or config dicts

    Returns
    -------
    dict
        Validated dictionary mapping widget_id to WidgetConfig objects

    Raises
    ------
    ValueError
        If the layout configuration is invalid
    """
    if not isinstance(layout, dict):
        raise ValueError(f"Widget layout must be a dict, got {type(layout)}")

    validated = {}
    for widget_id, config in layout.items():
        if isinstance(config, WidgetConfig):
            validated[widget_id] = config
        elif isinstance(config, dict):
            config["widget_id"] = widget_id
            validated[widget_id] = WidgetConfig(**config)
        else:
            raise ValueError(
                f"Invalid configuration for widget '{widget_id}': "
                f"expected WidgetConfig or dict, got {type(config)}"
            )

    return validated


def merge_widget_configs(
    default: Optional[Dict[str, WidgetConfig]], user: Optional[Dict[str, WidgetConfig]]
) -> Dict[str, WidgetConfig]:
    """Merge user widget configuration with default configuration.

    User configuration takes precedence over default configuration.

    Parameters
    ----------
    default : dict or None
        Default widget configuration

    user : dict or None
        User-provided widget configuration

    Returns
    -------
    dict
        Merged configuration dictionary
    """
    if default is None:
        default = {}
    if user is None:
        user = {}

    # Start with default config
    merged = dict(default)

    # Override with user config
    merged.update(user)

    return merged


def create_widget_from_config(
    widget_type: str,
    config: Optional[Union[WidgetConfig, Dict[str, Any]]] = None,
    **kwargs,
) -> WidgetBase:
    """Factory function to create a widget from configuration.

    Parameters
    ----------
    widget_type : str
        Type of widget to create. One of: "title", "search", "topic_tree",
        "histogram", "colormap_selector", "legend", "logo"

    config : WidgetConfig or dict, optional
        Configuration for the widget

    **kwargs
        Additional parameters to pass to the widget constructor

    Returns
    -------
    WidgetBase
        Instantiated widget

    Raises
    ------
    ValueError
        If widget_type is not recognized
    """
    widget_classes = {
        "title": TitleWidget,
        "search": SearchWidget,
        "topic_tree": TopicTreeWidget,
        "histogram": HistogramWidget,
        "colormap_selector": ColormapSelectorWidget,
        "legend": LegendWidget,
        "logo": LogoWidget,
    }

    if widget_type not in widget_classes:
        raise ValueError(
            f"Unknown widget type '{widget_type}'. "
            f"Must be one of: {', '.join(widget_classes.keys())}"
        )

    widget_class = widget_classes[widget_type]

    # Merge config with kwargs
    if config is not None:
        if isinstance(config, WidgetConfig):
            config_dict = config.to_dict()
        else:
            config_dict = config

        # Extract widget placement parameters
        kwargs.setdefault("location", config_dict.get("location"))
        kwargs.setdefault("order", config_dict.get("order"))
        kwargs.setdefault("visible", config_dict.get("visible"))
        kwargs.setdefault("collapsible", config_dict.get("collapsible"))

        # Merge custom params
        if "custom_params" in config_dict:
            kwargs.update(config_dict["custom_params"])

    return widget_class(**kwargs)


def widgets_from_legacy_params(**kwargs) -> List[WidgetBase]:
    """Convert legacy render_html parameters to widget instances.

    This function maintains backward compatibility by converting the old-style
    boolean flags and data parameters into the new widget system.

    Parameters
    ----------
    **kwargs
        Legacy parameters from render_html function

    Returns
    -------
    list
        List of WidgetBase instances
    """
    widgets = []

    # Title widget
    if kwargs.get("title") is not None:
        widgets.append(
            TitleWidget(
                title=kwargs["title"],
                sub_title=kwargs.get("sub_title", ""),
                title_font_family=kwargs.get("font_family", "Roboto"),
                title_font_size=kwargs.get("title_font_size", 36),
                sub_title_font_size=kwargs.get("sub_title_font_size", 18),
                title_font_weight=kwargs.get("font_weight", 600),
                title_font_color=kwargs.get("title_font_color", "#000000"),
                sub_title_font_color=kwargs.get("sub_title_font_color", "#666666"),
            )
        )

    # Search widget
    if kwargs.get("enable_search", False):
        widgets.append(
            SearchWidget(
                search_field=kwargs.get("search_field", "hover_text"),
            )
        )

    # Topic tree widget
    if kwargs.get("enable_topic_tree", False):
        topic_tree_kwds = kwargs.get("topic_tree_kwds", {})
        widgets.append(
            TopicTreeWidget(
                title=topic_tree_kwds.get("title", "Topic Tree"),
                font_size=topic_tree_kwds.get("font_size", "12pt"),
                max_width=topic_tree_kwds.get("max_width", "30vw"),
                max_height=topic_tree_kwds.get("max_height", "42vh"),
                color_bullets=topic_tree_kwds.get("color_bullets", False),
                button_on_click=topic_tree_kwds.get("button_on_click"),
                button_icon=topic_tree_kwds.get("button_icon", "&#128194;"),
            )
        )

    # Histogram widget
    if kwargs.get("histogram_data") is not None:
        histogram_settings = kwargs.get("histogram_settings", {})
        widgets.append(
            HistogramWidget(
                histogram_data=kwargs["histogram_data"],
                histogram_width=histogram_settings.get("histogram_width", 300),
                histogram_height=histogram_settings.get("histogram_height", 70),
                histogram_title=histogram_settings.get("histogram_title", ""),
                histogram_bin_count=kwargs.get("histogram_n_bins", 20),
                histogram_bin_fill_color=histogram_settings.get(
                    "histogram_bin_fill_color", "#6290C3"
                ),
                histogram_bin_selected_fill_color=histogram_settings.get(
                    "histogram_bin_selected_fill_color", "#2EBFA5"
                ),
                histogram_bin_unselected_fill_color=histogram_settings.get(
                    "histogram_bin_unselected_fill_color", "#9E9E9E"
                ),
                histogram_bin_context_fill_color=histogram_settings.get(
                    "histogram_bin_context_fill_color", "#E6E6E6"
                ),
                histogram_log_scale=histogram_settings.get(
                    "histogram_log_scale", False
                ),
            )
        )

    # Colormap selector widget (if colormaps are provided)
    if (
        kwargs.get("colormaps") is not None
        or kwargs.get("colormap_rawdata") is not None
    ):
        # Add legend widget first so it's available when colormap selector initializes
        widgets.append(LegendWidget())

        if kwargs.get("colormap_metadata") is not None:
            colormap_metadata = kwargs["colormap_metadata"]
            colormap_rawdata = kwargs.get("colormap_rawdata")
            cluster_layer_colormaps = kwargs.get("cluster_layer_colormaps", {})
            widgets.append(
                ColormapSelectorWidget(
                    colormap_metadata=colormap_metadata,
                    colormap_rawdata=colormap_rawdata,
                    cluster_layer_colormaps=cluster_layer_colormaps,
                )
            )
        else:
            widgets.append(ColormapSelectorWidget(colormaps=kwargs["colormaps"]))

    # Logo widget
    if kwargs.get("logo") is not None:
        widgets.append(
            LogoWidget(
                logo=kwargs["logo"],
                logo_width=kwargs.get("logo_width", 256),
            )
        )

    return widgets


def group_widgets_by_location(
    widgets: List[WidgetBase], widget_layout: Optional[Dict[str, WidgetConfig]] = None
) -> Dict[str, List[WidgetBase]]:
    """Group widgets by their target location.

    Parameters
    ----------
    widgets : list
        List of widget instances

    widget_layout : dict, optional
        Optional layout configuration to override widget default locations

    Returns
    -------
    dict
        Dictionary mapping location strings to lists of widgets,
        sorted by order within each location
    """
    if widget_layout is None:
        widget_layout = {}

    # Initialize location groups
    grouped = {loc: [] for loc in VALID_LOCATIONS}

    for widget in widgets:
        # Check if there's a layout override for this widget
        if widget.widget_id in widget_layout:
            config = widget_layout[widget.widget_id]
            location = config.location
            order = config.order
            widget.location = location
            widget.order = order
        else:
            location = widget.location
            order = widget.order

        grouped[location].append(widget)

    # Sort widgets within each location by order
    for location in grouped:
        grouped[location].sort(key=lambda w: w.order)

    return grouped


def get_drawer_enabled(grouped_widgets: Dict[str, List[WidgetBase]]) -> Dict[str, bool]:
    """Determine which drawers should be enabled based on widget placement.

    Parameters
    ----------
    grouped_widgets : dict
        Dictionary mapping locations to lists of widgets

    Returns
    -------
    dict
        Dictionary with keys "left", "right", and "bottom" indicating drawer enablement
    """
    return {
        "left": len(grouped_widgets.get("drawer-left", [])) > 0,
        "right": len(grouped_widgets.get("drawer-right", [])) > 0,
        "bottom": len(grouped_widgets.get("drawer-bottom", [])) > 0,
    }


def update_drawer_enabled_for_handlers(
    drawer_enabled: Dict[str, bool], selection_handlers
) -> Dict[str, bool]:
    """Update drawer enablement based on selection handler locations.

    Parameters
    ----------
    drawer_enabled : dict
        Current drawer enablement state from widgets
    selection_handlers : SelectionHandlerBase or list or None
        Selection handler(s) to check for drawer usage

    Returns
    -------
    dict
        Updated dictionary with keys "left", "right", and "bottom" indicating drawer enablement
    """
    from datamapplot.selection_handlers import SelectionHandlerBase
    from collections.abc import Iterable

    if selection_handlers is None:
        return drawer_enabled

    # Make a copy to avoid mutating the input
    result = dict(drawer_enabled)

    # Handle both single handler and list of handlers
    handlers = []
    if isinstance(selection_handlers, Iterable) and not isinstance(
        selection_handlers, SelectionHandlerBase
    ):
        handlers = list(selection_handlers)
    elif isinstance(selection_handlers, SelectionHandlerBase):
        handlers = [selection_handlers]

    # Check each handler's location
    for handler in handlers:
        if hasattr(handler, "location") and handler.location:
            if handler.location == "left-drawer":
                result["left"] = True
            elif handler.location == "right-drawer":
                result["right"] = True
            elif handler.location == "bottom-drawer":
                result["bottom"] = True

    return result


def collect_widget_dependencies(widgets: List[WidgetBase]) -> Dict[str, set]:
    """Collect all dependencies from widgets.

    Parameters
    ----------
    widgets : list
        List of widget instances

    Returns
    -------
    dict
        Dictionary with keys "js_files" and "css_files" containing sets of dependency names
    """
    dependencies = {
        "js_files": set(),
        "css_files": set(),
        "external_js": set(),
    }

    for widget in widgets:
        if widget.dependencies:
            for dep in widget.dependencies:
                # Parse dependency format: "js:name" or "css:name" or URL
                if ":" in dep and not dep.startswith(("http://", "https://")):
                    dep_type, dep_name = dep.split(":", 1)
                    if dep_type == "js":
                        dependencies["js_files"].add(dep_name)
                    elif dep_type == "css":
                        dependencies["css_files"].add(dep_name)
                elif dep.startswith(("http://", "https://")):
                    # External URL dependency
                    dependencies["external_js"].add(dep)
                elif dep.endswith(".css"):
                    # Legacy format - direct CSS file reference
                    dependencies["css_files"].add(dep.replace(".css", ""))
                else:
                    # Legacy format - assume JS
                    dependencies["js_files"].add(dep.replace(".js", ""))

    return dependencies


def legacy_widget_flags_from_widgets(widgets):

    enable_search = any(isinstance(w, SearchWidget) for w in widgets)
    enable_histogram = any(isinstance(w, HistogramWidget) for w in widgets)
    enable_topic_tree = any(isinstance(w, TopicTreeWidget) for w in widgets)

    histogram_ctx = {}
    topic_tree_kwds = {}
    search_field = "hover_text"
    for w in widgets:
        if isinstance(w, SearchWidget):
            search_field = w.search_field
        if isinstance(w, HistogramWidget):
            histogram_ctx = {
                "histogram_data": w.histogram_data,
                "histogram_settings": {
                    "histogram_width": w.histogram_width,
                    "histogram_height": w.histogram_height,
                    "histogram_title": w.histogram_title,
                    "histogram_bin_fill_color": w.histogram_bin_fill_color,
                    "histogram_bin_selected_fill_color": w.histogram_bin_selected_fill_color,
                    "histogram_bin_unselected_fill_color": w.histogram_bin_unselected_fill_color,
                    "histogram_bin_context_fill_color": w.histogram_bin_context_fill_color,
                    "histogram_log_scale": w.histogram_log_scale,
                },
            }
        if isinstance(w, TopicTreeWidget):
            topic_tree_kwds = {
                "title": w.title,
                "font_size": w.font_size,
                "max_width": w.max_width,
                "max_height": w.max_height,
                "color_bullets": w.color_bullets,
                "button_on_click": w.button_on_click,
                "button_icon": w.button_icon,
            }
            break

    return (
        enable_search,
        enable_histogram,
        enable_topic_tree,
        search_field,
        histogram_ctx,
        topic_tree_kwds,
    )


def collect_widget_data(widgets):
    """Extract data that needs to be encoded/embedded from widgets.

    Parameters
    ----------
    widgets : list
        List of widget instances

    Returns
    -------
    dict
        Dictionary with keys 'histograms', 'colormaps', 'search_fields'
        containing data from respective widget types
    """
    widget_data = {
        "histograms": [],
        "colormaps": [],
        "search_fields": [],
    }

    for widget in widgets:
        # HistogramWidget: needs external data array
        if isinstance(widget, HistogramWidget) and widget.histogram_data is not None:
            widget_data["histograms"].append(
                {
                    "widget_id": widget.widget_id,
                    "data": widget.histogram_data,
                    "settings": {
                        "width": widget.histogram_width,
                        "height": widget.histogram_height,
                        "title": widget.histogram_title,
                        "bin_count": widget.histogram_bin_count,
                        "bin_fill_color": widget.histogram_bin_fill_color,
                        "bin_selected_fill_color": widget.histogram_bin_selected_fill_color,
                        "bin_unselected_fill_color": widget.histogram_bin_unselected_fill_color,
                        "bin_context_fill_color": widget.histogram_bin_context_fill_color,
                        "log_scale": widget.histogram_log_scale,
                    },
                }
            )

        # ColormapSelectorWidget: needs colormap list
        elif isinstance(widget, ColormapSelectorWidget):
            if hasattr(widget, "colormap_metadata") and widget.colormap_metadata:
                widget_data["colormaps"].append(
                    {
                        "widget_id": widget.widget_id,
                        "available_colormaps": widget.colormap_metadata,
                    }
                )

        # SearchWidget: needs to configure search field
        elif isinstance(widget, SearchWidget):
            widget_data["search_fields"].append(
                {
                    "widget_id": widget.widget_id,
                    "search_field": widget.search_field,
                }
            )

    return widget_data


def encode_widget_data(widget_data, point_data_length):
    """Encode widget data for embedding in HTML.

    Parameters
    ----------
    widget_data : dict
        Raw widget data from collect_widget_data()
    point_data_length : int
        Number of points in the dataset (for validation)

    Returns
    -------
    dict
        Encoded widget data ready for template context
    """
    import pandas as pd
    from datamapplot.interactive_helpers import prepare_histogram_data

    encoded = {}

    # Encode histogram data - needs to be processed into bin/index format
    if widget_data["histograms"]:
        encoded["histograms"] = {}
        for hist in widget_data["histograms"]:
            # Validate data length matches point data
            if len(hist["data"]) != point_data_length:
                raise ValueError(
                    f"Histogram data for widget '{hist['widget_id']}' has "
                    f"{len(hist['data'])} elements but point data has "
                    f"{point_data_length} points"
                )

            # Convert to pandas Series if needed
            if not isinstance(hist["data"], pd.Series):
                histogram_series = pd.Series(hist["data"])
            else:
                histogram_series = hist["data"]

            # Process histogram data into bin and index data
            # Use settings from widget for n_bins, etc.
            bin_count = hist["settings"].get("bin_count", 20)
            bin_data, index_data = prepare_histogram_data(
                histogram_series,
                histogram_n_bins=bin_count,
                histogram_group_datetime_by=None,  # Could be added to widget params
                histogram_range=None,  # Could be added to widget params
            )

            # Format for D3Histogram - it expects {rawBinData, rawIndexData}
            encoded["histograms"][hist["widget_id"]] = {
                "rawBinData": bin_data.to_dict(orient="records"),
                "rawIndexData": index_data.tolist(),  # Series.tolist() returns list of bin IDs
            }
    if widget_data["colormaps"]:
        encoded["colormaps"] = {
            cm["widget_id"]: cm["available_colormaps"]
            for cm in widget_data["colormaps"]
        }

    # Search fields are simple strings
    if widget_data["search_fields"]:
        # Use the first search field found (typically only one)
        encoded["search_field"] = widget_data["search_fields"][0]["search_field"]

    return encoded
