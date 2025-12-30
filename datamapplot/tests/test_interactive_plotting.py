from datamapplot.interactive_rendering import InteractiveFigure, render_html
import datamapplot
import sys
import importlib.util
from pathlib import Path
import pytest
import bz2
import gzip
import re
import numpy as np
import pandas as pd


### HTML Validation Helpers
def validate_html_structure(html_content: str) -> dict:
    """
    Validate that the HTML content has the required structure for a DataMapPlot interactive figure.
    
    Returns a dict with validation results.
    """
    results = {
        "has_doctype": html_content.strip().lower().startswith("<!doctype html"),
        "has_html_tag": "<html" in html_content.lower(),
        "has_head": "<head" in html_content.lower(),
        "has_body": "<body" in html_content.lower(),
        "has_title": "<title>" in html_content.lower(),
        "has_deck_container": 'id="deck-container"' in html_content or "id='deck-container'" in html_content,
        "has_datamap_init": "new DataMap(" in html_content or "DataMap" in html_content,
        "has_loading_indicator": 'id="loading"' in html_content,
        "has_script_tags": "<script" in html_content.lower(),
        "has_style_tags": "<style" in html_content.lower() or "stylesheet" in html_content.lower(),
    }
    results["is_valid"] = all(results.values())
    return results


def validate_inline_data(html_content: str) -> dict:
    """
    Validate inline data encoding in HTML content.
    """
    results = {
        "has_point_data": "pointDataEncoded" in html_content,
        "has_hover_data": "hoverDataEncoded" in html_content,
        "has_label_data": "labelDataEncoded" in html_content,
        "has_base64_data": re.search(r'[A-Za-z0-9+/=]{100,}', html_content) is not None,
    }
    results["is_valid"] = all(results.values())
    return results


def validate_offline_data_references(html_content: str, prefix: str) -> dict:
    """
    Validate that offline data file references exist in HTML content.
    """
    results = {
        "has_point_data_ref": f"{prefix}_point_data" in html_content,
        "has_meta_data_ref": f"{prefix}_meta_data" in html_content,
        "has_label_data_ref": f"{prefix}_label_data" in html_content,
    }
    results["is_valid"] = all(results.values())
    return results


### Tests for Example Scripts
@pytest.mark.interactive
def test_interactive_cord19(examples_dir, mock_image_requests, change_np_load_path, mock_interactive_save,
        mock_bz2_open, mock_display, mock_gzip_open, html_dir):
    """
    Test that the outputs files from running examples/plot_interactive_cord19.py all exist.

    UI testing of the resulting html output can be found in the interactive_tests directory.
    """
    mock_image_requests([
        "https://allenai.org/newsletters/archive/2023-03-newsletter_files/927c3ca8-6c75-862c-ee5d-81703ef10a8d.png"
    ])

    mock_interactive_save(html_dir)
    mock_bz2_open(examples_dir)
    mock_gzip_open(html_dir)

    output_path = run_interactive_examples_script(
        "plot_interactive_cord19.py",
        examples_dir,
        html_dir,
        change_np_load_path,
        destination_html="cord19.html"
    )
    assert output_path.exists()
    assert (html_dir / "cord_gallery_meta_data_0.zip").exists()
    assert (html_dir / "cord_gallery_meta_data_1.zip").exists()
    assert (html_dir / "cord_gallery_point_data_0.zip").exists()
    assert (html_dir / "cord_gallery_point_data_1.zip").exists()
    assert (html_dir / "cord_gallery_label_data.zip").exists()
    
    # Validate HTML structure
    html_content = output_path.read_text()
    validation = validate_html_structure(html_content)
    assert validation["is_valid"], f"HTML validation failed: {validation}"
    
    # Validate offline data references
    offline_validation = validate_offline_data_references(html_content, "cord_gallery")
    assert offline_validation["is_valid"], f"Offline data validation failed: {offline_validation}"


