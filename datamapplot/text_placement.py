import numpy as np
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import MinMaxScaler
from pylabeladjust import adjust_texts

from datamapplot.overlap_computations import (
    get_2d_coordinates,
    overlap_intervals,
    text_line_overlaps,
    intersect,
)

from matplotlib import pyplot as plt


def row_norm(an_array):
    result = np.empty(an_array.shape[0], dtype=np.float64)
    for i in range(an_array.shape[0]):
        result[i] = np.sqrt(np.sum(an_array[i] ** 2))
    return result


def fix_crossings(text_locations, label_locations, n_iter=3):
    # Find crossing lines and swap labels; repeat as required
    for n in range(n_iter):
        for i in range(text_locations.shape[0]):
            for j in range(text_locations.shape[0]):
                if intersect(
                    text_locations[i],
                    label_locations[i],
                    text_locations[j],
                    label_locations[j],
                ):
                    swap = text_locations[i].copy()
                    text_locations[i] = text_locations[j]
                    text_locations[j] = swap


def initial_text_location_placement(
    label_locations, base_radius=None, theta_stretch=None
):
    # Heuristic to choose how many rings of text labels to use
    n_label_rings = (label_locations.shape[0] // 32) + 1

    # Find a center for label locations, ring radii, and how much to stretch theta; all heuristics
    mean_label_location = np.sum(label_locations, axis=0) / label_locations.shape[0]
    recentered_label_locations = label_locations - mean_label_location
    if base_radius is None:
        base_radius = np.max(row_norm(recentered_label_locations)) + 0.25 * np.mean(
            row_norm(recentered_label_locations)
        )
    if theta_stretch is None:
        theta_stretch = np.clip(((label_locations.shape[0] - 30) / 10), 1.0, 1.66)
    recentered_label_locations = (
        recentered_label_locations / row_norm(recentered_label_locations)[:, None]
    )

    # Spread thetas out such that we have smaller angles near the east-west points, larger at north sound
    # (since text is horizontal)
    label_thetas = np.arctan2(
        recentered_label_locations.T[0], recentered_label_locations.T[1]
    )
    xs = (
        np.linspace(0, 1, len(label_thetas) // 4 + (n_label_rings + 2)) ** theta_stretch
    )
    positive_thetas = np.hstack([xs * np.pi / 2, (np.pi - xs[::-1] * np.pi / 2)[1:]])
    uniform_thetas = np.hstack([positive_thetas, -positive_thetas[1:-1]])

    # Choose which ring to be in and set radii
    ring_choice = np.concatenate(
        [np.arange(n_label_rings), np.arange(n_label_rings - 2, 0, -1)]
    )
    ring_choice = np.tile(
        ring_choice, (uniform_thetas.shape[0] // ring_choice.shape[0]) + 1
    )
    base_radii = np.asarray(
        [
            base_radius * (1.33 ** (ring_choice[i]))
            for i in range(uniform_thetas.shape[0])
        ]
    )

    # Find an optimal rotation to match the existing label locations
    optimal_rotation = 0.0
    min_score = np.inf
    for rotation in np.linspace(
        -np.pi / int(len(label_thetas) + 5), np.pi / int(len(label_thetas) + 5), 32
    ):
        test_label_locations = np.vstack(
            [
                base_radii * np.cos(uniform_thetas + rotation),
                base_radii * np.sin(uniform_thetas + rotation),
            ]
        ).T
        score = np.sum(
            pairwise_distances(
                recentered_label_locations, test_label_locations, metric="cosine"
            ).min(axis=1)
        )
        if score < min_score:
            min_score = score
            optimal_rotation = rotation

    uniform_thetas += optimal_rotation
    uniform_label_locations = np.vstack(
        [base_radii * np.cos(uniform_thetas), base_radii * np.sin(uniform_thetas)]
    ).T

    # Sort labels by radius of the label location and pick the closest position in order;
    # This works surprisingly well
    order = np.argsort(-row_norm(label_locations - mean_label_location))
    taken = set([])
    adjustment_dict_alt = {}
    for i in order:
        candidates = list(set(range(uniform_label_locations.shape[0])) - taken)
        candidate_distances = pairwise_distances(
            [recentered_label_locations[i]],
            uniform_label_locations[candidates],
            metric="cosine",
        )
        selection = candidates[np.argmin(candidate_distances[0])]
        adjustment_dict_alt[i] = selection
        taken.add(selection)

    result = (
        np.asarray(
            [
                uniform_label_locations[adjustment_dict_alt[i]]
                for i in sorted(adjustment_dict_alt.keys())
            ]
        )
        + mean_label_location
    )

    return result


def estimate_font_size(
    text_locations,
    label_text,
    initial_font_size,
    fontfamily="Roboto",
    fontweight=400,
    linespacing=0.95,
    expand=(1.5, 1.5),
    overlap_percentage_allowed=0.5,
    min_font_size=3.0,
    max_font_size=16.0,
    ax=None,
):
    if ax is None:
        ax = plt.gca()

    font_size = initial_font_size
    overlap_percentage = 1.0
    while overlap_percentage > overlap_percentage_allowed and font_size > min_font_size:
        texts = [
            ax.text(
                *text_locations[i],
                label_text[i],
                ha="center",
                ma="center",
                va="center",
                linespacing=linespacing,
                alpha=0.0,
                fontfamily=fontfamily,
                fontweight=fontweight,
                fontsize=font_size,
            )
            for i in range(text_locations.shape[0])
        ]
        coords = get_2d_coordinates(texts, expand=expand)
        xoverlaps = overlap_intervals(
            coords[:, 0], coords[:, 1], coords[:, 0], coords[:, 1]
        )
        xoverlaps = xoverlaps[xoverlaps[:, 0] != xoverlaps[:, 1]]
        yoverlaps = overlap_intervals(
            coords[:, 2], coords[:, 3], coords[:, 2], coords[:, 3]
        )
        yoverlaps = yoverlaps[yoverlaps[:, 0] != yoverlaps[:, 1]]
        overlaps = yoverlaps[(yoverlaps[:, None] == xoverlaps).all(-1).any(-1)]
        overlap_percentage = len(overlaps) / (2 * text_locations.shape[0])
        # remove texts
        for t in texts:
            t.remove()

        font_size = 0.9 * font_size

    return font_size


def estimate_dynamic_font_size(
    text_locations,
    label_text,
    fontfamily="DejaVu Sans",
    linespacing=0.95,
    expand=(1.5, 1.5),
    overlap_percentage_allowed=0.5,
    dynamic_size_array=None,
    min_font_size=4.0,
    max_font_size=24.0,
    min_font_weight=200,
    max_font_weight=500,
    ax=None,
):
    if ax is None:
        ax = plt.gca()

    overlap_percentage = 1.0
    current_max_font_size = max_font_size
    weight_scaler = MinMaxScaler(feature_range=(min_font_weight, max_font_weight))
    font_weights = np.squeeze(
        weight_scaler.fit_transform(dynamic_size_array.reshape(-1, 1))
    )
    while (
        overlap_percentage > overlap_percentage_allowed
        and current_max_font_size > min_font_size
    ):
        size_scaler = MinMaxScaler(feature_range=(min_font_size, current_max_font_size))
        font_sizes = np.squeeze(
            size_scaler.fit_transform(dynamic_size_array.reshape(-1, 1))
        )
        texts = [
            ax.text(
                *text_locations[i],
                label_text[i],
                ha="center",
                ma="center",
                va="center",
                linespacing=linespacing,
                alpha=0.0,
                fontfamily=fontfamily,
                fontsize=font_sizes[i],
                fontweight=font_weights[i],
            )
            for i in range(text_locations.shape[0])
        ]
        coords = get_2d_coordinates(texts, expand=expand)
        xoverlaps = overlap_intervals(
            coords[:, 0], coords[:, 1], coords[:, 0], coords[:, 1]
        )
        xoverlaps = xoverlaps[xoverlaps[:, 0] != xoverlaps[:, 1]]
        yoverlaps = overlap_intervals(
            coords[:, 2], coords[:, 3], coords[:, 2], coords[:, 3]
        )
        yoverlaps = yoverlaps[yoverlaps[:, 0] != yoverlaps[:, 1]]
        overlaps = yoverlaps[(yoverlaps[:, None] == xoverlaps).all(-1).any(-1)]
        overlap_percentage = len(overlaps) / (2 * text_locations.shape[0])
        # remove texts
        for t in texts:
            t.remove()

        current_max_font_size = 0.9 * current_max_font_size

    return font_sizes, font_weights


def adjust_text_locations(
    text_locations,
    label_locations,
    label_text,
    font_size=12,
    fontfamily="DejaVu Sans",
    fontweight=400,
    linespacing=0.95,
    expand=(1.5, 1.5),
    max_iter=100,
    highlight=frozenset([]),
    highlight_label_keywords={},
    font_sizes=None,
    font_weights=None,
    ax=None,
):
    if ax is None:
        ax = plt.gca()

    # Add text to the axis and set up for optimization
    new_text_locations = text_locations.copy()
    texts = [
        ax.text(
            *new_text_locations[i],
            label_text[i],
            ha="center",
            ma="center",
            va="center",
            linespacing=linespacing,
            alpha=0.0,
            fontfamily=fontfamily,
            fontsize=(
                highlight_label_keywords.get("fontsize", font_size)
                if label_text[i] in highlight
                else font_size
            )
            if font_sizes is None
            else font_sizes[i],
            fontweight=(
                "bold"
                if label_text[i] in highlight
                else (font_weights[i] if font_weights is not None else fontweight)
            ),
        )
        for i in range(label_locations.shape[0])
    ]
    coords = get_2d_coordinates(texts, expand=expand)
    xoverlaps = overlap_intervals(
        coords[:, 0], coords[:, 1], coords[:, 0], coords[:, 1]
    )
    xoverlaps = xoverlaps[xoverlaps[:, 0] != xoverlaps[:, 1]]
    yoverlaps = overlap_intervals(
        coords[:, 2], coords[:, 3], coords[:, 2], coords[:, 3]
    )
    yoverlaps = yoverlaps[yoverlaps[:, 0] != yoverlaps[:, 1]]
    overlaps = yoverlaps[(yoverlaps[:, None] == xoverlaps).all(-1).any(-1)]
    tight_coords = get_2d_coordinates(texts, expand=(0.9, 0.9))
    bottom_lefts = ax.transData.inverted().transform(tight_coords[:, [0, 2]])
    top_rights = ax.transData.inverted().transform(tight_coords[:, [1, 3]])
    coords_in_dataspace = np.vstack(
        [bottom_lefts.T[0], top_rights.T[0], bottom_lefts.T[1], top_rights.T[1]]
    ).T
    box_line_overlaps = text_line_overlaps(
        text_locations, label_locations, coords_in_dataspace
    )
    n_iter = 0

    # While we have overlaps, tweak the label positions
    while (len(overlaps) > 0 or len(box_line_overlaps) > 0) and n_iter < max_iter:
        # Check for text boxes overlapping each other
        coords = get_2d_coordinates(texts, expand=expand)
        xoverlaps = overlap_intervals(
            coords[:, 0], coords[:, 1], coords[:, 0], coords[:, 1]
        )
        xoverlaps = xoverlaps[xoverlaps[:, 0] != xoverlaps[:, 1]]
        yoverlaps = overlap_intervals(
            coords[:, 2], coords[:, 3], coords[:, 2], coords[:, 3]
        )
        yoverlaps = yoverlaps[yoverlaps[:, 0] != yoverlaps[:, 1]]
        overlaps = yoverlaps[(yoverlaps[:, None] == xoverlaps).all(-1).any(-1)]
        recentered_locations = new_text_locations - label_locations.mean(axis=0)
        radii = np.linalg.norm(recentered_locations, axis=1)
        thetas = np.arctan2(recentered_locations.T[1], recentered_locations.T[0])
        for left, right in overlaps:
            # adjust thetas
            direction = thetas[left] - thetas[right]
            if direction > np.pi or direction < -np.pi:
                thetas[left] -= 0.005 * np.sign(direction)
                thetas[right] += 0.005 * np.sign(direction)
            else:
                thetas[left] += 0.005 * np.sign(direction)
                thetas[right] -= 0.005 * np.sign(direction)

        # Check for indicator lines crossing text boxes
        recentered_locations = np.vstack(
            [radii * np.cos(thetas), radii * np.sin(thetas)]
        ).T
        new_text_locations = recentered_locations + label_locations.mean(axis=0)
        fix_crossings(new_text_locations, label_locations)
        for i, text in enumerate(texts):
            text.set_position(new_text_locations[i])

        tight_coords = get_2d_coordinates(texts, expand=expand)
        bottom_lefts = ax.transData.inverted().transform(tight_coords[:, [0, 2]])
        top_rights = ax.transData.inverted().transform(tight_coords[:, [1, 3]])
        coords_in_dataspace = np.vstack(
            [bottom_lefts.T[0], top_rights.T[0], bottom_lefts.T[1], top_rights.T[1]]
        ).T
        box_line_overlaps = text_line_overlaps(
            new_text_locations, label_locations, coords_in_dataspace
        )
        recentered_locations = new_text_locations - label_locations.mean(axis=0)
        radii = np.linalg.norm(recentered_locations, axis=1)
        thetas = np.arctan2(recentered_locations.T[1], recentered_locations.T[0])

        for i, j in box_line_overlaps:
            direction = np.arctan2(
                np.sum(coords_in_dataspace[i, 2:]) / 2.0 - label_locations[j, 1],
                np.sum(coords_in_dataspace[i, :2]) / 2.0 - label_locations[j, 0],
            ) - np.arctan2(
                text_locations[j, 1] - label_locations[j, 1],
                text_locations[j, 0] - label_locations[j, 0],
            )
            if direction > np.pi or direction < -np.pi:
                thetas[i] -= 0.005 * np.sign(direction)
                thetas[j] += 0.0025 * np.sign(direction)
            else:
                thetas[i] += 0.005 * np.sign(direction)
                thetas[j] -= 0.0025 * np.sign(direction)

        radii *= 1.003

        recentered_locations = np.vstack(
            [radii * np.cos(thetas), radii * np.sin(thetas)]
        ).T
        new_text_locations = recentered_locations + label_locations.mean(axis=0)
        fix_crossings(new_text_locations, label_locations)
        for i, text in enumerate(texts):
            text.set_position(new_text_locations[i])

        n_iter += 1

    return new_text_locations


def pylabeladjust_text_locations(
    label_locations,
    label_text,
    font_size=12,
    font_sizes=None,
    font_weights=None,
    fontfamily="DejaVu Sans",
    linespacing=0.95,
    highlight=frozenset([]),
    highlight_label_keywords={},
    speed=None,
    max_iterations=500,
    adjust_by_size=True,
    margin_percentage=7.5,
    radius_scale=1.05,
    ax=None,
    fig=None,
):
    if ax is None:
        ax = plt.gca()

    if fig is None:
        fig = plt.gcf()

    if speed is None:
        data_radius = np.max(row_norm(label_locations))
        speed = data_radius / 125.0

    # Add text to the axis and set up for optimization
    new_text_locations = label_locations.copy()
    texts = [
        ax.text(
            *new_text_locations[i],
            label_text[i],
            ha="center",
            ma="center",
            va="center",
            linespacing=linespacing,
            alpha=0.0,
            fontfamily=fontfamily,
            fontsize=(
                highlight_label_keywords.get("fontsize", font_size)
                if label_text[i] in highlight
                else font_size
            )
            if font_sizes is None
            else font_sizes[i],
            fontweight=(
                "bold"
                if label_text[i] in highlight
                else (font_weights[i] if font_weights is not None else "normal")
            ),
        )
        for i in range(label_locations.shape[0])
    ]
    fig.canvas.draw()
    rectangles_adjusted = adjust_texts(
        texts,
        speed=speed,
        max_iterations=max_iterations,
        adjust_by_size=adjust_by_size,
        margin=margin_percentage,
        margin_type="percentage",
        radius_scale=radius_scale,
    )
    return rectangles_adjusted[["x_center", "y_center"]].values
