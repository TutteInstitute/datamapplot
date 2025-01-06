import numpy as np
from pathlib import Path
import pytest
import matplotlib.image as mpimg
from pathlib import Path
import importlib.util
import requests
import sys
import pytest
import matplotlib.pyplot as plt



@pytest.mark.mpl_image_compare(baseline_dir='baseline', style='default')
def test_plot_simple_arxiv(
    examples_dir, 
    mock_plt_show,
    mock_image_requests, 
    mock_savefig,
    change_np_load_path
):
    mock_image_requests([
        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/320px-ArXiv_logo_2022.svg.png"
    ])
    return run_static_examples_script('plot_simple_arxiv.py', examples_dir, change_np_load_path, mock_savefig)

@pytest.mark.mpl_image_compare(baseline_dir='baseline', style='default')
def test_plot_arxiv_ml(
    examples_dir, 
    mock_plt_show,
    mock_image_requests, 
    mock_savefig,
    change_np_load_path
):
    mock_image_requests([
        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/320px-ArXiv_logo_2022.svg.png"
    ])
    return run_static_examples_script('plot_arxiv_ml.py', examples_dir, change_np_load_path, mock_savefig)

def run_static_examples_script(script_filename, script_dir, change_np_load_path, mock_savefig):
    """
    Run an example script located in the examples directory with static output.

    Args:
        script_name (str): The name of the script to run (e.g., 'plot_arxiv_ml.py').
        examples_dir (str or Path): Path to the directory containing the script.
        change_np_load_path: Test mock for changing the loading path for np.load

    Returns:
        None
    """
    script_dir = Path(script_dir)
    script_name = Path(script_filename).stem
    script_path = script_dir / script_filename

    # Load and execute the script dynamically so we can use mocking
    spec = importlib.util.spec_from_file_location(
        script_name, str(script_path)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[script_name] = module

    with change_np_load_path(script_dir), mock_savefig():
        spec.loader.exec_module(module)
    return plt.gcf()


def test_mock_image_requests(mock_image_requests):
    mock_image_requests([
        'https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/320px-ArXiv_logo_2022.svg.png'
    ])
    response = requests.get('https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/ArXiv_logo_2022.svg/320px-ArXiv_logo_2022.svg.png')
    assert response.raw is not None