@pytest.mark.interactive
def test_interactive_arxiv_ml(examples_dir, mock_image_requests, change_np_load_path, mock_interactive_save,
        mock_bz2_open, mock_display, mock_gzip_open, html_dir):
    """
    Test that the outputs files from running examples/plot_interactive_arxiv_ml.py all exist.

    UI testing of the resulting html output can be found in the interactive_tests directory.
    """
    mock_image_requests([
        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/512px-ArXiv_logo_2022.svg.png"
    ])

    mock_interactive_save(html_dir)
    mock_bz2_open(examples_dir)
    mock_gzip_open(html_dir)

    output_path = run_interactive_examples_script(
        "plot_interactive_arxiv_ml.py",
        examples_dir,
        html_dir,
        change_np_load_path,
        destination_html="arxiv_ml.html"
    )
    assert output_path.exists()
    assert (html_dir / "arxivml_gallery_label_data.zip").exists()
    assert (html_dir / "arxivml_gallery_meta_data_0.zip").exists()
    assert (html_dir / "arxivml_gallery_point_data_0.zip").exists()
    
    # Validate HTML structure
    html_content = output_path.read_text()
    validation = validate_html_structure(html_content)
    assert validation["is_valid"], f"HTML validation failed: {validation}"


@pytest.mark.interactive
def test_interactive_arxiv_ml_topic_tree(examples_dir, mock_image_requests, change_np_load_path, 
        mock_interactive_save, mock_bz2_open, mock_display, mock_gzip_open, html_dir):
    """
    Test that the topic tree example generates valid output.
    """
    mock_image_requests([
        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/512px-ArXiv_logo_2022.svg.png"
    ])

    mock_interactive_save(html_dir)
    mock_bz2_open(examples_dir)
    mock_gzip_open(html_dir)

    output_path = run_interactive_examples_script(
        "plot_interactive_arxiv_ml_topic_tree.py",
        examples_dir,
        html_dir,
        change_np_load_path,
        destination_html="arxiv_ml_topic_tree.html"
    )
    assert output_path.exists()
    
    # Validate HTML structure
    html_content = output_path.read_text()
    validation = validate_html_structure(html_content)
    assert validation["is_valid"], f"HTML validation failed: {validation}"
    
    # Validate topic tree specific elements
    assert "topic-tree" in html_content.lower() or "TopicTree" in html_content


