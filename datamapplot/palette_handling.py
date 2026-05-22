from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
import numpy as np
import operator
from typing import Optional, Protocol

import colorspacious
from matplotlib.colors import rgb2hex, to_rgb, ListedColormap
from matplotlib.cm import hsv


EPS = 1e-6


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
        pol = cls(
            radii=np.linalg.norm(xy_centered, axis=1),
            thetas=np.arctan2(xy_centered.T[1], xy_centered.T[0]),
            center=center_,
        )
        assert np.all(pol.radii >= 0)
        assert np.all((pol.thetas >= -np.pi) & (pol.thetas <= np.pi))
        return pol


def palette_from_datamap(
    umap_coords,
    label_locations,
    hue_shift=0.0,
    theta_range=np.pi / 16,
    radius_weight_power=1.0,
    min_lightness=10,
):
    return palette_from_cmap_and_datamap(
        cmap=None,
        umap_coords=umap_coords,
        label_locations=label_locations,
        hue_shift=hue_shift,
        chroma_bounds=(20, 90),
        lightness_bounds=(min_lightness, 80),
        theta_range=theta_range,
        radius_weight_power=radius_weight_power,
    )


def scaling_parabolic(xs, lo, mid, hi):
    vals = (2 * (lo + hi) - 4 * mid) * xs**2 + (4 * mid - 3 * lo - hi) * xs + lo
    return np.clip(vals, lo, hi)


Scaler = Callable[[float], float]
Bounds = tuple[float, float]

class ColorSet(Protocol):

    def hues(self) -> np.ndarray: ...
    def scalers(self, bounds_chroma: Bounds, bounds_lightness: Bounds) -> Iterator[tuple[Scaler, Scaler]]: ...


@dataclass
class ColorsUntethered:
    weights: np.ndarray

    def hues(self) -> np.ndarray:
        return self.weights * 360.

    def scalers(self, bounds_chroma: Bounds, bounds_lightness: Bounds) -> Iterator[tuple[Scaler, Scaler]]:
        def linear01(bounds: Bounds) -> Scaler:
            return lambda x: bounds[0] + x * (bounds[1] - bounds[0])

        scale_chroma = linear01(bounds_chroma)
        scale_lightness = linear01(bounds_lightness)
        for _ in self.weights:
            yield scale_chroma, scale_lightness


class ColorsThroughMap:

    def __init__(self, weights: float, cmap: Callable[[Iterable[float]], np.ndarray]) -> None:
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

        rgb = cyclic_cmap(weights)[:, :3]
        self.jch = colorspacious.cspace_convert(rgb, "sRGB1", "JCh")

    def hues(self) -> np.ndarray:
        return self.jch.T[2]

    def scalers(self, bounds_chroma: Bounds, bounds_lightness: Bounds) -> Iterator[tuple[Scaler, Scaler]]:
        for lightness, chroma, _ in self.jch:
            yield (
                lambda x: scaling_parabolic(x, bounds_chroma[0], chroma, bounds_chroma[1]),
                lambda x: scaling_parabolic(x, bounds_lightness[0], lightness, bounds_lightness[1])
            )


def palette_from_cmap_and_datamap(
    cmap,
    umap_coords,
    label_locations,
    hue_shift=0.,
    chroma_bounds=(20, 90),
    lightness_bounds=(10, 80),
    theta_range=np.pi / 16,
    radius_weight_power=1.0,
    sector_scan=None,
):
    if label_locations.shape[0] == 0:
        return [cmap(0.5) if cmap else f"#888888"]

    pol_data = Polars.from_xy(umap_coords)
    pol_labels = Polars.from_xy(label_locations, center=pol_data.center)

    order_labels = np.argsort(pol_labels.thetas)
    weights_base = (pol_labels.radii**radius_weight_power)[order_labels].cumsum()
    weights_base /= weights_base.max()
    weights_spaced = np.interp(
        pol_labels.thetas, pol_labels.thetas[order_labels], weights_base
    )
    colorset = ColorsThroughMap(weights_spaced, cmap) if cmap else ColorsUntethered(weights_spaced)
    hue_labels = (colorset.hues() + hue_shift) % 360

    thetas_sector_uniform = lambda: np.linspace(-np.pi, np.pi, 256, endpoint=False)
    match sector_scan:
        case "labels":
            thetas_sector = pol_labels.thetas
        case "uniform":
            thetas_sector = thetas_sector_uniform()
        case None:
            thetas_sector = pol_labels.thetas if pol_labels.thetas.shape[0] < 256 else thetas_sector_uniform()
        case _:
            raise ValueError("Argument sector_scan must be either None, 'labels' or 'uniform'")

    radii_sector = []
    theta_range = min(theta_range, (1. - EPS) * np.pi)
    for theta in thetas_sector:
        mask_size = 0
        for theta_spread in np.linspace(2 * theta_range, np.pi, num=16):
            theta_high = theta + .5 * theta_spread
            theta_low = theta - .5 * theta_spread
            if theta_high > np.pi:
                theta_high -= 2 * np.pi
            if theta_low < -np.pi:
                theta_low += 2 * np.pi
            between = operator.or_ if theta_low > 0 and theta_high < 0 else operator.and_
            r_mask = between(pol_data.thetas > theta_low, pol_data.thetas < theta_high)
            mask_size = np.sum(r_mask)
            if mask_size > 0:
                break
        else:
            raise RuntimeError(f"Cannot reference data for computing chroma and lightness for label at angle {theta}")
        assert mask_size > 0
        radii_sector.append(np.sort(pol_data.radii[r_mask]))
    assert len(radii_sector) == len(thetas_sector)

    lightness_labels = []
    chroma_labels = []
    for (scale_chroma, scale_lightness), theta, radius in zip(colorset.scalers(chroma_bounds, lightness_bounds), pol_labels.thetas, pol_labels.radii):
        i_nearest_sector = np.argmin(np.abs(thetas_sector - theta))
        radii_reference = radii_sector[i_nearest_sector]
        scale = np.arange(len(radii_reference)) / len(radii_reference)

        chroma_labels.append(np.interp(radius, radii_reference, np.sort(scale_chroma(scale))))
        lightness_labels.append(np.interp(radius, radii_reference, np.sort(scale_lightness(1. - scale))[::-1]))

    palette = np.clip(
        colorspacious.cspace_convert(
            np.vstack([np.asarray(p) for p in [lightness_labels, chroma_labels, hue_labels]]).T,
            "JCh",
            "sRGB1",
        ),
        0.,
        1.,
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
