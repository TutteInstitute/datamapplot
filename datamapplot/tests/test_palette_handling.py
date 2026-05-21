from collections.abc import Callable
import matplotlib.cm as cmap
import numpy as np
import pytest  # noqa

from ..palette_handling import palette_from_datamap, palette_from_cmap_and_datamap

MakePalette = Callable[[np.ndarray, np.ndarray], list[str]]


@pytest.fixture
def datamap() -> np.ndarray:
    return np.array(
        [
            [-5, 1],
            [-4, 2],
            [-5, -1],
            [-4, -1],
            [5, 0],
            [5, 1],
        ]
    )


LOCATIONS_FEW = [
    [-4.5, 1.5],
    [-4, -0.5],
    [0, 0],
]
LOCATIONS_MANY = [
    *[
        [x, y]
        for x in np.linspace(-5, -3, num=15)
        for y in np.linspace(1., 2., num=10)
    ],
    *[
        [x, y]
        for x in np.linspace(-5, -3, num=15)
        for y in np.linspace(-.5, -1.5, num=10)
    ],
    [0, 0],
]


@pytest.mark.parametrize(
    "make_palette,locations",
    [
        (
            lambda datamap, locations: palette_from_cmap_and_datamap(
                cmap.twilight, datamap, locations
            ),
            LOCATIONS_FEW,
        ),
        (
            palette_from_datamap,
            LOCATIONS_FEW,
        ),
        (
            palette_from_datamap,
            LOCATIONS_MANY,
        ),
    ],
)
def test_labels_away_from_points_with_cmap(
    make_palette: MakePalette, datamap: np.ndarray, locations: list[list[float]],
) -> None:
    palette = make_palette(datamap, np.array(locations))
    assert len(locations) == len(palette)
    assert all(len(color) == 7 for color in palette)
