import io
import pytest
from pathlib import Path
import requests
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import contextlib

matplotlib.use("Agg")

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
    Fixture to modify np.load to use a specific directory

    Usage:
    def test_example(examples_dir, change_np_load_path):
        with change_np_load_path(examples_dir):
            data = np.load("arxiv_ml_data_map.npy")
    """
    @contextlib.contextmanager
    def _patch_load(base_path):
        base_path = Path(base_path)

        original_load = np.load

        def patched_load(file, *args, **kwargs):
            file_path = Path(file)

            if not file_path.is_absolute():
                file_path = base_path / file_path

            return original_load(str(file_path), *args, **kwargs)

        monkeypatch.setattr(np, 'load', patched_load)

        try:
            yield
        finally:
            monkeypatch.setattr(np, 'load', original_load)

    return _patch_load

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


