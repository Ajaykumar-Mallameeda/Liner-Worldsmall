"""Exact-LP local search over the operated service set (C2, opt-in, default OFF).

Why
    The time-limited MILP incumbent leaves profit on the table that single, exactly priced
    moves recover: services whose opening pays for itself once every valid path (not only the
    10 fastest per OD) is available, services that lose money, and frequencies one sailing off.
    Measured offline on recorded plans (reports/expansion_2026_10_12): four add moves were
    worth +1.1 .. +1.3 M USD/week.

What it does
    Starting from the MILP plan (services, weekly frequencies), repeatedly applies the single
    move that raises the weekly profit most, until no move gains more than ``min_gain_usd`` or
    the deadline passes.  Moves (each evaluated EXACTLY):

        add   an unoperated service at one weekly departure
        drop  an operated service
        freq  an operated service's frequency +1 / -1

    Profit of a service configuration F = LP_margin(F) - sum_s fixed_cost_s(f_s), where
    LP_margin is the optimum of the same cargo LP as ``flow_reopt.reoptimize_flows``
    (max sum (revenue_od - per-TEU charges_p) q_p; OD demand once; capacity of EVERY leg of
    every service  <= capacity_s * f_s) over all valid, time-feasible paths of the operated
    services, and fixed_cost_s is ``ServiceModel.weekly_fixed_cost`` (vessel hire of
    ceil(T f / 7) vessels + fuel + fixed port calls) - the same terms the MILP objective and the
    independent ledger use.

Hard constraints (a move that breaks one is never evaluated as feasible)
    * class vessel inventory (sum over operated services of ceil(T f / 7) per class <= limit);
    * f <= ``ServiceModel.max_departures(limit)``;
    * leg capacity and OD demand (inside the LP); transit-time limits are in the path set;
    * served TEU never falls below the incumbent's (or a coverage floor): the search may
      trade nothing against coverage.

What it does NOT do
    It never changes a price, cost, constraint or the path rule; it does not run a solver other
    than an LP; it does not claim optimality (a plan it changes is ``feasible``, its bound is
    that of the capped MILP).  The independent ledger verifies whatever is returned.

Time
    The caller gives an absolute deadline (``time.perf_counter()`` instant); no move is started
    after it.  The stage budget (MILP + this search) is split by the caller.
"""

from __future__ import annotations

import math
import os
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

ENV_ENABLED = "LINER_LOCAL_SEARCH"          # 0 | 1  (default 0)
ENV_RESERVE = "LINER_LOCAL_SEARCH_SEC"      # seconds taken from the stage budget (default 15)
ENV_MOVES = "LINER_LOCAL_SEARCH_MOVES"      # comma list of add,drop,freq (default all)
ENV_MULTIHOP = "LINER_LOCAL_SEARCH_MULTIHOP"  # 1: the search's path set enumerates two-transfer journeys for EVERY OD
ENV_VARIANTS = "LINER_LOCAL_SEARCH_VARIANTS"  # fraction of the pool: alternative-class variants visible ONLY to the search
ENV_VARIANTS_FLOOR = "LINER_LOCAL_SEARCH_VARIANTS_FLOOR"  # stand-alone profit floor (USD/week, <= 0) of those variants

ALL_MOVES = ("add", "drop", "freq")
DEFAULT_RESERVE_SEC = 15.0
MAX_RESERVE_FRACTION = 0.5                  # never more than half of the stage budget
MIN_GAIN_USD = 1000.0                       # a move must raise the weekly profit by more than this
COVERAGE_TOL_TEU = 1e-6
FLOW_NOISE_TEU = 1e-6


@dataclass(frozen=True)
class LocalSearchConfig:
    enabled: bool = False
    reserve_sec: float = DEFAULT_RESERVE_SEC
    moves: Tuple[str, ...] = ALL_MOVES
    max_iterations: int = 60
    min_gain_usd: float = MIN_GAIN_USD
    # enumerate two-transfer journeys for every OD (not only where the shorter journeys are too few): a
    # richer evaluator at the price of ~10 s of path construction inside the reserve
    multi_hop: bool = False

    def __post_init__(self):
        if not (0.0 < self.reserve_sec <= 3600.0):
            raise ValueError("local-search reserve must be in (0, 3600] seconds")
        bad = [m for m in self.moves if m not in ALL_MOVES]
        if bad or not self.moves:
            raise ValueError(f"local-search moves must be a non-empty subset of {ALL_MOVES}, got {self.moves!r}")


