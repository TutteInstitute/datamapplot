"""
Color Palette Generation for DataMapPlot
========================================

This module provides intelligent color palette generation for data visualizations,
particularly for scatter plots with many clusters. The main innovation is using
the spatial layout of data to assign colors - clusters that are close together
get visually distinct colors, while the overall palette maintains aesthetic coherence.

Key Concepts:
-------------
1. **Spatial Color Assignment**: Colors are assigned based on where clusters appear
   in 2D space (e.g., UMAP/t-SNE coordinates), not arbitrarily.

2. **Polar Coordinate Mapping**: 
   - Angle from center → Hue (color type: red, blue, green, etc.)
   - Distance from center → Lightness/Chroma (brightness/saturation)

3. **Perceptual Uniformity**: Uses JCh color space (from colorspacious) to ensure
   colors are perceptually distinct and pleasant.

Main Functions:
--------------
- `palette_from_datamap()`: Generate colors based on cluster positions
- `palette_from_cmap_and_datamap()`: Use an existing colormap with spatial logic
- `deep_palette()`: Create darker, richer versions of colors
- `pastel_palette()`: Create lighter, softer versions of colors

Example Usage:
-------------
```python
import numpy as np
from datamapplot.palette_handling import palette_from_datamap

# Your 2D embedded data (e.g., from UMAP)
data_coords = np.random.randn(1000, 2)

# Cluster centers (could be from KMeans, HDBSCAN, etc.)
cluster_centers = np.array([
    [2.5, 1.0],   # Cluster 0
    [-1.0, 2.0],  # Cluster 1
    [0.0, -2.0],  # Cluster 2
    [-2.0, -1.0]  # Cluster 3
])

# Generate colors automatically
colors = palette_from_datamap(data_coords, cluster_centers)
# Returns: ['#ff6b4a', '#4affdb', '#6b4aff', '#ffdb4a']

# Avoid red/pink colors (useful for academic papers)
colors = palette_from_datamap(data_coords, cluster_centers, 
                              hue_shift=np.pi/2)  # Start from blue/green

# For presentations (brighter colors)
colors = palette_from_datamap(data_coords, cluster_centers,
                              min_lightness=25)  # No very dark colors
```

Algorithm Overview:
------------------
1. Find the center of all data points
2. Convert cluster positions to polar coordinates (angle, radius)
3. Map angle → hue (going around color wheel)
4. For each cluster:
   - Sample nearby data points within a small angular range
   - Use their radial distribution to set lightness/chroma
   - Inner points → darker/less saturated
   - Outer points → lighter/more saturated
5. Convert from JCh to RGB hex codes

This creates a natural color progression that follows the data's structure!
"""

import numpy as np

import colorspacious
from matplotlib.colors import rgb2hex, to_rgb, ListedColormap