### Unit Tests for render_html function
@pytest.mark.interactive
class TestRenderHtmlBasic:
    """Basic unit tests for render_html function."""
    
    @pytest.fixture
    def simple_point_data(self):
        """Create simple point data for testing."""
        n_points = 100
        np.random.seed(42)
        return pd.DataFrame({
            "x": np.random.randn(n_points),
            "y": np.random.randn(n_points),
            "r": np.random.randint(0, 255, n_points, dtype=np.uint8),
            "g": np.random.randint(0, 255, n_points, dtype=np.uint8),
            "b": np.random.randint(0, 255, n_points, dtype=np.uint8),
            "a": np.full(n_points, 255, dtype=np.uint8),
            "hover_text": [f"Point {i}" for i in range(n_points)],
        })
    
    @pytest.fixture
    def simple_label_data(self):
        """Create simple label data for testing."""
        n_labels = 5
        np.random.seed(42)
        return pd.DataFrame({
            "x": np.random.randn(n_labels),
            "y": np.random.randn(n_labels),
            "r": np.random.randint(0, 255, n_labels, dtype=np.uint8),
            "g": np.random.randint(0, 255, n_labels, dtype=np.uint8),
            "b": np.random.randint(0, 255, n_labels, dtype=np.uint8),
            "a": np.full(n_labels, 255, dtype=np.uint8),
            "label": [f"Cluster {i}" for i in range(n_labels)],
            "size": np.random.uniform(10, 100, n_labels),
        })
    
    def test_render_html_inline_basic(self, simple_point_data, simple_label_data):
        """Test basic render_html with inline data."""
        # render_html returns a string, not InteractiveFigure
        html_content = render_html(
            simple_point_data,
            simple_label_data,
            inline_data=True,
            title="Test Plot",
            sub_title="Test Subtitle",
        )
        
        assert isinstance(html_content, str)
        
        # Validate HTML structure
        validation = validate_html_structure(html_content)
        assert validation["is_valid"], f"HTML validation failed: {validation}"
        
        # Validate inline data
        inline_validation = validate_inline_data(html_content)
        assert inline_validation["is_valid"], f"Inline data validation failed: {inline_validation}"
        
        # Check title is in output
        assert "Test Plot" in html_content
        assert "Test Subtitle" in html_content
    
    def test_render_html_darkmode(self, simple_point_data, simple_label_data):
        """Test render_html with darkmode enabled."""
        html_content = render_html(
            simple_point_data,
            simple_label_data,
            inline_data=True,
            darkmode=True,
        )
        
        validation = validate_html_structure(html_content)
        assert validation["is_valid"], f"HTML validation failed: {validation}"
    
    def test_render_html_with_search(self, simple_point_data, simple_label_data):
        """Test render_html with search enabled."""
        html_content = render_html(
            simple_point_data,
            simple_label_data,
            inline_data=True,
            enable_search=True,
        )
        
        validation = validate_html_structure(html_content)
        assert validation["is_valid"], f"HTML validation failed: {validation}"
        
        # Check for search-related elements
        assert "text-search" in html_content or "search" in html_content.lower()
    
    def test_render_html_custom_font(self, simple_point_data, simple_label_data):
        """Test render_html with custom font family."""
        html_content = render_html(
            simple_point_data,
            simple_label_data,
            inline_data=True,
            font_family="Arial",
        )
        
        validation = validate_html_structure(html_content)
        assert validation["is_valid"], f"HTML validation failed: {validation}"


@pytest.mark.interactive
class TestRenderHtmlAdvanced:
    """Advanced tests for render_html with more features."""
    
    @pytest.fixture
    def point_data_with_extras(self):
        """Create point data with extra columns for testing."""
        n_points = 50
        np.random.seed(42)
        return pd.DataFrame({
            "x": np.random.randn(n_points),
            "y": np.random.randn(n_points),
            "r": np.random.randint(0, 255, n_points, dtype=np.uint8),
            "g": np.random.randint(0, 255, n_points, dtype=np.uint8),
            "b": np.random.randint(0, 255, n_points, dtype=np.uint8),
            "a": np.full(n_points, 255, dtype=np.uint8),
            "hover_text": [f"Point {i}" for i in range(n_points)],
            "size": np.random.uniform(0.5, 2.0, n_points),
        })
    
    @pytest.fixture
    def label_data_with_polygons(self):
        """Create label data with polygon bounds for testing."""
        n_labels = 3
        np.random.seed(42)
        return pd.DataFrame({
            "x": np.random.randn(n_labels),
            "y": np.random.randn(n_labels),
            "r": np.random.randint(0, 255, n_labels, dtype=np.uint8),
            "g": np.random.randint(0, 255, n_labels, dtype=np.uint8),
            "b": np.random.randint(0, 255, n_labels, dtype=np.uint8),
            "a": np.full(n_labels, 255, dtype=np.uint8),
            "label": [f"Cluster {i}" for i in range(n_labels)],
            "size": np.random.uniform(10, 100, n_labels),
        })
    
    def test_render_html_with_histogram(self, point_data_with_extras, label_data_with_polygons):
        """Test render_html with histogram data."""
        n_points = len(point_data_with_extras)
        histogram_values = np.random.randn(n_points)
        
        html_content = render_html(
            point_data_with_extras,
            label_data_with_polygons,
            inline_data=True,
            histogram_data=histogram_values,
        )
        
        validation = validate_html_structure(html_content)
        assert validation["is_valid"], f"HTML validation failed: {validation}"
        
        # Check for histogram-related elements
        assert "histogram" in html_content.lower() or "D3Histogram" in html_content
    
    def test_render_html_with_custom_css(self, point_data_with_extras, label_data_with_polygons):
        """Test render_html with custom CSS."""
        custom_css = ".custom-class { color: red; }"
        
        html_content = render_html(
            point_data_with_extras,
            label_data_with_polygons,
            inline_data=True,
            custom_css=custom_css,
        )
        
        validation = validate_html_structure(html_content)
        assert validation["is_valid"], f"HTML validation failed: {validation}"
        assert ".custom-class" in html_content
    
    def test_render_html_with_custom_js(self, point_data_with_extras, label_data_with_polygons):
        """Test render_html with custom JavaScript."""
        custom_js = "console.log('test');"
        
        html_content = render_html(
            point_data_with_extras,
            label_data_with_polygons,
            inline_data=True,
            custom_js=custom_js,
        )
        
        validation = validate_html_structure(html_content)
        assert validation["is_valid"], f"HTML validation failed: {validation}"
        assert "console.log" in html_content
    
    def test_render_html_with_on_click(self, point_data_with_extras, label_data_with_polygons):
        """Test render_html with on_click handler."""
        html_content = render_html(
            point_data_with_extras,
            label_data_with_polygons,
            inline_data=True,
            on_click="window.open(`http://example.com?q={hover_text}`)",
        )
        
        validation = validate_html_structure(html_content)
        assert validation["is_valid"], f"HTML validation failed: {validation}"


