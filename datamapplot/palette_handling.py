import numpy as np

import colorspacious
from matplotlib.colors import rgb2hex, to_rgb


def palette_from_datamap(
    umap_coords, label_locations, hue_shift=0.0, theta_range=np.pi / 16, radius_weight_power=1.0
):
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

    sorter = np.argsort(label_location_thetas)
    weights = (label_location_radii**radius_weight_power)[sorter]
    hue = weights.cumsum()
    hue = (hue / hue.max()) * 360

    location_hue = np.interp(
        label_location_thetas, np.sort(label_location_thetas), np.sort(hue)
    )
    location_hue = (location_hue + hue_shift) % 360

    location_chroma = []
    location_lightness = []
    for r, theta in zip(label_location_radii, label_location_thetas):
        theta_high = theta + theta_range
        theta_low = theta - theta_range
        if theta_high > np.pi:
            theta_high -= 2 * np.pi
        if theta_low < -np.pi:
            theta_low -= 2 * np.pi

        if theta_low > 0 and theta_high < 0:
            r_mask = (data_map_thetas < theta_low) & (data_map_thetas > theta_high)
        else:
            r_mask = (data_map_thetas > theta_low) & (data_map_thetas < theta_high)

        mask_size = np.sum(r_mask)
        chroma = (np.argsort(np.argsort(data_map_radii[r_mask])) / mask_size) * 80 + 20
        lightness = (
            1.0 - (np.argsort(np.argsort(data_map_radii[r_mask])) / mask_size)
        ) * 70 + 10
        location_lightness.append(
            np.interp(
                r,
                np.sort(data_map_radii[r_mask]),
                np.sort(lightness)[::-1],
            )
        )
        location_chroma.append(
            np.interp(r, np.sort(data_map_radii[r_mask]), np.sort(chroma))
        )

    palette = np.clip(
        colorspacious.cspace_convert(
            np.vstack(
                (
                    np.asarray(location_lightness),
                    np.asarray(location_chroma),
                    location_hue,
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
    jch_palette = colorspacious.cspace_convert(initial_palette, "sRGB1", "JCh")
    jch_palette[:, 0] = np.clip(jch_palette[:, 0] / 2.0, 10, 50)
    jch_palette[:, 1] = np.clip(jch_palette[:, 1] - 20, 30, 100)
    result = [
        rgb2hex(x)
        for x in np.clip(
            colorspacious.cspace_convert(jch_palette, "JCh", "sRGB1"), 0, 1
        )
    ]
    return result

def pastel_palette(base_palette):
    initial_palette = [to_rgb(color) for color in base_palette]
    jch_palette = colorspacious.cspace_convert(initial_palette, "sRGB1", "JCh")
    jch_palette[:, 0] = np.clip(jch_palette[:, 0] + 30, 60, 100)
    jch_palette[:, 1] = np.clip(jch_palette[:, 0], 5, 20)
    result = [
        rgb2hex(x)
        for x in np.clip(
            colorspacious.cspace_convert(jch_palette, "JCh", "sRGB1"), 0, 1
        )
    ]
    return result
