"""
Example demonstrating the use_system_fonts parameter to avoid downloading
fonts from Google Fonts. This is useful when working offline or behind a firewall.
"""

import numpy as np

import datamapplot

# Generate example data
np.random.seed(42)
n_samples = 1000
n_clusters = 5

# Create cluster centers
centers = np.random.randn(n_clusters, 2) * 10

# Generate data points around centers
data_coords = []
labels = []

for i, center in enumerate(centers):
    n_points = n_samples // n_clusters
    cluster_data = np.random.randn(n_points, 2) + center
    data_coords.append(cluster_data)
    labels.extend([f"Cluster {i+1}"] * n_points)

# Add some noise points
noise_points = np.random.uniform(-15, 15, (n_samples // 10, 2))
data_coords.append(noise_points)
labels.extend(["Unlabelled"] * len(noise_points))

# Combine all data
data_coords = np.vstack(data_coords)
labels = np.array(labels)

print("Creating plot with Google Fonts download (default behavior)...")
fig1, ax1 = datamapplot.create_plot(
    data_coords,
    labels,
    title="With Google Fonts",
    sub_title="This plot attempts to download fonts from Google",
    font_family="Roboto",
    use_system_fonts=False,  # Default behavior
    verbose=True,
)
fig1.savefig("example_with_google_fonts.png", dpi=150, bbox_inches="tight")

print("\nCreating plot with system fonts only...")
fig2, ax2 = datamapplot.create_plot(
    data_coords,
    labels,
    title="With System Fonts Only",
    sub_title="This plot uses only locally installed fonts",
    font_family="Arial",  # Use a common system font
    use_system_fonts=True,  # Skip Google Fonts download
    verbose=True,
)
fig2.savefig("example_with_system_fonts.png", dpi=150, bbox_inches="tight")

print("\nDone! Check the generated PNG files to see the difference.")
print(
    "Note: When use_system_fonts=True, make sure to specify fonts that are installed on your system."
)