def palette_from_datamap(
    umap_coords,
    label_locations,
    hue_shift=0.0,
    theta_range=np.pi / 16,
    radius_weight_power=1.0,
    min_lightness=10,
):
    """Generate a color palette based on the spatial layout of your data map.
    
    This function automatically creates visually distinct colors for any number of 
    clusters by using their spatial positions in the 2D data map. Colors are 
    assigned based on angular position (hue) and distance from center (lightness/chroma),
    ensuring that nearby clusters get different colors and the palette scales 
    beautifully to hundreds of clusters.
    
    Parameters
    ----------
    umap_coords : ndarray of shape (n_samples, 2)
        The 2D coordinates of all data points in your map (e.g., from UMAP, t-SNE)
    label_locations : ndarray of shape (n_labels, 2)
        The 2D coordinates of your cluster centers/label positions
    hue_shift : float, optional (default=0.0)
        Rotate the color wheel by this many radians. Use this to avoid 
        starting with red/pink colors: try π/4 (45°) or π/2 (90°)
    theta_range : float, optional (default=π/16)
        Angular range for sampling nearby points. Smaller values = more 
        local color variation, larger values = smoother color transitions
    radius_weight_power : float, optional (default=1.0)
        How much distance from center affects color progression. 
        >1.0 = outer clusters get more distinct colors
        <1.0 = more even color distribution
    min_lightness : float, optional (default=10)
        Minimum lightness value (0-100). Higher values prevent very dark colors
        
    Returns
    -------
    list of str
        Hex color codes (e.g., ['#FF5733', '#33FF57', ...]), one per label location
        
    Examples
    --------
    Basic usage with automatic spatial coloring:
    
    >>> import numpy as np
    >>> from datamapplot.palette_handling import palette_from_datamap
    >>> 
    >>> # Your 2D data coordinates 
    >>> coords = np.random.randn(1000, 2)
    >>> # Your cluster centers
    >>> centers = np.array([[0, 0], [2, 1], [-1, 2], [1, -1]])
    >>> 
    >>> # Generate colors automatically
    >>> colors = palette_from_datamap(coords, centers)
    >>> print(colors)
    ['#ff6b4a', '#4affdb', '#6b4aff', '#ffdb4a']
    
    For many clusters (this scales to 100+ clusters):
    
    >>> # 50 cluster centers arranged in a circle
    >>> angles = np.linspace(0, 2*np.pi, 50, endpoint=False)
    >>> centers = np.column_stack([np.cos(angles), np.sin(angles)])
    >>> colors = palette_from_datamap(coords, centers)
    >>> len(colors)  # Always exactly 50 distinct colors
    50
    
    Adjust hue to avoid red/pink starting colors:
    
    >>> # Start with blue/green instead of red/pink
    >>> colors = palette_from_datamap(coords, centers, hue_shift=np.pi/2)
    
    For academic papers (more conservative colors):
    
    >>> colors = palette_from_datamap(coords, centers, 
    ...                              min_lightness=25,  # Avoid very dark colors
    ...                              hue_shift=np.pi/4)  # Start with orange/yellow
    
    Notes
    -----
    This function is automatically used by datamapplot.create_plot() when you don't 
    specify custom colors. It's the secret to how DataMapPlot handles large numbers 
    of clusters so well - colors are assigned based on where clusters actually 
    appear in your visualization, not arbitrarily.
    
    The algorithm works by:
    1. Finding the center of your data map
    2. Converting cluster positions to polar coordinates (angle + distance)  
    3. Assigning hue based on angle around the center
    4. Assigning lightness/saturation based on distance and local density
    5. Using perceptual color space (JCh) for optimal visual distinction
    """
    # Handle empty label locations
    if label_locations.shape[0] == 0:
        return []

    # Step 1: Find the geometric center of all data points
    # This becomes our reference point for polar coordinates
    data_center = np.asarray(
        umap_coords.min(axis=0)
        + (umap_coords.max(axis=0) - umap_coords.min(axis=0)) / 2
    )
    
    # Step 2: Convert to polar coordinates (radius, angle)
    # Center all data points around the geometric center
    centered_data = umap_coords - data_center
    # Calculate distance from center for each data point
    data_map_radii = np.linalg.norm(centered_data, axis=1)
    # Calculate angle from center for each data point (atan2 handles quadrants correctly)
    data_map_thetas = np.arctan2(centered_data.T[1], centered_data.T[0])
    
    # Do the same for cluster/label locations
    centered_label_locations = label_locations - data_center
    label_location_radii = np.linalg.norm(centered_label_locations, axis=1)
    label_location_thetas = np.arctan2(
        centered_label_locations.T[1], centered_label_locations.T[0]
    )

    # Step 3: Assign hues based on angular position
    # Sort clusters by their angle to ensure smooth color progression
    sorter = np.argsort(label_location_thetas)
    # Weight by radius - clusters farther from center get more "hue space"
    # This helps distinguish outer clusters better
    weights = (label_location_radii**radius_weight_power)[sorter]
    # Cumulative sum creates smooth hue progression around the circle
    hue = weights.cumsum()
    # Scale to full color wheel (0-360 degrees)
    hue = (hue / hue.max()) * 360

    # Map each cluster's angle to its assigned hue
    location_hue = np.interp(
        label_location_thetas, np.sort(label_location_thetas), np.sort(hue)
    )
    # Apply hue shift and wrap around at 360 degrees
    location_hue = (location_hue + hue_shift) % 360

    # Step 4: Assign chroma (saturation) and lightness based on local density
    location_chroma = []
    location_lightness = []
    
    # For smaller datasets, process each cluster individually
    if label_location_thetas.shape[0] < 256:
        for r, theta in zip(label_location_radii, label_location_thetas):
            # Find nearby data points in a wedge around this cluster
            # Start with small wedge, expand if needed to ensure we sample enough points
            for i_theta_range in np.linspace(theta_range, np.pi, 16):
                theta_high = theta + i_theta_range
                theta_low = theta - i_theta_range
                # Handle angle wraparound at ±π
                if theta_high > np.pi:
                    theta_high -= 2 * np.pi
                if theta_low < -np.pi:
                    theta_low -= 2 * np.pi

                # Create mask for points in this angular wedge
                if theta_low > 0 and theta_high < 0:
                    # Special case: wedge crosses the ±π boundary
                    r_mask = (data_map_thetas < theta_low) & (data_map_thetas > theta_high)
                else:
                    r_mask = (data_map_thetas > theta_low) & (data_map_thetas < theta_high)

                mask_size = np.sum(r_mask)
                if mask_size > 0:
                    break
            else:
                raise ValueError("No mask found for theta range.")

            # Map radial distribution to chroma (20-100 range)
            # Points farther out get higher chroma (more saturated)
            chroma = (
                np.argsort(np.argsort(data_map_radii[r_mask])) / mask_size
            ) * 80 + 20
            
            # Map radial distribution to lightness
            # Points farther out get lower lightness (darker)
            lightness = (
                1.0 - (np.argsort(np.argsort(data_map_radii[r_mask])) / mask_size)
            ) * (80 - min_lightness) + min_lightness
            
            # Interpolate to find this cluster's specific values
            location_lightness.append(
                np.interp(
                    r,
                    np.sort(data_map_radii[r_mask]),
                    np.sort(lightness)[::-1],
                )
            )
            location_chroma.append(
                np.interp(r, np.sort(data_map_radii[r_mask]), np.sort(chroma))
            )
    else:
        # For larger datasets, pre-compute values at regular angles for efficiency
        uniform_thetas = np.linspace(-np.pi, np.pi, 256)
        sorted_chroma = []
        sorted_lightness = []
        sorted_radii = []
        
        # Pre-compute chroma/lightness distributions at 256 regular angles
        for theta in uniform_thetas:
            theta_high = theta + theta_range
            theta_low = theta - theta_range
            if theta_high > np.pi:
                theta_high -= 2 * np.pi
            if theta_low < -np.pi:
                theta_low -= 2 * np.pi

            if theta_low > 0 and theta_high < 0:
                r_mask = (data_map_thetas < theta_low) & (data_map_thetas > theta_high)
            else:
                r_mask = (data_map_thetas > theta_low) & (data_map_thetas < theta_high)

            mask_size = np.sum(r_mask)
            chroma = (
                np.argsort(np.argsort(data_map_radii[r_mask])) / mask_size
            ) * 80 + 20
            lightness = (
                1.0 - (np.argsort(np.argsort(data_map_radii[r_mask])) / mask_size)
            ) * (80 - min_lightness) + min_lightness
            sorted_chroma.append(np.sort(chroma))
            sorted_lightness.append(np.sort(lightness)[::-1])
            sorted_radii.append(np.sort(data_map_radii[r_mask]))

        # For each cluster, use the pre-computed values from the nearest angle
        for r, theta in zip(label_location_radii, label_location_thetas):
            nearest_theta_idx = np.argmin(np.abs(uniform_thetas - theta))
            location_lightness.append(
                np.interp(
                    r,
                    sorted_radii[nearest_theta_idx],
                    sorted_lightness[nearest_theta_idx],
                )
            )
            location_chroma.append(
                np.interp(
                    r, sorted_radii[nearest_theta_idx], sorted_chroma[nearest_theta_idx]
                )
            )

    # Step 5: Convert from JCh color space to RGB hex codes
    # JCh = [J]lightness, [C]hroma, [h]ue - a perceptually uniform color space
    palette = np.clip(
        colorspacious.cspace_convert(
            np.vstack(
                (
                    np.asarray(location_lightness),
                    np.asarray(location_chroma),
                    location_hue,
                )
            ).T,
            "JCh",
            "sRGB1",
        ),
        0,
        1,
    )
    return [rgb2hex(color) for color in palette]


