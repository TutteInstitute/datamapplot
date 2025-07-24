import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

import numpy as np

import datamapplot
from datamapplot.create_plots import create_plot
from datamapplot.plot_rendering import manage_google_font
from datamapplot.plot_rendering import render_plot


class TestUseSystemFonts(unittest.TestCase):
    """Test suite for the use_system_fonts parameter."""

    def setUp(self):
        """Set up test data."""
        # Generate simple test data
        np.random.seed(42)
        self.n_samples = 100
        self.data_coords = np.random.randn(self.n_samples, 2)
        self.labels = np.array(["Group A"] * 50 + ["Group B"] * 50)

    def test_use_system_fonts_default_false(self):
        """Test that by default, use_system_fonts is False and fonts are downloaded."""
        with patch(
            "datamapplot.plot_rendering.can_reach_google_fonts", return_value=True
        ), patch("datamapplot.plot_rendering.manage_google_font") as mock_manage_font:

            # Create plot with default use_system_fonts (False)
            fig, ax = create_plot(
                self.data_coords, self.labels, title="Test Plot", verbose=True
            )

            # Verify that manage_google_font was called
            self.assertTrue(mock_manage_font.called)

    def test_use_system_fonts_true_prevents_download(self):
        """Test that use_system_fonts=True prevents font downloads."""
        with patch(
            "datamapplot.plot_rendering.can_reach_google_fonts", return_value=True
        ), patch("datamapplot.plot_rendering.manage_google_font") as mock_manage_font:

            # Create plot with use_system_fonts=True
            fig, ax = create_plot(
                self.data_coords,
                self.labels,
                title="Test Plot",
                use_system_fonts=True,
                verbose=True,
            )

            # Verify that manage_google_font was NOT called
            self.assertFalse(mock_manage_font.called)

    def test_use_system_fonts_parameter_propagation(self):
        """Test that use_system_fonts parameter propagates correctly from create_plot to render_plot."""
        with patch("datamapplot.create_plots.render_plot") as mock_render:
            # Set up the mock to return a figure and axis
            mock_fig = MagicMock()
            mock_ax = MagicMock()
            mock_render.return_value = (mock_fig, mock_ax)

            # Create plot with use_system_fonts=True
            create_plot(self.data_coords, self.labels, use_system_fonts=True)

            # Verify render_plot was called with use_system_fonts=True
            self.assertTrue(mock_render.called)
            args, kwargs = mock_render.call_args
            self.assertTrue("use_system_fonts" in kwargs)
            self.assertTrue(kwargs["use_system_fonts"])

    def test_use_system_fonts_false_with_no_internet(self):
        """Test behavior when use_system_fonts=False but can't reach Google Fonts."""
        with patch(
            "datamapplot.plot_rendering.can_reach_google_fonts", return_value=False
        ), patch(
            "datamapplot.plot_rendering.manage_google_font"
        ) as mock_manage_font, patch(
            "datamapplot.plot_rendering.warn"
        ) as mock_warn:

            # Create plot with use_system_fonts=False but no internet
            fig, ax = create_plot(
                self.data_coords,
                self.labels,
                title="Test Plot",
                use_system_fonts=False,
                verbose=True,
            )

            # Verify that manage_google_font was NOT called
            self.assertFalse(mock_manage_font.called)

            # Verify that a warning was issued
            self.assertTrue(mock_warn.called)

    def test_render_plot_directly_with_use_system_fonts(self):
        """Test render_plot function directly with use_system_fonts parameter."""
        # Prepare data for render_plot
        color_list = ["#FF0000"] * 50 + ["#0000FF"] * 50
        label_text = ["Group A", "Group B"]
        label_locations = np.array([[0.0, 0.0], [1.0, 1.0]])
        label_cluster_sizes = np.array([50, 50])

        with patch(
            "datamapplot.plot_rendering.can_reach_google_fonts", return_value=True
        ), patch("datamapplot.plot_rendering.manage_google_font") as mock_manage_font:

            # Test with use_system_fonts=True
            fig, ax = render_plot(
                self.data_coords,
                color_list,
                label_text,
                label_locations,
                label_cluster_sizes,
                use_system_fonts=True,
                verbose=True,
            )

            # Verify that manage_google_font was NOT called
            self.assertFalse(mock_manage_font.called)

            # Test with use_system_fonts=False
            fig, ax = render_plot(
                self.data_coords,
                color_list,
                label_text,
                label_locations,
                label_cluster_sizes,
                use_system_fonts=False,
                verbose=True,
            )

            # Verify that manage_google_font was called
            self.assertTrue(mock_manage_font.called)

    def test_use_system_fonts_with_custom_font_family(self):
        """Test that use_system_fonts works with custom font_family parameter."""
        with patch(
            "datamapplot.plot_rendering.can_reach_google_fonts", return_value=True
        ), patch("datamapplot.plot_rendering.manage_google_font") as mock_manage_font:

            # Create plot with custom font and use_system_fonts=True
            fig, ax = create_plot(
                self.data_coords,
                self.labels,
                title="Test Plot",
                font_family="Arial",
                use_system_fonts=True,
                verbose=True,
            )

            # Verify that manage_google_font was NOT called
            self.assertFalse(mock_manage_font.called)

    def test_use_system_fonts_with_title_subtitle_fonts(self):
        """Test that use_system_fonts affects title and subtitle font downloads."""
        with patch(
            "datamapplot.plot_rendering.can_reach_google_fonts", return_value=True
        ), patch("datamapplot.plot_rendering.manage_google_font") as mock_manage_font:

            # Create plot with custom title/subtitle fonts and use_system_fonts=True
            fig, ax = create_plot(
                self.data_coords,
                self.labels,
                title="Test Title",
                sub_title="Test Subtitle",
                title_keywords={"fontfamily": "Times New Roman"},
                sub_title_keywords={"fontfamily": "Georgia"},
                use_system_fonts=True,
                verbose=True,
            )

            # Verify that manage_google_font was NOT called for any font
            self.assertFalse(mock_manage_font.called)


if __name__ == "__main__":
    unittest.main()
