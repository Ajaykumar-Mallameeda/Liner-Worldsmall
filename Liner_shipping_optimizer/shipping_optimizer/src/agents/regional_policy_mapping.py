"""
Regional Policy Mapping — Phase F2 of Regional Intelligence Differentiation Sprint.

Maps the 10 regional metrics to a complete regional policy using a
deterministic rule set. The mapping is rule-based and reproducible —
no randomness, no LLM.

Each policy is justified by the metrics that produced it (a `rationale`
list of human-readable strings) so the decision is auditable.

Mapping design principles
-------------------------
* High concentration → corridor focus + high profit priority
* Low concentration  → coverage focus + broad corridors
* Dense network      → direct service + large vessels + low margin
* Sparse network     → feeder services + small vessels + higher margin
* Severe imbalance   → higher min margin (one-way flows)
* Balanced flows     → standard margin
* High hub dominance → hub focus = top hubs
* Distributed hubs   → hub focus = empty (let optimizer decide)
* Large lane volume  → large vessel bias + relaxed margin
* Small lane volume  → small vessel bias + stricter margin
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.agents.regional_metrics import compute_regional_metrics
from src.optimization.data import Problem


# ── Tier boundaries for coverage and profit priority ────────────────
# These are the deterministic knobs.  Each region will land in one tier
# per metric and the combination defines a unique policy.
CONCENTRATION_TO_PROFIT = {
    "very_high": 0.85,   # Top-3 corridors dominant → profit from concentration
    "high":      0.70,
    "moderate":  0.55,
    "low":       0.25,   # Spread out → coverage matters more
}
CONCENTRATION_TO_COVERAGE = {
    "very_high": 0.15,   # Coverage is easy when demand is concentrated
    "high":      0.30,
    "moderate":  0.45,
    "low":       0.75,   # Need to chase every corridor
}
# Profit + coverage must balance — overwrite if their sum drifts far from 1.0

# Density nudges: dense networks tilt toward profit (load factor)
# while sparse networks tilt toward coverage (spread cost)
DENSITY_TO_PROFIT_NUDGE = {
    "very_dense":  +0.10,
    "dense":       +0.05,
    "moderate":     0.00,
    "sparse":      -0.05,
    "very_sparse": -0.05,
}
DENSITY_TO_COVERAGE_NUDGE = {
    "very_dense":  -0.10,
    "dense":       -0.05,
    "moderate":     0.00,
    "sparse":      +0.05,
    "very_sparse": +0.05,
}

# Imbalance nudges: high imbalance → profit (round-trip economics matter)
IMBALANCE_TO_PROFIT_NUDGE = {
    "severe":   +0.10,
    "moderate": +0.05,
    "mild":     +0.02,
    "balanced":  0.00,
}

DENSITY_TO_VESSEL_BIAS = {
    "very_dense": "large",   # Many lanes → large vessel economies of scale
    "dense":      "large",
    "moderate":   "balanced",
    "sparse":     "small",
    "very_sparse": "small",  # Few lanes → small/feeder vessels
}
DENSITY_TO_CORRIDOR_COUNT = {
    # Cap corridor_focus length by density — dense regions have too many
    # viable corridors to list all of them.
    "very_dense":  3,
    "dense":       5,
    "moderate":    8,
    "sparse":     10,
    "very_sparse": 3,
}
DENSITY_TO_MARGIN = {
    # Dense networks: tougher competition → relax margin floor
    "very_dense":  0.03,
    "dense":       0.05,
    "moderate":    0.08,
    "sparse":      0.10,
    "very_sparse": 0.12,
}

IMBALANCE_TO_MARGIN_BONUS = {
    "severe":   +0.05,   # One-way flows need bigger margin
    "moderate": +0.03,
    "mild":     +0.01,
    "balanced":  0.00,
}

VESSEL_TO_MARGIN = {
    # Large vessels spread fixed cost → looser margin
    "large":    -0.02,
    "balanced":  0.00,
    "small":    +0.02,    # Smaller vessel: keep tighter margin
    "feeder":   +0.03,
}

HUB_DOMINANCE_TO_HUB_FOCUS = {
    "dominant":    1,   # Just the top hub
    "strong":      2,   # Top 2 hubs
    "moderate":    3,   # Top 3 hubs
    "distributed": 0,   # No hub focus
}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _select_top_corridors(
    problem: Problem,
    max_count: int,
) -> List[List[str]]:
    """Pick the top-N corridors by weekly TEU."""
    if not problem.demands:
        return []
    sorted_demands = sorted(problem.demands, key=lambda d: d.weekly_teu, reverse=True)
    return [
        [str(d.origin), str(d.destination)]
        for d in sorted_demands[:max_count]
    ]


def _select_top_hubs(
    problem: Problem,
    count: int,
) -> List[str]:
    """Pick the top-N hubs by demand + connectivity score."""
    if count <= 0 or not problem.ports:
        return []
    from collections import defaultdict
    demand: Dict[str, float] = defaultdict(float)
    conn: Dict[str, int] = defaultdict(int)
    for d in problem.demands:
        demand[d.origin] += d.weekly_teu
        demand[d.destination] += d.weekly_teu
        conn[d.origin] += 1
        conn[d.destination] += 1
    scores = {
        p.id: demand.get(p.id, 0) * 0.7 + conn.get(p.id, 0) * 0.3
        for p in problem.ports
    }
    top = sorted(scores, key=scores.get, reverse=True)[:count]
    return [str(h) for h in top]


def derive_regional_policy(
    metrics: Dict[str, Any],
    problem: Optional[Problem] = None,
) -> Dict[str, Any]:
    """Derive a complete regional policy from a metrics dict.

    Parameters
    ----------
    metrics : dict
        Output of ``compute_regional_metrics`` — must contain the
        ``derived`` sub-dict.
    problem : Problem, optional
        If provided, the function populates ``corridor_focus`` and
        ``hub_focus`` with concrete port IDs drawn from the actual data.

    Returns
    -------
    dict
        A regional policy with the standard keys plus a ``rationale``
        list explaining each decision.
    """
    derived = metrics["derived"]
    conc = derived["concentration_level"]
    dens = derived["density_level"]
    imb = derived["imbalance_level"]
    vessel_class = derived["vessel_class"]
    hub_dom = derived["hub_dominance"]

    rationale: List[str] = []

    # ── 1. coverage_priority and profit_priority ───────────────────
    cov_base = CONCENTRATION_TO_COVERAGE[conc]
    prof_base = CONCENTRATION_TO_PROFIT[conc]

    # Density and imbalance add differential nudges — this is what
    # breaks ties between regions that share a concentration level
    # but differ in network structure.
    prof_pri = prof_base + DENSITY_TO_PROFIT_NUDGE[dens] + IMBALANCE_TO_PROFIT_NUDGE[imb]
    cov_pri = cov_base + DENSITY_TO_COVERAGE_NUDGE[dens] - IMBALANCE_TO_PROFIT_NUDGE[imb]

    # Clamp to [0, 1]
    cov_pri = _clamp(cov_pri, 0.0, 1.0)
    prof_pri = _clamp(prof_pri, 0.0, 1.0)
    rationale.append(
        f"Concentration={conc} (top-3 share {metrics['top3_corridor_share']:.1f}%) → "
        f"base cov={cov_base:.2f}, prof={prof_base:.2f}; "
        f"density={dens} nudges cov {DENSITY_TO_COVERAGE_NUDGE[dens]:+.2f}/prof {DENSITY_TO_PROFIT_NUDGE[dens]:+.2f}; "
        f"imbalance={imb} prof nudge {IMBALANCE_TO_PROFIT_NUDGE[imb]:+.2f} → "
        f"coverage_priority={cov_pri:.2f}, profit_priority={prof_pri:.2f}"
    )

    # ── 2. min_service_margin ──────────────────────────────────────
    base_margin = DENSITY_TO_MARGIN[dens]
    imbalance_bonus = IMBALANCE_TO_MARGIN_BONUS[imb]
    vessel_bonus = VESSEL_TO_MARGIN.get(vessel_class, 0.0)
    margin = base_margin + imbalance_bonus + vessel_bonus
    margin = _clamp(margin, 0.0, 0.30)
    rationale.append(
        f"Density={dens} margin base={base_margin:.2f} + "
        f"imbalance={imb} bonus={imbalance_bonus:+.2f} + "
        f"vessel_class={vessel_class} bonus={vessel_bonus:+.2f} → "
        f"min_service_margin={margin:.2f}"
    )

    # ── 3. vessel_bias ─────────────────────────────────────────────
    vessel_bias = DENSITY_TO_VESSEL_BIAS[dens]
    # Cross-check with median lane volume
    if metrics["median_lane_volume"] < 10 and vessel_bias not in ("small", "feeder"):
        vessel_bias = "small"
        rationale.append(
            f"Median lane {metrics['median_lane_volume']:.0f} TEU overrides density → vessel_bias=small"
        )
    elif metrics["median_lane_volume"] > 5000 and vessel_bias != "large":
        vessel_bias = "large"
        rationale.append(
            f"Median lane {metrics['median_lane_volume']:.0f} TEU overrides density → vessel_bias=large"
        )
    else:
        rationale.append(
            f"Density={dens} → vessel_bias={vessel_bias}"
        )

    # ── 4. hub_focus ───────────────────────────────────────────────
    hub_count = HUB_DOMINANCE_TO_HUB_FOCUS[hub_dom]
    hub_focus: List[str] = []
    if problem is not None and hub_count > 0:
        hub_focus = _select_top_hubs(problem, hub_count)
    rationale.append(
        f"Hub dominance={hub_dom} → hub_focus={hub_focus}"
    )

    # ── 5. corridor_focus ──────────────────────────────────────────
    corridor_count = DENSITY_TO_CORRIDOR_COUNT[dens]
    # Boost corridor count when concentration is high (focus on the
    # dominant corridors that drive the region).
    if conc in ("very_high", "high"):
        corridor_count = max(corridor_count, 5)
    corridor_focus: List[List[str]] = []
    if problem is not None:
        corridor_focus = _select_top_corridors(problem, corridor_count)
    rationale.append(
        f"Density={dens} × concentration={conc} → corridor_focus count={len(corridor_focus)}"
    )

    # ── 6. Build final policy ──────────────────────────────────────
    policy = {
        "coverage_priority":  round(cov_pri, 4),
        "profit_priority":    round(prof_pri, 4),
        "min_service_margin": round(margin, 4),
        "vessel_bias":        vessel_bias,
        "hub_focus":          hub_focus,
        "corridor_focus":     corridor_focus,
        "notes":              (
            f"Region {metrics['region']}: conc={conc}, dens={dens}, "
            f"imb={imb}, vessel={vessel_class}, hub_dom={hub_dom}. "
            f"Total demand {metrics['total_demand']:,.0f} TEU/wk."
        ),
        "rationale":          rationale,
    }
    return policy


def derive_all_regional_policies(
    regional_problems: Dict[int, Problem],
    region_names: Dict[int, str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Compute metrics + derive policy for all regions in one shot.

    Returns a dict mapping region name → {"metrics": ..., "policy": ...}.
    """
    from src.agents.regional_metrics import compute_all_regions_metrics

    all_metrics = compute_all_regions_metrics(regional_problems, region_names)
    result: Dict[str, Dict[str, Any]] = {}
    # Build reverse lookup: name → problem
    name_to_problem: Dict[str, Problem] = {}
    for cid, prob in regional_problems.items():
        name = (region_names or {}).get(cid, f"region_{cid}")
        name_to_problem[name] = prob

    for name, metrics in all_metrics.items():
        prob = name_to_problem.get(name)
        policy = derive_regional_policy(metrics, problem=prob)
        result[name] = {"metrics": metrics, "policy": policy}
    return result
