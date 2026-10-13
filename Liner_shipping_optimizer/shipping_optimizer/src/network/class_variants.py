"""Targeted alternative-class candidates for rotations of an over-subscribed vessel class (opt-in).

Problem (measured, reports/expansion_2026_10_12): after the regional filter the candidate pool is
83 % one class (Feeder_800: 1,288 of 1,551 regional candidates) while that class owns 29 vessels;
every operated plan exhausts it, and 16 % of the demand is blocked by class inventory although the
same rotations could be sailed - inside the transit limit - by a class with idle vessels
(Panamax_2400: 58-59 idle, Panamax_1200: 18-24, Post_panamax: 15-21).  The class screening
offers one class per rotation (k = 1), so no such variant exists in the pool.

What this does (``LINER_CLASS_VARIANTS`` = fraction of the unique pool to add; 0 / unset = OFF)
  1. a class is *over-subscribed* when the pool holds at least ``PRESSURE_RATIO`` (2.0) candidates
     per vessel of the class's inventory; a class is a *target* when it is not over-subscribed;
  2. every rotation of an over-subscribed class is evaluated in every target class with the
     canonical stand-alone model (``ClassScreener.evaluate_class``: feasibility, vessels per
     weekly sailing against the class inventory, ride-feasible cargo inside the transit limit,
     hire + fuel + port calls at the pinned price);
  3. only variants with a POSITIVE stand-alone profit are kept by default (``LINER_CLASS_VARIANTS_FLOOR``
     < 0 admits variants that lose up to that much stand-alone: a labelled experiment on complementary
     roles - the MILP still charges their real fixed and variable costs), at most one variant per
     rotation (the best profit per vessel - variants of one rotation are substitutes);
  4. the best ``fraction * |pool|`` variants by profit per vessel are appended to the pool.

Nothing here prices cargo or accounts cost: variants are ordinary candidates; the global MILP
decides, with their actual fixed and variable costs, and the independent ledger verifies the plan.
Every addition is returned with its provenance.
"""

from __future__ import annotations

import math
import os
import time
from collections import Counter
from typing import Dict, List, Optional, Sequence, Tuple

ENV_VARIANTS = "LINER_CLASS_VARIANTS"
ENV_FLOOR = "LINER_CLASS_VARIANTS_FLOOR"     # stand-alone profit floor, USD/week (default 0 = positive only)
PRESSURE_RATIO = 2.0


def fraction_from_environment(env: Optional[Dict[str, str]] = None) -> float:
    """Fraction of the unique pool to add (0 = off).  Malformed values raise ``ValueError``."""
    raw = ((os.environ if env is None else env).get(ENV_VARIANTS) or "").strip()
    if not raw:
        return 0.0
    try:
        v = float(raw)
    except ValueError:
        raise ValueError(f"{ENV_VARIANTS} must be a fraction in [0, 1], got {raw!r}") from None
    if not (0.0 <= v <= 1.0) or not math.isfinite(v):
        raise ValueError(f"{ENV_VARIANTS} must be a fraction in [0, 1], got {v}")
    return v


def floor_from_environment(env: Optional[Dict[str, str]] = None) -> float:
    """Stand-alone profit floor (USD/week, <= 0).  0 (default) keeps only variants that earn money
    stand-alone; a negative value ADMITS variants that lose up to that much stand-alone, as a labelled
    experiment on complementary network roles (the MILP still charges their real costs)."""
    raw = ((os.environ if env is None else env).get(ENV_FLOOR) or "").strip()
    if not raw:
        return 0.0
    try:
        v = float(raw)
    except ValueError:
        raise ValueError(f"{ENV_FLOOR} must be a number <= 0, got {raw!r}") from None
    if not math.isfinite(v) or v > 0:
        raise ValueError(f"{ENV_FLOOR} must be a finite number <= 0, got {v}")
    return v


