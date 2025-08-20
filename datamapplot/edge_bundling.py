import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from scipy.interpolate import RegularGridInterpolator
from datashader.bundling import hammer_bundle


def _hex_to_rgb(hex_color):
    """
    Converts a hex color string to an RGB tuple.

    Parameters:
    - hex_color (str): A hex color string, e.g., '#FF5733' or '#FF5733FF' for RGBA.

    Returns:
    - rgb (tuple): A tuple of integers representing the RGB values, e.g., (255, 87, 51) or (255, 87, 51, 255) for RGBA.
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))  # RGB
    elif len(hex_color) == 8:
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4, 6))  # RGBA


def _rgb_to_hex(rgb, round_to=30):
    """
    Converts a NumPy array of RGB/RGBA values to hex strings.
    Rounds RGB values to limit number of classes in datashader's aggregator.


    Parameters:
    - rgb_array (np.ndarray): A NumPy array of shape (N, 3) or (N, 4) containing RGB/RGBA values.

    Returns:
    - hex_colors (np.ndarray): A NumPy array of hex color strings.
    """
    _hex_lookup = [f"{i:02x}" for i in range(0, 256, round_to)]

    rgb = (round_to * np.round(rgb / round_to)).astype(np.uint8)

    indices = rgb // round_to

    num_components = rgb.shape[1]
    if num_components not in (3, 4):
        raise ValueError("rgb array must have shape (N, 3) or (N, 4)")

    hex_components = np.take(_hex_lookup, indices)

    hex_components = hex_components.reshape((-1, num_components))
    hex_colors = np.array(["#" + "".join(row) for row in hex_components])

    return hex_colors


def _interpolate_colors(tree, colors, target_points, nn=100):
    grid_x = np.linspace(target_points[:, 0].min(), target_points[:, 0].max(), 100)
    grid_y = np.linspace(target_points[:, 1].min(), target_points[:, 1].max(), 100)
    grid_xx, grid_yy = np.meshgrid(grid_x, grid_y, indexing="ij")
    grid_points = np.vstack([grid_xx.ravel(), grid_yy.ravel()]).T

    # construct color grid

    colors = np.array([_hex_to_rgb(color) for color in colors])
    distances, indices = tree.kneighbors(grid_points, n_neighbors=nn)
    weights = 1 / np.maximum(distances, 1e-6) ** 1  # Avoid division by zero
    weights /= weights.sum(axis=1)[:, None]  #
    grid_colors = np.einsum("ij,ijk->ik", weights, colors[indices])
    grid_colors = grid_colors.reshape((len(grid_x), len(grid_y), 3))

    # Interpolate
    color_interpolator = RegularGridInterpolator(
        (grid_x, grid_y), grid_colors, method="slinear"
    )
    segment_colors = color_interpolator(target_points)

    return _rgb_to_hex(segment_colors)


def bundle_edges(
    data_map_coords,
    color_list,
    n_neighbors=10,
    color_map_nn=100,
    edges=None,
    hammer_bundle_kwargs=None,
):
    if hammer_bundle_kwargs is None:
        hammer_bundle_kwargs = {"use_dask": False}

    """Use hammer edge bundling on nearest neighbors"""
    nbrs = NearestNeighbors(
        n_neighbors=max(n_neighbors, color_map_nn), algorithm="ball_tree", n_jobs=-1
    ).fit(data_map_coords)

    # if user does not provide edges, use KNN
    if edges is None:
        _, indices = nbrs.kneighbors(data_map_coords, n_neighbors=n_neighbors)

        source_nodes = np.repeat(np.arange(indices.shape[0]), indices.shape[1])
        target_nodes = indices.flatten()
        edges = np.stack((source_nodes, target_nodes), axis=1)
        mask = edges[:, 0] != edges[:, 1]
        edges = edges[mask]

        edges = pd.DataFrame(
            {
                "source": edges[:, 0],
                "target": edges[:, 1],
            }
        )
    bundle_points = pd.DataFrame({"x": data_map_coords.T[0], "y": data_map_coords.T[1]})
    # Perform edge bundling
    bundled = hammer_bundle(bundle_points, edges, **hammer_bundle_kwargs)

    bundled["is_valid"] = bundled.isnull().all(axis=1).cumsum()
    bundled = bundled.dropna()
    x = bundled["x"][:-1].values
    y = bundled["y"][:-1].values
    x1 = bundled["x"][1:].values
    y1 = bundled["y"][1:].values
    is_valid = bundled["is_valid"][1:].values == bundled["is_valid"][:-1].values
    segments = np.array([x, y, x1, y1]).T[is_valid]

    midpoints = np.array(
        [(segments[:, 0] + segments[:, 2]) / 2, (segments[:, 1] + segments[:, 3]) / 2]
    ).T

    # Compute line segment color based on midpoint
    segment_colors = _interpolate_colors(nbrs, color_list, midpoints, nn=color_map_nn)

    return segments, segment_colors