def config_from_environment(env: Optional[Dict[str, str]] = None) -> LocalSearchConfig:
    """Unset = disabled.  A malformed value raises ``ValueError`` (never silently replaced)."""
    e = os.environ if env is None else env
    raw = (e.get(ENV_ENABLED) or "").strip().lower()
    if raw in ("", "0", "false", "no", "off"):
        return LocalSearchConfig(enabled=False)
    if raw not in ("1", "true", "yes", "on"):
        raise ValueError(f"{ENV_ENABLED} must be 0 or 1, got {raw!r}")
    kw: Dict = {"enabled": True}
    r = (e.get(ENV_RESERVE) or "").strip()
    if r:
        try:
            kw["reserve_sec"] = float(r)
        except ValueError:
            raise ValueError(f"{ENV_RESERVE} must be a number of seconds, got {r!r}") from None
    m = (e.get(ENV_MOVES) or "").strip().lower()
    if m:
        kw["moves"] = tuple(x.strip() for x in m.split(",") if x.strip())
    mh = (e.get(ENV_MULTIHOP) or "").strip().lower()
    if mh in ("1", "true", "yes", "on"):
        kw["multi_hop"] = True
    elif mh not in ("", "0", "false", "no", "off"):
        raise ValueError(f"{ENV_MULTIHOP} must be 0 or 1, got {mh!r}")
    return LocalSearchConfig(**kw)


def variants_from_environment(env: Optional[Dict[str, str]] = None) -> float:
    """Fraction of the unique pool offered to the SEARCH as extra alternative-class services (they never
    enter the MILP, so they cannot slow it down).  0 / unset = none.  See src/network/class_variants.py."""
    raw = ((os.environ if env is None else env).get(ENV_VARIANTS) or "").strip()
    if not raw:
        return 0.0
    try:
        v = float(raw)
    except ValueError:
        raise ValueError(f"{ENV_VARIANTS} must be a fraction in [0, 1], got {raw!r}") from None
    if not (0.0 <= v <= 1.0):
        raise ValueError(f"{ENV_VARIANTS} must be a fraction in [0, 1], got {v}")
    return v


def variants_floor_from_environment(env: Optional[Dict[str, str]] = None) -> Optional[float]:
    """Stand-alone profit floor (USD/week, <= 0) of the search-only variants.  A variant that loses money
    stand-alone can still be worth opening as a complement; the search prices every move EXACTLY and keeps
    it only when the plan's profit rises, so a negative floor cannot buy a loss.  Unset = ``None``: the
    generator's own default applies (``LINER_CLASS_VARIANTS_FLOOR`` if set, else 0 = positive only)."""
    raw = ((os.environ if env is None else env).get(ENV_VARIANTS_FLOOR) or "").strip()
    if not raw:
        return None
    try:
        v = float(raw)
    except ValueError:
        raise ValueError(f"{ENV_VARIANTS_FLOOR} must be a number <= 0, got {raw!r}") from None
    if v != v or v in (float("inf"), float("-inf")) or v > 0:
        raise ValueError(f"{ENV_VARIANTS_FLOOR} must be a finite number <= 0, got {v}")
    return v


def reserve_for(cfg: LocalSearchConfig, stage_budget_sec: float) -> float:
    """Seconds of the stage budget given to the search (never more than half of it)."""
    return min(cfg.reserve_sec, MAX_RESERVE_FRACTION * float(stage_budget_sec))


