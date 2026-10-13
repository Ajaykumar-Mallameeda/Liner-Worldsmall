import numpy as np


def build_distance_matrix(dist_df, n_ports):

    matrix = np.full((n_ports, n_ports), np.inf)

    for _, row in dist_df.iterrows():

        i = int(row["from"])
        j = int(row["to"])
        d = float(row["distance"])

        matrix[i][j] = d
        matrix[j][i] = d

    return matrix


def build_adjacency(problem):

    adjacency = {}

    for service in problem.services:

        ports = service.ports

        for i in range(len(ports) - 1):

            a = ports[i]
            b = ports[i + 1]

            adjacency.setdefault(a, set()).add(b)

    return adjacency


def build_demand_lookup(problem):

    lookup = {}

    for d in problem.demands:

        lookup.setdefault(d.origin, []).append(d)

    return lookup