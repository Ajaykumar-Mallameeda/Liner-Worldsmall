import weakref

import numpy as np
from collections import defaultdict


class HubDetector:
    # id(problem) -> (weak reference to that problem, scores). The weak reference is
    # what makes the cache correct: ``id()`` values are reused once an object is freed,
    # and the previous cache (keyed by ``id`` alone) then served the demand scores of a
    # DIFFERENT, already-freed problem - non-reproducible hubs, loops and feeders.
    _demand_cache = {}

    def __init__(self, problem):
        self.problem = problem

    def compute_demand_scores(self):
        cache_key = id(self.problem)
        hit = self._demand_cache.get(cache_key)
        if hit is not None and hit[0]() is self.problem:
            return hit[1]

        scores = defaultdict(float)

        for d in self.problem.demands:
            scores[d.origin] += d.weekly_teu
            scores[d.destination] += d.weekly_teu

        try:
            self._demand_cache[cache_key] = (weakref.ref(self.problem), scores)
        except TypeError:                     # not weak-referenceable: do not cache
            self._demand_cache.pop(cache_key, None)
        return scores

    def compute_connectivity_scores(self):
        connections = defaultdict(int)
        for d in self.problem.demands:
            connections[d.origin] += 1
            connections[d.destination] += 1

        return connections

    def detect_hubs(self, top_k=10):
        demand_scores = self.compute_demand_scores()
        conn_scores = self.compute_connectivity_scores()

        hub_scores = {}

        for p in self.problem.ports:
            pid = p.id

            demand = demand_scores.get(pid, 0)
            conn = conn_scores.get(pid, 0)

            hub_scores[pid] = demand * 0.7 + conn * 0.3

        hubs = sorted(
            hub_scores,
            key=hub_scores.get,
            reverse=True
        )[:top_k]

        return hubs

    def hub_summary(self, hubs):

        summary = []

        for h in hubs:

            p = self.problem.ports[h]

            summary.append({
                "id": h,
                "name": p.name,
                "lat": p.latitude,
                "lon": p.longitude
            })

        return summary