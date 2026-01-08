import unittest
import tempfile
import json
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
import datamapplot
from datamapplot.interactive_rendering import get_google_font_for_embedding


class TestOfflineFontFileHandling(unittest.TestCase):
    """Test suite for offline mode font file handling (issue #112)."""

    def setUp(self):
        """Set up test data."""
        # Generate simple test data
        np.random.seed(42)
        self.n_samples = 100
        self.data_coords = np.random.randn(self.n_samples, 2)
        self.labels = np.array(["Group A"] * 50 + ["Group B"] * 50)

    def test_get_google_font_for_embedding_with_custom_file(self):
        """Test that get_google_font_for_embedding uses custom font file path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a custom font cache file
            font_cache_path = Path(temp_dir) / "custom_fonts.json"
            mock_font_data = {
                "TestFont": [
                    {
                        "style": "normal",
                        "weight": "400",
                        "unicode_range": "",
                        "type": "ttf",
                        "content": "VGVzdEZvbnRDb250ZW50",
                    }
                ]
            }

            with open(font_cache_path, "w") as f:
                json.dump(mock_font_data, f)

            # Test with custom file path
            result = get_google_font_for_embedding(
                "TestFont", offline_mode=True, offline_font_file=str(font_cache_path)
            )

            # Verify it returns the font data
            self.assertIn("@font-face", result)
            self.assertIn("TestFont", result)
            self.assertIn("VGVzdEZvbnRDb250ZW50", result)

    def test_offline_mode_with_missing_font(self):
        """Test behavior when requested font is not in the cache file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a font cache file without the requested font
            font_cache_path = Path(temp_dir) / "custom_fonts.json"
            mock_font_data = {
                "OtherFont": [
                    {
                        "style": "normal",
                        "weight": "400",
                        "unicode_range": "",
                        "type": "ttf",
                        "content": "T3RoZXJGb250Q29udGVudA==",
                    }
                ]
            }

            with open(font_cache_path, "w") as f:
                json.dump(mock_font_data, f)

            # Test with font not in cache
            result = get_google_font_for_embedding(
                "MissingFont", offline_mode=True, offline_font_file=str(font_cache_path)
            )

            # Should return empty string when font not found
            self.assertEqual(result, "")

    def test_create_interactive_plot_with_custom_font_file(self):
        """Test that create_interactive_plot passes font file path correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create font and JS cache files
            font_cache_path = Path(temp_dir) / "fonts.json"
            js_cache_path = Path(temp_dir) / "js.json"

            mock_font_data = {
                "Arial": [
                    {
                        "style": "normal",
                        "weight": "400",
                        "unicode_range": "",
                        "type": "ttf",
                        "content": "QXJpYWxGb250Q29udGVudA==",
                    }
                ]
            }

            # Need all required JS files for offline mode
            mock_js_data = {
                "https://unpkg.com/deck.gl@latest/dist.min.js": {
                    "encoded_content": "ZGVja2dsX2NvbnRlbnQ=",
                    "name": "unpkg_com_deck_gl_latest_dist_min_js",
                },
                "https://unpkg.com/apache-arrow@latest/Arrow.es2015.min.js": {
                    "encoded_content": "YXJyb3dfY29udGVudA==",
                    "name": "unpkg_com_apache_arrow_latest_Arrow_es2015_min_js",
                },
                "https://unpkg.com/d3@latest/dist/d3.min.js": {
                    "encoded_content": "ZDNfY29udGVudA==",
                    "name": "unpkg_com_d3_latest_dist_d3_min_js",
                },
                "https://unpkg.com/jquery@3.7.1/dist/jquery.min.js": {
                    "encoded_content": "anF1ZXJ5X2NvbnRlbnQ=",
                    "name": "unpkg_com_jquery_3_7_1_dist_jquery_min_js",
                },
                "https://unpkg.com/d3-cloud@1.2.7/build/d3.layout.cloud.js": {
                    "encoded_content": "ZDNfY2xvdWRfY29udGVudA==",
                    "name": "unpkg_com_d3_cloud_1_2_7_build_d3_layout_cloud_js",
                },
            }

            with open(font_cache_path, "w") as f:
                json.dump(mock_font_data, f)
            with open(js_cache_path, "w") as f:
                json.dump(mock_js_data, f)

            # Create plot with custom font file
            fig = datamapplot.create_interactive_plot(
                self.data_coords,
                self.labels,
                inline_data=False,
                offline_mode=True,
                offline_mode_font_data_file=str(font_cache_path),
                offline_mode_js_data_file=str(js_cache_path),
                font_family="Arial",
            )

            # Verify the plot was created successfully
            self.assertIsNotNone(fig)
            self.assertIsInstance(
                fig, datamapplot.interactive_rendering.InteractiveFigure
            )

    def test_offline_mode_without_custom_file_uses_default(self):
        """Test that offline mode falls back to default cache when no file specified."""
        with patch("datamapplot.offline_mode_caching.load_fonts") as mock_load_fonts:
            # Set up mock to return empty dict
            mock_load_fonts.return_value = {}

            # Call without custom file path
            result = get_google_font_for_embedding(
                "SomeFont", offline_mode=True, offline_font_file=None
            )

            # Verify it called load_fonts with None (default behavior)
            mock_load_fonts.assert_called_once_with(file_path=None)

    def test_online_mode_ignores_font_file_parameter(self):
        """Test that online mode ignores the offline font file parameter."""
        # Need to patch at the correct import location
        with (
            patch("datamapplot.fonts.can_reach_google_fonts", return_value=True),
            patch("datamapplot.fonts.query_google_fonts") as mock_query,
        ):

            # Set up mock
            mock_font = MagicMock()
            mock_font.url = "https://fonts.googleapis.com/font.ttf"
            mock_collection = MagicMock()
            mock_collection.__iter__ = lambda self: iter([mock_font])
            mock_collection.content = "@font-face { font-family: 'Test'; }"
            mock_query.return_value = mock_collection

            # Call in online mode with font file (should be ignored)
            result = get_google_font_for_embedding(
                "TestFont", offline_mode=False, offline_font_file="/path/to/fonts.json"
            )

            # Should query Google Fonts, not use the file
            mock_query.assert_called_once_with("TestFont")
            self.assertIn("@font-face", result)


if __name__ == "__main__":
    unittest.main()
