"""
Example demonstrating offline mode with custom font file paths.
This addresses issue #112 where offline mode would fail when specifying individual files.
"""

import numpy as np
import datamapplot
import tempfile
import json
from pathlib import Path

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

print("Creating example with custom font cache file...")

# Create a temporary directory for demonstration
with tempfile.TemporaryDirectory() as temp_dir:
    # Path for our custom font cache
    custom_font_file = Path(temp_dir) / "my_custom_fonts.json"
    
    # Create a minimal font cache (in practice, you'd use dmp_offline_cache to generate this)
    font_cache = {
        "Roboto": [{
            "style": "normal",
            "weight": "400", 
            "unicode_range": "",
            "type": "woff2",
            "content": "d09GMgABAAAAAAIAAA4AAAAAA..."  # Truncated for example
        }]
    }
    
    with open(custom_font_file, 'w') as f:
        json.dump(font_cache, f)
    
    print(f"Created custom font cache at: {custom_font_file}")
    
    # Also need a JS cache file for offline mode
    js_cache_file = Path(temp_dir) / "my_js_cache.json"
    js_cache = {
        "https://unpkg.com/deck.gl@latest/dist.min.js": {
            "encoded_content": "ZGVja2dsX2NvbnRlbnQ=",  # Placeholder
            "name": "unpkg_com_deck_gl_latest_dist_min_js"
        }
    }
    
    with open(js_cache_file, 'w') as f:
        json.dump(js_cache, f)
    
    try:
        # Create interactive plot with custom font file
        fig = datamapplot.create_interactive_plot(
            data_coords,
            labels,
            title="Offline Mode with Custom Font File",
            sub_title="Using specified font cache file instead of default location",
            font_family="Roboto",
            inline_data=False,
            offline_mode=True,
            offline_mode_font_data_file=str(custom_font_file),
            offline_mode_js_data_file=str(js_cache_file),
            offline_data_path=temp_dir / "plot_data"
        )
        
        # Save the plot
        output_file = Path(temp_dir) / "offline_custom_font_plot.html"
        fig.save(str(output_file))
        
        print(f"\nSuccess! Plot saved to: {output_file}")
        print("\nThis demonstrates the fix for issue #112:")
        print("- Offline mode now correctly uses specified font file paths")
        print("- No longer defaults to potentially non-existent cache locations")
        
    except Exception as e:
        print(f"\nError: {e}")
        print("\nNote: For a real use case, you would:")
        print("1. Use 'dmp_offline_cache' to create proper font/JS cache files")
        print("2. Store them in your desired location")
        print("3. Reference them using the offline_mode_*_data_file parameters")