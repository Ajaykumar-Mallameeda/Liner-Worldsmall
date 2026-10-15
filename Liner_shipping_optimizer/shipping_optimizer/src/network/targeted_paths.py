"""Targeted path additions for selected high-value ODs (opt-in ``LINER_PATH_TARGETED=K,M`` or ``K:M``, default OFF).

Why: the model keeps the ``max_paths_per_od`` (10) fastest paths per OD; a path that is cheaper to carry is dropped when
it is not among the fastest.  Raising the cap globally was tried and breaks the solver (reports/class_mismatch_campaign:
adaptive budget, CBC ``not_solved``), so this adds a SMALL number of paths for a SMALL number of ODs, once.

How (one round of LP column pricing, then the normal pipeline):
  1. the LP relaxation is solved as usual; its duals are read (validated in ``tests/test_targeted_paths.py``):
        dem_d   dual = marginal profit of one more TEU of OD d                         [USD / TEU]
        cap_s,l dual = marginal profit of one more TEU of capacity on leg l of service s [USD / TEU], >= 0
     (PuLP/CBC, maximisation: a dual is d objective / d right-hand side.)
  2. every excluded VALID path (time-feasible, <= 2 transfers, enumerated without a cap) of every demand whose services
     all have LP rows is priced:   reduced profit = revenue/TEU - per-TEU port charges - dual(dem) - sum dual(cap of its legs)
     (a leg without a capacity row has price 0: that is optimistic, which is why the result is only a RANKING);
  3. demands are ranked by  weekly TEU x best positive reduced profit  - the plausible incremental value - and only the top
     ``K`` are kept; of each, the ``M`` best-priced excluded paths are added;
  4. the LP is solved once more with the added columns; if that fails the original LP and path set are kept.
A demand qualifies only if (a) its LP relaxation leaves part of it unserved, (b) it has a valid excluded path (so it is not
blocked by the transit limit or by the pool) and (c) one of those paths has a positive reduced profit.  The integer problem, the
local search and the flow re-optimisation are unchanged; the reduced profit is an LP signal, never a promise for the
integer plan (the plan's profit comes from the independent ledger).
"""
from __future__ import annotations

import os
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Sequence, Tuple

ENV_TARGETED = "LINER_PATH_TARGETED"
HARD_MAX_ODS = 200
HARD_MAX_PATHS = 5
MIN_REDUCED_PROFIT = 1e-6        # USD per TEU


def targeted_from_environment(env: Optional[Dict[str, str]] = None) -> Optional[Tuple[int, int]]:
    """``K,M`` or ``K:M`` (K demands, M added paths per demand) or None when off.  Malformed values raise ``ValueError``."""
    raw = ((os.environ if env is None else env).get(ENV_TARGETED) or "").strip()
    if not raw or raw == "0":
        return None
    parts = [x.strip() for x in raw.replace(":", ",").split(",")]       # 'K,M' or 'K:M' (a comma breaks some env lists)
    if len(parts) == 3:                                                 # optional third field R, see ``targeted_resolve_from_environment``
        parts = parts[:2]
    if len(parts) != 2:
        raise ValueError(f"{ENV_TARGETED} must be 'K,M' (demands, paths per demand), got {raw!r}")
    try:
        k, m = int(parts[0]), int(parts[1])
    except ValueError:
        raise ValueError(f"{ENV_TARGETED} must be 'K,M' with integers, got {raw!r}") from None
    if not (1 <= k <= HARD_MAX_ODS) or not (1 <= m <= HARD_MAX_PATHS):
        raise ValueError(f"{ENV_TARGETED}: K in [1, {HARD_MAX_ODS}] and M in [1, {HARD_MAX_PATHS}], got {raw!r}")
    return k, m


def targeted_resolve_from_environment(env: Optional[Dict[str, str]] = None) -> bool:
    """Third field of ``LINER_PATH_TARGETED=K:M:R``: 1 (default) = solve the LP again with the added columns and take the
    integer problem's support from it; 0 = keep the first LP and its support, add the paths of services that are already in that
    support to the integer problem only (no second LP: the round then costs seconds instead of ~30 s of the 120 s stage)."""
    raw = ((os.environ if env is None else env).get(ENV_TARGETED) or "").strip()
    parts = [x.strip() for x in raw.replace(":", ",").split(",")]
    if len(parts) < 3:
        return True
    if parts[2] not in ("0", "1"):
        raise ValueError(f"{ENV_TARGETED}: the third field must be 0 or 1, got {parts[2]!r}")
    return parts[2] == "1"


