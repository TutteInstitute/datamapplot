import numpy as np
import pandas as pd

import datashader as ds
import datashader.transfer_functions as tf
from datashader.mpl_ext import dsshow

from functools import partial

from sklearn.neighbors import KernelDensity
from skimage.transform import rescale

from matplotlib import pyplot as plt

from datamapplot.overlap_computations import get_2d_coordinates
from datamapplot.text_placement import (
    initial_text_location_placement,
    fix_crossings,
    adjust_text_locations,
    estimate_font_size,
)

from warnings import warn


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
    approx_patch_size=64,
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
        class_kde = KernelDensity(bandwidth=kernel_bandwidth, kernel=kernel, atol=1e-8, rtol=1e-4).fit(
            cluster_embedding
        )
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
    title=None,
    sub_title=None,
    figsize=(12, 12),
    label_font_size=None,
    label_colors=None,
    point_size=1,
    alpha=1.0,
    dpi=plt.rcParams["figure.dpi"],
    label_base_radius=None,
    label_margin_factor=2.0,
    highlight_labels=None,
    highlight_label_keywords={"fontweight": "bold"},
    add_glow=True,
    noise_color="#999999",
    label_size_adjustments=None,
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
):
    # Create the figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi, constrained_layout=True)
    font_scale_factor = np.sqrt(figsize[0] * figsize[1])
    if label_font_size is None:
        label_font_size = 0.8 * font_scale_factor

    # Apply matplotlib or datashader based on heuristics
    if data_map_coords.shape[0] < 100_000 or force_matplotlib:
        if marker_size_array is not None:
            point_size = marker_size_array * point_size
        ax.scatter(*data_map_coords.T, c=color_list, marker=marker_type, s=point_size, alpha=alpha, edgecolors='none')
    else:
        if marker_size_array is not None or marker_type != "o":
            warn("Adjusting marker type or size cannot be done with datashader; use force_matplotlib=True")
        datashader_scatterplot(data_map_coords, color_list, point_size=point_size, ax=ax)

    # Create background glow
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
    ax.autoscale_view()
    label_text_locations = initial_text_location_placement(
        label_locations, base_radius=label_base_radius, theta_stretch=label_direction_bias
    )
    fix_crossings(label_text_locations, label_locations)

    font_scale_factor = np.sqrt(figsize[0] * figsize[1])
    if label_font_size is None:
        label_font_size = estimate_font_size(label_text_locations, label_text, 0.8 * font_scale_factor, ax=ax)

    label_text_locations = adjust_text_locations(
        label_text_locations,
        label_locations,
        label_text,
        font_size=label_font_size,
        ax=ax,
        expand=(label_margin_factor, label_margin_factor),
        label_size_adjustments=label_size_adjustments,
    )

    # Ensure we can look up labels for highlighting
    if highlight_labels is not None:
        highlight = set(highlight_labels)
    else:
        highlight = set([])

    # Add the annotations to the plot
    if label_colors is None:
        texts = [
            ax.annotate(
                label_text[i],
                label_locations[i],
                xytext=label_text_locations[i],
                ha="center",
                ma="center",
                va="center",
                linespacing=0.95,
                arrowprops=dict(
                    arrowstyle="-",
                    linewidth=0.5,
                    color="#dddddd" if darkmode else "#333333",
                ),
                fontsize=(
                    highlight_label_keywords.get("fontsize", label_font_size)
                    if label_text[i] in highlight
                    else label_font_size
                )
                + label_size_adjustments[i]
                if label_size_adjustments is not None
                else 0.0,
                fontweight="bold" if label_text[i] in highlight else "normal",
            )
            for i in range(label_locations.shape[0])
        ]
    else:
        texts = [
            ax.annotate(
                label_text[i],
                label_locations[i],
                xytext=label_text_locations[i],
                ha="center",
                ma="center",
                va="center",
                linespacing=0.95,
                arrowprops=dict(
                    arrowstyle="-",
                    linewidth=0.5,
                    color="#dddddd" if darkmode else "#333333",
                ),
                fontsize=(
                    highlight_label_keywords.get("fontsize", label_font_size)
                    if label_text[i] in highlight
                    else label_font_size
                )
                + label_size_adjustments[i]
                if label_size_adjustments is not None
                else 0.0,
                color=label_colors[i],
                fontweight=highlight_label_keywords.get("fontweight", "normal")
                if label_text[i] in highlight
                else "normal",
            )
            for i in range(label_locations.shape[0])
        ]

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

    # decorate the plot
    ax.set(xticks=[], yticks=[])
    if sub_title is not None:
        axis_title = ax.set_title(
            sub_title,
            loc="left",
            fontdict=dict(fontweight="light", color="gray", fontsize=(1.2 * font_scale_factor)),
        )
        sup_title_y_value = (
            ax.transAxes.inverted().transform(get_2d_coordinates([axis_title])[0, [0, 3]])[
                1
            ]
            + 0.005
        )
    else:
        sup_title_y_value = 1.005

    if title is not None:
        fig.suptitle(
            title,
            x=0.0,
            y=sup_title_y_value,
            color="white" if darkmode else "black",
            ha="left",
            va="baseline",
            fontweight="bold",
            fontsize=int(1.6 * font_scale_factor),
            transform=ax.transAxes,
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