@pytest.mark.interactive  
class TestInteractiveFigure:
    """Tests for the InteractiveFigure class."""
    
    def test_interactive_figure_repr(self):
        """Test InteractiveFigure string representation."""
        fig = InteractiveFigure("<html></html>", width="100%", height=600)
        repr_str = repr(fig)
        assert "InteractiveFigure" in repr_str
        assert "100%" in repr_str
        assert "600" in repr_str
    
    def test_interactive_figure_str(self):
        """Test InteractiveFigure string conversion."""
        html_str = "<html><body>Test</body></html>"
        fig = InteractiveFigure(html_str)
        assert str(fig) == html_str
    
    def test_interactive_figure_save(self, tmp_path):
        """Test InteractiveFigure save method."""
        html_str = "<html><body>Test Content</body></html>"
        fig = InteractiveFigure(html_str)
        
        output_file = tmp_path / "test_output.html"
        fig.save(str(output_file))
        
        assert output_file.exists()
        assert output_file.read_text() == html_str


### Tests using create_interactive_plot API
@pytest.mark.interactive
class TestCreateInteractivePlot:
    """Tests for the high-level create_interactive_plot API."""
    
    def test_create_interactive_plot_minimal(self):
        """Test create_interactive_plot with minimal arguments."""
        n_points = 100
        np.random.seed(42)
        data_map = np.random.randn(n_points, 2)
        labels = np.array(["A"] * 30 + ["B"] * 30 + ["C"] * 40)
        
        result = datamapplot.create_interactive_plot(
            data_map,
            labels,
            inline_data=True,
        )
        
        assert isinstance(result, InteractiveFigure)
        html_content = str(result)
        validation = validate_html_structure(html_content)
        assert validation["is_valid"], f"HTML validation failed: {validation}"
    
    def test_create_interactive_plot_with_hover_text(self):
        """Test create_interactive_plot with hover text."""
        n_points = 50
        np.random.seed(42)
        data_map = np.random.randn(n_points, 2)
        labels = np.array(["A"] * 25 + ["B"] * 25)
        hover_text = np.array([f"Item {i}" for i in range(n_points)])
        
        result = datamapplot.create_interactive_plot(
            data_map,
            labels,
            hover_text=hover_text,
            inline_data=True,
        )
        
        assert isinstance(result, InteractiveFigure)
        html_content = str(result)
        validation = validate_html_structure(html_content)
        assert validation["is_valid"], f"HTML validation failed: {validation}"
    
    def test_create_interactive_plot_multiple_label_layers(self):
        """Test create_interactive_plot with multiple label layers."""
        n_points = 100
        np.random.seed(42)
        data_map = np.random.randn(n_points, 2)
        labels_layer1 = np.array(["A"] * 50 + ["B"] * 50)
        labels_layer2 = np.array(["X"] * 25 + ["Y"] * 25 + ["Z"] * 50)
        
        result = datamapplot.create_interactive_plot(
            data_map,
            labels_layer1,
            labels_layer2,
            inline_data=True,
        )
        
        assert isinstance(result, InteractiveFigure)
        html_content = str(result)
        validation = validate_html_structure(html_content)
        assert validation["is_valid"], f"HTML validation failed: {validation}"

