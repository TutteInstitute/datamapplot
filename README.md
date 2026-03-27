# datamapplot

`datamapplot` is a Python library designed to create beautiful, high-quality, and interactive visualizations of data maps. It leverages modern techniques like UMAP for dimensionality reduction and provides tools to render large datasets effectively, both as static images and interactive web-based plots.

## Features

*   **High-Quality Static Plots**: Generate publication-ready static plots with fine-grained control over aesthetics.
*   **Interactive Web Visualizations**: Create interactive plots that can be embedded in Jupyter notebooks or exported as standalone HTML files, powered by Deck.gl.
*   **Scalability**: Designed to handle large datasets efficiently.
*   **Customization**: Extensive options for customizing colors, labels, annotations, and more.
*   **Integration**: Seamlessly integrates with the Python data science ecosystem.

## Installation

YouYou can install `datamapplot` using `pip`:

```bash
pip install datamapplot
```

For interactive features, you might also need `jupyterlab` and `ipywidgets`:

```bash
pip install jupyterlab ipywidgets
jupyter labextension enable @jupyter-widgets/jupyterlab-manager
```

## Quick Start

Here's a minimal example to get you started:

```python
import numpy as np
import datamapplot

# Generate some sample data
data = np.random.rand(1000, 10)
labels = np.random.randint(0, 5, 1000)
hover_data = [f"Item {i}" for i in range(1000)]

# Create a datamap plot
fig, ax = datamapplot.create_plot(
    data,
    labels=labels,
    hover_text=hover_data,
    title="My First Data Map",
    # You can add many more customization options here
)

# Display the plot (for static plots)
fig.show()

# For interactive plots (in Jupyter notebooks)
# interactive_plot = datamapplot.create_interactive_plot(
#     data,
#     labels=labels,
#     hover_text=hover_data,
#     title="My First Interactive Data Map",
# )
# interactive_plot
```

## Documentation

For more detailed information, API reference, and advanced usage examples, please refer to the [official documentation](https://datamapplot.readthedocs.io/en/latest/).

## Contributing

We welcome contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to get started.

## License

`datamapplot` is released under the [MIT License](LICENSE).
