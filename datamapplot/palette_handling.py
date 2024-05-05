import numpy as np

import colorspacious
from matplotlib.colors import rgb2hex, to_rgb, ListedColormap


def palette_from_datamap(
    umap_coords,
    label_locations,
    hue_shift=0.0,
    theta_range=np.pi / 16,
    radius_weight_power=1.0,
    min_lightness=10,
):
    if label_locations.shape[0] == 0:
        return []

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
    if label_location_thetas.shape[0] < 256:
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
            chroma = (
                np.argsort(np.argsort(data_map_radii[r_mask])) / mask_size
            ) * 80 + 20
            lightness = (
                1.0 - (np.argsort(np.argsort(data_map_radii[r_mask])) / mask_size)
            ) * (80 - min_lightness) + min_lightness
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
    else:
        uniform_thetas = np.linspace(-np.pi, np.pi, 256)
        sorted_chroma = []
        sorted_lightness = []
        sorted_radii = []
        for theta in uniform_thetas:
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
            chroma = (
                np.argsort(np.argsort(data_map_radii[r_mask])) / mask_size
            ) * 80 + 20
            lightness = (
                1.0 - (np.argsort(np.argsort(data_map_radii[r_mask])) / mask_size)
            ) * (80 - min_lightness) + min_lightness
            sorted_chroma.append(np.sort(chroma))
            sorted_lightness.append(np.sort(lightness)[::-1])
            sorted_radii.append(np.sort(data_map_radii[r_mask]))

        for r, theta in zip(label_location_radii, label_location_thetas):
            nearest_theta_idx = np.argmin(np.abs(uniform_thetas - theta))
            location_lightness.append(
                np.interp(
                    r,
                    sorted_radii[nearest_theta_idx],
                    sorted_lightness[nearest_theta_idx],
                )
            )
            location_chroma.append(
                np.interp(
                    r, sorted_radii[nearest_theta_idx], sorted_chroma[nearest_theta_idx]
                )
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


def scaling_func(xs, lo, mid, hi):
    vals = (2 * (lo + hi) - 4 * mid) * xs**2 + (4 * mid - 3 * lo - hi) * xs + lo
    return np.clip(vals, lo, hi)


def palette_from_cmap_and_datamap(
    cmap,
    umap_coords,
    label_locations,
    chroma_bounds=(20, 90),
    lightness_bounds=(10, 80),
    theta_range=np.pi / 16,
    radius_weight_power=1.0,
):
    if label_locations.shape[0] == 0:
        return [cmap(0.5)]

    endpoints = cmap((0.0, 1.0))
    endpoint_distance = np.sum((endpoints[0] - endpoints[1]) ** 2)
    if endpoint_distance < 0.05:
        cyclic_cmap = cmap
    else:
        new_colors = np.vstack(
            (
                cmap(np.linspace(0, 1, 128)),
                cmap(np.linspace(1, 0, 128)),
            )
        )
        cyclic_cmap = ListedColormap(new_colors, name="generated_cyclic_cmap")

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
    weights = weights.cumsum()
    weights /= weights.max()

    location_base_vals = np.interp(
        label_location_thetas, np.sort(label_location_thetas), np.sort(weights)
    )
    base_colors = cyclic_cmap(location_base_vals)[:, :3]

    base_colors_jch = colorspacious.cspace_convert(base_colors, "sRGB1", "JCh")

    location_hue = base_colors_jch.T[2]
    location_chroma = []
    location_lightness = []
    for i, (r, theta) in enumerate(zip(label_location_radii, label_location_thetas)):
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

        chroma_scale = np.argsort(np.argsort(data_map_radii[r_mask])) / mask_size
        chroma = scaling_func(
            chroma_scale, chroma_bounds[0], base_colors_jch[i, 1], chroma_bounds[1]
        )

        lightness_scale = 1.0 - (
            np.argsort(np.argsort(data_map_radii[r_mask])) / mask_size
        )
        lightness = scaling_func(
            lightness_scale,
            lightness_bounds[0],
            base_colors_jch[i, 0],
            lightness_bounds[1],
        )
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
