from dataclasses import dataclass
import numpy as np
import operator
from typing import Optional

import colorspacious
from matplotlib.colors import rgb2hex, to_rgb, ListedColormap


@dataclass
class Polars:
    radii: np.ndarray
    thetas: np.ndarray
    center: np.ndarray

    @classmethod
    def from_xy(cls, xy: np.ndarray, center: Optional[np.ndarray] = None) -> "Polars":
        if center is None:
            min_ = np.min(xy, axis=0)
            max_ = np.max(xy, axis=0)
            center_ = min_ + (max_ - min_) / 2
        else:
            center_ = np.asarray(center)

        xy_centered = xy - center_
        return cls(
            radii=np.linalg.norm(xy_centered, axis=1),
            thetas=np.arctan2(xy_centered.T[1], xy_centered.T[0]),
            center=center_,
        )

    
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

    pol_data = Polars.from_xy(umap_coords)
    pol_labels = Polars.from_xy(label_locations, center=pol_data.center)

    sorter = np.argsort(pol_labels.thetas)
    weights = (pol_labels.radii**radius_weight_power)[sorter]
    hue = weights.cumsum()
    hue = (hue / hue.max()) * 360

    location_hue = np.interp(
        pol_labels.thetas, np.sort(pol_labels.thetas), np.sort(hue)
    )
    location_hue = (location_hue + hue_shift) % 360

    location_chroma = []
    location_lightness = []
    if pol_labels.thetas.shape[0] < 256:
        for r, theta in zip(pol_labels.radii, pol_labels.thetas):
            # use increasing values of theta range to ensure that we find a mask containing some elements
            for i_theta_range in np.linspace(theta_range, np.pi, 16):
                theta_high = theta + i_theta_range
                theta_low = theta - i_theta_range
                if theta_high > np.pi:
                    theta_high -= 2 * np.pi
                if theta_low < -np.pi:
                    theta_low += 2 * np.pi

                between = operator.or_ if theta_low > 0 and theta_high < 0 else operator.and_
                r_mask = between(pol_data.thetas > theta_low, pol_data.thetas < theta_high)
                # if theta_low > 0 and theta_high < 0:
                #     r_mask = (pol_data.thetas < theta_low) & (pol_data.thetas > theta_high)
                # else:
                #     r_mask = (pol_data.thetas > theta_low) & (pol_data.thetas < theta_high)

                mask_size = np.sum(r_mask)
                if mask_size > 0:
                    break
            else:
                raise ValueError("No mask found for theta range.")

            chroma = (
                np.argsort(np.argsort(pol_data.radii[r_mask])) / mask_size
            ) * 80 + 20
            lightness = (
                1.0 - (np.argsort(np.argsort(pol_data.radii[r_mask])) / mask_size)
            ) * (80 - min_lightness) + min_lightness
            location_lightness.append(
                np.interp(
                    r,
                    np.sort(pol_data.radii[r_mask]),
                    np.sort(lightness)[::-1],
                )
            )
            location_chroma.append(
                np.interp(r, np.sort(pol_data.radii[r_mask]), np.sort(chroma))
            )
    else:
        uniform_thetas = np.linspace(-np.pi, np.pi, 256)
        sorted_chroma = []
        sorted_lightness = []
        sorted_radii = []
        for theta in uniform_thetas:
            mask_size = 0
            for theta_spread in np.linspace(theta_range, np.pi, num=16):
                theta_high = theta + theta_spread
                theta_low = theta - theta_spread
                if theta_high > np.pi:
                    theta_high -= 2 * np.pi
                if theta_low < -np.pi:
                    theta_low += 2 * np.pi

                between = operator.or_ if theta_low > 0 and theta_high < 0 else operator.and_
                r_mask = between(pol_data.thetas > theta_low, pol_data.thetas < theta_high)
                # if theta_low > 0 and theta_high < 0:
                #     r_mask = (pol_data.thetas < theta_low) & (pol_data.thetas > theta_high)
                # else:
                #     r_mask = (pol_data.thetas > theta_low) & (pol_data.thetas < theta_high)
                mask_size = np.sum(r_mask)
                if mask_size > 0:
                    break
            else:
                raise RuntimeError(f"Cannot reference data for computing chroma and lightness for label at angle {theta}")
            assert mask_size > 0

            # mask_size = np.sum(r_mask)
            chroma = (
                np.argsort(np.argsort(pol_data.radii[r_mask])) / mask_size
            ) * 80 + 20
            lightness = (
                1.0 - (np.argsort(np.argsort(pol_data.radii[r_mask])) / mask_size)
            ) * (80 - min_lightness) + min_lightness
            sorted_chroma.append(np.sort(chroma))
            sorted_lightness.append(np.sort(lightness)[::-1])
            sorted_radii.append(np.sort(pol_data.radii[r_mask]))

        for r, theta in zip(pol_labels.radii, pol_labels.thetas):
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

    pol_data = Polars.from_xy(umap_coords)
    pol_labels = Polars.from_xy(label_locations, center=pol_data.center)

    sorter = np.argsort(pol_labels.thetas)
    weights = (pol_labels.radii**radius_weight_power)[sorter]
    weights = weights.cumsum()
    weights /= weights.max()

    location_base_vals = np.interp(
        pol_labels.thetas, np.sort(pol_labels.thetas), np.sort(weights)
    )
    base_colors = cyclic_cmap(location_base_vals)[:, :3]

    base_colors_jch = colorspacious.cspace_convert(base_colors, "sRGB1", "JCh")

    location_hue = base_colors_jch.T[2]
    location_chroma = []
    location_lightness = []
    for i, (r, theta) in enumerate(zip(pol_labels.radii, pol_labels.thetas)):
        mask_size = 0
        for theta_spread in np.linspace(theta_range, np.pi, num=16):
            theta_high = theta + .5 * theta_spread
            theta_low = theta - .5 * theta_spread
            if theta_high > np.pi:
                theta_high -= 2 * np.pi
            if theta_low < -np.pi:
                theta_low += 2 * np.pi

            between = operator.or_ if theta_low > 0 and theta_high < 0 else operator.and_
            r_mask = between(pol_data.thetas > theta_low, pol_data.thetas < theta_high)
            #     r_mask_neg = (pol_data.thetas < 0) & 
            #     r_mask = (pol_data.thetas < theta_low) & (pol_data.thetas > theta_high)
            # else:
            #     r_mask = (pol_data.thetas > theta_low) & (pol_data.thetas < theta_high)
            mask_size = np.sum(r_mask)
            if mask_size > 0:
                break
        else:
            raise RuntimeError(f"Cannot reference data for computing chroma and lightness for label at angle {theta}")
        assert mask_size > 0

        chroma_scale = np.argsort(np.argsort(pol_data.radii[r_mask])) / mask_size
        chroma = scaling_func(
            chroma_scale, chroma_bounds[0], base_colors_jch[i, 1], chroma_bounds[1]
        )

        lightness_scale = 1.0 - (
            np.argsort(np.argsort(pol_data.radii[r_mask])) / mask_size
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
                np.sort(pol_data.radii[r_mask]),
                np.sort(lightness)[::-1],
            )
        )
        location_chroma.append(
            np.interp(r, np.sort(pol_data.radii[r_mask]), np.sort(chroma))
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


def deep_palette(base_palette, degree=2.0):
    if len(base_palette) == 0:
        return []
    initial_palette = [to_rgb(color) for color in base_palette]
    jch_palette = colorspacious.cspace_convert(initial_palette, "sRGB1", "JCh")
    min_lightness = jch_palette.T[0].min()
    min_chroma = jch_palette.T[1].min()
    jch_palette[:, 0] = np.clip(jch_palette[:, 0] / degree, min(20 / degree, min_lightness), 50)
    jch_palette[:, 1] = np.clip(jch_palette[:, 1] / degree, min(40 / degree, min_chroma), 100)
    result = [
        rgb2hex(x)
        for x in np.clip(
            colorspacious.cspace_convert(jch_palette, "JCh", "sRGB1"), 0, 1
        )
    ]
    return result


def pastel_palette(base_palette, degree=2.0):
    if len(base_palette) == 0:
        return []
    initial_palette = [to_rgb(color) for color in base_palette]
    jch_palette = colorspacious.cspace_convert(initial_palette, "sRGB1", "JCh")
    min_lightness = jch_palette.T[0].min()
    min_chroma = jch_palette.T[1].min()
    jch_palette[:, 0] = np.clip(jch_palette[:, 0] * np.sqrt(degree), min_lightness, 100)
    jch_palette[:, 1] = np.clip(jch_palette[:, 1] / degree, min(10 / degree, min_chroma), 50)
    result = [
        rgb2hex(x)
        for x in np.clip(
            colorspacious.cspace_convert(jch_palette, "JCh", "sRGB1"), 0, 1
        )
    ]
    return result
