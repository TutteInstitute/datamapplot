import numpy as np
import io
from matplotlib import pyplot as plt

try:
    from matplotlib.backend_bases import _get_renderer as matplot_get_renderer
except ImportError:
    matplot_get_renderer = None


def ccw(a, b, c):
    return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])


def intersect(a, b, c, d):
    return ccw(a, c, d) != ccw(b, c, d) and ccw(a, b, c) != ccw(a, b, d)


# From bioframe (https://github.com/open2c/bioframe)
def arange_multi(starts, stops):
    lengths = stops - starts

    if np.isscalar(starts):
        starts = np.full(len(stops), starts)
    cat_start = np.repeat(starts, lengths)
    cat_counter = np.arange(lengths.sum()) - np.repeat(
        lengths.cumsum() - lengths, lengths
    )
    cat_range = cat_start + cat_counter
    return cat_range


# From bioframe (https://github.com/open2c/bioframe)
def overlap_intervals(starts1, ends1, starts2, ends2, closed=False, sort=False):
    starts1 = np.asarray(starts1)
    ends1 = np.asarray(ends1)
    starts2 = np.asarray(starts2)
    ends2 = np.asarray(ends2)

    # Concatenate intervals lists
    n1 = len(starts1)
    n2 = len(starts2)
    ids1 = np.arange(0, n1)
    ids2 = np.arange(0, n2)

    # Sort all intervals together
    order1 = np.lexsort([ends1, starts1])
    order2 = np.lexsort([ends2, starts2])
    starts1, ends1, ids1 = starts1[order1], ends1[order1], ids1[order1]
    starts2, ends2, ids2 = starts2[order2], ends2[order2], ids2[order2]

    # Find interval overlaps
    match_2in1_starts = np.searchsorted(starts2, starts1, "left")
    match_2in1_ends = np.searchsorted(starts2, ends1, "right" if closed else "left")
    # "right" is intentional here to avoid duplication
    match_1in2_starts = np.searchsorted(starts1, starts2, "right")
    match_1in2_ends = np.searchsorted(starts1, ends2, "right" if closed else "left")

    # Ignore self-overlaps
    match_2in1_mask = match_2in1_ends > match_2in1_starts
    match_1in2_mask = match_1in2_ends > match_1in2_starts
    match_2in1_starts, match_2in1_ends = (
        match_2in1_starts[match_2in1_mask],
        match_2in1_ends[match_2in1_mask],
    )
    match_1in2_starts, match_1in2_ends = (
        match_1in2_starts[match_1in2_mask],
        match_1in2_ends[match_1in2_mask],
    )

    # Generate IDs of pairs of overlapping intervals
    overlap_ids = np.block(
        [
            [
                np.repeat(ids1[match_2in1_mask], match_2in1_ends - match_2in1_starts)[
                    :, None
                ],
                ids2[arange_multi(match_2in1_starts, match_2in1_ends)][:, None],
            ],
            [
                ids1[arange_multi(match_1in2_starts, match_1in2_ends)][:, None],
                np.repeat(ids2[match_1in2_mask], match_1in2_ends - match_1in2_starts)[
                    :, None
                ],
            ],
        ]
    )

    if sort:
        # Sort overlaps according to the 1st
        overlap_ids = overlap_ids[np.lexsort([overlap_ids[:, 1], overlap_ids[:, 0]])]

    return overlap_ids


# From adjustText (https://github.com/Phyla/adjustText)
def get_renderer(fig):
    # If the backend support get_renderer() or renderer, use that.
    if hasattr(fig.canvas, "get_renderer"):
        return fig.canvas.get_renderer()

    if hasattr(fig.canvas, "renderer"):
        return fig.canvas.renderer

    # Otherwise, if we have the matplotlib function available, use that.
    if matplot_get_renderer:
        return matplot_get_renderer(fig)

    # No dice, try and guess.
    # Write the figure to a temp location, and then retrieve whichever
    # render was used (doesn't work in all matplotlib versions).
    fig.canvas.print_figure(io.BytesIO())
    try:
        return fig._cachedRenderer

    except AttributeError:
        # No luck.
        # We're out of options.
        raise ValueError("Unable to determine renderer") from None


# From adjustText (https://github.com/Phyla/adjustText)
def get_bboxes(objs, r=None, expand=(1, 1), ax=None):
    ax = ax or plt.gca()
    r = r or get_renderer(ax.get_figure())
    return [i.get_window_extent(r).expanded(*expand) for i in objs]


# From adjustText (https://github.com/Phyla/adjustText)
def get_2d_coordinates(objs, expand=(1.0, 1.0)):
    try:
        ax = objs[0].axes
    except:
        ax = objs.axes
    bboxes = get_bboxes(objs, get_renderer(ax.get_figure()), expand, ax)
    xs = [
        (ax.convert_xunits(bbox.xmin), ax.convert_yunits(bbox.xmax)) for bbox in bboxes
    ]
    ys = [
        (ax.convert_xunits(bbox.ymin), ax.convert_yunits(bbox.ymax)) for bbox in bboxes
    ]
    coords = np.hstack([np.array(xs), np.array(ys)])
    return coords


def text_line_overlaps(text_locations, label_locations, text_bounding_boxes):
    result = []
    for i, box in enumerate(text_bounding_boxes):
        for j in range(text_locations.shape[0]):
            if i == j:
                continue

            if intersect(
                text_locations[j], label_locations[j], box[[0, 2]], box[[1, 3]]
            ) or intersect(
                text_locations[j], label_locations[j], box[[0, 3]], box[[1, 2]]
            ):
                result.append((i, j))

    return result
