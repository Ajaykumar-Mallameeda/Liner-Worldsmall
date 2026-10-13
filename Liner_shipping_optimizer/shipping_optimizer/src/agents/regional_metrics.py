
from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Dict, List, Tuple

from src.optimization.data import Problem


# Vessel-class thresholds (TEU/wk) — keep in sync with map_capacity_to_vessel_class
VESSEL_THRESHOLDS = [
    (300, "feeder"),       # < 300 TEU/lane  →  feeder vessels
    (3000, "small"),       # 300–3 000        →  small / panamax
    (15000, "balanced"),   # 3 000–15 000    →  panamax / post-panamax
]
# >= 15 000 TEU/lane → large (ULCV)


def _classify_vessel(median_teu: float) -> str:
    """Map median lane TEU to dominant vessel class requirement."""
    for cap, name in VESSEL_THRESHOLDS:
        if median_teu < cap:
            return name
    return "large"


def _hub_scores(problem: Problem) -> Dict[str, float]:
    """Same scoring as HubDetector: demand * 0.7 + connectivity * 0.3."""
    demand: Dict[str, float] = defaultdict(float)
    conn: Dict[str, int] = defaultdict(int)
    for d in problem.demands:
        demand[d.origin] += d.weekly_teu
        demand[d.destination] += d.weekly_teu
        conn[d.origin] += 1
        conn[d.destination] += 1
    return {
        p.id: demand.get(p.id, 0.0) * 0.7 + conn.get(p.id, 0) * 0.3
        for p in problem.ports
    }