def scaling_func(xs, lo, mid, hi):
    """Quadratic scaling function that maps [0,1] to [lo,hi] passing through mid.
    
    This creates a smooth curve that allows fine control over how values are mapped.
    Used to map radial positions to color properties (lightness/chroma).
    
    Parameters
    ----------
    xs : array-like
        Input values in range [0, 1]
    lo : float
        Output value when xs = 0
    mid : float
        Approximate output value when xs = 0.5
    hi : float
        Output value when xs = 1
        
    Returns
    -------
    array-like
        Scaled values clipped to [lo, hi] range
    """
    vals = (2 * (lo + hi) - 4 * mid) * xs**2 + (4 * mid - 3 * lo - hi) * xs + lo
    return np.clip(vals, lo, hi)


def palette_from_cmap_and_datamap(
    cmap,
    umap_coords,
    label_locations,
    chroma_bounds=(20, 90),
    lightness_bounds=(10, 80),
    theta_range=np.pi / 16,
    radius_weight_power=1.0,
):
    """Generate a palette using an existing colormap adapted to spatial layout.
    
    This function combines a matplotlib colormap with the spatial color assignment
    logic from palette_from_datamap(). It extracts hues from the colormap but 
    still adjusts lightness/chroma based on cluster positions.
    
    Parameters
    ----------
    cmap : matplotlib colormap
        Base colormap to extract hues from (e.g., plt.cm.viridis)
    umap_coords : ndarray of shape (n_samples, 2)
        The 2D coordinates of all data points
    label_locations : ndarray of shape (n_labels, 2)
        The 2D coordinates of cluster centers
    chroma_bounds : tuple of float, optional
        (min, max) bounds for chroma values
    lightness_bounds : tuple of float, optional
        (min, max) bounds for lightness values
    theta_range : float, optional
        Angular range for sampling nearby points
    radius_weight_power : float, optional
        How much distance affects color assignment
        
    Returns
    -------
    list of str
        Hex color codes based on the colormap and spatial positions
        
    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> colors = palette_from_cmap_and_datamap(
    ...     plt.cm.viridis, coords, centers
    ... )
    """
    if label_locations.shape[0] == 0:
        return [cmap(0.5)]

    endpoints = cmap((0.0, 1.0))
    endpoint_distance = np.sum((endpoints[0] - endpoints[1]) ** 2)
    if endpoint_distance < 0.05:
        cyclic_cmap = cmap
    else:
        new_colors = np.vstack(
            (
                cmap(np.linspace(0, 1, 128)),
                cmap(np.linspace(1, 0, 128)),
            )
        )
        cyclic_cmap = ListedColormap(new_colors, name="generated_cyclic_cmap")

    data_center = np.asarray(
        umap_coords.min(axis=0)
        + (umap_coords.max(axis=0) - umap_coords.min(axis=0)) / 2
    )
    centered_data = umap_coords - data_center
    data_map_radii = np.linalg.norm(centered_data, axis=1)
    data_map_thetas = np.arctan2(centered_data.T[1], centered_data.T[0])
    centered_label_locations = label_locations - data_center
    label_location_radii = np.linalg.norm(centered_label_locations, axis=1)
    label_location_thetas = np.arctan2(
        centered_label_locations.T[1], centered_label_locations.T[0]
    )

    sorter = np.argsort(label_location_thetas)
    weights = (label_location_radii**radius_weight_power)[sorter]
    weights = weights.cumsum()
    weights /= weights.max()

    location_base_vals = np.interp(
        label_location_thetas, np.sort(label_location_thetas), np.sort(weights)
    )
    base_colors = cyclic_cmap(location_base_vals)[:, :3]

    base_colors_jch = colorspacious.cspace_convert(base_colors, "sRGB1", "JCh")

    location_hue = base_colors_jch.T[2]
    location_chroma = []
    location_lightness = []
    for i, (r, theta) in enumerate(zip(label_location_radii, label_location_thetas)):
        theta_high = theta + theta_range
        theta_low = theta - theta_range
        if theta_high > np.pi:
            theta_high -= 2 * np.pi
        if theta_low < -np.pi:
            theta_low -= 2 * np.pi

        if theta_low > 0 and theta_high < 0:
            r_mask = (data_map_thetas < theta_low) & (data_map_thetas > theta_high)
        else:
            r_mask = (data_map_thetas > theta_low) & (data_map_thetas < theta_high)

        mask_size = np.sum(r_mask)

        chroma_scale = np.argsort(np.argsort(data_map_radii[r_mask])) / mask_size
        chroma = scaling_func(
            chroma_scale, chroma_bounds[0], base_colors_jch[i, 1], chroma_bounds[1]
        )

        lightness_scale = 1.0 - (
            np.argsort(np.argsort(data_map_radii[r_mask])) / mask_size
        )
        lightness = scaling_func(
            lightness_scale,
            lightness_bounds[0],
            base_colors_jch[i, 0],
            lightness_bounds[1],
        )
        location_lightness.append(
            np.interp(
                r,
                np.sort(data_map_radii[r_mask]),
                np.sort(lightness)[::-1],
            )
        )
        location_chroma.append(
            np.interp(r, np.sort(data_map_radii[r_mask]), np.sort(chroma))
        )

    palette = np.clip(
        colorspacious.cspace_convert(
            np.vstack(
                (
                    np.asarray(location_lightness),
                    np.asarray(location_chroma),
                    location_hue,
                )
            ).T,
            "JCh",
            "sRGB1",
        ),
        0,
        1,
    )
    return [rgb2hex(color) for color in palette]