class _Evaluator:
    """Cargo LP over a fixed column set (all valid paths of the pool)."""

    def __init__(self, models, demands, all_paths: Dict[int, List], plan_paths: Optional[Dict[int, List]] = None):
        from scipy.optimize import linprog                       # scipy is a pinned requirement
        from scipy.sparse import coo_matrix
        import numpy as np
        self._linprog, self._coo, self._np = linprog, coo_matrix, np
        self.models, self.demands = models, demands
        self.cols: List[Tuple[int, object, frozenset, float, Tuple]] = []
        self.by_service: Dict[int, List[int]] = defaultdict(list)
        # the plan's own paths are always columns: the incumbent is then feasible in the evaluator by
        # construction (a path the MILP / earlier steps used may lie outside the enumerated set)
        merged: Dict[int, List] = {di: list(pl) for di, pl in all_paths.items()}
        if plan_paths:
            seen = {(di, tuple(p.services), tuple(p.transfer_ports), tuple(s.legs for s in p.segments))
                    for di, pl in merged.items() for p in pl}
            for di, pl in plan_paths.items():
                for p in pl:
                    key = (di, tuple(p.services), tuple(p.transfer_ports), tuple(s.legs for s in p.segments))
                    if key not in seen:
                        seen.add(key)
                        merged.setdefault(di, []).append(p)
        for di, plist in merged.items():
            if not demands[di].weekly_teu > 0:
                continue
            for p in plist:
                j = len(self.cols)
                legs = tuple((seg.service, leg) for seg in p.segments for leg in seg.legs)
                self.cols.append((di, p, frozenset(p.services),
                                  float(demands[di].revenue_per_teu - p.port_cost_per_teu), legs))
                for s in set(p.services):
                    self.by_service[s].append(j)
        self.n_lp = 0

    def columns_for(self, services) -> List[int]:
        S = frozenset(services)
        out, seen = [], set()
        for s in S:
            for j in self.by_service.get(s, ()):
                if j not in seen:
                    seen.add(j)
                    if self.cols[j][2] <= S:
                        out.append(j)
        return out

    def solve(self, freq: Dict[int, int], ids: Sequence[int], floor_teu: float = 0.0,
              want_flows: bool = False):
        """(margin, served_teu, {col: q}) of the best routing, or None if the floor is unattainable."""
        self.n_lp += 1
        if not ids:
            return (0.0, 0.0, {}) if floor_teu <= COVERAGE_TOL_TEU else None
        np = self._np
        od_row: Dict[int, int] = {}
        leg_row: Dict[Tuple[int, int], int] = {}
        rows, cs, b = [], [], []
        cvec = np.empty(len(ids))
        for ci, j in enumerate(ids):
            di, _p, _S, margin, legs = self.cols[j]
            r = od_row.get(di)
            if r is None:
                r = od_row[di] = len(b)
                b.append(float(self.demands[di].weekly_teu))
            rows.append(r)
            cs.append(ci)
            cvec[ci] = -margin
            for key in legs:
                r = leg_row.get(key)
                if r is None:
                    r = leg_row[key] = len(b)
                    b.append(float(self.models[key[0]].capacity_teu * freq[key[0]]))
                rows.append(r)
                cs.append(ci)
        vals = [1.0] * len(rows)
        n_rows = len(b)
        if floor_teu > COVERAGE_TOL_TEU:                      # sum q >= floor  <=>  -sum q <= -floor
            for ci in range(len(ids)):
                rows.append(n_rows)
                cs.append(ci)
                vals.append(-1.0)
            b.append(-float(floor_teu))
            n_rows += 1
        A = self._coo((vals, (rows, cs)), shape=(n_rows, len(ids))).tocsr()
        r = self._linprog(cvec, A_ub=A, b_ub=np.array(b), bounds=(0, None), method="highs")
        if not r.success:
            return None
        flows = {}
        if want_flows:
            for ci, j in enumerate(ids):
                if r.x[ci] > FLOW_NOISE_TEU:
                    flows[j] = float(r.x[ci])
        return float(-r.fun), float(r.x.sum()), flows


