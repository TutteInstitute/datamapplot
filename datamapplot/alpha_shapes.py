import numpy as np
import numba

@numba.njit()
def circumradius(points):
    bc = points[1:] - points[0]
    d = 2 * (bc[0, 0] * bc[1, 1] - bc[0, 1] * bc[1, 0])
    b_norm = bc[0, 0] * bc[0, 0] + bc[0, 1] * bc[0, 1]
    c_norm = bc[1, 0] * bc[1, 0] + bc[1, 1] * bc[1, 1]
    ux = ((bc[1, 1] * b_norm - bc[0, 1] * c_norm) / d)
    uy = ((bc[0, 0] * c_norm - bc[1, 0] * b_norm) / d)
    return np.sqrt(ux * ux + uy * uy)


# @numba.njit()
def create_boundary_polygons(points, simplices, alpha=0.1):
    all_edges = set([(np.int32(0), np.int32(0)) for i in range(0)])
    boundary = set([(np.int32(0), np.int32(0)) for i in range(0)])
    for simplex in simplices:
        if circumradius(points[simplex]) < alpha:
            for e in ((simplex[0], simplex[1]), (simplex[0], simplex[2]), (simplex[1], simplex[2])):
                if e[0] < e[1]:
                    if (e[0], e[1]) not in all_edges:
                        all_edges.add((e[0], e[1]))
                        boundary.add((e[0], e[1]))
                    else:
                        boundary.remove((e[0], e[1]))
                else:
                    if (e[1], e[0]) not in all_edges:
                        all_edges.add((e[1], e[0]))
                        boundary.add((e[1], e[0]))
                    else:
                        boundary.remove((e[1], e[0]))

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

    result = [
        np.empty((len(sequence) + 1, 2), dtype=np.float32)
        for sequence in polygons
    ]
    for s, sequence in enumerate(polygons):
        for i, n in enumerate(sequence):
            result[s][i] = points[n]
        result[s][-1] = points[sequence[0]]

    return result
