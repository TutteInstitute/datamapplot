from datamapplot.interactive_rendering import InteractiveFigure
import contextlib
import datamapplot
import sys
import importlib.util
from pathlib import Path
import pytest
import bz2
import gzip
from io import BytesIO


### Tests
@pytest.mark.interactive
@pytest.mark.slow
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
        destination_html="cord19.html",
        load_handlers=[change_np_load_path],
    )
    assert output_path.exists()
    assert (html_dir / "cord_gallery_meta_data_0.zip").exists()
    assert (html_dir / "cord_gallery_meta_data_1.zip").exists()
    assert (html_dir / "cord_gallery_point_data_0.zip").exists()
    assert (html_dir / "cord_gallery_point_data_1.zip").exists()
    assert (html_dir / "cord_gallery_label_data.zip").exists()

@pytest.mark.interactive
@pytest.mark.fast
def test_interactive_cord19_small(examples_dir, mock_image_requests, change_np_load_path, mock_interactive_save,
        mock_bz2_open, mock_display, mock_gzip_open, html_dir):
    """
    Test that the outputs files from running examples/plot_interactive_cord19.py all exist.
    Uses a reduced dataset to size max_points for faster test execution.

    UI testing of the resulting html output can be found in the interactive_tests directory.
    """
    mock_image_requests([
        "https://allenai.org/newsletters/archive/2023-03-newsletter_files/927c3ca8-6c75-862c-ee5d-81703ef10a8d.png"
    ])
    max_points = 250000 # Reduced by about half
    destination_html=f"cord19_{max_points}.html"
    mock_interactive_save(html_dir, destination_html, max_points=max_points)
    mock_bz2_open(examples_dir, max_points=max_points)
    mock_gzip_open(html_dir)

    output_path = run_interactive_examples_script(
        "plot_interactive_cord19.py",
        examples_dir,
        html_dir,
        destination_html,
        load_handlers=[change_np_load_path],
        max_points=max_points
    )
    assert output_path.exists()
    assert (html_dir / f"cord_gallery_{max_points}_meta_data_0.zip").exists()
    assert (html_dir / f"cord_gallery_{max_points}_point_data_0.zip").exists()
    assert (html_dir / f"cord_gallery_{max_points}_label_data.zip").exists()

@pytest.mark.interactive
@pytest.mark.fast
def test_interactive_cord19_custom_small(examples_dir, mock_image_requests, change_np_load_path, mock_interactive_save,
        mock_bz2_open, mock_display, mock_gzip_open, html_dir, change_read_feather_load_path):
    """
    Test that the outputs files from running examples/plot_interactive_custom_cord19.py all exist.
    Uses a reduced dataset to size max_points for faster test execution.

    UI testing of the resulting html output can be found in the interactive_tests directory.
    """
    mock_image_requests([
        "https://allenai.org/newsletters/archive/2023-03-newsletter_files/927c3ca8-6c75-862c-ee5d-81703ef10a8d.png"
    ])
    max_points = 250000 # Reduced by about half
    destination_html=f"custom_cord19_{max_points}.html"
    mock_interactive_save(html_dir, destination_html, max_points=max_points)
    mock_bz2_open(examples_dir, max_points=max_points)
    mock_gzip_open(html_dir)

    output_path = run_interactive_examples_script(
        "plot_interactive_custom_cord19.py",
        examples_dir,
        html_dir,
        destination_html,
        load_handlers = [change_np_load_path, change_read_feather_load_path],
        max_points=max_points
    )
    assert output_path.exists()
    assert (html_dir / f"custom_cord_gallery_{max_points}_meta_data_0.zip").exists()
    assert (html_dir / f"custom_cord_gallery_{max_points}_point_data_0.zip").exists()
    assert (html_dir / f"custom_cord_gallery_{max_points}_label_data.zip").exists()

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
        "arxiv_ml.html",
        load_handlers = [change_np_load_path],
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
    """
    Mock the save method of InteractiveFigure and modify create_interactive_plot
    to handle destination_html and offline_data_prefix customization.

    Args:
        html_output_dir: Directory where HTML outputs should be saved
        destination_html: Optional specific filename to use for saving
        max_points: Optional number of max points to insert into offline_data_prefix
    """
    def _mock_save(html_output_dir, destination_html=None, max_points=None):

        # Patch the InteractiveFigure.save method
        original_save = InteractiveFigure.save

        def patched_save(self, filename, *args, **kwargs):
            filename_to_use = destination_html if destination_html else filename
            output_path = html_output_dir / filename_to_use
            return original_save(self, str(output_path), *args, **kwargs)

        monkeypatch.setattr('datamapplot.interactive_rendering.InteractiveFigure.save', patched_save)

        # Patch datamapplot.create_interactive_plot to modify offline_data_prefix
        if max_points is not None:
            original_create_interactive_plot = datamapplot.create_interactive_plot

            def patched_create_interactive_plot(*args, **kwargs):
                if 'offline_data_prefix' in kwargs:
                    original_prefix = kwargs['offline_data_prefix']
                    kwargs['offline_data_prefix'] = f"{original_prefix}_{max_points}"

                return original_create_interactive_plot(*args, **kwargs)

            monkeypatch.setattr(datamapplot, 'create_interactive_plot', patched_create_interactive_plot)

    return _mock_save