def augment_candidates(problem, assumptions, candidates: Sequence, *, fraction: float,
                       deadline: Optional[float] = None, standalone_floor: Optional[float] = None,
                       id_prefix: str = "cv") -> Tuple[List, Dict]:
    """Return (new candidates, report).  ``candidates`` are ``Candidate`` objects (service_id, ports,
    vessel_class).  Never raises for an unattainable variant: it is counted in the report."""
    from src.network.plan import Candidate
    from src.services.class_screening import ClassScreener, ClassScreeningConfig

    t0 = time.perf_counter()
    floor = floor_from_environment() if standalone_floor is None else float(standalone_floor)
    rep: Dict = {"requested_fraction": fraction, "standalone_profit_floor": floor,
                 "pool_unique": len(candidates), "added": 0,
                 "over_subscribed_classes": {}, "target_classes": [], "rotations_evaluated": 0,
                 "variants_feasible": 0, "variants_positive_standalone": 0, "variants_already_in_pool": 0,
                 "additions": [], "sec": 0.0, "stopped_by_deadline": False}
    if fraction <= 0 or not candidates:
        return [], rep
    fleet = problem.fleet
    inventory = {c.vessel_class: int(c.quantity) for c in fleet.classes}
    count = Counter(c.vessel_class for c in candidates)
    ratio = {cls: count.get(cls, 0) / max(1, inventory[cls]) for cls in inventory}
    over = {cls for cls, r in ratio.items() if r >= PRESSURE_RATIO}
    targets = [cls for cls in inventory if cls not in over and inventory[cls] > 0]
    rep["over_subscribed_classes"] = {cls: {"candidates": count.get(cls, 0), "inventory": inventory[cls],
                                            "ratio": round(ratio[cls], 2)} for cls in sorted(over)}
    rep["target_classes"] = sorted(targets)
    if not over or not targets:
        rep["reason"] = "no over-subscribed class" if not over else "no target class"
        rep["sec"] = round(time.perf_counter() - t0, 2)
        return [], rep

    screener = ClassScreener(problem, fleet, assumptions, ClassScreeningConfig(k=1))
    existing = {(tuple(c.ports), c.vessel_class) for c in candidates}
    scored: List[Tuple[float, float, str, Tuple[str, ...], str, str, object]] = []
    for c in candidates:
        if c.vessel_class not in over:
            continue
        if deadline is not None and time.perf_counter() > deadline:
            rep["stopped_by_deadline"] = True
            break
        rep["rotations_evaluated"] += 1
        best = None
        for tgt in targets:
            if (tuple(c.ports), tgt) in existing:
                rep["variants_already_in_pool"] += 1
                continue
            try:
                ev = screener.evaluate_class(list(c.ports), fleet.get_class(tgt))
            except Exception:                                           # noqa: BLE001
                continue
            if not ev.feasible:
                continue
            rep["variants_feasible"] += 1
            if ev.vessels_at_best > inventory[tgt]:
                continue
            if ev.standalone_profit_best <= 0.0 and (floor >= 0.0 or ev.standalone_profit_best < floor):
                continue
            rep["variants_positive_standalone"] += 1
            key = (ev.profit_per_vessel, ev.standalone_profit_best)
            if best is None or key > best[0]:
                best = (key, tgt, ev)
        if best is not None:
            (ppv, sap), tgt, ev = best
            scored.append((ppv, sap, c.service_id, tuple(c.ports), c.vessel_class, tgt, ev))
    scored.sort(key=lambda r: (-r[0], -r[1], r[2]))
    n_add = min(len(scored), max(1, int(round(fraction * len(candidates)))))
    new: List = []
    for rank, (ppv, sap, src_id, ports, src_cls, tgt, ev) in enumerate(scored[:n_add]):
        cid = f"{id_prefix}{rank:04d}"
        new.append(Candidate(cid, ports, tgt))
        rep["additions"].append({
            "service_id": cid, "ports": list(ports), "vessel_class": tgt, "rotation_of": src_id,
            "source_class": src_cls, "standalone_profit_usd_per_week": round(sap, 1),
            "profit_per_vessel_usd_per_week": round(ppv, 1), "best_frequency": ev.best_frequency,
            "vessels_at_best": ev.vessels_at_best, "served_teu_best": round(ev.served_teu_best, 1),
            "fixed_cost_usd_per_week": round(ev.fixed_cost_best, 1), "rank": rank,
            "standalone_negative": sap <= 0.0,
            "reason": "alternative class for a rotation of an over-subscribed class "
                      f"({src_cls}: {rep['over_subscribed_classes'][src_cls]['ratio']} candidates "
                      f"per vessel); stand-alone profit {'positive' if sap > 0 else 'within the stated floor (negative)'}; "
                      f"best profit per vessel of the rotation's variants"})
    rep["added"] = len(new)
    rep["scored_variants_available"] = len(scored)
    rep["sec"] = round(time.perf_counter() - t0, 2)
    return new, rep
