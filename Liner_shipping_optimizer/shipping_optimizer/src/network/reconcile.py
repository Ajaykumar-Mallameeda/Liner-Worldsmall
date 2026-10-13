"""Global reconciliation: one jointly optimised, independently verified network.

Regional agents (GA + region-local allocation) are *candidate generators and
hints*: they share services and compete for the same vessels, so their results are
NOT additive. This stage

  1. takes the union of every region's candidate services (cyclic rotations are
     de-duplicated so the same rotation is not offered twice),
  2. plans ONE network over ALL demand with the real per-class fleet inventory
     (``NetworkPlanner``: path MILP + independent ledger),
  3. partitions the verified result back to regions so the downstream pipeline sees
     additive numbers:
       - cargo (revenue, served/unserved TEU, per-TEU port charges) belongs to the
         region of the OD's origin - a disjoint partition;
       - a service's vessel, fuel and fixed port-call costs belong to the region that
         first proposed it;
     so that  sum(regions) == the global ledger exactly.

If the global stage cannot produce a verified plan, the result says so
(``ok = False`` with a status/message); regional numbers are never presented as
verified in that case.
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from src.network.economics import EconomicsAssumptions, assumptions_for_problem
from src.network.assumption_register import build as _assumption_register
from src.network.class_variants import (
    augment_candidates as _augment_candidates, fraction_from_environment as _class_variant_fraction,
)
from src.network.plan import Candidate, NetworkPlanner, PlanResult
from src.services.class_screening import config_from_environment as _class_screen_config
from src.services.demand_coherent import config_from_environment as _demand_loop_config
from src.services.route_operators import config_from_environment as _route_operator_config
from src.services.regional_filter import filter_mode as _regional_filter_mode

logger = logging.getLogger(__name__)


def _candidate_generation_settings() -> Dict:
    """Settings of the candidate generator in force (read from the environment, the
    same source the generator reads), so a result states how its pool was built."""
    try:
        dl, cs = _demand_loop_config(), _class_screen_config()
        ro = _route_operator_config()
    except ValueError as exc:                                      # misconfigured: say so
        return {"error": str(exc)}
    return {
        "demand_coherent_loops": {
            "enabled": dl.enabled and dl.budget > 0, "budget_per_regional_problem": dl.budget,
            "min_ports": dl.min_ports, "max_ports": dl.max_ports, "seed_pairs": dl.seed_pairs,
            "complementarity_share": dl.complementarity_share,
            "randomness": "none (deterministic for fixed inputs)",
        },
        "class_screening": {
            "mode": "per_rotation_screening" if cs.enabled else "legacy_nearest_capacity",
            "alternatives_per_rotation": cs.k if cs.enabled else 1,
            "time_feasible_class": bool(cs.enabled and cs.time_feasible),
        },
        "route_operators": {
            "variants_per_regional_problem": ro.budget, "elitism": ro.elitism,
            "elites": ro.elites, "randomness": "none (deterministic for fixed inputs)",
        },
        "regional_filter": _regional_filter_mode(),
    }


ENV_GLOBAL_MIN_COVERAGE = "LINER_GLOBAL_MIN_COVERAGE"


def _global_min_coverage() -> Optional[float]:
    """``LINER_GLOBAL_MIN_COVERAGE`` = a coverage floor in (0, 1] for the global MILP, or None.
    A malformed value is an error (never ignored); an unattainable floor makes the stage
    ``infeasible`` with its explicit status - it is never relaxed silently."""
    import os
    raw = (os.environ.get(ENV_GLOBAL_MIN_COVERAGE) or "").strip()
    if not raw:
        return None
    try:
        v = float(raw)
    except ValueError:
        raise ValueError(f"{ENV_GLOBAL_MIN_COVERAGE} must be a number in (0, 1], got {raw!r}") from None
    if not (0.0 < v <= 1.0):
        raise ValueError(f"{ENV_GLOBAL_MIN_COVERAGE} must be in (0, 1], got {v}")
    return v


def canonical_rotation(ports: Sequence[str]) -> Tuple[str, ...]:
    """Unique rotation rotated to start at its smallest port (so [A,B,C] == [B,C,A];
    direction is preserved because directed distances differ)."""
    p = list(ports)
    if len(p) >= 2 and p[0] == p[-1]:
        p = p[:-1]
    if not p:
        return tuple()
    i = min(range(len(p)), key=lambda k: p[k])
    return tuple(p[i:] + p[:i])


@dataclass
class GlobalStageResult:
    ok: bool
    status: str
    message: str = ""
    plan: Optional[PlanResult] = None
    region_updates: Dict[str, Dict] = field(default_factory=dict)
    network_ledger: Dict = field(default_factory=dict)


def collect_candidates_with_proposers(
    pools: Dict[str, List[Dict]],
) -> Tuple[List[Candidate], Dict[str, str], Dict[str, List[str]]]:
    """Union of regional candidate pools. Returns the candidates, ``owner[id]`` = the
    region that FIRST proposed the rotation (stable: region order) and
    ``proposers[id]`` = every region that proposed the same rotation and class."""
    seen: Dict[Tuple, str] = {}
    cands: List[Candidate] = []
    owner: Dict[str, str] = {}
    proposers: Dict[str, List[str]] = {}
    for region, pool in pools.items():
        for c in pool:
            key = (canonical_rotation(c["ports"]), c["vessel_class"])
            if not key[0]:
                continue
            if key in seen:
                p = proposers[seen[key]]
                if region not in p:
                    p.append(region)
                continue
            cid = str(c["id"])
            if cid in owner:                      # same id from another region: make unique
                cid = f"{region}:{cid}"
            seen[key] = cid
            owner[cid] = region
            proposers[cid] = [region]
            cands.append(Candidate(cid, key[0], c["vessel_class"]))
    return cands, owner, proposers


def collect_candidates(pools: Dict[str, List[Dict]]) -> Tuple[List[Candidate], Dict[str, str]]:
    """Union of regional candidate pools. Returns the candidates and ``owner[id]`` =
    region that first proposed the rotation (stable: region order)."""
    cands, owner, _ = collect_candidates_with_proposers(pools)
    return cands, owner


def _register_variant_owners(additions, owner: Dict[str, Optional[str]], proposers: Dict[str, List[str]]) -> None:
    """Search-only class variants (``lv####``) are modelled inside the plan, after the regional pools
    were collected: give each the owner / proposers of the rotation it is a class variant of."""
    for add in additions or []:
        sid, src = add.get("service_id"), add.get("rotation_of")
        if sid and sid not in owner:
            owner[sid] = owner.get(src)
            proposers[sid] = list(proposers.get(src, [owner[sid]] if owner.get(sid) else []))


def _fallback_owner(proposers_of_sid: Sequence[str], owner_of_sid: Optional[str],
                    regions, region_names: Sequence[str]) -> Optional[str]:
    """Region charged for a service that carries no attributable cargo: its first proposer, else the
    region that owns the rotation, else - so that no service ever drops out of the regional partition
    (its cost is part of the network total) - the first region in the stated order."""
    props = [p for p in proposers_of_sid if p in regions]
    cand = props[0] if props else owner_of_sid
    if cand in regions:
        return cand
    return region_names[0] if region_names else None


def _capped_gap(plan):
    m = getattr(plan, "milp_stage", None) or {}
    inc, bd = m.get("incumbent_profit_usd_per_week"), m.get("relaxation_bound_usd_per_week")
    if inc is None or bd is None:
        return None, None
    return float(bd) - float(inc), (100.0 * (float(bd) - float(inc)) / abs(float(bd)) if bd else None)


def _capped_model_block(plan, led) -> Dict:
    m = dict(getattr(plan, "milp_stage", None) or {})
    usd, pct = _capped_gap(plan)
    m.update({"gap_usd_per_week": usd, "gap_pct_of_bound": pct,
              "scope": "model over the retained (capped) path set, restricted to the LP-support services; "
                       "the bound is valid for this model only"})
    return m


def _final_plan_block(plan, led) -> Dict:
    m = getattr(plan, "milp_stage", None) or {}
    inc, bd = m.get("incumbent_profit_usd_per_week"), m.get("relaxation_bound_usd_per_week")
    final = float(led.operating_profit)
    exceeds = (bd is not None and final > float(bd) + 1e-6 * max(1.0, abs(float(bd))))
    return {
        "profit_usd_per_week": final,
        "post_solve_change_usd_per_week": (final - float(inc)) if inc is not None else None,
        "post_solve_steps": {"local_search_applied": bool((getattr(plan, "local_search", {}) or {}).get("applied")),
                             "flow_reoptimisation_applied": bool((plan.flow_reopt or {}).get("applied")),
                             "profit_floor_repair_applied": bool(((plan.flow_reopt or {}).get("repair") or {}).get("applied"))},
        "exceeds_capped_model_bound": bool(exceeds),
        "scope": "ledger-verified plan after post-solve steps; it may use paths and services outside the capped "
                 "model, so it is not comparable with the capped model's bound and a value above the bound "
                 "is not a negative gap and does not prove optimality",
    }


def reconcile(
    problem,
    pools: Dict[str, List[Dict]],
    region_of_od: Dict[Tuple[str, str], str],
    region_names: Sequence[str],
    *,
    hints: Optional[Dict[str, int]] = None,
    time_limit_sec: float = 120.0,
    max_paths_per_od: int = 10,
    assumptions: Optional[EconomicsAssumptions] = None,
    iteration: Optional[int] = None,
) -> GlobalStageResult:
    t0 = time.perf_counter()
    assumptions = assumptions or assumptions_for_problem(problem)
    cands, owner, proposers = collect_candidates_with_proposers(pools)
    if not cands:
        return GlobalStageResult(False, "invalid_input", "no candidate services from any region")
    try:
        planner = NetworkPlanner(problem, assumptions=assumptions, max_paths_per_od=max_paths_per_od)
    except ValueError as exc:
        return GlobalStageResult(False, "invalid_input", str(exc))

    # Opt-in targeted alternative-class candidates (``LINER_CLASS_VARIANTS`` = fraction of the pool).
    # The original candidates are untouched; the additions are listed with their provenance and
    # the time the step takes is taken out of the stage budget (the stage never exceeds it).
    class_variant_report = None
    cv_fraction = _class_variant_fraction()
    if cv_fraction > 0:
        t_cv = time.perf_counter()
        extra, class_variant_report = _augment_candidates(problem, assumptions, cands, fraction=cv_fraction,
                                                          deadline=t_cv + 0.25 * float(time_limit_sec))
        src_owner = {c.service_id: owner.get(c.service_id) for c in cands}
        for add in class_variant_report.get("additions", []):
            sid = add["service_id"]
            base_owner = src_owner.get(add["rotation_of"])
            owner[sid] = base_owner
            proposers[sid] = list(proposers.get(add["rotation_of"], [base_owner] if base_owner else []))
        cands = list(cands) + list(extra)
        time_limit_sec = max(1.0, float(time_limit_sec) - (time.perf_counter() - t_cv))

    initial = None
    if hints:
        # hints are keyed by regional ids; map through the canonical rotation
        by_key = {(canonical_rotation(c.ports), c.vessel_class): c.service_id for c in cands}
        initial = {}
        for region, pool in pools.items():
            for c in pool:
                f = hints.get(str(c["id"]))
                if f:
                    cid = by_key.get((canonical_rotation(c["ports"]), c["vessel_class"]))
                    if cid:
                        initial[cid] = max(initial.get(cid, 0), int(f))

    # Opt-in epsilon constraint (Task 19, experimental, NOT the default): profit-maximising
    # subject to served TEU >= fraction x total demand.  Unset = the production objective.
    min_cov = _global_min_coverage()
    plan = planner.plan(cands, demands=problem.demands, initial_frequencies=initial or None,
                        time_limit_sec=time_limit_sec, min_served_fraction=min_cov)
    if cands and not plan.models:
        # nothing could be modelled: an empty network would be "valid" but is not a result
        why = sorted({r for b in plan.rejected_candidates for r in b.get("reasons", [])})
        return GlobalStageResult(
            False, "invalid_input",
            f"all {len(cands)} candidate service(s) were rejected "
            f"({', '.join(why) or 'no reason recorded'})", plan=plan)
    if not plan.ok:
        reasons = [v.get("type") for v in (plan.ledger.violations if plan.ledger else [])]
        return GlobalStageResult(
            False, plan.status if plan.status not in ("optimal", "feasible") else "invalid_plan",
            plan.message or ("ledger violations: " + ", ".join(sorted(set(map(str, reasons))))),
            plan=plan)

    # services the local search opened from search-only variants (``lv####``) were modelled inside the plan:
    # give them the owner / proposers of the rotation they are a class variant of
    _register_variant_owners((getattr(plan, "local_search", None) or {}).get("variant_additions"), owner, proposers)

    led, sol = plan.ledger, plan.solution
    port_lookup = planner.port_lookup
    models_by_id = {m.service_id: m for m in plan.models}
    models_by_id_idx = [m.service_id for m in plan.models]          # path segment index -> id

    def pc(pid, name):
        v = getattr(port_lookup.get(pid), name, 0.0)
        return float(v) if isinstance(v, (int, float)) and math.isfinite(v) else 0.0

    # ---- partition by region ------------------------------------------------------
    per = {r: defaultdict(float) for r in region_names}
    demands = plan.demands
    for di, d in enumerate(demands):
        if d.weekly_teu > 0:
            r = region_of_od.get((d.origin, d.destination))
            if r in per:
                per[r]["total_demand"] += d.weekly_teu
    for di, k, teu in sol.flows:
        d = demands[di]
        r = region_of_od.get((d.origin, d.destination))
        if r not in per:
            continue
        path = plan.paths[di][k]
        per[r]["served"] += teu
        per[r]["revenue"] += teu * d.revenue_per_teu
        trans = 0.0
        for hub in path.transfer_ports:
            trans += pc(hub, "transshipment_cost")
        per[r]["transship"] += teu * trans
        per[r]["port_per_teu"] += teu * (path.port_cost_per_teu - trans)

    # A service's vessel, fuel and fixed port-call cost are attributed to ONE region.
    # The regions that can be charged for a service are those whose own cargo (origin
    # region) rides it. Two phases, deterministic:
    #   1. representation - every region that has cargo on the network is given, if it
    #      is possible, one service it uses: the region with the fewest unclaimed
    #      services to choose from goes first (ties: the larger cargo, then the region
    #      order), taking the unclaimed service on which its cargo is largest;
    #   2. every other service goes to the region whose cargo uses it most; a tie
    #      prefers a region that proposed it, then the region order. A service that
    #      carries no attributable cargo falls back to its first proposer.
    # Only the split between regions can change - never the network totals.
    carried_by: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for di, k, teu in sol.flows:
        d = demands[di]
        rr = region_of_od.get((d.origin, d.destination))
        if rr not in per:
            continue
        for seg in plan.paths[di][k].segments:
            carried_by[models_by_id_idx[seg.service]][rr] += teu
    order = {r: i for i, r in enumerate(region_names)}
    sids = sorted(led.service_rows)
    claimed: Dict[str, str] = {}
    users_of_region: Dict[str, List[str]] = defaultdict(list)
    for sid in sids:
        for rr, v in carried_by.get(sid, {}).items():
            if v > 0.0:
                users_of_region[rr].append(sid)
    unrepresented = set(users_of_region)
    while unrepresented:
        best = None
        for rr in unrepresented:
            free = [sid for sid in users_of_region[rr] if sid not in claimed]
            if not free:
                continue
            top = min(free, key=lambda x: (-carried_by[x][rr], x))
            key = (len(free), -carried_by[top][rr], order.get(rr, 1 << 30))
            if best is None or key < best[0]:
                best = (key, rr, top)
        if best is None:
            break
        claimed[best[2]] = best[1]
        unrepresented.discard(best[1])
    service_owner: Dict[str, Optional[str]] = {}
    for sid in sids:
        if sid in claimed:
            service_owner[sid] = claimed[sid]
            continue
        users = {r: v for r, v in carried_by.get(sid, {}).items() if v > 0.0}
        if users:
            props = set(proposers.get(sid, []))
            service_owner[sid] = min(
                users, key=lambda r: (-users[r], 0 if r in props else 1, order.get(r, 1 << 30)))
        else:
            service_owner[sid] = _fallback_owner(proposers.get(sid, []), owner.get(sid), per, region_names)

    services_by_region: Dict[str, List[Dict]] = {r: [] for r in region_names}
    for sid, row in led.service_rows.items():
        r = service_owner.get(sid)
        if r not in per:
            continue
        per[r]["vessel"] += row["vessel_cost"]
        per[r]["fuel"] += row["fuel_cost"]
        m = models_by_id.get(sid)
        per[r]["port_fixed"] += (row["frequency"] * m.port_fixed_per_rotation) if m else 0.0
        cost = row["vessel_cost"] + row["fuel_cost"] + row["port_cost"]
        services_by_region[r].append({
            "id": sid,
            "ports": list(row["ports"]),
            "load": float(row["load"]),
            "capacity": float(row["capacity_per_departure"]),
            "weekly_capacity_per_leg": float(row["weekly_capacity_per_leg"]),
            "carried_teu_legs": float(row["carried_teu_legs"]),
            "offered_teu_legs": float(row["offered_teu_legs"]),
            "leg_load_factor": row["leg_load_factor"],
            "vessel_class": row["vessel_class"],
            "vessel_cost": float(row["vessel_cost"]),
            "fuel_cost": float(row["fuel_cost"]),
            "port_cost": float(row["port_cost"]),
            "revenue": float(row["revenue"]),
            "cost": float(cost),
            "weekly_profit": float(row["revenue"] - cost),
            "margin_pct": round((row["revenue"] - cost) / row["revenue"] * 100, 2) if row["revenue"] > 0 else 0.0,
            "region": r,
            "frequency_per_week": int(row["frequency"]),
            "vessels": int(row["vessels"]),
            "cycle_time_days": int(row["cycle_time_days"]),
        })

    status_label = "Optimal" if plan.status == "optimal" else "Feasible"
    updates: Dict[str, Dict] = {}
    for r in region_names:
        x = per[r]
        total_cost = x["vessel"] + x["fuel"] + x["port_fixed"] + x["port_per_teu"] + x["transship"]
        profit = x["revenue"] - total_cost
        n_svc = len(services_by_region[r])
        tot = x["total_demand"]
        cov = x["served"] / tot * 100 if tot > 0 else 0.0
        updates[r] = {
            "status": status_label,
            "weekly_profit": profit,
            "annual_profit": profit * 52,
            "revenue": x["revenue"],
            "operating_cost": x["vessel"],
            "fuel_cost": x["fuel"],
            "transship_cost": x["transship"],
            "port_cost": x["port_fixed"] + x["port_per_teu"],
            "total_cost": total_cost,
            "coverage_percent": cov,
            "satisfied_demand": x["served"],
            "unserved_demand": max(0.0, tot - x["served"]),
            "total_demand": tot,
            "uncovered_teu": max(0.0, tot - x["served"]),
            "services_selected": n_svc,
            "profit_margin_pct": round(profit / x["revenue"] * 100, 1) if x["revenue"] > 0 else 0,
            "profit_per_service": round(profit / n_svc, 0) if n_svc else 0,
            "cost_per_service": round(total_cost / n_svc, 0) if n_svc else 0,
            "selected_services": services_by_region[r],
        }

    # ---- network ledger block -------------------------------------------------------
    fleet = problem.fleet
    fleet_use = {c.vessel_class: {"used": int(led.vessels_by_class.get(c.vessel_class, 0)),
                                  "available": int(c.quantity)} for c in fleet.classes}
    a = assumptions
    ledger_block = {
        "verified": bool(led.valid and plan.reconciliation.get("reconciled")),
        "status": plan.status,
        "iteration": iteration,
        "method": ("global path-based network MILP (integer weekly departures and vessels, "
                   "per-leg capacity, per-class fleet inventory, transit-time-feasible paths) "
                   "followed by an independent ledger recomputation"),
        "weekly_usd": {
            "revenue": led.revenue,
            "vessel_cost": led.vessel_cost,
            "fuel_cost": led.fuel_cost,
            "port_call_fixed_cost": led.port_call_fixed_cost,
            "handling_cost": led.handling_cost,
            "transshipment_cost": led.transshipment_cost,
            "port_variable_cost": led.port_variable_cost,
            "total_operating_cost": led.operating_cost,
            "operating_profit": led.operating_profit,
            "profit_margin_on_revenue": (led.operating_profit / led.revenue) if led.revenue > 0 else None,
        },
        "demand_teu_per_week": {
            "total": led.total_demand_teu, "served": led.served_teu,
            "unserved": led.unserved_teu, "coverage_pct": led.coverage * 100.0,
        },
        "fleet_by_class": fleet_use,
        "services": {
            "candidates_offered": len(cands),
            "candidates_modelled": len(plan.models),
            "candidates_rejected": len(plan.rejected_candidates),
            "operated": len(led.service_rows),
            # composition of the modelled pool (what the optimiser could choose from)
            "modelled_by_n_ports": {str(k): v for k, v in sorted(
                {n: sum(1 for m in plan.models if len(m.ports) == n)
                 for n in {len(m.ports) for m in plan.models}}.items())},
            "modelled_by_class": {c.vessel_class: sum(1 for m in plan.models
                                                      if m.vessel_class == c.vessel_class)
                                  for c in fleet.classes},
            "operated_by_n_ports": {str(k): v for k, v in sorted(
                {n: sum(1 for r in led.service_rows.values() if len(r["ports"]) == n)
                 for n in {len(r["ports"]) for r in led.service_rows.values()}}.items())},
        },
        "reconciliation": dict(plan.reconciliation),
        # The plan itself (services, weekly departures, routed flows): enough for anyone to
        # recompute every figure above from the raw data files without trusting this block.
        "plan": {
            "services": [
                {"id": sid, "ports": list(r["ports"]), "vessel_class": r["vessel_class"],
                 "frequency_per_week": int(r["frequency"]),
                 # the applicable bunker price of this service and where it came from
                 "fuel_price_usd_per_t": float(r.get("fuel_price_usd_per_t", float("nan"))),
                 "fuel_price_basis": plan.fuel_prices.get(sid, {}).get("basis"),
                 "bunkering_port": plan.fuel_prices.get(sid, {}).get("bunkering_port"),
                 "price_observed_on": plan.fuel_prices.get(sid, {}).get("observed_on")}
                for sid, r in led.service_rows.items()
            ],
            "flows": [
                {"origin": demands[di].origin, "destination": demands[di].destination,
                 "teu": float(teu), "kind": plan.paths[di][k].kind,
                 "segments": [[models_by_id_idx[s.service], s.from_port, s.to_port]
                              for s in plan.paths[di][k].segments]}
                for di, k, teu in sol.flows if teu > 1e-9
            ],
        },
        "optimality": {
            "milp_status": plan.status,
            "relaxation_upper_bound_usd_per_week": sol.relaxation_bound,
            # the gap is a property of the CAPPED MODEL: its incumbent as the solver returned it versus
            # its own bound.  The final plan (after local search / flow re-optimisation over the full
            # valid path set) lies outside that model and is reported separately; a negative
            # final-plan-minus-bound is NOT a proof of optimality and not a negative gap.
            "gap_to_bound_usd_per_week": _capped_gap(plan)[0],
            "capped_model": _capped_model_block(plan, led),
            "final_plan": _final_plan_block(plan, led),
            "solver_backend": sol.solver_backend,
            "mip_gap_reported_by_backend": sol.mip_gap,
            "bound_applies_to": "the model over the retained (capped) path set",
            "flow_reoptimisation": dict(plan.flow_reopt),
            # optional formulation changes in force (LINER_MILP_VUB ...): empty = the baseline model
            "formulation": dict(getattr(sol, "formulation", {}) or {}),
            "local_search": dict(getattr(plan, "local_search", {}) or {}),
            "stage_timing": dict(getattr(plan, "stage_timing", {}) or {}),
            "note": ("a feasible plan with a stated upper bound; not a proof of optimality "
                     "unless status is 'optimal'"),
        },
        "path_model": plan.path_stats.to_dict() if plan.path_stats else {},
        "candidate_augmentation": class_variant_report or {"enabled": False},
        "violations": list(led.violations),
        "assumptions": {
            "port_stay_hours": a.port_stay_hours,
            "transshipment_min_hours": a.transshipment_min_hours,
            "transfer_wait_days": a.transfer_wait_days,
            # uniform legacy price, or (regional_snapshot) the snapshot's reference
            # price; the per-service prices are in ``plan.services`` and the full
            # pricing description is ``fuel_pricing``
            "bunker_price_usd_per_t": (
                a.effective_fuel_pricing.reference_price_usd_per_t
                if a.effective_fuel_pricing.reference_price_usd_per_t is not None
                else a.bunker_price_usd_per_t),
            "fuel_pricing": a.effective_fuel_pricing.describe(),
            "speed_factor": a.speed_factor,
            "basis": a.basis,
            "sailing_speed": "class designSpeed (only speed with a source consumption)",
            "max_transfers_per_od": planner.path_config.max_transfers,
            "global_min_coverage": min_cov,
            "path_selection": planner.path_config.describe(),
            "capacity_unit": {
                "status": getattr(fleet, "capacity_unit_status", "provisional"),
                "internal_unit": getattr(fleet, "capacity_unit", "TEU"),
                "source_column": getattr(fleet, "capacity_source_column", "Capacity FFE"),
                "capacity_feasibility_is_conditional":
                    getattr(fleet, "capacity_unit_status", "provisional") != "verified",
            },
            "transit_time_unit": "TransitTime column read as days (unverified unit)",
            "assumption_register": _assumption_register(a, fleet),
            # how the candidate pool was generated (reproducibility record)
            "candidate_generation": _candidate_generation_settings(),
        },
        "runtime_sec": round(time.perf_counter() - t0, 2),
    }
    # strategy / utilisation / unserved-demand report of the verified plan (Task 19): derived
    # from the routed cargo, reconciled against the ledger inside the report; never an input
    try:
        from src.network.strategy_report import build_strategy_report
        ledger_block["strategy_report"] = build_strategy_report(
            plan, fleet=problem.fleet, distance_matrix=problem.distance_matrix,
            speed_factor=assumptions.speed_factor)
    except Exception as exc:                                       # noqa: BLE001
        logger.error("strategy_report_failed | %s: %s", type(exc).__name__, exc)
        ledger_block["strategy_report"] = {"available": False,
                                           "error": f"{type(exc).__name__}: {exc}"}
    return GlobalStageResult(True, plan.status, plan.message, plan, updates, ledger_block)
