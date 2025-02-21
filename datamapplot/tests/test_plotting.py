import numpy as np
import os
from pathlib import Path
import pytest
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from pathlib import Path
import importlib.util
import requests
import sys
import pytest

custom_style = {
    "figure.constrained_layout.use": True,
    "figure.dpi": 95,
    "figure.constrained_layout.h_pad": 0.05,
    "figure.constrained_layout.w_pad": 0.05,
}

@pytest.mark.mpl_image_compare(baseline_dir='baseline', style='default')
def test_plot_cord19(
    examples_dir,
    mock_plt_show,
    mock_image_requests,
    mock_savefig,
    change_np_load_path
):
    """
    Test that the output figure from 'examples/plot_cord19.py' matches baseline
    """
    mock_image_requests([
        "https://allenai.org/newsletters/archive/2023-03-newsletter_files/927c3ca8-6c75-862c-ee5d-81703ef10a8d.png"
    ])
    fig = run_static_examples_script('plot_cord19.py', examples_dir, change_np_load_path, mock_savefig)
    return fig

@pytest.mark.mpl_image_compare(baseline_dir='baseline', style='default')
def test_plot_arxiv_ml(
    examples_dir,
    mock_plt_show,
    mock_image_requests,
    mock_savefig,
    change_np_load_path
):
    """
    Test that the output figure from 'examples/plot_arxiv_ml.py' matches baseline
    """
    mock_image_requests([
        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/320px-ArXiv_logo_2022.svg.png"
    ])
    fig = run_static_examples_script('plot_arxiv_ml.py', examples_dir, change_np_load_path, mock_savefig)
    return fig

@pytest.mark.mpl_image_compare(baseline_dir='baseline', style='default', tolerance=20)
def test_plot_arxiv_ml_word_cloud(
    examples_dir,
    mock_plt_show,
    mock_image_requests,
    mock_savefig,
    change_np_load_path
):
    """
    Test that the output figure from 'examples/plot_arxiv_ml_word_cloud.py' matches baseline.
    """
    mock_image_requests([
        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/320px-ArXiv_logo_2022.svg.png"
    ])
    fig = run_static_examples_script('plot_arxiv_ml_word_cloud.py', examples_dir, change_np_load_path, mock_savefig)
    return fig

@pytest.mark.mpl_image_compare(baseline_dir='baseline', style=custom_style, tolerance=35)
#@pytest.mark.xfail(os.environ.get('TF_BUILD') == 'True', reason="Image dimensions differ slightly in CI", strict=False)
def test_plot_wikipedia(
    examples_dir,
    mock_plt_show,
    mock_image_requests,
    mock_savefig,
    change_np_load_path
):
    """
    Test that the output figure from 'examples/plot_wikipedia.py' matches baseline.

    Note this currently has a fairly high tolerance set. The labels often get permuted in this example, and they are
    not in the same places. Still deciding what to consider a pass or a fail and how strictly deterministic this 
    test should be. It should pass most of the time with RMS 30.
    """
    mock_image_requests([
        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/320px-ArXiv_logo_2022.svg.png"
    ])
    fig = run_static_examples_script('plot_wikipedia.py', examples_dir, change_np_load_path, mock_savefig)
    return fig

@pytest.mark.mpl_image_compare(baseline_dir='baseline', style=custom_style)
#@pytest.mark.xfail(os.environ.get('TF_BUILD') == 'True', reason="Image dimensions differ slightly in CI", strict=False)
def test_plot_simple_arxiv(
    examples_dir,
    mock_plt_show,
    mock_image_requests,
    mock_savefig,
    change_np_load_path
):
    """
    Test that the output figure from 'examples/plot_simple_arxiv.py' matches baseline.
    """
    mock_image_requests([
        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/320px-ArXiv_logo_2022.svg.png"
    ])
    fig = run_static_examples_script('plot_simple_arxiv.py', examples_dir, change_np_load_path, mock_savefig)
    return fig

def run_static_examples_script(script_filename, script_dir, change_np_load_path, mock_savefig):
    """
    Run an example script located in the examples directory with static output.

    Args:
        script_filename (str): The name of the script to run (e.g., 'plot_arxiv_ml.py').
        script_dir (str or Path): Path to the directory containing the script.
        change_np_load_path: Test fixture to mock for changing the loading path for np.load
        mock_savefig: Test fixture to move savefig in the example so there are no side effects

    Returns:
        matplotlib figure
    """
    script_dir = Path(script_dir)
    script_name = Path(script_filename).stem
    script_path = script_dir / script_filename

    # Setup to load and execute the script dynamically so we can use mocking
    spec = importlib.util.spec_from_file_location(
        script_name, str(script_path)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[script_name] = module

    # Run the script with the necessary test fixtures
    with change_np_load_path(script_dir), mock_savefig():
        spec.loader.exec_module(module)

    return plt.gcf()

def test_mock_image_requests(mock_image_requests):
    """
    Test that the mock_image_requests fixture works as expected
    """
    mock_image_requests([
        'https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/320px-ArXiv_logo_2022.svg.png'
    ])
    response = requests.get('https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/320px-ArXiv_logo_2022.svg.png')
    assert response.raw is not None