def lp_duals(lp: Dict) -> Dict[str, Dict]:
    """Duals of the LP relaxation (``_build_and_solve(..., integer=False)``): demand rows by OD index and capacity rows by
    (service, leg).  Rows that are absent (or whose dual the solver did not return) are absent here."""
    dem: Dict[int, float] = {}
    cap: Dict[Tuple[int, int], float] = {}
    for name, con in lp["prob"].constraints.items():
        pi = getattr(con, "pi", None)
        if pi is None:
            continue
        if name.startswith("dem_"):
            dem[int(name[4:])] = float(pi)
        elif name.startswith("cap_"):
            _, si, leg = name.split("_")
            cap[(int(si), int(leg))] = float(pi)
    return {"dem": dem, "cap": cap}


def price_path(path, demand, duals: Dict[str, Dict], di: int) -> float:
    """Reduced profit (USD per TEU) of ``path`` for demand ``di`` under the LP duals."""
    price = float(demand.revenue_per_teu) - float(path.port_cost_per_teu) - duals["dem"].get(di, 0.0)
    for seg in path.segments:
        for leg in seg.legs:
            price -= duals["cap"].get((seg.service, leg), 0.0)
    return price


def select_targeted_paths(lp: Dict, demands: Sequence, paths_by_od: Dict[int, List], all_valid_by_od: Dict[int, List],
                          k_ods: int, m_paths: int, allowed_services=None) -> Tuple[Dict[int, List], Dict]:
    """(extra paths by OD, report).  ``all_valid_by_od``: every valid path per demand (no cap).  ``allowed_services``: only
    paths whose services are all in this set qualify (default: every service with LP rows)."""
    duals = lp_duals(lp)
    active = set(lp["active"]) if allowed_services is None else set(allowed_services)
    u = lp["u"]
    rep: Dict = {"requested": {"ods": k_ods, "paths_per_od": m_paths}, "duals": {"demand_rows": len(duals["dem"]),
                 "capacity_rows": len(duals["cap"])}, "ods_examined": 0, "ods_with_excluded_valid_path": 0,
                 "ods_with_positive_reduced_profit": 0, "ods_selected": 0, "paths_added": 0, "additions": []}
    ranked: List[Tuple[float, int, List[Tuple[float, int, object]]]] = []
    for di, d in enumerate(demands):
        if not d.weekly_teu > 0:
            continue
        rep["ods_examined"] += 1
        lp_unserved = float(u[di].varValue or 0.0) if di in u else 0.0
        if lp_unserved <= 1e-6 * float(d.weekly_teu):
            continue                                       # fully served in the relaxation: not an unserved demand
        rep["ods_lp_unserved"] = rep.get("ods_lp_unserved", 0) + 1
        kept_keys = {(p.services, p.transfer_ports) for p in paths_by_od.get(di, ())}
        excluded = [p for p in all_valid_by_od.get(di, ()) if (p.services, p.transfer_ports) not in kept_keys]
        if not excluded:
            continue
        rep["ods_with_excluded_valid_path"] += 1
        priced = []
        for p in excluded:
            if not all(s in active for s in p.services):
                continue                                   # a service without LP rows cannot be priced here
            priced.append((price_path(p, d, duals, di), len(priced), p))
        priced = [x for x in priced if x[0] > MIN_REDUCED_PROFIT]
        if not priced:
            continue
        rep["ods_with_positive_reduced_profit"] += 1
        priced.sort(key=lambda x: (-x[0], x[2].transit_days, x[1]))
        value = float(d.weekly_teu) * priced[0][0]
        ranked.append((value, di, priced[:m_paths], lp_unserved))
    ranked.sort(key=lambda r: (-r[0], r[1]))
    extra: Dict[int, List] = {}
    for value, di, best, lp_unserved in ranked[:k_ods]:
        extra[di] = [p for _price, _i, p in best]
        rep["additions"].append({"od": di, "weekly_teu": float(demands[di].weekly_teu), "lp_unserved_teu": lp_unserved,
                                 "plausible_value_usd_per_week": value,
                                 "reduced_profit_usd_per_teu": [round(pr, 3) for pr, _i, _p in best],
                                 "paths": [{"services": list(p.services), "transfers": list(p.transfer_ports),
                                            "transit_days": p.transit_days, "port_cost_per_teu": p.port_cost_per_teu}
                                           for _pr, _i, p in best]})
    rep["ods_selected"] = len(extra)
    rep["paths_added"] = sum(len(v) for v in extra.values())
    return extra, rep


def merge_paths(paths_by_od: Dict[int, List], extra: Dict[int, List]) -> Dict[int, List]:
    """New dict: the original paths first (indices unchanged), the additions appended."""
    out = {di: list(pl) for di, pl in paths_by_od.items()}
    for di, add in extra.items():
        out.setdefault(di, []).extend(add)
    return out
