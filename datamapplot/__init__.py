from datamapplot.create_plots import create_plot, create_interactive_plot
from datamapplot.plot_rendering import render_plot
from datamapplot.interactive_rendering import render_html
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
from datamapplot.widget_helpers import (
    WidgetConfig,
    VALID_LOCATIONS,
    load_widget_config_from_json,
    validate_widget_layout,
    merge_widget_configs,
    create_widget_from_config,
)
from datamapplot.selection_handlers import (
    SelectionHandlerBase,
    DisplaySample,
    WordCloud,
    CohereSummary,
    TagSelection,
    DataTable,
    ExportSelection,
    Statistics,
    Histogram,
)
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("datamapplot")
except PackageNotFoundError:
    __version__ = "0.3-dev"

__all__ = [
    "create_plot",
    "create_interactive_plot",
    "render_plot",
    "render_html",
    # Widget classes
    "WidgetBase",
    "TitleWidget",
    "SearchWidget",
    "TopicTreeWidget",
    "HistogramWidget",
    "ColormapSelectorWidget",
    "LegendWidget",
    "LogoWidget",
    # Widget helpers
    "WidgetConfig",
    "VALID_LOCATIONS",
    "load_widget_config_from_json",
    "validate_widget_layout",
    "merge_widget_configs",
    "create_widget_from_config",
    # Selection handlers
    "SelectionHandlerBase",
    "DisplaySample",
    "WordCloud",
    "CohereSummary",
    "TagSelection",
    "DataTable",
    "ExportSelection",
    "Statistics",
    "Histogram",
]
