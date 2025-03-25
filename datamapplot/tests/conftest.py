import io
import logging
import pytest
from pathlib import Path
import requests
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import contextlib

matplotlib.use("Agg")

# Create logger without handlers - let pytest handle the output
logger = logging.getLogger("datamapplot.tests")
logger.setLevel(logging.INFO)
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

def pytest_configure(config):
    """Configure pytest options and logging"""
    # Configure log capturing - this handles the output formatting
    config.option.log_cli = True
    config.option.log_cli_level = "INFO"
    config.option.log_cli_format = "%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s)"
    config.option.log_cli_date_format = "%Y-%m-%d %H:%M:%S"


@pytest.fixture
def mock_plt_show(monkeypatch):
    """
    Fixture to mock plt.show() and prevent hanging
    """
    monkeypatch.setattr(plt, 'show', lambda: None)

@pytest.fixture
def mock_savefig():
    """
    Fixture that provides the context manager for mocking savefig.
    """
    @contextlib.contextmanager
    def _mock_savefig_context():
        original_savefig = plt.Figure.savefig

        def mock_save(self, *args, **kwargs):
            return self

        plt.Figure.savefig = mock_save
        try:
            yield
        finally:
            plt.Figure.savefig = original_savefig

    return _mock_savefig_context

@pytest.fixture
def mock_image_requests(monkeypatch, request):
    """
    Fixture to mock specific requests with local files from tests/images

    Usage:
    def test_example(mock_image_requests):
        mock_image_requests([
            'https://example.com/image.png'  # Will look for tests/images/image.png
        ])

    Note: This currently mocks image retrieval to remove a dependency on the internet. However, since the codebase itself
    fetchs fonts remotely, tests still require online access.
    """
    def _mock_requests(urls=None):
        urls_to_mock = set(urls or [])
        original_get = requests.get

        def mock_get(url, *args, **kwargs):

            if url in urls_to_mock:
                images_dir = Path(request.fspath).parent / 'images'
                filename = url.split('/')[-1]
                image_path = images_dir / filename

                if image_path.exists():
                    with open(image_path, 'rb') as f:
                        image_bytes = f.read()
                    mock_response = type('MockResponse', (object,), {
                        'raw': io.BytesIO(image_bytes),
                    })()
                    return mock_response
                raise FileNotFoundError(f"Mock file not found: {image_path}")

            return original_get(url, *args, **kwargs)

        monkeypatch.setattr(requests, 'get', mock_get)

    return _mock_requests

@pytest.fixture
def change_np_load_path(monkeypatch):
    """
    Fixture to modify np.load to use a specific directory and optionally limit dataset size

    Usage:
    def test_example(examples_dir, change_np_load_path):
        with change_np_load_path(examples_dir, max_points=10000):
            data = np.load("arxiv_ml_data_map.npy")
    """
    @contextlib.contextmanager
    def _patch_load(base_path, max_points=None):
        base_path = Path(base_path)

        original_load = np.load

        def patched_load(file, *args, **kwargs):
            file_path = Path(file)

            if not file_path.is_absolute():
                file_path = base_path / file_path

            data = original_load(str(file_path), *args, **kwargs)
            logger.info(f"{file_path} data original shape: {data.shape}")
            # If max_points is specified and this is a dataset file, limit the number of points
            if max_points is not None and isinstance(data, np.ndarray) and len(data.shape) > 0:
                file_str = str(file_path)
                if data.shape[0] > max_points:
                    new_data = data[:max_points]
                    logger.info(f"{file_path} data new shape: {new_data.shape}")
                    return new_data


            return data

        monkeypatch.setattr(np, 'load', patched_load)

        try:
            yield
        finally:
            monkeypatch.setattr(np, 'load', original_load)

    return _patch_load

@pytest.fixture
def change_read_feather_load_path(monkeypatch):
    """
    Fixture to modify pd.read_feather to use a specific directory and optionally limit dataset size

    Usage:
    def test_example(examples_dir, change_read_feather_load_path):
        with change_read_feather_load_path(examples_dir, max_points=10000):
            data = pd.read_feather("cord19_extra_data.arrow")
    """
    @contextlib.contextmanager
    def _patch_read(base_path, max_points=None):
        base_path = Path(base_path)

        original_read = pd.read_feather

        def patched_read(file, *args, **kwargs):
            file_path = Path(file)

            if not file_path.is_absolute():
                file_path = base_path / file_path

            data = original_read(str(file_path), *args, **kwargs)
            logger.info(f"{file_path} data original shape: {data.shape}")
            # If max_points is specified and this is a dataset file, limit the number of points
            if max_points is not None and len(data.shape) > 0:
                file_str = str(file_path)
                if len(data) > max_points:
                    new_data = data[:max_points]
                    logger.info(f"{file_path} data new shape: {new_data.shape}")
                    return new_data


            return data

        monkeypatch.setattr(pd, 'read_feather', patched_read)

        try:
            yield
        finally:
            monkeypatch.setattr(pd, 'read_feather', original_read)

    return _patch_read

@pytest.fixture
def examples_dir(request):
    """
    Fixture that returns the path to the examples directory
    """
    return Path(request.fspath).parent.parent.parent / "examples"

@pytest.fixture
def html_dir(request):
    """
    Fixture that returns the path to the html output directory
    """
    return Path(request.fspath).parent / "html"


