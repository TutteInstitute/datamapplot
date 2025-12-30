"""
Helper functions for plot rendering.

This module contains refactored helper functions extracted from the main render_plot
function to improve code organization, reusability, and maintainability.
"""

import numpy as np
from tempfile import NamedTemporaryFile
from warnings import warn

from matplotlib import font_manager
from matplotlib import patheffects
from matplotlib.collections import LineCollection

from datamapplot.fonts import (
    can_reach_google_fonts,
    query_google_fonts,
    GoogleAPIUnreachable,
)


# =============================================================================
# Font Management
# =============================================================================


def download_google_font(fontname):
    """
    Download and register a Google Font for use with matplotlib.

    Parameters
    ----------
    fontname : str
        The name of the Google Font to download.
    """
    for font in query_google_fonts(fontname):
        f = NamedTemporaryFile(delete=False, suffix=".ttf")
        f.write(font.fetch())
        f.close()
        font_manager.fontManager.addfont(f.name)


def setup_fonts(
    font_family,
    title_keywords=None,
    sub_title_keywords=None,
    use_system_fonts=False,
    verbose=False,
):
    """
    Set up fonts for the plot, downloading from Google Fonts if necessary.

    Parameters
    ----------
    font_family : str
        The primary font family to use for the plot.
    title_keywords : dict or None
        Keyword arguments for the title, may contain a fontfamily key.
    sub_title_keywords : dict or None
        Keyword arguments for the subtitle, may contain a fontfamily key.
    use_system_fonts : bool
        If True, skip downloading fonts and use system fonts only.
    verbose : bool
        If True, print progress messages.
    """
    if use_system_fonts:
        if verbose:
            print("Using system fonts only (use_system_fonts=True)")
        return

    if not can_reach_google_fonts(timeout=5.0):
        warn(
            "Cannot reach Google APIs to download the font you selected. "
            "Will fallback on fonts already installed.",
            GoogleAPIUnreachable,
        )
        return

    if verbose:
        print("Getting any required fonts...")

    # Download main font and its base variant
    download_google_font(font_family)
    download_google_font(font_family.split()[0])

    # Download title font if specified
    if title_keywords is not None and "fontfamily" in title_keywords:
        download_google_font(title_keywords["fontfamily"])
        download_google_font(title_keywords["fontfamily"].split()[0])

    # Download subtitle font if specified
    if sub_title_keywords is not None and "fontfamily" in sub_title_keywords:
        download_google_font(sub_title_keywords["fontfamily"])
        download_google_font(sub_title_keywords["fontfamily"].split()[0])


# =============================================================================
# Scatterplot Rendering
# =============================================================================


def render_matplotlib_scatter(
    ax,
    data_map_coords,
    color_list,
    point_size,
    alpha,
    marker_type,
    marker_size_array=None,
    lines=None,
    line_colors=None,
    matplotlib_lineswidth=0.05,
):
    """
    Render the scatterplot using matplotlib.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes to render to.
    data_map_coords : ndarray
        The 2D coordinates for the data map.
    color_list : list
        List of colors for each point.
    point_size : float
        The base point size.
    alpha : float
        The alpha transparency value.
    marker_type : str
        The matplotlib marker type.
    marker_size_array : ndarray or None
        Variable marker sizes, if any.
    lines : ndarray or None
        Edge bundle lines to render.
    line_colors : list or None
        Colors for edge bundle lines.
    matplotlib_lineswidth : float
        Line width for edge bundles.
    """
    if marker_size_array is not None:
        point_size = marker_size_array * point_size

    if lines is not None and line_colors is not None:
        lc = LineCollection(
            lines.reshape((-1, 2, 2)),
            colors=line_colors,
            linewidths=matplotlib_lineswidth,
        )
        ax.add_collection(lc)

    ax.scatter(
        *data_map_coords.T,
        c=color_list,
        marker=marker_type,
        s=point_size,
        alpha=alpha,
        edgecolors="none",
    )


