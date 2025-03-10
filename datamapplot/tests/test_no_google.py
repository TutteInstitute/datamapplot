from contextlib import contextmanager
from matplotlib.axes import Axes
from matplotlib.figure import Figure
import numpy as np
import pytest
from requests.exceptions import ConnectionError
from unittest.mock import patch
from warnings import catch_warnings

import datamapplot as dmp
from datamapplot.interactive_rendering import InteractiveFigure
from datamapplot.plot_rendering import GoogleAPIUnreachable


@pytest.fixture
def datamap():
    return np.array([[0, 2], [-1, 2], [1, 0]])


@pytest.fixture
def labels():
    return ["asdf", "qwer", "Unlabelled"]


@pytest.fixture
def hover_text():
    return ["heyhey", "hoho", "aha"]


@contextmanager
def no_google(num_warnings):
    with patch(
        "datamapplot.fonts.requests.get",
        side_effect=ConnectionError
    ) as mock_get, catch_warnings(record=True) as caught:
        yield mock_get
    assert num_warnings == len(
        [wm for wm in caught if wm.category is GoogleAPIUnreachable]
    )


def test_no_google_static(datamap):
    with no_google(1):
        fig, ax = dmp.create_plot(datamap, labels=None)
    assert isinstance(fig, Figure)
    assert isinstance(ax, Axes)


def test_no_google_interactive(datamap, labels, hover_text):
    with no_google(0):
        fig = dmp.create_interactive_plot(
            datamap,
            labels,
            hover_text=hover_text
        )
    assert isinstance(fig, InteractiveFigure)
