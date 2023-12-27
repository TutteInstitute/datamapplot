import numpy as np
import numba


@numba.njit(
    [
        "f4(f4[::1],f4[::1])",
        numba.types.float32(
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
            numba.types.Array(numba.types.float32, 1, "C", readonly=True),
        ),
    ],
    fastmath=True,
    locals={
        "result": numba.types.float32,
        "diff": numba.types.float32,
        "dim": numba.types.intp,
        "i": numba.types.uint16,
    },
)
def euclidean(x, y):
    r"""Squared euclidean distance.

    .. math::
        D(x, y) = \sum_i (x_i - y_i)^2
    """
    result = 0.0
    dim = x.shape[0]
    for i in range(dim):
        diff = x[i] - y[i]
        result += diff * diff

    return np.sqrt(result)


@numba.njit(parallel=True, nogil=True)
def chunked_parallel_pairwise_distances(X, Y=None, metric=euclidean, chunk_size=16):
    if Y is None:
        XX, symmetrical = X, True
        row_size = col_size = X.shape[0]
    else:
        XX, symmetrical = Y, False
        row_size, col_size = X.shape[0], Y.shape[0]

    result = np.zeros((row_size, col_size), dtype=np.float32)
    n_row_chunks = (row_size // chunk_size) + 1
    for chunk_idx in numba.prange(n_row_chunks):
        n = chunk_idx * chunk_size
        chunk_end_n = min(n + chunk_size, row_size)
        m_start = n if symmetrical else 0
        for m in range(m_start, col_size, chunk_size):
            chunk_end_m = min(m + chunk_size, col_size)
            for i in range(n, chunk_end_n):
                for j in range(m, chunk_end_m):
                    result[i, j] = metric(X[i], XX[j])
    return result


@numba.njit()
def pull_arms(data, arms, num_pulls_per_arm, estimates, pull_counts):
    other_candidates = np.random.choice(
        data.shape[0], size=num_pulls_per_arm, replace=False
    ).astype(np.int32)
    data_arm = data[arms]
    data_other = data[other_candidates]

    distance_sums = np.sum(
        chunked_parallel_pairwise_distances(data_arm, data_other), axis=1
    )

    estimates *= pull_counts
    estimates += distance_sums
    pull_counts += num_pulls_per_arm
    estimates /= pull_counts


@numba.njit()
def medoid(data, arm_budget=20):
    pull_counts = np.zeros(data.shape[0], dtype=np.int32)
    pull_budget = arm_budget * data.shape[0]
    estimates = np.zeros(data.shape[0], dtype=np.float32)
    current_active_arms = np.arange(data.shape[0])
    n_rounds = int(np.ceil(np.log2(data.shape[0])))

    while current_active_arms.shape[0] > 1:
        num_pulls_per_arm = max(
            1,
            int(
                min(
                    data.shape[0],
                    np.floor(pull_budget / (current_active_arms.shape[0] * n_rounds)),
                )
            ),
        )
        pull_arms(data, current_active_arms, num_pulls_per_arm, estimates, pull_counts)

        median = np.median(estimates)
        mask = estimates <= median
        current_active_arms = current_active_arms[mask]
        estimates = estimates[mask]
        pull_counts = pull_counts[mask]

    return data[current_active_arms[0]]