def render_datashader_scatter(
    ax, data_map_coords, color_list, point_size, lines=None, line_colors=None
):
    """
    Render the scatterplot using datashader.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes to render to.
    data_map_coords : ndarray
        The 2D coordinates for the data map.
    color_list : list
        List of colors for each point.
    point_size : int
        The pixel radius for each point.
    lines : ndarray or None
        Edge bundle lines to render.
    line_colors : list or None
        Colors for edge bundle lines.
    """
    # Import here to avoid loading datashader unnecessarily
    import pandas as pd
    import datashader as ds
    import datashader.transfer_functions as tf
    from datashader.mpl_ext import dsshow
    from functools import partial

    data = pd.DataFrame(
        {
            "x": data_map_coords.T[0],
            "y": data_map_coords.T[1],
            "label": pd.Categorical(color_list),
        }
    )

    if lines is not None and line_colors is not None:
        lines = np.array(lines)
        lines_data = pd.DataFrame(
            {
                "x": lines[:, 0],
                "x1": lines[:, 2],
                "y": lines[:, 1],
                "y1": lines[:, 3],
                "color": pd.Categorical(line_colors),
            }
        )

        lines_color_key = {x: x for x in np.unique(line_colors)}

        dsshow(
            lines_data,
            ds.glyphs.LinesAxis1(["x", "x1"], ["y", "y1"]),
            ds.count_cat("color"),
            norm="eq_hist",
            color_key=lines_color_key,
            ax=ax,
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


def render_scatterplot(
    ax,
    data_map_coords,
    color_list,
    point_size,
    alpha,
    marker_type,
    marker_size_array,
    force_matplotlib,
    edge_bundle,
    lines,
    line_colors,
    matplotlib_lineswidth,
    verbose=False,
):
    """
    Render the scatterplot, choosing between matplotlib and datashader.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes to render to.
    data_map_coords : ndarray
        The 2D coordinates for the data map.
    color_list : list
        List of colors for each point.
    point_size : float or int
        The point size.
    alpha : float
        The alpha transparency value.
    marker_type : str
        The matplotlib marker type.
    marker_size_array : ndarray or None
        Variable marker sizes, if any.
    force_matplotlib : bool
        Force use of matplotlib instead of datashader.
    edge_bundle : bool
        Whether edge bundling is enabled.
    lines : ndarray or None
        Edge bundle lines.
    line_colors : list or None
        Colors for edge bundle lines.
    matplotlib_lineswidth : float
        Line width for edge bundles.
    verbose : bool
        Print progress messages.

    Returns
    -------
    ax : matplotlib.axes.Axes
        The axes with the scatterplot rendered.
    """
    use_matplotlib = data_map_coords.shape[0] < 100_000 or force_matplotlib

    if use_matplotlib:
        render_matplotlib_scatter(
            ax=ax,
            data_map_coords=data_map_coords,
            color_list=color_list,
            point_size=point_size,
            alpha=alpha,
            marker_type=marker_type,
            marker_size_array=marker_size_array,
            lines=lines if edge_bundle else None,
            line_colors=line_colors if edge_bundle else None,
            matplotlib_lineswidth=matplotlib_lineswidth,
        )
    else:
        if marker_size_array is not None or marker_type != "o":
            warn(
                "Adjusting marker type or size cannot be done with datashader; "
                "use force_matplotlib=True"
            )
        render_datashader_scatter(
            ax=ax,
            data_map_coords=data_map_coords,
            color_list=color_list,
            point_size=point_size,
            lines=lines if edge_bundle else None,
            line_colors=line_colors if edge_bundle else None,
        )

    return ax


# =============================================================================
# Logo Rendering
# =============================================================================


def add_logo(ax, logo, logo_width, figsize):
    """
    Add a logo to the bottom right of the plot.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes to add the logo to.
    logo : ndarray
        The logo image array.
    logo_width : float
        The width of the logo as a fraction of figure width.
    figsize : tuple
        The figure size (width, height).
    """
    if logo is None:
        return

    mark_height = (
        (figsize[0] / figsize[1]) * (logo.shape[0] / logo.shape[1]) * logo_width
    )
    ax.imshow(
        logo,
        extent=(0.98 - logo_width, 0.98, 0.02, 0.02 + mark_height),
        transform=ax.transAxes,
    )


# =============================================================================
# Label Color Helpers
# =============================================================================


def get_text_color(label_text_colors, index, darkmode):
    """
    Determine the text color for a label.

    Parameters
    ----------
    label_text_colors : str, list, or None
        The label text colors configuration.
    index : int
        The index of the current label.
    darkmode : bool
        Whether darkmode is enabled.

    Returns
    -------
    str
        The color to use for the text.
    """
    if isinstance(label_text_colors, str):
        return label_text_colors
    elif label_text_colors:
        return label_text_colors[index]
    elif darkmode:
        return "white"
    else:
        return "black"


def get_arrow_color(label_arrow_colors, index, darkmode):
    """
    Determine the arrow color for a label.

    Parameters
    ----------
    label_arrow_colors : str, list, or None
        The label arrow colors configuration.
    index : int
        The index of the current label.
    darkmode : bool
        Whether darkmode is enabled.

    Returns
    -------
    str
        The color to use for the arrow.
    """
    if isinstance(label_arrow_colors, str):
        return label_arrow_colors
    elif label_arrow_colors:
        return label_arrow_colors[index]
    elif darkmode:
        return "#dddddd"
    else:
        return "#333333"


def get_outline_color(darkmode, label_font_outline_alpha):
    """
    Get the outline color for text labels.

    Parameters
    ----------
    darkmode : bool
        Whether darkmode is enabled.
    label_font_outline_alpha : float
        The alpha value for the outline.

    Returns
    -------
    str
        The outline color as a hex string with alpha.
    """
    outline_alpha = hex(int(255 * label_font_outline_alpha)).removeprefix("0x")
    if len(outline_alpha) == 1:
        outline_alpha = "0" + outline_alpha
    return f"#000000{outline_alpha}" if darkmode else f"#ffffff{outline_alpha}"


def get_bbox_keywords(
    base_bbox_keywords, index, highlight_colors, darkmode
):
    """
    Get the bounding box keywords for a highlighted label.

    Parameters
    ----------
    base_bbox_keywords : dict or None
        The base bounding box keywords from highlight_label_keywords.
    index : int
        The index of the current label.
    highlight_colors : list or None
        The highlight colors for each label.
    darkmode : bool
        Whether darkmode is enabled.

    Returns
    -------
    dict or None
        The bounding box keywords to use.
    """
    if base_bbox_keywords is None:
        return None

    bbox_keywords = dict(base_bbox_keywords.items())
    if "fc" not in base_bbox_keywords:
        if highlight_colors is not None:
            bbox_keywords["fc"] = highlight_colors[index][:7] + "33"
        else:
            bbox_keywords["fc"] = "#cccccc33" if darkmode else "#33333333"
    if "ec" not in base_bbox_keywords:
        bbox_keywords["ec"] = "none"

    return bbox_keywords


# =============================================================================
# Annotation Creation
# =============================================================================


def create_label_annotation(
    ax,
    label_text,
    label_location,
    text_location,
    *,
    font_family,
    font_size,
    font_weight,
    text_color,
    arrow_color,
    label_linespacing,
    label_over_points,
    label_font_stroke_width,
    outline_color,
    arrowprops,
    bbox_keywords,
    is_highlighted,
    highlight_label_keywords,
    font_sizes=None,
    font_weights=None,
    label_index=None,
):
    """
    Create a single label annotation on the plot.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes to add the annotation to.
    label_text : str
        The text for the label.
    label_location : ndarray
        The location of the label point.
    text_location : ndarray
        The location of the text.
    font_family : str
        The font family to use.
    font_size : float or None
        The base font size (used if font_sizes is None).
    font_weight : int
        The base font weight (used if font_weights is None).
    text_color : str
        The color for the text.
    arrow_color : str
        The color for the arrow.
    label_linespacing : float
        The line spacing for the label.
    label_over_points : bool
        Whether labels are placed over points.
    label_font_stroke_width : float
        The stroke width for the font outline.
    outline_color : str
        The outline color.
    arrowprops : dict
        Arrow properties.
    bbox_keywords : dict or None
        Bounding box keywords for highlighted labels.
    is_highlighted : bool
        Whether this label is highlighted.
    highlight_label_keywords : dict
        Keywords for highlighted labels.
    font_sizes : list or None
        Individual font sizes for each label.
    font_weights : list or None
        Individual font weights for each label.
    label_index : int or None
        The index of this label (for font_sizes/font_weights lookup).

    Returns
    -------
    matplotlib.text.Annotation
        The created annotation.
    """
    # Determine font size
    if font_sizes is not None and label_index is not None:
        actual_font_size = font_sizes[label_index]
    elif is_highlighted:
        actual_font_size = highlight_label_keywords.get("fontsize", font_size)
    else:
        actual_font_size = font_size

    # Determine font weight
    if font_weights is not None and label_index is not None:
        actual_font_weight = font_weights[label_index]
    elif is_highlighted:
        actual_font_weight = highlight_label_keywords.get("fontweight", font_weight)
    else:
        actual_font_weight = font_weight

    # Build arrow props
    if label_over_points:
        actual_arrowprops = None
        path_effects_list = [
            patheffects.Stroke(
                linewidth=label_font_stroke_width,
                foreground=outline_color,
            ),
            patheffects.Normal(),
        ]
    else:
        actual_arrowprops = {
            "arrowstyle": "-",
            "linewidth": 0.5,
            "color": arrow_color,
            **arrowprops,
        }
        path_effects_list = None

    return ax.annotate(
        label_text,
        label_location,
        xytext=text_location,
        ha="center",
        ma="center",
        va="center",
        linespacing=label_linespacing,
        fontfamily=font_family,
        arrowprops=actual_arrowprops,
        fontsize=actual_font_size,
        path_effects=path_effects_list,
        bbox=bbox_keywords if is_highlighted else None,
        color=text_color,
        fontweight=actual_font_weight,
    )


def create_all_annotations(
    ax,
    label_text,
    label_locations,
    label_text_locations,
    *,
    font_family,
    font_size,
    font_weight,
    font_sizes,
    font_weights,
    label_text_colors,
    label_arrow_colors,
    label_linespacing,
    label_over_points,
    label_font_stroke_width,
    label_font_outline_alpha,
    arrowprops,
    highlight,
    highlight_label_keywords,
    highlight_colors,
    darkmode,
    verbose=False,
):
    """
    Create all label annotations for the plot.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes to add annotations to.
    label_text : list
        The text for each label.
    label_locations : ndarray
        The locations of each label point.
    label_text_locations : ndarray
        The locations for each text label.
    font_family : str
        The font family to use.
    font_size : float or None
        The base font size.
    font_weight : int
        The base font weight.
    font_sizes : list or None
        Individual font sizes for each label.
    font_weights : list or None
        Individual font weights for each label.
    label_text_colors : str, list, or None
        Colors for text labels.
    label_arrow_colors : str, list, or None
        Colors for arrows.
    label_linespacing : float
        Line spacing for labels.
    label_over_points : bool
        Whether labels are over points.
    label_font_stroke_width : float
        Stroke width for font outline.
    label_font_outline_alpha : float
        Alpha for font outline.
    arrowprops : dict
        Arrow properties.
    highlight : set
        Set of highlighted label texts.
    highlight_label_keywords : dict
        Keywords for highlighted labels.
    highlight_colors : list or None
        Colors for highlights.
    darkmode : bool
        Whether darkmode is enabled.
    verbose : bool
        Print progress messages.

    Returns
    -------
    list
        List of created annotations.
    """
    if verbose:
        print("Adding labels to the plot...")

    # Pre-compute outline color once
    outline_color = get_outline_color(darkmode, label_font_outline_alpha)

    # Get base bbox keywords if present
    if (
        "bbox" in highlight_label_keywords
        and highlight_label_keywords["bbox"] is not None
    ):
        base_bbox_keywords = highlight_label_keywords["bbox"]
    else:
        base_bbox_keywords = None

    texts = []
    for i in range(label_locations.shape[0]):
        is_highlighted = label_text[i] in highlight

        # Get bbox keywords for highlighted labels
        if is_highlighted:
            bbox_keywords = get_bbox_keywords(
                base_bbox_keywords, i, highlight_colors, darkmode
            )
        else:
            bbox_keywords = None

        text_color = get_text_color(label_text_colors, i, darkmode)
        arrow_color = get_arrow_color(label_arrow_colors, i, darkmode)

        annotation = create_label_annotation(
            ax=ax,
            label_text=label_text[i],
            label_location=label_locations[i],
            text_location=label_text_locations[i],
            font_family=font_family,
            font_size=font_size,
            font_weight=font_weight,
            text_color=text_color,
            arrow_color=arrow_color,
            label_linespacing=label_linespacing,
            label_over_points=label_over_points,
            label_font_stroke_width=label_font_stroke_width,
            outline_color=outline_color,
            arrowprops=arrowprops,
            bbox_keywords=bbox_keywords,
            is_highlighted=is_highlighted,
            highlight_label_keywords=highlight_label_keywords,
            font_sizes=font_sizes,
            font_weights=font_weights,
            label_index=i,
        )
        texts.append(annotation)

    return texts


# =============================================================================
# Plot Bounds
# =============================================================================


def compute_label_bounds(texts, ax, data_map_coords):
    """
    Compute the plot bounds that include all labels.

    Parameters
    ----------
    texts : list
        List of text annotations.
    ax : matplotlib.axes.Axes
        The axes.
    data_map_coords : ndarray
        The data map coordinates.

    Returns
    -------
    tuple
        (x_min, x_max, y_min, y_max) bounds for the plot.
    """
    from datamapplot.overlap_computations import get_2d_coordinates

    if texts:
        coords = get_2d_coordinates(texts)
        x_min, y_min = ax.transData.inverted().transform(
            (coords[:, [0, 2]].copy().min(axis=0))
        )
        x_max, y_max = ax.transData.inverted().transform(
            (coords[:, [1, 3]].copy().max(axis=0))
        )
    else:
        x_min, y_min = data_map_coords.min(axis=0)
        x_max, y_max = data_map_coords.max(axis=0)

    # Add 5% margin
    width = x_max - x_min
    height = y_max - y_min
    x_min -= 0.05 * width
    x_max += 0.05 * width
    y_min -= 0.05 * height
    y_max += 0.05 * height

    return x_min, x_max, y_min, y_max


# =============================================================================
# Plot Decoration
# =============================================================================


def apply_title_and_subtitle(
    fig,
    ax,
    title,
    sub_title,
    font_family,
    font_weight,
    font_scale_factor,
    title_keywords,
    sub_title_keywords,
    darkmode,
):
    """
    Apply the title and subtitle to the plot.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure.
    ax : matplotlib.axes.Axes
        The axes.
    title : str or None
        The title text.
    sub_title : str or None
        The subtitle text.
    font_family : str
        The font family.
    font_weight : int
        The font weight.
    font_scale_factor : float
        The font scale factor based on figure size.
    title_keywords : dict or None
        Additional title keywords.
    sub_title_keywords : dict or None
        Additional subtitle keywords.
    darkmode : bool
        Whether darkmode is enabled.
    """
    from datamapplot.overlap_computations import get_2d_coordinates

    sup_title_y_value = 1.00

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


def finalize_axes(ax, fig, x_min, x_max, y_min, y_max, darkmode):
    """
    Finalize the axes with proper limits and styling.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axes.
    fig : matplotlib.figure.Figure
        The figure.
    x_min, x_max, y_min, y_max : float
        The plot bounds.
    darkmode : bool
        Whether darkmode is enabled.
    """
    ax.set(xticks=[], yticks=[])

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
