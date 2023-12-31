import numpy as np
import pandas as pd
import textwrap

from matplotlib import pyplot as plt

from datamapplot.palette_handling import (
    palette_from_datamap,
    palette_from_cmap_and_datamap,
    deep_palette,
    pastel_palette,
)
from datamapplot.plot_rendering import render_plot
from datamapplot.medoids import medoid


def create_plot(
    data_map_coords,
    labels,
    *,
    title=None,
    sub_title=None,
    noise_label="Unlabelled",
    noise_color="#999999",
    color_label_text=True,
    label_wrap_width=16,
    label_color_map=None,
    figsize=(12, 12),
    dynamic_label_size=False,
    dpi=plt.rcParams["figure.dpi"],
    force_matplotlib=False,
    darkmode=False,
    highlight_labels=None,
    palette_hue_shift=0.0,
    palette_hue_radius_dependence=1.0,
    use_medoids=False,
    cmap=None,
    **render_plot_kwds,
):
    """Create a static plot from ``data_map_coords`` with text labels provided by ``labels``.
    This is the primary function for DataMapPlot and provides the easiest interface to the
    static plotting functionality. This function provides a number of options, but also
    passes any further keyword options through to the lower level ``render_plot`` function
    so be sure to check the documentation for ``render_plot`` to discover further keyword
    arguments that can be used here as well.

    Parameters
    ----------
    data_map_coords: ndarray of floats of shape (n_samples, 2)
        The 2D coordinates for the data map. Usually this is produced via a
        dimension reduction technique such as UMAP, t-SNE, PacMAP, PyMDE etc.

    labels: ndarray of strings (object) of shape (n_samples,)
        A string label each data point in the data map. There should ideally by
        only up to 64 unique labels. Noise or unlabelled points should have the
        same label as ``noise_label``, which is "Unlabelled" by default.

    title: str or None (optional, default=None)
        A title for the plot. If ``None`` then no title is used for the plot.
        The title should be succint; three to seven words.

    sub_title: str or None (optional, default=None)
        A sub-title for the plot. If ``None`` then no sub-title is used for the plot.
        The sub-title can be significantly longer then the title and provide more information\
        about the plot and data sources.

    noise_label: str (optional, default="Unlabelled")
        The string used in the ``labels`` array to identify the unlabelled or noise points
        in the dataset.

    noise_color: str (optional, default="#999999")
        The colour to use for unlabelled or noise points in the data map. This should usually
        be a muted or neutral colour to distinguish background points from the labelled clusters.

    color_label_text: bool (optional, default=True)
        Whether to use colours for the text labels generated in the plot. If ``False`` then
        the text labels will default to either black or white depending on ``darkmode``.

    label_wrap_width: int (optional, default=16)
        The number of characters to apply text-wrapping at when creating text labels for
        display in the plot. Note that long words will not be broken, so you can choose
        relatively small values if you want tight text-wrapping.

    label_color_map: dict or None (optional, default=None)
        A colour mapping to use to colour points/clusters in the data map. The mapping should
        be keyed by the unique cluster labels in ``labels`` and take values that are hex-string
        representations of colours. If ``None`` then a colour mapping will be auto-generated.

    figsize: (int, int) (optional, default=(12,12))
        How big to make the figure in inches (actual pixel size will depend on ``dpi``).

    dynamic_label_size: bool (optional, default=False)
        Whether to dynamically resize the text labels based on the relative sizes of the
        clusters. This can be useful to help highlight larger clusters.

    dpi: int (optional, default=plt.rcParams["figure.dpi"])
        The dots-per-inch setting usd when rendering the plot.

    force_matplotlib: bool (optional, default=False)
        Force using matplotlib instead of datashader for rendering the scatterplot of the
        data map. This can be useful if you wish to have a different marker_type, or variably
        sized markers based on a marker_size_array, neither of which are supported by the
        datashader based renderer.

    darkmode: bool (optional, default=False)
        Whether to render the plot in darkmode (with a dark background) or not.

    highlight_labels: list of str or None (optional, default=None)
        A list of unique labels that should have their text highlighted in the resulting plot.
        Arguments supported by ``render_plot`` can allow for control over how highlighted labels
        are rendered. By default they are simply rendered in bold text.

    palette_hue_shift: float (optional, default=0.0)
        A setting, in degrees clockwise, to shift the hue channel when generating a colour
        palette and color_mapping for the labels.

    palette_hue_radius_dependence: float (optional, default=1.0)
        A setting that determines how dependent on the radius the hue channel is. Larger
        values will result in more hue variation where there are more outlying points.

    use_medoids: bool (optional, default=False)
        Whether to use medoids instead of centroids to determine the "location" of the cluster,
        both for the label indicator line, and for palette colouring. Note that medoids are
        more computationally expensive, especially for large plots, so use with some caution.

    cmap: matplotlib cmap or None (optional, default=None)
        A linear matplotlib cmap colour map to use as the base for a generated colour mapping.
        This *should* be a matplotlib cmap that is smooth and linear, and cyclic
        (see the colorcet package for some good options). If not a cyclic cmap it will be
        "made" cyclic by reflecting it. If ``None`` then a custom method will be used instead.

    **render_plot_kwds
        All opther keyword arguments are passed through the ``render_plot`` which provides
        significant further control over the aesthetics of the plot.

    Returns
    -------

    fig: matplotlib.Figure
        The figure that the resulting plot is rendered to.

    ax: matpolotlib.Axes
        The axes contained within the figure that the plot is rendered to.

    """
    cluster_label_vector = np.asarray(labels)
    unique_non_noise_labels = [
        label for label in np.unique(cluster_label_vector) if label != noise_label
    ]
    if use_medoids:
        label_locations = np.asarray(
            [
                medoid(data_map_coords[cluster_label_vector == i])
                for i in unique_non_noise_labels
            ]
        )
    else:
        label_locations = np.asarray(
            [
                data_map_coords[cluster_label_vector == i].mean(axis=0)
                for i in unique_non_noise_labels
            ]
        )
    label_text = [
        textwrap.fill(x, width=label_wrap_width, break_long_words=False)
        for x in unique_non_noise_labels
    ]
    if highlight_labels is not None:
        highlight_labels = [
            textwrap.fill(x, width=label_wrap_width, break_long_words=False)
            for x in highlight_labels
        ]

    # If we don't have a color map, generate one
    if label_color_map is None:
        if cmap is None:
            palette = palette_from_datamap(
                data_map_coords,
                label_locations,
                hue_shift=palette_hue_shift,
                radius_weight_power=palette_hue_radius_dependence,
            )
        else:
            palette = palette_from_cmap_and_datamap(
                cmap,
                data_map_coords,
                label_locations,
                radius_weight_power=palette_hue_radius_dependence,
            )
        label_to_index_map = {
            name: index for index, name in enumerate(unique_non_noise_labels)
        }
        color_list = [
            palette[label_to_index_map[x]] if x in label_to_index_map else noise_color
            for x in cluster_label_vector
        ]
        label_color_map = {
            x: (
                palette[label_to_index_map[x]]
                if x in label_to_index_map
                else noise_color
            )
            for x in np.unique(cluster_label_vector)
        }
    else:
        color_list = [
            label_color_map[x] if x != noise_label else noise_color
            for x in cluster_label_vector
        ]

    # Darken and reduce chroma of label colors to get text labels
    if color_label_text:
        if darkmode:
            label_text_colors = pastel_palette(
                [label_color_map[x] for x in unique_non_noise_labels]
            )
        else:
            label_text_colors = deep_palette(
                [label_color_map[x] for x in unique_non_noise_labels]
            )
    else:
        label_text_colors = None

    if dynamic_label_size:
        font_scale_factor = np.sqrt(figsize[0] * figsize[1])
        cluster_sizes = np.sqrt(pd.Series(cluster_label_vector).value_counts())
        label_size_adjustments = cluster_sizes - cluster_sizes.min()
        label_size_adjustments /= label_size_adjustments.max()
        label_size_adjustments *= (
            render_plot_kwds.get("label_font_size", font_scale_factor) + 2
        )
        label_size_adjustments = dict(label_size_adjustments - 2)
        label_size_adjustments = [
            label_size_adjustments[x] for x in unique_non_noise_labels
        ]
    else:
        label_size_adjustments = [0.0] * len(unique_non_noise_labels)

    # Heuristics for point size and alpha values
    n_points = data_map_coords.shape[0]
    if data_map_coords.shape[0] < 100_000 or force_matplotlib:
        magic_number = np.clip(128 * 4 ** (-np.log10(n_points)), 0.05, 64)
        point_scale_factor = np.sqrt(figsize[0] * figsize[1])
        point_size = magic_number * (point_scale_factor / 2)
        alpha = np.clip(magic_number, 0.05, 1)
    else:
        point_size = int(np.sqrt(figsize[0] * figsize[1]) * dpi) // 2048
        alpha = 1.0

    if "point_size" in render_plot_kwds:
        point_size = render_plot_kwds.pop("point_size")

    if "alpha" in render_plot_kwds:
        alpha = render_plot_kwds.pop("alpha")

    fig, ax = render_plot(
        data_map_coords,
        color_list,
        label_text,
        label_locations,
        title=title,
        sub_title=sub_title,
        point_size=point_size,
        alpha=alpha,
        label_colors=None if not color_label_text else label_text_colors,
        highlight_colors=[label_color_map[x] for x in unique_non_noise_labels],
        figsize=figsize,
        noise_color=noise_color,
        label_size_adjustments=label_size_adjustments,
        dpi=dpi,
        force_matplotlib=force_matplotlib,
        darkmode=darkmode,
        highlight_labels=highlight_labels,
        **render_plot_kwds,
    )

    return fig, ax
