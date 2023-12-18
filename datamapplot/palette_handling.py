import numpy as np

import colorspacious
from matplotlib.colors import rgb2hex, to_rgb


def palette_from_datamap(umap_coords, label_locations):
    data_center = np.asarray(
        umap_coords.min(axis=0)
        + (umap_coords.max(axis=0) - umap_coords.min(axis=0)) / 2
    )
    centered_data = umap_coords - data_center
    data_map_radii = np.linalg.norm(centered_data, axis=1)
    data_map_thetas = np.arctan2(centered_data.T[1], centered_data.T[0])
    centered_label_locations = label_locations - data_center
    label_location_radii = np.linalg.norm(centered_label_locations, axis=1)
    label_location_thetas = np.arctan2(
        centered_label_locations.T[1], centered_label_locations.T[0]
    )

    hue = (np.argsort(np.argsort(data_map_thetas)) / data_map_thetas.shape[0]) * 360
    chroma = (
        np.argsort(np.argsort(data_map_radii)) / data_map_thetas.shape[0]
    ) * 80 + 20
    lightness = (
        1.0 - (np.argsort(np.argsort(data_map_radii)) / data_map_thetas.shape[0])
    ) * 70 + 10

    palette = np.clip(
        colorspacious.cspace_convert(
            np.vstack(
                (
                    np.interp(
                        label_location_radii,
                        np.sort(data_map_radii),
                        np.sort(lightness)[::-1],
                    ),
                    np.interp(
                        label_location_radii, np.sort(data_map_radii), np.sort(chroma)
                    ),
                    np.interp(
                        label_location_thetas, np.sort(data_map_thetas), np.sort(hue)
                    ),
                )
            ).T,
            "JCh",
            "sRGB1",
        ),
        0,
        1,
    )
    return [rgb2hex(color) for color in palette]


def deep_palette(base_palette):
    initial_palette = [to_rgb(color) for color in base_palette]
    jch_palette = colorspacious.cspace_convert(initial_palette, "sRGB1", "JCH")
    jch_palette[:, 0] = np.clip(jch_palette[:, 0] - 20, 20, 50)
    jch_palette[:, 1] = np.clip(jch_palette[:, 0] - 20, 30, 100)
    result = [
        rgb2hex(x)
        for x in np.clip(
            colorspacious.cspace_convert(jch_palette, "JCh", "sRGB1"), 0, 1
        )
    ]
    return result