### Fixtures
@pytest.fixture
def mock_display(monkeypatch):
    """Mock display functionality for InteractiveFigure to do nothing"""
    def _mock_display(html_output_dir):
        def mock_display(*args, **kwargs):
            pass

        # Add it to the builtins so it's available everywhere
        monkeypatch.setattr('builtins.display', mock_display)
    
    return _mock_display

@pytest.fixture
def mock_interactive_save(monkeypatch):
    """Mock the save method of InteractiveFigure to append the html_output_dir directory"""
    def _mock_save(html_output_dir):
        original_save = InteractiveFigure.save

        def save(self, filename, *args, **kwargs):
            output_path = html_output_dir / filename
            return original_save(self, str(output_path), *args, **kwargs)
        
        monkeypatch.setattr('datamapplot.interactive_rendering.InteractiveFigure.save', save)
    
    return _mock_save

@pytest.fixture
def mock_bz2_open(monkeypatch):
    """Mock bz2.open to look for files in the script_dir directory"""
    def _mock_bz2_open(script_dir):
        original_bz2_open = bz2.open
        
        def bz2_open(filename, *args, **kwargs):
            filename = Path(filename)
            
            if not filename.is_absolute():
                filepath = script_dir / filename
            else:
                filepath = filename

            return original_bz2_open(filepath, *args, **kwargs)
        
        monkeypatch.setattr(bz2, 'open', bz2_open)
    
    return _mock_bz2_open

@pytest.fixture
def mock_gzip_open(monkeypatch):
    """Mock gzip.open to write files to the output_dir directory"""
    def _mock_gzip_open(output_dir):
        original_gzip_open = gzip.open
        
        def gzip_open(filename, *args, **kwargs):
            filename = Path(filename)
            
            if not filename.is_absolute():
                filepath = output_dir / filename
            else:
                filepath = filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            return original_gzip_open(filepath, *args, **kwargs)
        
        monkeypatch.setattr(gzip, 'open', gzip_open)
    
    return _mock_gzip_open


### Helper Scripts
def run_interactive_examples_script(
    script_filename: str, 
    script_dir: Path,
    html_output_dir: Path,
    change_np_load_path,
    destination_html: str
):
    """
    Run an example script that generates interactive HTML output.
    
    Args:
        script_filename (str): The name of the script to run (e.g., 'plot_cord19_interactive.py')
        script_dir (Path): Path to the directory containing the script
        html_output_dir (Path): Directory where HTML outputs should be saved
        change_np_load_path: Test fixture to mock numpy.load paths
        destination_html (str): The name of the destination html file
        
    Returns:
        Path: Path to the generated HTML file
    """
    script_dir = Path(script_dir)
    script_name = Path(script_filename).stem
    script_path = script_dir / script_filename
    
    html_output_dir.mkdir(parents=True, exist_ok=True)
    
    spec = importlib.util.spec_from_file_location(script_name, str(script_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[script_name] = module

    
    with change_np_load_path(script_dir):
        spec.loader.exec_module(module)
    
        html_files = list(html_output_dir.glob('*.html'))
        html_output = html_output_dir / destination_html
        if not (html_output in html_files):
            raise RuntimeError(f"No HTML file was generated in {html_output_dir}")
        
        return html_output


