import numpy as np
import numba

@numba.njit(fastmath=True)
def euclidean(x, y):
    r"""Euclidean distance between two vectors x and y."""
    return np.sqrt(np.sum((x - y) ** 2))

def medoid(data, max_points=5000, max_iter=1000, arm_budget=20):
    """
    Dumb version of medoid calculation:
      - Subsamples the data to at most 1,000 points (ignoring max_points, max_iter, arm_budget).
      - Computes the full pairwise distance matrix.
      - Returns the point with the minimum total distance to all other points.
    
    This function has the same API as the original so you can simply copy-paste it.
    """
    n_points = data.shape[0]
    sample_size = min(n_points, 1000)
    
    # Subsample the data if necessary
    if n_points > sample_size:
        indices = np.random.choice(n_points, sample_size, replace=False)
        data_sample = data[indices]
    else:
        data_sample = data

    # Compute the pairwise distance matrix using broadcasting.
    # data_sample shape: (N, d) where N <= 1000
    diff = data_sample[:, np.newaxis, :] - data_sample[np.newaxis, :, :]
    distances = np.linalg.norm(diff, axis=2)  # shape: (N, N)
    
    # Sum distances for each candidate medoid.
    distance_sums = distances.sum(axis=1)
    
    # Return the data point with the smallest total distance.
    medoid_index = np.argmin(distance_sums)
    return data_sample[medoid_index]