def local_search(models, demands, paths: Dict[int, List], sol, class_limits: Dict[str, int],
                 build_all_paths, *, config: LocalSearchConfig, deadline: float,
                 min_served_teu: float = 0.0) -> Dict:
    """Improve ``sol`` in place when (and only when) the exact evaluator shows a gain; return a report.

    ``build_all_paths()`` -> (dict od -> [OdPath], stats): every valid time-feasible path of the pool.
    ``deadline`` is a ``time.perf_counter()`` instant; no evaluation starts after it."""
    t_start = time.perf_counter()
    rep: Dict = {"applied": False, "reason": "", "moves": [], "evaluations": 0, "iterations": 0,
                 "profit_before": None, "profit_after": None, "served_before": None, "served_after": None,
                 "gain_usd": 0.0, "setup_sec": 0.0, "search_sec": 0.0, "terminated_by": "",
                 "reserve_sec": config.reserve_sec, "moves_enabled": list(config.moves)}
    f0 = {si: int(fr) for si, fr in sol.frequencies.items() if fr > 0}
    if not f0 or not sol.flows:
        rep.update(reason="no operated service", terminated_by="no_incumbent")
        return rep
    try:
        full, _stats = build_all_paths()
        ev = _Evaluator(models, demands, full, plan_paths=paths)
    except Exception as exc:                                         # noqa: BLE001
        rep.update(reason=f"evaluator unavailable: {type(exc).__name__}: {exc}", terminated_by="error")
        return rep
    rep["setup_sec"] = round(time.perf_counter() - t_start, 2)
    if time.perf_counter() >= deadline:
        rep.update(reason="deadline reached during set-up", terminated_by="deadline_before_search")
        return rep

    def vessels_used(freq) -> Dict[str, int]:
        used: Dict[str, int] = defaultdict(int)
        for s, f in freq.items():
            used[models[s].vessel_class] += models[s].vessels(f)
        return used

    def fixed(freq) -> float:
        return sum(models[s].weekly_fixed_cost(f) for s, f in freq.items())

    incumbent_served = float(sum(t for _, _, t in sol.flows))
    floor = max(float(min_served_teu), incumbent_served) - COVERAGE_TOL_TEU
    cur = dict(f0)
    cur_ids = ev.columns_for(cur)
    base = ev.solve(cur, cur_ids, floor)
    if base is None:
        rep.update(reason="incumbent infeasible in the evaluator", terminated_by="error")
        return rep
    cur_margin, cur_served, _ = base
    cur_profit = cur_margin - fixed(cur)
    start_profit = cur_profit
    rep.update(profit_before=cur_profit, served_before=incumbent_served)
    used = vessels_used(cur)

    def room(cls: str) -> int:
        return int(class_limits.get(cls, 0)) - used.get(cls, 0)

    def expired() -> bool:
        return time.perf_counter() >= deadline

    # ORDERING heuristic for the add moves (not a bound, nothing is pruned on it): gross margin the
    # service could earn at one weekly departure if every TEU-leg of its capacity earned the best unit
    # margin of its columns, minus its fixed cost.  Services with no column are never candidates.
    ub_open: Dict[int, float] = {}
    for s in range(len(models)):
        cols = ev.by_service.get(s)
        if not cols or s in cur:
            continue
        best_margin = max(ev.cols[j][3] for j in cols)
        gross = models[s].capacity_teu * len(models[s].legs) * max(best_margin, 0.0)
        ub_open[s] = gross - models[s].weekly_fixed_cost(1)
    add_queue = sorted(ub_open, key=lambda s: -ub_open[s])
    stale: Dict[int, float] = {}            # last evaluated delta of an add (lazy greedy)
    t_search = time.perf_counter()
    terminated = "local_optimum"

    for it in range(config.max_iterations):
        if expired():
            terminated = "deadline"
            break
        best = None                                          # (profit, kind, service, f, ids, served)
        # --- operated services: drop / frequency moves (cheap: few services) ---------------------
        if "drop" in config.moves or "freq" in config.moves:
            for s, f in list(cur.items()):
                if expired():
                    break
                trial_moves = []
                if "drop" in config.moves:
                    trial_moves.append(("drop", s, 0))
                if "freq" in config.moves:
                    cls = models[s].vessel_class
                    if (f + 1 <= models[s].max_departures(int(class_limits.get(cls, 0)))
                            and room(cls) >= models[s].vessels(f + 1) - models[s].vessels(f)):
                        trial_moves.append(("up", s, f + 1))
                    if f > 1:
                        trial_moves.append(("down", s, f - 1))
                for kind, s2, f2 in trial_moves:
                    trial = dict(cur)
                    if kind == "drop":
                        trial.pop(s2)
                        ids = [j for j in cur_ids if s2 not in ev.cols[j][2]]
                    else:
                        trial[s2] = f2
                        ids = cur_ids
                    got = ev.solve(trial, ids, floor)
                    rep["evaluations"] += 1
                    if got is None:
                        continue
                    pr = got[0] - fixed(trial)
                    if best is None or pr > best[0]:
                        best = (pr, kind, s2, f2, ids, got[1])
        # --- unoperated services: add at f=1, lazy greedy over the UB-ordered queue -------------
        if "add" in config.moves and not expired():
            order = sorted((s for s in add_queue if s not in cur),
                           key=lambda s: -(stale.get(s, ub_open.get(s, 0.0))))
            best_add = None
            for s in order:
                if expired():
                    break
                # lazy: stale values are optimistic upper bounds only if they were measured at an
                # earlier (smaller) network; skip when even the stale value cannot beat the best
                if best_add is not None and stale.get(s, float("inf")) + 1.0 < best_add[0] - cur_profit:
                    continue
                cls = models[s].vessel_class
                if room(cls) < models[s].vessels(1) or models[s].max_departures(int(class_limits.get(cls, 0))) < 1:
                    continue
                S = set(cur) | {s}
                ids = cur_ids + [j for j in ev.by_service.get(s, ()) if ev.cols[j][2] <= S]
                trial = dict(cur)
                trial[s] = 1
                got = ev.solve(trial, ids, floor)
                rep["evaluations"] += 1
                if got is None:
                    continue
                pr = got[0] - fixed(trial)
                stale[s] = pr - cur_profit
                if best_add is None or pr > best_add[0]:
                    best_add = (pr, "add", s, 1, ids, got[1])
            if best_add is not None and (best is None or best_add[0] > best[0]):
                best = best_add
        if best is None:
            terminated = "deadline" if expired() else "local_optimum"
            break
        if best[0] <= cur_profit + config.min_gain_usd:
            terminated = "deadline" if expired() else "local_optimum"
            break
        pr, kind, s, f, ids, srv = best
        if kind == "drop":
            cur.pop(s)
        else:
            cur[s] = f
        cur_ids = ids            # add: extended; drop: filtered; up/down: unchanged (same service set)
        used = vessels_used(cur)
        rep["moves"].append({"iter": it, "move": kind, "service": models[s].service_id, "f": f,
                             "profit": round(pr, 1), "gain": round(pr - cur_profit, 1),
                             "served_teu": round(srv, 1),
                             "t_sec": round(time.perf_counter() - t_start, 2)})
        cur_profit, cur_served = pr, srv
        rep["iterations"] = it + 1
    else:
        terminated = "max_iterations"
    rep["search_sec"] = round(time.perf_counter() - t_search, 2)
    rep["terminated_by"] = terminated
    rep["profit_after"] = cur_profit
    rep["served_after"] = cur_served
    rep["gain_usd"] = cur_profit - start_profit
    if not rep["moves"] or cur_profit <= start_profit + config.min_gain_usd:
        rep["reason"] = "no move raises the weekly profit"
        rep["profit_after"] = start_profit
        rep["served_after"] = incumbent_served
        rep["gain_usd"] = 0.0
        return rep

    # ---- apply: final exact routing at the final configuration (flows over the evaluator's paths) --
    final_ids = ev.columns_for(cur)
    got = ev.solve(cur, final_ids, floor, want_flows=True)
    if got is None:
        rep.update(reason="final routing infeasible", terminated_by="error", profit_after=start_profit,
                   served_after=incumbent_served, gain_usd=0.0)
        return rep
    margin, served_final, carrying = got
    known = {(di, tuple(p.services), tuple(p.transfer_ports), tuple(s.legs for s in p.segments)): k
             for di, plist in paths.items() for k, p in enumerate(plist)}
    new_flows: List[Tuple[int, int, float]] = []
    served_by_od: Dict[int, float] = defaultdict(float)
    appended = 0
    for j, val in carrying.items():
        di, p = ev.cols[j][0], ev.cols[j][1]
        key = (di, tuple(p.services), tuple(p.transfer_ports), tuple(s.legs for s in p.segments))
        k = known.get(key)
        if k is None:
            paths.setdefault(di, [])
            paths[di].append(p)
            k = len(paths[di]) - 1
            known[key] = k
            appended += 1
        new_flows.append((di, k, val))
        served_by_od[di] += val
    revenue = sum(demands[di].revenue_per_teu * t for di, _k, t in new_flows)
    port = sum(paths[di][k].port_cost_per_teu * t for di, k, t in new_flows)
    comp = dict(sol.objective_components)
    comp["revenue"], comp["per_teu_port_cost"] = revenue, port
    comp["vessel_cost"] = sum(models[s].vessel_week_cost * models[s].vessels(f) for s, f in cur.items())
    comp["fuel_cost"] = sum(models[s].fuel_cost_per_rotation * f for s, f in cur.items())
    comp["port_fixed_cost"] = sum(models[s].port_fixed_per_rotation * f for s, f in cur.items())
    pen = comp.get("unserved_penalty", 0.0)
    sol.frequencies = {s: int(f) for s, f in cur.items()}
    sol.vessels = {s: int(models[s].vessels(f)) for s, f in cur.items()}
    sol.objective_value = (revenue - port - comp["vessel_cost"] - comp["fuel_cost"]
                           - comp["port_fixed_cost"] - pen)
    sol.objective_components = comp
    sol.flows = sorted(new_flows)
    sol.unserved = {di: max(0.0, float(demands[di].weekly_teu) - served_by_od.get(di, 0.0))
                    for di, d in enumerate(demands) if d.weekly_teu > 0}
    rep.update(applied=True, reason="services / frequencies changed by exact-LP moves",
               paths_added=appended, profit_after=margin - fixed(cur), served_after=served_final,
               gain_usd=(margin - fixed(cur)) - start_profit, lp_evaluations=ev.n_lp,
               services_after=len(cur), vessels_after=sum(used.values()))
    return rep


