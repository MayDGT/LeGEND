import numpy as np


def cdist(A, B, **kwargs):
    from scipy.spatial import distance
    return distance.cdist(A.astype(float), B.astype(float), **kwargs)

def find_duplicates(X, epsilon=1e-16):
    # calculate the distance matrix from each point to another
    D = cdist(X, X)

    # set the diagonal to infinity
    D[np.triu_indices(len(X))] = np.inf

    # set as duplicate if a point is really close to this one
    is_duplicate = np.any(D <= epsilon, axis=1)

    return is_duplicate

def calc_crowding_distance(F, filter_out_duplicates=True):
    n_points, n_obj = F.shape

    if n_points <= 2:
        return np.full(n_points, np.inf)

    else:

        if filter_out_duplicates:
            # filter out solutions which are duplicates - duplicates get a zero finally
            is_unique = np.where(np.logical_not(find_duplicates(F, epsilon=1e-32)))[0]
        else:
            # set every point to be unique without checking it
            is_unique = np.arange(n_points)

        # index the unique points of the array
        _F = F[is_unique]

        # sort each column and get index
        I = np.argsort(_F, axis=0, kind='mergesort')

        # sort the objective space values for the whole matrix
        _F = _F[I, np.arange(n_obj)]

        # calculate the distance from each point to the last and next
        dist = np.row_stack([_F, np.full(n_obj, np.inf)]) - np.row_stack([np.full(n_obj, -np.inf), _F])

        # calculate the norm for each objective - set to NaN if all values are equal
        norm = np.max(_F, axis=0) - np.min(_F, axis=0)
        norm[norm == 0] = np.nan

        # prepare the distance to last and next vectors
        dist_to_last, dist_to_next = dist, np.copy(dist)
        dist_to_last, dist_to_next = dist_to_last[:-1] / norm, dist_to_next[1:] / norm

        # if we divide by zero because all values in one columns are equal replace by none
        dist_to_last[np.isnan(dist_to_last)] = 0.0
        dist_to_next[np.isnan(dist_to_next)] = 0.0

        # sum up the distance to next and last and norm by objectives - also reorder from sorted list
        J = np.argsort(I, axis=0)
        _cd = np.sum(dist_to_last[J, np.arange(n_obj)] + dist_to_next[J, np.arange(n_obj)], axis=1) / n_obj

        # save the final vector which sets the crowding distance for duplicates to zero to be eliminated
        crowding = np.zeros(n_points)
        crowding[is_unique] = _cd

    # crowding[np.isinf(crowding)] = 1e+14
    return crowding


def fast_non_dominated_sort(F):
    n = F.shape[0]
    m = F.shape[0]
    fronts = []
    L = np.repeat(F, m, axis=0)
    R = np.tile(F, (n, 1))

    smaller = np.reshape(np.any(L < R, axis=1), (n, m))
    larger = np.reshape(np.any(L > R, axis=1), (n, m))

    M = np.logical_and(smaller, np.logical_not(larger)) * 1 \
                + np.logical_and(larger, np.logical_not(smaller)) * -1

    n_ranked = 0
    ranked = np.zeros(n, dtype=int)

    is_dominating = [[] for _ in range(n)]
    n_dominated = np.zeros(n)
    current_front = []
    for i in range(n):

        for j in range(i + 1, n):
            rel = M[i, j]
            if rel == 1:
                is_dominating[i].append(j)
                n_dominated[j] += 1
            elif rel == -1:
                is_dominating[j].append(i)
                n_dominated[i] += 1

        if n_dominated[i] == 0:
            current_front.append(i)
            ranked[i] = 1.0
            n_ranked += 1

    # append the first front to the current front
    fronts.append(current_front)

    # while not all solutions are assigned to a pareto front
    while n_ranked < n:

        next_front = []

        # for each individual in the current front
        for i in current_front:

            # all solutions that are dominated by this individuals
            for j in is_dominating[i]:
                n_dominated[j] -= 1
                if n_dominated[j] == 0:
                    next_front.append(j)
                    ranked[j] = 1.0
                    n_ranked += 1

        fronts.append(next_front)
        current_front = next_front

    _fronts = []
    n_ranked = 0
    for front in fronts:

        _fronts.append(np.array(front, dtype=int))

        # increment the n_ranked solution counter
        n_ranked += len(front)

        # stop if more than this solutions are n_ranked
        if n_ranked >= 20:
            break

    fronts = _fronts

    return fronts

F = np.random.random((20, 2))
print(F)
fronts = fast_non_dominated_sort(F)
for k, front in enumerate(fronts):
    print(k, front)