@pytest.fixture
def mock_bz2_open(monkeypatch):
    """
    Mock bz2.open to look for files in the script_dir directory and optionally limit dataset size

    Usage:
    def test_example(examples_dir, mock_bz2_open):
        mock_bz2_open(examples_dir, max_points=10000)
    """
    def _mock_bz2_open(script_dir, max_points=None):
        original_bz2_open = bz2.open

        def bz2_open(filename, *args, **kwargs):
            filename = Path(filename)

            if not filename.is_absolute():
                filepath = script_dir / filename
            else:
                filepath = filename

            file_obj = original_bz2_open(filepath, *args, **kwargs)

            # If max_points is specified and this is the hover text file, limit the number of lines
            if max_points is not None and "cord19_large_hover_text.txt.bz2" in str(filepath):
                mode = kwargs.get('mode', args[0] if args else 'r')

                if 'r' in mode:  # Only limit when reading
                    lines = []
                    for i, line in enumerate(file_obj):
                        if i >= max_points:
                            break
                        lines.append(line)

                    file_obj.close()

                    # Create a mock file-like object
                    mock_file = BytesIO(b''.join(lines))

                    # Create a simple wrapper that behaves like a bz2 file
                    class MockBZ2File:
                        def __init__(self, data, mode):
                            self.data = data
                            self.mode = mode

                        def __iter__(self):
                            self.data.seek(0)
                            return self

                        def __next__(self):
                            line = self.data.readline()
                            if not line:
                                raise StopIteration
                            return line

                        def read(self):
                            self.data.seek(0)
                            return self.data.read()

                        def readlines(self):
                            self.data.seek(0)
                            return self.data.readlines()

                        def close(self):
                            self.data.close()

                    return MockBZ2File(mock_file, mode)

            return file_obj

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
    script_filename,
    script_dir,
    html_output_dir,
    destination_html,
    load_handlers = None,
    max_points = None
):
    """
    Run an example script that generates interactive HTML output with an option to limit dataset size.

    Args:
        script_filename (str): The name of the script to run (e.g., 'plot_cord19_interactive.py')
        script_dir (Path): Path to the directory containing the script
        html_output_dir (Path): Directory where HTML outputs should be saved
        change_np_load_path: Test fixture for numpy.load path context
        destination_html (str): The name of the destination html file
        load_handlers (list, optional): List of context managers to use for loading data
        max_points (int, optional): Maximum number of points to use in the dataset

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


    with contextlib.ExitStack() as stack:
        if load_handlers:
            for handler in load_handlers:
                stack.enter_context(handler(script_dir, max_points=max_points))

        spec.loader.exec_module(module)

        html_files = list(html_output_dir.glob('*.html'))
        html_output = html_output_dir / destination_html
        if not (html_output in html_files):
            raise RuntimeError(f"No HTML file was generated in {html_output_dir}")

        return html_output