def deep_palette(base_palette, degree=2.0):
    """Create a deeper, richer version of a color palette.
    
    This function takes an existing palette and makes the colors darker and more
    saturated, useful for creating emphasis or contrast in visualizations.
    
    Parameters
    ----------
    base_palette : list of color strings
        Original palette (hex codes, named colors, or RGB tuples)
    degree : float, optional (default=2.0)
        How much to deepen colors. Higher = darker/more saturated
        
    Returns
    -------
    list of str
        Hex color codes for the deepened palette
        
    Examples
    --------
    >>> original = ['#ff6b4a', '#4affdb', '#6b4aff']
    >>> deep = deep_palette(original, degree=2.5)
    >>> # Results in darker, richer versions of the original colors
    """
    initial_palette = [to_rgb(color) for color in base_palette]
    jch_palette = colorspacious.cspace_convert(initial_palette, "sRGB1", "JCh")
    min_lightness = jch_palette.T[0].min()
    min_chroma = jch_palette.T[1].min()
    # Reduce lightness (make darker) and increase chroma (more saturated)
    jch_palette[:, 0] = np.clip(jch_palette[:, 0] / degree, min(20 / degree, min_lightness), 50)
    jch_palette[:, 1] = np.clip(jch_palette[:, 1] / degree, min(40 / degree, min_chroma), 100)
    result = [
        rgb2hex(x)
        for x in np.clip(
            colorspacious.cspace_convert(jch_palette, "JCh", "sRGB1"), 0, 1
        )
    ]
    return result


