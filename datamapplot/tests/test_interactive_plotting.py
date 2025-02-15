from datamapplot.interactive_rendering import InteractiveFigure
import sys
import importlib.util
from pathlib import Path
import pytest
import bz2
import gzip

### Tests
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


