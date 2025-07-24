import unittest
import numpy as np
import tempfile
from pathlib import Path
from datamapplot import create_interactive_plot


class TestOfflineDataPath(unittest.TestCase):
    """Test the offline_data_path parameter functionality."""

    def setUp(self):
        """Set up test data."""
        np.random.seed(42)
        self.data_coords = np.random.randn(100, 2)
        self.labels = np.random.choice(["A", "B", "C"], size=100)

    def test_backward_compatibility_with_prefix(self):
        """Test that offline_data_prefix still works for backward compatibility."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp directory to avoid polluting the project
            import os

            original_dir = os.getcwd()
            os.chdir(tmpdir)

            try:
                fig = create_interactive_plot(
                    self.data_coords,
                    self.labels,
                    inline_data=False,
                    offline_data_prefix="test_prefix",
                )

                # Check files are created with the prefix
                assert Path("test_prefix_point_data_0.zip").exists()
                assert Path("test_prefix_label_data.zip").exists()
                assert Path("test_prefix_meta_data_0.zip").exists()
            finally:
                os.chdir(original_dir)

    def test_offline_data_path_with_directory(self):
        """Test offline_data_path with a directory path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output" / "data" / "myplot"

            fig = create_interactive_plot(
                self.data_coords,
                self.labels,
                inline_data=False,
                offline_data_path=str(output_path),
            )

            # Check directory was created
            assert output_path.parent.exists()

            # Check files are created in the correct location
            assert (output_path.parent / "myplot_point_data_0.zip").exists()
            assert (output_path.parent / "myplot_label_data.zip").exists()
            assert (output_path.parent / "myplot_meta_data_0.zip").exists()

    def test_offline_data_path_with_path_object(self):
        """Test offline_data_path with a Path object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "plots" / "viz"

            fig = create_interactive_plot(
                self.data_coords,
                self.labels,
                inline_data=False,
                offline_data_path=output_path,
            )

            # Check files are created
            assert (output_path.parent / "viz_point_data_0.zip").exists()
            assert (output_path.parent / "viz_label_data.zip").exists()

    def test_offline_data_path_creates_nested_directories(self):
        """Test that nested directories are created if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a deeply nested path that doesn't exist
            output_path = Path(tmpdir) / "a" / "b" / "c" / "d" / "plot"

            fig = create_interactive_plot(
                self.data_coords,
                self.labels,
                inline_data=False,
                offline_data_path=output_path,
            )

            # Check all directories were created
            assert output_path.parent.exists()
            assert (output_path.parent / "plot_point_data_0.zip").exists()

    def test_offline_data_path_with_extension(self):
        """Test offline_data_path when user provides a path with extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # User might accidentally include .html extension
            output_path = Path(tmpdir) / "output" / "myplot.html"

            fig = create_interactive_plot(
                self.data_coords,
                self.labels,
                inline_data=False,
                offline_data_path=str(output_path),
            )

            # Should strip the extension and use the stem
            assert (output_path.parent / "myplot_point_data_0.zip").exists()
            assert (output_path.parent / "myplot_label_data.zip").exists()
