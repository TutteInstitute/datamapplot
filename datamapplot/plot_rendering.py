import numpy as np
import pandas as pd

import datashader as ds
import datashader.transfer_functions as tf
from datashader.mpl_ext import dsshow

from functools import partial

from sklearn.neighbors import KernelDensity
from skimage.transform import rescale

from matplotlib import pyplot as plt
from matplotlib import font_manager
from matplotlib import patheffects

from datamapplot.overlap_computations import get_2d_coordinates
from datamapplot.text_placement import (
    estimate_dynamic_font_size,
    initial_text_location_placement,
    fix_crossings,
    adjust_text_locations,
    estimate_font_size,
    pylabeladjust_text_locations,
)

from warnings import warn
from tempfile import NamedTemporaryFile

import requests
import re


class GoogleAPIUnreachable(Warning):
    pass


def _can_reach_google_fonts(timeout: float = 5.0) -> bool:
    try:
        response = requests.get("https://fonts.googleapis.com/css?family=Roboto", timeout=timeout)
        return response.ok
    except requests.RequestException:
        return False


def get_google_font(fontname):
    try:
        api_fontname = fontname.replace(" ", "+")
        api_response = requests.get(
            f"https://fonts.googleapis.com/css?family={api_fontname}:black,bold,regular,light"
        )
        if api_response.ok:
            font_urls = re.findall(r"(https?://[^\)]+)", str(api_response.content))
            for font_url in font_urls:
                font_data = requests.get(font_url)
                f = NamedTemporaryFile(delete=False, suffix=".ttf")
                f.write(font_data.content)
                f.close()
                font_manager.fontManager.addfont(f.name)
    except:
        warn(f"Failed in getting google-font {fontname}; using fallback ...")


def datashader_scatterplot(
    data_map_coords,
    color_list,
    point_size,
    ax,
):
    data = pd.DataFrame(
        {
            "x": data_map_coords.T[0],
            "y": data_map_coords.T[1],
            "label": pd.Categorical(color_list),
        }
    )
    color_key = {x: x for x in np.unique(color_list)}
    dsshow(
        data,
        ds.Point("x", "y"),
        ds.count_cat("label"),
        color_key=color_key,
        norm="eq_hist",
        ax=ax,
        shade_hook=partial(tf.spread, px=point_size, how="over"),
    )
    return ax


def add_glow_to_scatterplot(
    data_map_coords,
    color_list,
    ax,
    noise_color="#999999",
    kernel_bandwidth=0.25,
    approx_patch_size=32,
    kernel="gaussian",
    n_levels=8,
    max_alpha=0.5,
):
    # we are assuming colors are hex strings!
    unique_colors = np.unique(color_list)
    color_array = np.asarray(color_list)

    for color in unique_colors:
        if color == noise_color:
            continue

        cluster_embedding = data_map_coords[color_array == color]

        # find bounds for the cluster
        xmin, xmax = (
            np.min(cluster_embedding.T[0]) - 8 * kernel_bandwidth,
            np.max(cluster_embedding.T[0]) + 8 * kernel_bandwidth,
        )
        ymin, ymax = (
            np.min(cluster_embedding.T[1]) - 8 * kernel_bandwidth,
            np.max(cluster_embedding.T[1]) + 8 * kernel_bandwidth,
        )
        width = xmax - xmin
        height = ymax - ymin
        aspect_ratio = width / height

        # Make an appropriately sized image patch
        patch_size = min(
            max(max(width, height) * approx_patch_size / 6.0, approx_patch_size), 384
        )
        patch_width = int(patch_size * aspect_ratio)
        patch_height = int(patch_size)

        # Build a meshgrid over which to evaluate the KDE
        xs = np.linspace(xmin, xmax, patch_width)
        ys = np.linspace(ymin, ymax, patch_height)
        xv, yv = np.meshgrid(xs, ys[::-1])
        for_scoring = np.vstack([xv.ravel(), yv.ravel()]).T

        # Build the KDE of the cluster
        class_kde = KernelDensity(
            bandwidth=kernel_bandwidth, kernel=kernel, atol=1e-8, rtol=1e-4
        ).fit(cluster_embedding)
        zv = class_kde.score_samples(for_scoring).reshape(xv.shape)
        zv = rescale(zv, 12)
        # Construct colours of varying alpha values for different levels
        alphas = [
            f"{x:02X}"
            for x in np.linspace(0, max_alpha * 255, n_levels, endpoint=True).astype(
                np.uint8
            )
        ]
        level_colors = [color + alpha for alpha in alphas]

        # Create a countour plot for the image patch
        contour_data = np.exp(zv)
        ax.contourf(
            contour_data,
            levels=n_levels,
            colors=level_colors,
            extent=(xmin, xmax, ymin, ymax),
            extend="max",
            origin="upper",
            antialiased=True,
            zorder=0,
        )


