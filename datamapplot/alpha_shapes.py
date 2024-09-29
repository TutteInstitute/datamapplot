import numpy as np
import numba

from scipy.interpolate import splprep, splev


@numba.njit()
def circumradius(points):
    bc = points[1:] - points[0]
    d = 2 * (bc[0, 0] * bc[1, 1] - bc[0, 1] * bc[1, 0])
    if d == 0:
        return 0
    b_norm = bc[0, 0] * bc[0, 0] + bc[0, 1] * bc[0, 1]
    c_norm = bc[1, 0] * bc[1, 0] + bc[1, 1] * bc[1, 1]
    ux = (bc[1, 1] * b_norm - bc[0, 1] * c_norm) / d
    uy = (bc[0, 0] * c_norm - bc[1, 0] * b_norm) / d
    return np.sqrt(ux * ux + uy * uy)


@numba.njit(locals={"candidate_idx": numba.uint64})
def find_boundary_candidates(points, simplices, alpha=0.1):
    candidates = np.full((simplices.shape[0] * 3, 2), -1, dtype=np.int32)
    candidate_idx = 0
    for simplex in simplices:
        if circumradius(points[simplex]) < alpha:
            candidates[candidate_idx] = (simplex[0], simplex[1])
            candidates[candidate_idx + 1] = (simplex[0], simplex[2])
            candidates[candidate_idx + 2] = (simplex[1], simplex[2])
            candidate_idx += 3
    return candidates[:candidate_idx]

@numba.njit()
def boundary_from_candidates(boundary_candidates):
    occurrence_counts = {(np.int32(0), np.int32(0)):0 for i in range(0)}
    for candidate in boundary_candidates:
        tuple_candidate = (candidate[0], candidate[1])
        if tuple_candidate in occurrence_counts:
            occurrence_counts[tuple_candidate] += 1
        else:
            occurrence_counts[tuple_candidate] = 1

    return set([x for x in occurrence_counts if occurrence_counts[x] == 1])

@numba.njit()
def build_polygons(boundary):
    polygons = []
    search_set = boundary.copy()
    sequence = list(search_set.pop())
    while len(search_set) > 0:
        to_find = sequence[-1]
        for link in search_set:
            if link[0] == to_find:
                sequence.append(link[1])
                search_set.remove(link)
                break
            elif link[1] == to_find:
                sequence.append(link[0])
                search_set.remove(link)
                break
        else:
            polygons.append(sequence.copy())
            sequence = list(search_set.pop())

    polygons.append(sequence)
    return polygons

def create_boundary_polygons(points, simplices, alpha=0.1):
    simplices.sort(axis=1)
    boundary_candidates = find_boundary_candidates(points, simplices, alpha=alpha)
    boundary = boundary_from_candidates(boundary_candidates)
    if len(boundary) == 0:
        raise ValueError("The value of polygon_alpha was too low, and no boundary was formed. Try increasing polygon_alpha.")
    polygons = build_polygons(boundary)

    result = [
        np.empty((len(sequence) + 1, 2), dtype=np.float32) for sequence in polygons
    ]
    for s, sequence in enumerate(polygons):
        for i, n in enumerate(sequence):
            result[s][i] = points[n]
        result[s][-1] = points[sequence[0]]

    return result


def smooth_polygon(p, point_multipler=4, spline_coeff=0.0001):
    dist = np.sqrt(np.sum((p[:-2] - p[1:-1]) ** 2, axis=1))
    dist_along = np.concatenate(([0], dist.cumsum()))
    spline, u = splprep(p[:-1].T, u=dist_along, s=spline_coeff, per=True)

    interp_d = np.linspace(dist_along[0], dist_along[-1], len(p) * point_multipler)
    interp_x, interp_y = splev(interp_d, spline)

    return np.vstack([interp_x, interp_y]).T