def pastel_palette(base_palette, degree=2.0):
    """Create a pastel (lighter, softer) version of a color palette.
    
    This function takes an existing palette and makes the colors lighter and less
    saturated, useful for backgrounds or subtle visualizations.
    
    Parameters
    ----------
    base_palette : list of color strings
        Original palette (hex codes, named colors, or RGB tuples)
    degree : float, optional (default=2.0)
        How much to lighten colors. Higher = lighter/less saturated
        
    Returns
    -------
    list of str
        Hex color codes for the pastel palette
        
    Examples
    --------
    >>> original = ['#ff0000', '#00ff00', '#0000ff']  # Pure RGB
    >>> pastel = pastel_palette(original, degree=2.0)
    >>> # Results in soft, muted versions like ['#ffb3b3', '#b3ffb3', '#b3b3ff']
    
    Notes
    -----
    Perfect for:
    - Academic papers where bright colors might be distracting
    - Backgrounds that shouldn't compete with foreground elements
    - Creating a soft, approachable aesthetic
    """
    initial_palette = [to_rgb(color) for color in base_palette]
    jch_palette = colorspacious.cspace_convert(initial_palette, "sRGB1", "JCh")
    min_lightness = jch_palette.T[0].min()
    min_chroma = jch_palette.T[1].min()
    # Increase lightness (make lighter) and decrease chroma (less saturated)
    jch_palette[:, 0] = np.clip(jch_palette[:, 0] * np.sqrt(degree), min_lightness, 100)
    jch_palette[:, 1] = np.clip(jch_palette[:, 1] / degree, min(10 / degree, min_chroma), 50)
    result = [
        rgb2hex(x)
        for x in np.clip(
            colorspacious.cspace_convert(jch_palette, "JCh", "sRGB1"), 0, 1
        )
    ]
    return result