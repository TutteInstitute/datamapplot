"""
Example demonstrating the new offline_data_path parameter for better control
over where data files are saved when inline_data=False.
"""

import numpy as np
import datamapplot
from pathlib import Path

# Generate example data
np.random.seed(42)
data_coords = np.random.randn(1000, 2) * 10
labels = np.random.choice(
    ["Category A", "Category B", "Category C", "Unlabelled"],
    size=1000,
    p=[0.3, 0.3, 0.3, 0.1],
)

# Example 1: Using the new offline_data_path parameter
print("Example 1: Saving data files to a specific directory")
output_dir = Path("output/interactive_plots")
fig = datamapplot.create_interactive_plot(
    data_coords,
    labels,
    inline_data=False,
    offline_data_path=output_dir / "example_plot",
    title="Example with offline_data_path",
)

# Save the HTML file in the same directory
output_dir.mkdir(parents=True, exist_ok=True)
fig.save(str(output_dir / "example_plot.html"))
print(f"Files saved to: {output_dir}")
print("- example_plot.html")
print("- example_plot_point_data_0.zip")
print("- example_plot_meta_data_0.zip")
print("- example_plot_label_data.zip")

# Example 2: Backward compatibility with offline_data_prefix
print("\nExample 2: Using offline_data_prefix (backward compatibility)")
fig2 = datamapplot.create_interactive_plot(
    data_coords,
    labels,
    inline_data=False,
    offline_data_prefix="legacy_plot",
    title="Example with offline_data_prefix",
)
fig2.save("legacy_plot.html")
print("Files saved to current directory with prefix 'legacy_plot'")

# Example 3: Using Path objects
print("\nExample 3: Using pathlib.Path objects")
output_path = Path("visualizations") / "datamaps" / "analysis_2025"
fig3 = datamapplot.create_interactive_plot(
    data_coords,
    labels,
    inline_data=False,
    offline_data_path=output_path,
    title="Example with Path object",
)

# The directory is automatically created
fig3.save(str(output_path.parent / "analysis_2025.html"))
print(f"Files saved to: {output_path.parent}")
