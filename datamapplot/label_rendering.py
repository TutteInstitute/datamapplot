"""
Label rendering and placement helpers.

This module contains functions for computing label positions, font sizes,
and creating the label annotations on the plot.
"""

import numpy as np

from datamapplot.text_placement import (
    estimate_dynamic_font_size,
    initial_text_location_placement,
    fix_crossings,
    adjust_text_locations,
    estimate_font_size,
    pylabeladjust_text_locations,
)


def compute_font_sizes(
    label_locations,
    label_text,
    label_cluster_sizes,
    *,
    font_family,
    font_weight,
    label_linespacing,
    label_font_size,
    dynamic_label_size,
    dynamic_label_size_scaling_factor,
    min_font_size,
    max_font_size,
    min_font_weight,
    max_font_weight,
    label_over_points,
    label_text_locations=None,
    label_margin_factor=1.5,
    font_scale_factor=1.0,
    ax=None,
    verbose=False,
):
    """
    Compute font sizes and weights for labels.

    This function handles the logic for determining font sizes, either using a fixed size,
    estimating an optimal size, or using dynamic sizing based on cluster sizes.

    Parameters
    ----------
    label_locations : ndarray
        The locations of each label point.
    label_text : list
        The text for each label.
    label_cluster_sizes : ndarray
        The sizes of each cluster.
    font_family : str
        The font family to use.
    font_weight : int
        The base font weight.
    label_linespacing : float
        Line spacing for labels.
    label_font_size : float or None
        Explicit font size to use, or None to estimate.
    dynamic_label_size : bool
        Whether to use dynamic sizing based on cluster sizes.
    dynamic_label_size_scaling_factor : float
        Scaling factor for dynamic sizing.
    min_font_size : float
        Minimum font size.
    max_font_size : float
        Maximum font size.
    min_font_weight : int
        Minimum font weight for dynamic sizing.
    max_font_weight : int
        Maximum font weight for dynamic sizing.
    label_over_points : bool
        Whether labels are placed over points.
    label_text_locations : ndarray or None
        The text locations (used for non-label-over-points mode).
    label_margin_factor : float
        Margin factor for label bounding boxes.
    font_scale_factor : float
        Scale factor based on figure size.
    ax : matplotlib.axes.Axes or None
        The axes.
    verbose : bool
        Print progress messages.

    Returns
    -------
    tuple
        (font_size, font_sizes, font_weights) where font_size is the single size
        or None if using per-label sizes, font_sizes is the per-label sizes or None,
        and font_weights is the per-label weights or None.
    """
    if verbose:
        print("Estimating font size...")

    if label_font_size is not None:
        return label_font_size, None, None

    if label_over_points:
        expand = (1.0, 1.0)
        overlap_percentage_allowed = 0.66
        locations_for_estimation = label_locations
    else:
        expand = (label_margin_factor, label_margin_factor)
        overlap_percentage_allowed = 0.5 if dynamic_label_size else None
        locations_for_estimation = (
            label_text_locations if label_text_locations is not None else label_locations
        )

    if dynamic_label_size:
        font_sizes, font_weights = estimate_dynamic_font_size(
            label_locations,
            label_text,
            fontfamily=font_family,
            linespacing=label_linespacing,
            expand=expand,
            overlap_percentage_allowed=overlap_percentage_allowed,
            dynamic_size_array=label_cluster_sizes ** dynamic_label_size_scaling_factor,
            min_font_size=min_font_size,
            max_font_size=max_font_size,
            min_font_weight=min_font_weight,
            max_font_weight=max_font_weight,
            ax=ax,
        )
        return None, font_sizes, font_weights
    else:
        scale = font_scale_factor if label_over_points else 0.9 * font_scale_factor
        font_size = estimate_font_size(
            locations_for_estimation,
            label_text,
            scale,
            fontfamily=font_family,
            fontweight=font_weight,
            linespacing=label_linespacing,
            expand=expand if not label_over_points else (1.0, 1.0),
            min_font_size=min_font_size,
            max_font_size=max_font_size,
            ax=ax,
        )
        return font_size, None, None


