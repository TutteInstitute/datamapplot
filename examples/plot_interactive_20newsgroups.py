"""
Interactive 20 Newsgroups with Widget Configuration
---------------------------------------------------

Demonstrating interactive plotting with the 20 Newsgroups dataset and
the analyst widget configuration preset.

This example shows how to:
- Load data from Hugging Face datasets
- Use the 'analyst' preset widget configuration
- Work with text classification data

The 20 Newsgroups dataset is a classic text classification dataset
containing posts from 20 different newsgroups.
"""

import numpy as np
import datamapplot


# Note: This example requires the 'datasets' package from Hugging Face
# Install with: pip install datasets
try:
    from datasets import load_dataset

    # Load the pre-embedded 20 Newsgroups dataset from Hugging Face
    dataset = load_dataset("lmcinnes/20newsgroups_embedded", split="train")

    # Extract the data map (2D coordinates)
    data_map = np.array(dataset["datamap"])

    # Get newsgroup categories as labels
    labels = np.array(dataset["newsgroup"])

    # Get the text content for hover (truncated for display)
    hover_text = np.array(
        [text[:200] + "..." if len(text) > 200 else text for text in dataset["text"]]
    )

    # Create the interactive plot
    # Using legacy parameters for simplicity - these automatically create widgets
    plot = datamapplot.create_interactive_plot(
        data_map,
        labels,
        hover_text=hover_text,
        title="20 Newsgroups",
        sub_title="Classic text classification dataset",
        font_family="Roboto",
        enable_search=True,
        cluster_boundary_polygons=True,
        darkmode=True,
        inline_data=False,
        offline_data_prefix="newsgroups_gallery",
    )
    plot.save("20newsgroups.html")
    plot

except ImportError:
    print("This example requires the 'datasets' package from Hugging Face.")
    print("Install with: pip install datasets")
    print("\nAlternatively, you can load data manually from:")
    print("https://huggingface.co/datasets/lmcinnes/20newsgroups_embedded")