def compute_regional_metrics(
    problem: Problem,
    region_name: str = "Unknown",
) -> Dict[str, Any]:
    """Compute the 10-metric regional intelligence profile.

    Returns a dict containing all metrics plus a `derived` sub-dict with
    categorical labels (e.g. concentration_level) ready for the policy
    mapping.  The function is deterministic.
    """
    demands = problem.demands
    ports = problem.ports
    n_ports = len(ports)
    n_lanes = len(demands)
    total_demand = sum(d.weekly_teu for d in demands)

    # ── Per-lane volumes sorted descending ─────────────────────────────
    lane_volumes = sorted((d.weekly_teu for d in demands), reverse=True)
    if not lane_volumes:
        # Empty region — return safe defaults
        return {
            "region": region_name,
            "total_demand": 0.0,
            "top10_concentration": 0.0,
            "top3_corridor_share": 0.0,
            "median_lane_volume": 0.0,
            "avg_lane_volume": 0.0,
            "network_density": 0.0,
            "hub_centrality": 0.0,
            "import_export_imbalance": 0.0,
            "dominant_vessel_requirement": "balanced",
            "service_fragmentation": 0.0,
            "derived": {
                "concentration_level": "low",
                "density_level": "sparse",
                "imbalance_level": "balanced",
                "vessel_class": "balanced",
                "hub_dominance": "distributed",
            },
        }

    median_lane = float(median(lane_volumes))
    avg_lane = total_demand / n_lanes

    # Top-N concentration
    top10_teu = sum(lane_volumes[:10])
    top3_teu = sum(lane_volumes[:3])
    top10_conc = top10_teu / total_demand * 100 if total_demand else 0.0
    top3_share = top3_teu / total_demand * 100 if total_demand else 0.0

    # Network density
    max_lanes = n_ports * (n_ports - 1) / 2 if n_ports > 1 else 1
    network_density = n_lanes / max_lanes * 100 if max_lanes > 0 else 0.0

    # Hub centrality — top-hub dominance (max / sum)
    hscores = _hub_scores(problem)
    total_score = sum(hscores.values())
    top_hub_score = max(hscores.values()) if hscores else 0.0
    hub_centrality = top_hub_score / total_score * 100 if total_score else 0.0

    # Import/export imbalance — per-port directional asymmetry
    # The total outgoing and incoming of the region as a whole is symmetric
    # (every lane's origin TEU equals its destination TEU), so we measure
    # imbalance at the port level and then aggregate.
    outgoing_by_port: Dict[str, float] = defaultdict(float)
    incoming_by_port: Dict[str, float] = defaultdict(float)
    for d in demands:
        outgoing_by_port[d.origin] += d.weekly_teu
        incoming_by_port[d.destination] += d.weekly_teu
    # Per-port imbalance
    port_imbalances = []
    for pid in set(list(outgoing_by_port.keys()) + list(incoming_by_port.keys())):
        out_p = outgoing_by_port.get(pid, 0.0)
        in_p = incoming_by_port.get(pid, 0.0)
        total_p = out_p + in_p
        if total_p > 0:
            port_imbalances.append(abs(out_p - in_p) / total_p)
    # Aggregate: mean per-port imbalance
    imbalance = (sum(port_imbalances) / len(port_imbalances) * 100) if port_imbalances else 0.0

    # Dominant vessel requirement
    vessel_class = _classify_vessel(median_lane)

    # Service fragmentation: average ports per service / n_lanes
    if problem.services:
        avg_ports_per_service = sum(len(s.ports) for s in problem.services) / len(problem.services)
    else:
        avg_ports_per_service = 0
    service_fragmentation = avg_ports_per_service / n_lanes if n_lanes else 0.0

    # ── Derived categorical labels for policy mapping ─────────────────
    # Concentration level — buckets widened so per-region structure
    # is actually visible (most lanes in this dataset are small).
    if top3_share >= 30:
        concentration_level = "very_high"
    elif top3_share >= 10:
        concentration_level = "high"
    elif top3_share >= 5:
        concentration_level = "moderate"
    else:
        concentration_level = "low"

    # Density level — bucket boundaries match this dataset
    if network_density >= 100:
        density_level = "very_dense"
    elif network_density >= 60:
        density_level = "dense"
    elif network_density >= 30:
        density_level = "moderate"
    elif network_density >= 10:
        density_level = "sparse"
    else:
        density_level = "very_sparse"

    # Imbalance level
    if imbalance >= 40:
        imbalance_level = "severe"
    elif imbalance >= 20:
        imbalance_level = "moderate"
    elif imbalance >= 10:
        imbalance_level = "mild"
    else:
        imbalance_level = "balanced"

    # Hub dominance
    if hub_centrality >= 20:
        hub_dominance = "dominant"
    elif hub_centrality >= 15:
        hub_dominance = "strong"
    elif hub_centrality >= 10:
        hub_dominance = "moderate"
    else:
        hub_dominance = "distributed"

    return {
        "region": region_name,
        "total_demand": round(total_demand, 2),
        "top10_concentration": round(top10_conc, 2),
        "top3_corridor_share": round(top3_share, 2),
        "median_lane_volume": round(median_lane, 2),
        "avg_lane_volume": round(avg_lane, 2),
        "network_density": round(network_density, 2),
        "hub_centrality": round(hub_centrality, 2),
        "import_export_imbalance": round(imbalance, 2),
        "dominant_vessel_requirement": vessel_class,
        "service_fragmentation": round(service_fragmentation, 4),
        "derived": {
            "concentration_level": concentration_level,
            "density_level": density_level,
            "imbalance_level": imbalance_level,
            "vessel_class": vessel_class,
            "hub_dominance": hub_dominance,
        },
    }


def compute_all_regions_metrics(
    regional_problems: Dict[int, Problem],
    region_names: Dict[int, str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Compute metrics for multiple regions.

    Parameters
    ----------
    regional_problems : dict mapping cluster_id → Problem
    region_names      : optional mapping cluster_id → human region name

    Returns
    -------
    dict mapping region name → metrics dict
    """
    region_names = region_names or {}
    result: Dict[str, Dict[str, Any]] = {}
    for cid, prob in regional_problems.items():
        name = region_names.get(cid, f"region_{cid}")
        result[name] = compute_regional_metrics(prob, region_name=name)
    return result


# Standard mapping from orchestrator cluster index → region name
# (must match OrchestratorAgent.REGIONAL_AGENTS order)
STANDARD_REGION_NAMES = {
    0: "Asia",
    1: "Europe",
    2: "Americas",
    3: "Middle East",
    4: "Africa",
}
