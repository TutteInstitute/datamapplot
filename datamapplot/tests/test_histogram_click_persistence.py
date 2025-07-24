import numpy as np
import pytest

from datamapplot import create_interactive_plot


@pytest.fixture
def sample_data():
    """Sample data for testing histogram functionality"""
    coords = np.random.rand(100, 2) * 10
    labels = ["Cluster A"] * 30 + ["Cluster B"] * 40 + ["Cluster C"] * 30
    return coords, labels


def test_histogram_click_persistence_parameter_default(sample_data):
    """Test that histogram_enable_click_persistence defaults to False"""
    coords, labels = sample_data
    fig = create_interactive_plot(coords, labels, histogram_data=coords[:, 0])
    # Verify the parameter is passed correctly to the template
    assert hasattr(fig, "_html_str")
    # Verify default value is false
    assert "enableClickPersistence: false" in fig._html_str


def test_histogram_click_persistence_parameter_enabled(sample_data):
    """Test that histogram_enable_click_persistence can be enabled"""
    coords, labels = sample_data
    fig = create_interactive_plot(
        coords,
        labels,
        histogram_data=coords[:, 0],
        histogram_enable_click_persistence=True,
    )
    # Verify the parameter is passed correctly
    assert hasattr(fig, "_html_str")
    # Verify enabled value is true
    assert "enableClickPersistence: true" in fig._html_str


def test_histogram_click_persistence_without_histogram_data(sample_data):
    """Test that click persistence parameter is ignored when no histogram data"""
    coords, labels = sample_data
    fig = create_interactive_plot(
        coords, labels, histogram_enable_click_persistence=True  # Should be ignored
    )
    assert hasattr(fig, "_html_str")
    # Verify that the parameter is ignored when no histogram data is provided
    # The HTML should not contain histogram-related code
    assert "enableClickPersistence" not in fig._html_str
