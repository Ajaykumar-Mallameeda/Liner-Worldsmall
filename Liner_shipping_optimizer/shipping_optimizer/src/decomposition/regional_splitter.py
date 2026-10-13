"""
================================
Cross-region demands (origin in region A, destination in region B):
  - Assigned to origin's region (Option A from spec).
  - MILP in that region will model them as unserved if no direct or
    transshipment path exists — which is correct: they count against coverage.

Services are included if ANY port on the service is in the region.  This
allows trunk/feeder services that straddle region boundaries to still be
considered, giving the MILP the routing flexibility it needs.
"""

from copy import deepcopy
from typing import Dict, List, Set


class RegionalSplitter:

    def __init__(self, problem):
        self.problem = problem

    # ------------------------------------------------------------------
    # Build a single region's sub-problem
    # ------------------------------------------------------------------
    def build_region(self, port_ids: List[int]):
        port_set = set(port_ids)

        # ── Ports ──────────────────────────────────────────────────────
        ports = [p for p in self.problem.ports if p.id in port_set]

        # ── Demands: ORIGIN-ONLY assignment (zero duplication) ─────────
        demands = [
            d for d in self.problem.demands
            if d.origin in port_set
        ]

        # ── Services: include if ANY port is in the region ──────────────
        # Trunk services crossing region boundaries still provide capacity
        # for within-region legs.
        services = []
        for s in self.problem.services:
            if any(p in port_set for p in s.ports):
                services.append(deepcopy(s))

        regional_problem                 = deepcopy(self.problem)
        regional_problem.ports           = ports
        regional_problem.demands         = demands
        regional_problem.services        = services
        regional_problem.region_port_set = port_set  # stored for MILP reference
        # A region lists only its own ports, but its services call at ports of other
        # regions and its demands end there: the full catalogue travels with it so
        # every port cost is looked up (never assumed to be zero).
        regional_problem.port_catalog    = {p.id: p for p in self.problem.ports}
        # The region's own ``demands`` are origin-only. Candidate generation values a
        # rotation against ALL demand (reverse and cross-region flows it also carries),
        # so the full list travels with the region (a reference, not a copy).
        regional_problem.global_demands  = self.problem.demands

        return regional_problem

    # ------------------------------------------------------------------
    # Split global problem into regional problems (zero duplication)
    # ------------------------------------------------------------------
    def split(self, clusters: Dict[int, List[int]]) -> Dict[int, object]:
        # Build forward map: port_id → cluster_id
        port_to_cluster: Dict[int, int] = {}
        for cluster_id, port_ids in clusters.items():
            for pid in port_ids:
                port_to_cluster[pid] = cluster_id

        all_assigned_origins: Set[int] = set(port_to_cluster.keys())

        # Build regional problems
        regional_problems: Dict[int, object] = {}
        for cluster_id, port_ids in clusters.items():
            regional_problems[cluster_id] = self.build_region(port_ids)

        # Safety net: origins not in any cluster → assign to largest region
        largest_cluster_id = max(clusters, key=lambda c: len(clusters[c]))
        orphan_demands = [
            d for d in self.problem.demands
            if d.origin not in all_assigned_origins
        ]
        if orphan_demands:
            rp = regional_problems[largest_cluster_id]
            # Append without deepcopy — they are already unique objects
            rp.demands = list(rp.demands) + orphan_demands

        # Validate: total demand across regions == global demand (no duplication)
        global_total = sum(d.weekly_teu for d in self.problem.demands)
        regional_total = sum(
            sum(d.weekly_teu for d in rp.demands)
            for rp in regional_problems.values()
        )
        if abs(global_total - regional_total) > 1.0:
            raise AssertionError(
                f"Demand partitioning error: global={global_total:.0f} "
                f"regional_sum={regional_total:.0f} — duplication or loss detected"
            )

        return regional_problems