def compute_label_text_locations_over_points(
    label_locations,
    label_text,
    *,
    font_family,
    font_size,
    font_sizes,
    font_weights,
    label_linespacing,
    highlight,
    highlight_label_keywords,
    ax,
    fig,
    pylabeladjust_speed,
    pylabeladjust_max_iterations,
    pylabeladjust_adjust_by_size,
    pylabeladjust_margin_percentage,
    pylabeladjust_radius_scale,
):
    """
    Compute label text locations when placing labels over points.

    Parameters
    ----------
    label_locations : ndarray
        The locations of each label point.
    label_text : list
        The text for each label.
    font_family : str
        The font family to use.
    font_size : float or None
        The font size (if using fixed size).
    font_sizes : list or None
        Individual font sizes for each label.
    font_weights : list or None
        Individual font weights for each label.
    label_linespacing : float
        Line spacing for labels.
    highlight : set
        Set of highlighted label texts.
    highlight_label_keywords : dict
        Keywords for highlighted labels.
    ax : matplotlib.axes.Axes
        The axes.
    fig : matplotlib.figure.Figure
        The figure.
    pylabeladjust_speed : float or None
        Speed for pylabeladjust.
    pylabeladjust_max_iterations : int
        Maximum iterations for pylabeladjust.
    pylabeladjust_adjust_by_size : bool
        Whether to adjust by size.
    pylabeladjust_margin_percentage : float
        Margin percentage.
    pylabeladjust_radius_scale : float
        Radius scale factor.

    Returns
    -------
    ndarray
        The computed text locations.
    """
    return pylabeladjust_text_locations(
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


def compute_label_text_locations_around_plot(
    label_locations,
    label_text,
    *,
    label_base_radius,
    label_direction_bias,
    font_family,
    font_size,
    font_weight,
    font_sizes,
    font_weights,
    label_linespacing,
    label_margin_factor,
    highlight,
    highlight_label_keywords,
    ax,
    verbose=False,
):
    """
    Compute label text locations when placing labels around the plot.

    Parameters
    ----------
    label_locations : ndarray
        The locations of each label point.
    label_text : list
        The text for each label.
    label_base_radius : float or None
        Base radius for label placement rings.
    label_direction_bias : float or None
        Bias toward east-west placement.
    font_family : str
        The font family to use.
    font_size : float or None
        The font size (if using fixed size).
    font_weight : int
        The font weight.
    font_sizes : list or None
        Individual font sizes for each label.
    font_weights : list or None
        Individual font weights for each label.
    label_linespacing : float
        Line spacing for labels.
    label_margin_factor : float
        Margin factor for label bounding boxes.
    highlight : set
        Set of highlighted label texts.
    highlight_label_keywords : dict
        Keywords for highlighted labels.
    ax : matplotlib.axes.Axes
        The axes.
    verbose : bool
        Print progress messages.

    Returns
    -------
    ndarray
        The computed text locations.
    """
    if verbose:
        print("Creating initial label placements...")

    label_text_locations = initial_text_location_placement(
        label_locations,
        base_radius=label_base_radius,
        theta_stretch=label_direction_bias,
    )
    fix_crossings(label_text_locations, label_locations)

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

    return label_text_locations


def process_labels(
    label_locations,
    label_text,
    label_cluster_sizes,
    *,
    figsize,
    font_family,
    font_weight,
    label_linespacing,
    label_font_size,
    dynamic_label_size,
    dynamic_label_size_scaling_factor,
    min_font_size,
    max_font_size,
    min_font_weight,
    max_font_weight,
    label_over_points,
    label_base_radius,
    label_margin_factor,
    label_direction_bias,
    highlight_labels,
    highlight_label_keywords,
    pylabeladjust_speed,
    pylabeladjust_max_iterations,
    pylabeladjust_adjust_by_size,
    pylabeladjust_margin_percentage,
    pylabeladjust_radius_scale,
    ax,
    fig,
    verbose=False,
):
    """
    Process all label placement and font sizing.

    This is the main entry point for label processing, combining font size
    computation and text location placement.

    Parameters
    ----------
    label_locations : ndarray
        The locations of each label point.
    label_text : list
        The text for each label.
    label_cluster_sizes : ndarray
        The sizes of each cluster.
    figsize : tuple
        The figure size.
    font_family : str
        The font family to use.
    font_weight : int
        The base font weight.
    label_linespacing : float
        Line spacing for labels.
    label_font_size : float or None
        Explicit font size or None.
    dynamic_label_size : bool
        Whether to use dynamic sizing.
    dynamic_label_size_scaling_factor : float
        Scaling factor for dynamic sizing.
    min_font_size : float
        Minimum font size.
    max_font_size : float
        Maximum font size.
    min_font_weight : int
        Minimum font weight.
    max_font_weight : int
        Maximum font weight.
    label_over_points : bool
        Whether labels are over points.
    label_base_radius : float or None
        Base radius for label rings.
    label_margin_factor : float
        Margin factor.
    label_direction_bias : float or None
        Direction bias.
    highlight_labels : list or None
        Labels to highlight.
    highlight_label_keywords : dict
        Keywords for highlighted labels.
    pylabeladjust_speed : float or None
        pylabeladjust speed.
    pylabeladjust_max_iterations : int
        Maximum iterations.
    pylabeladjust_adjust_by_size : bool
        Adjust by size flag.
    pylabeladjust_margin_percentage : float
        Margin percentage.
    pylabeladjust_radius_scale : float
        Radius scale.
    ax : matplotlib.axes.Axes
        The axes.
    fig : matplotlib.figure.Figure
        The figure.
    verbose : bool
        Print progress messages.

    Returns
    -------
    tuple
        (label_text_locations, font_size, font_sizes, font_weights, highlight)
    """
    if verbose:
        print("Placing labels...")

    ax.autoscale_view()

    # Ensure we can look up labels for highlighting
    highlight = set(highlight_labels) if highlight_labels is not None else set()

    font_scale_factor = np.sqrt(figsize[0] * figsize[1])

    if label_over_points:
        # Compute font sizes first for label-over-points mode
        font_size, font_sizes, font_weights = compute_font_sizes(
            label_locations,
            label_text,
            label_cluster_sizes,
            font_family=font_family,
            font_weight=font_weight,
            label_linespacing=label_linespacing,
            label_font_size=label_font_size,
            dynamic_label_size=dynamic_label_size,
            dynamic_label_size_scaling_factor=dynamic_label_size_scaling_factor,
            min_font_size=min_font_size,
            max_font_size=max_font_size,
            min_font_weight=min_font_weight,
            max_font_weight=max_font_weight,
            label_over_points=True,
            font_scale_factor=font_scale_factor,
            ax=ax,
            verbose=verbose,
        )

        label_text_locations = compute_label_text_locations_over_points(
            label_locations,
            label_text,
            font_family=font_family,
            font_size=font_size,
            font_sizes=font_sizes,
            font_weights=font_weights,
            label_linespacing=label_linespacing,
            highlight=highlight,
            highlight_label_keywords=highlight_label_keywords,
            ax=ax,
            fig=fig,
            pylabeladjust_speed=pylabeladjust_speed,
            pylabeladjust_max_iterations=pylabeladjust_max_iterations,
            pylabeladjust_adjust_by_size=pylabeladjust_adjust_by_size,
            pylabeladjust_margin_percentage=pylabeladjust_margin_percentage,
            pylabeladjust_radius_scale=pylabeladjust_radius_scale,
        )
    else:
        # For around-plot mode, we need initial placement first
        if verbose:
            print("Creating initial label placements...")

        label_text_locations = initial_text_location_placement(
            label_locations,
            base_radius=label_base_radius,
            theta_stretch=label_direction_bias,
        )
        fix_crossings(label_text_locations, label_locations)

        # Then compute font sizes
        font_size, font_sizes, font_weights = compute_font_sizes(
            label_locations,
            label_text,
            label_cluster_sizes,
            font_family=font_family,
            font_weight=font_weight,
            label_linespacing=label_linespacing,
            label_font_size=label_font_size,
            dynamic_label_size=dynamic_label_size,
            dynamic_label_size_scaling_factor=dynamic_label_size_scaling_factor,
            min_font_size=min_font_size,
            max_font_size=max_font_size,
            min_font_weight=min_font_weight,
            max_font_weight=max_font_weight,
            label_over_points=False,
            label_text_locations=label_text_locations,
            label_margin_factor=label_margin_factor,
            font_scale_factor=font_scale_factor,
            ax=ax,
            verbose=verbose,
        )

        # Then adjust positions
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

    return label_text_locations, font_size, font_sizes, font_weights, highlight