def render_plot(
    data_map_coords,
    color_list,
    label_text,
    label_locations,
    label_cluster_sizes,
    *,
    title=None,
    sub_title=None,
    figsize=(12, 12),
    dynamic_label_size=False,
    dynamic_label_size_scaling_factor=0.75,
    font_family="Roboto",
    font_weight=400,
    label_linespacing=0.95,
    label_font_size=None,
    label_text_colors=None,
    label_arrow_colors=None,
    highlight_colors=None,
    point_size=1,
    alpha=1.0,
    dpi=plt.rcParams["figure.dpi"],
    label_over_points=False,
    label_base_radius=None,
    label_margin_factor=1.5,
    min_font_size=4.0,
    max_font_size=24.0,
    min_font_weight=200,
    max_font_weight=800,
    highlight_labels=None,
    highlight_label_keywords={"fontweight": 1000},
    add_glow=True,
    noise_color="#999999",
    glow_keywords={
        "kernel": "gaussian",
        "kernel_bandwidth": 0.25,
        "approx_patch_size": 64,
    },
    darkmode=False,
    logo=None,
    logo_width=0.15,
    force_matplotlib=False,
    label_direction_bias=None,
    marker_type="o",
    marker_size_array=None,
    arrowprops={},
    title_keywords=None,
    sub_title_keywords=None,
    pylabeladjust_speed=None,
    pylabeladjust_max_iterations=500,
    pylabeladjust_adjust_by_size=True,
    pylabeladjust_margin_percentage=7.5,
    pylabeladjust_radius_scale=1.05,
    label_font_stroke_width=3,
    label_font_outline_alpha=0.5,
    ax=None,
    verbose=False,
):
    """Render a static data map plot with given colours and label locations and text. This is
    a lower level function, and should usually not be used directly unless there are specific
    reasons for digging in. This usually involves things like getting direct control over label
    locations, altering label texts to suit specific needs, or direct control over point
    colouring in the scatterplot.

    All keyword arguments from ``create_plot`` are passed on to ``render_plot``, so any
    *keyword* arguments here are also valid keyword arguments for ``create_plot``.

    Parameters
    ----------
    data_map_coords: ndarray of floats of shape (n_samples, 2)
        The 2D coordinates for the data map. Usually this is produced via a
        dimension reduction technique such as UMAP, t-SNE, PacMAP, PyMDE etc.

    color_list: iterable of str of len n_samples
        A list of hex-string colours, one per sample, for colouring points in the
        scatterplot of the data map.

    label_text: list of str
        A list of label text strings, one per unique label.

    label_locations: ndarray of floats of shape (n_labels, 2)
        An array of the "location" (usually centroid) of the cluster of the
        associated text label (see ``label_text``).

    title: str or None (optional, default=None)
        A title for the plot. If ``None`` then no title is used for the plot.
        The title should be succint; three to seven words.

    sub_title: str or None (optional, default=None)
        A sub-title for the plot. If ``None`` then no sub-title is used for the plot.
        The sub-title can be significantly longer then the title and provide more information\
        about the plot and data sources.

    figsize: (int, int) (optional, default=(12,12))
        How big to make the figure in inches (actual pixel size will depend on ``dpi``).

    dynamic_label_size: bool (optional, default=False)
        Whether to use dynamic label sizing based on the sizes of the clusters.

    dynamic_label_size_scaling_factor: float (optional, default=0.75)
        The scaling factor to use when using dynamic label sizing based on the sizes of the clusters.

    font_family: str (optional, default="DejaVu Sans")
        The font_family to use for the plot -- the labels and the title and sub-title
        unless explicitly over-ridden by title_keywords or sub_title_keywords.

    label_linespacing: float (optional, default=0.95)
        The line-spacing to use when rendering multi-line labels in the plot. The default
        of 0.95 keeps multi-line labels compact, but can be less than ideal for some fonts.

    label_font_size: float or None (optional, default=None)
        The font-size (in pts) to use for the text labels in the plot. If this is ``None``
        then a heuristic will be used to try to find the best font size that can fit all
        the labels in.

    label_text_colors: str or list of str or None (optional, default=None)
        The colours of the text labels, one per text label. If None then the text labels
        will be either black or white depending on ``darkmode``. If just a single string
        then it is assumed to be a fixed colour for all labels.

    label_arrow_colors: str or list of str or None (optional, default=None)
        The colours of the arrows between the text labels and clusters, one per text label.
        If None then the arrows will be either black or white depending on ``darkmode``.
        If just a single string then it is assumed to be a fixed colour for all arrows.

    highlight_colors: list of str or None (optional default=None)
        The colours used if text labels are highlighted and a bounding box around the label is
        used. For example ``create_plot`` uses the cluster colours from the colour mapping that
        was passed or created.

    point_size: int or float (optional, default=1)
        How big to make points in the scatterplot rendering of the data map. Depending on
        whether you are in datashader mode or matplotlib mode this can either be an
        int (datashader) or a float (matplotlib). If in datashader mode this is explicitly
        the radius, in number of pixels, that each point should be. If in matplotlib mode
        this is the matplotlib scatterplot size, which can be relative to the plot-size
         and other factors.

    alpha: float (optional, default=1.0)
        The alpha transparency value to use when rendering points.

    dpi: int (optional, default=plt.rcParams["figure.dpi"])
        The dots-per-inch to use when rendering the plot.

    label_over_points: bool (optional, default=False)
        Whether to attempt tom place text labels directly on top of the points in clusters. This
        can result in severe over-packing, and this is remedied via pylabeladjust which can end up
        moving labels some distance. For smaller numbers of labels this is likely a good choice, for
        more than 20 labels this will require a small font. For larger numbers of labels still this
        may be sub-optimal.

    label_base_radius: float or None (optional, default=None)
        Labels are placed in rings around the data map. This value can explicitly control the
        radius (in data coordinates) of the innermost such ring.

    label_margin_factor: float (optional, default=1.5)
        The expansion factor to use when creating a bounding box around the label text
        to compute whether overlaps are occurring during the label placement adjustment phase.

    min_font_size: float (optional, default=4.0)
        The minimum font size to use when estimating the font size for the labels.

    max_font_size: float (optional, default=24.0)
        The maximum font size to use when estimating the font size for the labels.

    min_font_weight: int (optional, default=200)
        The minimum font weight to use when using dynamic label sizing (font weights will vary as well).

    max_font_weight: int (optional, default=800)
        The maximum font weight to use when using dynamic label sizing (font weights will vary as well).

    highlight_labels: list of str or None (optional, default=None)
        A list of the labels to be highlighted.

    highlight_label_keywords: dict (optional, default={"fontweight": "bold"})
        Keywords for how to highlight the labels. This dict will be passed on as keyword
        arguments to the matplotlib ``annotate`` function. See the matplotlib documentation
        for more details on what can be done.

    add_glow: bool (optional, default=True)
        Whether to add a glow-effect using KDEs.

    noise_color: str (optional, default="#999999")
        The colour to use for unlabelled or noise points in the data map. This should usually
        be a muted or neutral colour to distinguish background points from the labelled clusters.

    glow_keywords: dict (optional, default={"kernel": "gaussian","kernel_bandwidth": 0.25})
        Keyword arguments that will be passed along to the ``add_glow_to_scatterplot``
        function. See that function for more details.

    darkmode: bool (optional, default=False)
        Whether to render the plot in darkmode (with a dark background) or not.

    logo: ndarray or None (optional, default=None)
        A numpy array representation of an image (suitable for matplotlib's ``imshow``) to
        be used as a logo placed in the bottom right corner of the plot.

    logo_width: float (optional, default=0.15)
        The width, as a fraction of the total figure width, of the logo.

    force_matplotlib: bool (optional, default=False)
        Force using matplotlib instead of datashader for rendering the scatterplot of the
        data map. This can be useful if you wish to have a different marker_type, or variably
        sized markers based on a marker_size_array, neither of which are supported by the
        datashader based renderer.

    label_direction_bias: float or None (optional, default=None)
        When placing labels in rings, how much bias to place toward east-west compass points
        as opposed to north-south. A value of 1.0 provides no bias (uniform placement around
        the circle). Values larger than one will place more labels ion the east-west areas.

    marker_type: str (optional, default="o")
        The type of marker to use for rendering the scatterplot. This is only valid if
        matplotlib mode is being used. Valid marker_types are any matplotlib marker string.
        See the matplotlib marker documentation for more details.

    marker_size_array: ndarray of shape (n_samples,) or None (optional, default=None)
        The (variable) size or markers to use. This is only valid if matplotlib mode is being
        used. This should be an array of (matplotlib) marker sizes as you would use for the
        ``s`` argument in ``matplotlib.pyplot.scatterplot``.

    arrowprops: dict (optional default={})
        A dict of keyword argumetns to pass through to the ``arrowprops`` argument of
        ``matplotlib.pyplot.annotate``. This allows for control of arrow-styles,
        connection-styles, linewidths, colours etc. See the documentation of matplotlib's
        ``annotate`` function for more details.

    title_keywords: dict or None (optional, default=None)
        A dictionary of keyword arguments to pass through to matplotlib's ``suptitle`` fucntion.
        This includes things like fontfamily, fontsize, fontweight, color, etc.

    sub_title_keywords: dict or None (optional, default=None)
        A dictionary of keyword arguments to pass through to matplotlib's ``title`` fucntion.
        This includes things like fontfamily, fontsize, fontweight, color, etc.

    pylabeladjust_speed: None or float (optional, default=None)
        pylabeladjust speed for adjusting label positioning when doing labels over points. If
        ``label_over_points`` is ``False`` then this will have no effect. If ``None`` then
        a good choice of speed will be approximated from the data.

    pylabeladjust_max_iterations: int (optional, default=500)
        The maximum number of pylabeladjust iterations for adjusting label positioning when
        doing labels over points. If ``label_over_points`` is ``False`` then this will have
        no effect.

    pylabeladjust_adjust_by_size: bool (optional, default=True)
        Whether to adjust the labels based on the size of the rectangles for adjusting label
        positioning when doing labels over points. If ``label_over_points`` is ``False`` then
        this will have no effect.

    pylabeladjust_margin_percentage: float (optional, default=7.5)
        The margin percentage for the repulsion radius for adjusting label positioning when
        doing labels over points. If ``label_over_points`` is ``False`` then this will have no effect.

    pylabeladjust_radius_scale: float (optional, default=1.05)
        The scale factor for the repulsion radius for adjusting label
        positioning when doing labels over points. If ``label_over_points`` is ``False`` then
        this will have no effect.

    label_font_stroke_width: float (optional, default=3)
        The width of the stroke to use when rendering the font. This is used to create an outline
        that distinguishes the text from the background. Larger values will make text more visible 
        against the background at some loss of font legibility. You may need to change this value
        when rendering at particularly high resolutions.

    label_font_outline_alpha: float (optional, default=0.5)
        The alpha value to use when rendering the font outline. This is used to create an outline
        that distinguishes the text from the background. Larger values will make text more visible
        against the background at some loss of font legibility.

    verbose: bool (optional, default=False)
        Print progress as the plot is being created.

    ax: None or matplotlib.axes (optional, default=None)
        If not None, render the plot to this axis, otherwise create a new figure and axis.

    Returns
    -------
    fig: matplotlib.Figure
        The figure that the resulting plot is rendered to.

    ax: matpolotlib.Axes
        The axes contained within the figure that the plot is rendered to.

    """
    # Create the figure
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi, constrained_layout=True)
    else:
        fig = ax.get_figure()


    if _can_reach_google_fonts(timeout=5.0):
        if verbose:
            print("Getting any required fonts...")
        # Get any google fonts if required
        get_google_font(font_family)
        get_google_font(font_family.split()[0])
        if title_keywords is not None and "fontfamily" in title_keywords:
            get_google_font(title_keywords["fontfamily"])
            get_google_font(title_keywords["fontfamily"].split()[0])
        if sub_title_keywords is not None and "fontfamily" in sub_title_keywords:
            get_google_font(sub_title_keywords["fontfamily"])
            get_google_font(sub_title_keywords["fontfamily"].split()[0])
    else:
        warn(
            "Cannot reach out Google APIs to download the font you selected. Will fallback on fonts already installed.",
            GoogleAPIUnreachable
        )

    # Apply matplotlib or datashader based on heuristics
    if data_map_coords.shape[0] < 100_000 or force_matplotlib:
        if marker_size_array is not None:
            point_size = marker_size_array * point_size
        ax.scatter(
            *data_map_coords.T,
            c=color_list,
            marker=marker_type,
            s=point_size,
            alpha=alpha,
            edgecolors="none",
        )
    else:
        if marker_size_array is not None or marker_type != "o":
            warn(
                "Adjusting marker type or size cannot be done with datashader; use force_matplotlib=True"
            )
        datashader_scatterplot(
            data_map_coords, color_list, point_size=point_size, ax=ax
        )

    # Create background glow
    if verbose:
        print("Adding glow to scatterplot...")
    if add_glow:
        add_glow_to_scatterplot(
            data_map_coords, color_list, ax, noise_color=noise_color, **glow_keywords
        )

    # Add a mark in the bottom right if provided
    if logo is not None:
        mark_height = (
            (figsize[0] / figsize[1]) * (logo.shape[0] / logo.shape[1]) * logo_width
        )
        ax.imshow(
            logo,
            extent=(0.98 - logo_width, 0.98, 0.02, 0.02 + mark_height),
            transform=ax.transAxes,
        )

    # Find initial placements for text, fix any line crossings, then optimize placements
    if verbose:
        print("Placing labels...")
    ax.autoscale_view()
    if label_locations.shape[0] > 0:

        # Ensure we can look up labels for highlighting
        if highlight_labels is not None:
            highlight = set(highlight_labels)
        else:
            highlight = set([])

        if label_over_points:
            font_scale_factor = np.sqrt(figsize[0] * figsize[1])
            if verbose:
                print("Estimating font size...")
            if label_font_size is None:
                if dynamic_label_size:
                    font_sizes, font_weights = estimate_dynamic_font_size(
                        label_locations,
                        label_text,
                        fontfamily=font_family,
                        linespacing=label_linespacing,
                        expand=(1.0, 1.0),
                        overlap_percentage_allowed=0.66,
                        dynamic_size_array=label_cluster_sizes
                        ** dynamic_label_size_scaling_factor,
                        min_font_size=min_font_size,
                        max_font_size=max_font_size,
                        min_font_weight=min_font_weight,
                        max_font_weight=max_font_weight,
                        ax=ax,
                    )
                    font_size = None
                else:
                    font_size = estimate_font_size(
                        label_locations,
                        label_text,
                        font_scale_factor,
                        fontfamily=font_family,
                        fontweight=font_weight,
                        linespacing=label_linespacing,
                        expand=(1.0, 1.0),
                        overlap_percentage_allowed=0.66,
                        min_font_size=min_font_size,
                        max_font_size=max_font_size,
                        ax=ax,
                    )
                    font_sizes = None
                    font_weights = None
            else:
                font_size = label_font_size
                font_sizes = None
                font_weights = None

            label_text_locations = pylabeladjust_text_locations(
                label_locations,
                label_text,
                fontfamily=font_family,
                font_size=font_size,
                font_sizes=font_sizes,
                font_weights=font_weights,
                linespacing=label_linespacing,
                highlight=highlight,
                highlight_label_keywords=highlight_label_keywords,
                ax=ax,
                fig=fig,
                speed=pylabeladjust_speed,
                max_iterations=pylabeladjust_max_iterations,
                adjust_by_size=pylabeladjust_adjust_by_size,
                margin_percentage=pylabeladjust_margin_percentage,
                radius_scale=pylabeladjust_radius_scale,
            )
        else:
            if verbose:
                print("Creating initial label placements...")
            label_text_locations = initial_text_location_placement(
                label_locations,
                base_radius=label_base_radius,
                theta_stretch=label_direction_bias,
            )
            fix_crossings(label_text_locations, label_locations)

            if verbose:
                print("Estimating font size...")
            font_scale_factor = np.sqrt(figsize[0] * figsize[1])
            if label_font_size is None:
                if dynamic_label_size:
                    font_sizes, font_weights = estimate_dynamic_font_size(
                        label_locations,
                        label_text,
                        fontfamily=font_family,
                        linespacing=label_linespacing,
                        expand=(label_margin_factor, label_margin_factor),
                        overlap_percentage_allowed=0.5,
                        dynamic_size_array=label_cluster_sizes
                        ** dynamic_label_size_scaling_factor,
                        min_font_size=min_font_size,
                        max_font_size=max_font_size,
                        min_font_weight=min_font_weight,
                        max_font_weight=max_font_weight,
                        ax=ax,
                    )
                    font_size = None
                else:
                    font_size = estimate_font_size(
                        label_text_locations,
                        label_text,
                        0.9 * font_scale_factor,
                        fontfamily=font_family,
                        fontweight=font_weight,
                        linespacing=label_linespacing,
                        min_font_size=min_font_size,
                        max_font_size=max_font_size,
                        ax=ax,
                    )
                    font_sizes = None
                    font_weights = None
            else:
                font_size = label_font_size
                font_sizes = None
                font_weights = None

            if verbose:
                print("Adjusting label placements...")
            label_text_locations = adjust_text_locations(
                label_text_locations,
                label_locations,
                label_text,
                fontfamily=font_family,
                font_size=font_size,
                fontweight=font_weight,
                linespacing=label_linespacing,
                highlight=highlight,
                highlight_label_keywords=highlight_label_keywords,
                ax=ax,
                expand=(label_margin_factor, label_margin_factor),
                font_sizes=font_sizes,
                font_weights=font_weights,
            )

        # Build highlight boxes
        if (
            "bbox" in highlight_label_keywords
            and highlight_label_keywords["bbox"] is not None
        ):
            base_bbox_keywords = highlight_label_keywords["bbox"]
        else:
            base_bbox_keywords = None

        if verbose:
            print("Adding labels to the plot...")
        # Add the annotations to the plot
        texts = []
        for i in range(label_locations.shape[0]):
            if base_bbox_keywords is not None:
                bbox_keywords = dict(base_bbox_keywords.items())
                if "fc" not in base_bbox_keywords:
                    if highlight_colors is not None:
                        bbox_keywords["fc"] = highlight_colors[i][:7] + "33"
                    else:
                        bbox_keywords["fc"] = "#cccccc33" if darkmode else "#33333333"
                if "ec" not in base_bbox_keywords:
                    bbox_keywords["ec"] = "none"
            else:
                bbox_keywords = None

            if type(label_text_colors) == str:
                text_color = label_text_colors
            elif label_text_colors:
                text_color = label_text_colors[i]
            elif darkmode:
                text_color = "white"
            else:
                text_color = "black"

            outline_alpha = hex(int(255 * label_font_outline_alpha)).removeprefix('0x')
            outline_color = f"#000000{outline_alpha}" if darkmode else f"#ffffff{outline_alpha}"

            if type(label_arrow_colors) == str:
                arrow_color = label_arrow_colors
            elif label_arrow_colors:
                arrow_color = label_arrow_colors[i]
            elif darkmode:
                arrow_color = "#dddddd"
            else:
                arrow_color = "#333333"

            texts.append(
                ax.annotate(
                    label_text[i],
                    label_locations[i],
                    xytext=label_text_locations[i],
                    ha="center",
                    ma="center",
                    va="center",
                    linespacing=label_linespacing,
                    fontfamily=font_family,
                    arrowprops=(
                        {
                            "arrowstyle": "-",
                            "linewidth": 0.5,
                            "color": arrow_color,
                            **arrowprops,
                        }
                        if not label_over_points
                        else None
                    ),
                    fontsize=(
                        highlight_label_keywords.get("fontsize", font_size)
                        if label_text[i] in highlight
                        else font_size
                    )
                    if font_sizes is None
                    else font_sizes[i],
                    path_effects=(
                        [
                            patheffects.Stroke(linewidth=label_font_stroke_width, foreground=outline_color),
                            patheffects.Normal(),
                        ]
                        if label_over_points
                        else None
                    ),
                    bbox=bbox_keywords if label_text[i] in highlight else None,
                    color=text_color,
                    fontweight=(
                        highlight_label_keywords.get("fontweight", font_weight)
                        if label_text[i] in highlight
                        else (font_weights[i] if font_weights is not None else font_weight)
                    ),
                )
            )

        # Ensure we have plot bounds that meet the newly place annotations
        coords = get_2d_coordinates(texts)
        x_min, y_min = ax.transData.inverted().transform(
            (coords[:, [0, 2]].copy().min(axis=0))
        )
        x_max, y_max = ax.transData.inverted().transform(
            (coords[:, [1, 3]].copy().max(axis=0))
        )
        width = x_max - x_min
        height = y_max - y_min
        x_min -= 0.05 * width
        x_max += 0.05 * width
        y_min -= 0.05 * height
        y_max += 0.05 * height
    else:
        x_min, y_min = data_map_coords.min(axis=0)
        x_max, y_max = data_map_coords.max(axis=0)
        width = x_max - x_min
        height = y_max - y_min
        x_min -= 0.05 * width
        x_max += 0.05 * width
        y_min -= 0.05 * height
        y_max += 0.05 * height

    # decorate the plot
    if verbose:
        print("Decorating plot...")
    ax.set(xticks=[], yticks=[])
    if sub_title is not None:
        if sub_title_keywords is not None:
            keyword_args = {
                "fontweight": "light",
                "color": "gray",
                "fontsize": (1.6 * font_scale_factor),
                "fontfamily": font_family,
                "fontweight": font_weight,
                **sub_title_keywords,
            }
        else:
            keyword_args = {
                "fontweight": "light",
                "color": "gray",
                "fontsize": (1.6 * font_scale_factor),
                "fontfamily": font_family,
                "fontweight": font_weight,
            }
        axis_title = ax.set_title(
            sub_title,
            loc="left",
            va="baseline",
            fontdict=keyword_args,
        )
        sup_title_y_value = (
            ax.transAxes.inverted().transform(
                get_2d_coordinates([axis_title])[0, [0, 3]]
            )[1]
            + 1e-4
        )
    else:
        sup_title_y_value = 1.00

    if title is not None:
        if title_keywords is not None:
            keyword_args = {
                "color": "white" if darkmode else "black",
                "ha": "left",
                "va": "bottom",
                "fontweight": 900,
                "fontsize": int(3.2 * font_scale_factor),
                "fontfamily": font_family,
                **title_keywords,
            }
        else:
            keyword_args = {
                "color": "white" if darkmode else "black",
                "ha": "left",
                "va": "bottom",
                "fontweight": 900,
                "fontsize": int(3.2 * font_scale_factor),
                "fontfamily": font_family,
            }
        fig.suptitle(
            title, x=0.0, y=sup_title_y_value, transform=ax.transAxes, **keyword_args
        )

    ax_x_min, ax_x_max = ax.get_xlim()
    ax_y_min, ax_y_max = ax.get_ylim()
    ax.set_xlim(min(x_min, ax_x_min), max(x_max, ax_x_max))
    ax.set_ylim(min(y_min, ax_y_min), max(y_max, ax_y_max))
    for spine in ax.spines.values():
        spine.set_edgecolor("#555555" if darkmode else "#aaaaaa")
    ax.set_aspect("auto")

    if darkmode:
        ax.set(facecolor="black")
        fig.set(facecolor="black")

    return fig, ax