#: a routed quantity at or below this is solver noise, not cargo (same as flow_reopt / the MILP)
IDLE_TEU = 1e-6


def prune_idle_services(models, paths: Dict[int, List], sol) -> Dict:
    """Drop every operated service that carries NO cargo in the final flows.

    Found by the hold-out gate (campaign 2026-10-12, seed 17): the last move of the search added a
    one-vessel service for a 9 k USD/week gain, then the final re-routing found better paths and the
    service ended up empty - a vessel hired for nothing (74.5 k USD/week).  An idle service changes
    neither cargo nor coverage, so removing it can only raise profit (by its weekly fixed cost) and
    frees its vessels.  Applied only inside the opt-in local-search stage, after the re-routing and
    the profit-floor repair; frequencies, vessels and the cost terms of the objective are updated from
    the same service models the MILP and the independent ledger use.
    """
    rep: Dict = {"applied": False, "dropped": [], "gain_usd": 0.0}
    carrying = set()
    for di, k, teu in sol.flows:
        if teu > IDLE_TEU:
            carrying.update(paths[di][k].services)
    idle = sorted(si for si, f in sol.frequencies.items() if f > 0 and si not in carrying)
    if not idle:
        return rep
    comp = dict(sol.objective_components)
    saved = 0.0
    for si in idle:
        f = int(sol.frequencies[si])
        m = models[si]
        comp["vessel_cost"] = comp.get("vessel_cost", 0.0) - m.vessel_week_cost * m.vessels(f)
        comp["fuel_cost"] = comp.get("fuel_cost", 0.0) - m.fuel_cost_per_rotation * f
        comp["port_fixed_cost"] = comp.get("port_fixed_cost", 0.0) - m.port_fixed_per_rotation * f
        saved += m.weekly_fixed_cost(f)
        rep["dropped"].append({"service": m.service_id, "vessel_class": m.vessel_class,
                               "frequency": f, "vessels": int(m.vessels(f)),
                               "weekly_fixed_cost_usd": round(float(m.weekly_fixed_cost(f)), 1)})
    keep = {si: int(f) for si, f in sol.frequencies.items() if f > 0 and si not in set(idle)}
    sol.frequencies = keep
    sol.vessels = {si: int(models[si].vessels(f)) for si, f in keep.items()}
    sol.objective_components = comp
    sol.objective_value = sol.objective_value + saved
    rep.update(applied=True, gain_usd=float(saved))
    return rep
