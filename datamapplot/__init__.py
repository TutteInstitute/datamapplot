from datamapplot.create_plots import create_plot, create_interactive_plot
from datamapplot.plot_rendering import render_plot
from datamapplot.interactive_rendering import render_html
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("datamapplot")
except PackageNotFoundError:
    __version__ = "0.3-dev"

__all__ = ["create_plot", "create_interactive_plot", "render_plot", "render_html"]
