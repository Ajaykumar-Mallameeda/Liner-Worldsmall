"""Controlled global-stage experiment for Tasks 15 and 16 (WorldSmall only).

For one generator seed the SAME production candidate pool (default configuration:
demand-coherent loops budget 60 + class screening k=1, regional ``_filter_services``)
goes through the SAME production global stage ``src.network.reconcile.reconcile``
(NetworkPlanner = path MILP + independent ledger + regional partition).  The only thing
that varies between strategies is the solve step: ``src.network.plan.solve_network`` is
replaced, inside this process only, by the strategy under test.  Planning, path
construction, the independent ledger and the regional partition are the production code.

usage:
    python -I global_stage_experiment.py <tree_root> <out.json> <seed> <time_limit_sec> <strategy> [...]

strategy grammar
    prod                   production: LP relaxation -> restrict to its support -> integer solve
    fullint                unrestricted integer problem (no restriction)
    two:<T1>               two-stage: production restricted solve with budget T1, then the
                           unrestricted integer problem warm-started from its incumbent for the
                           remaining budget; the best valid incumbent is kept
    A_sa                   restricted to LP support  U  stand-alone-profitable candidates
    A_pert                 restricted to the union of the supports of the LP and two LPs with
                           perturbed vessel costs (x0.8, x1.2)
    A_top<K>               restricted to the K LP-support services carrying the most LP revenue
    A_pool<K>              restricted to LP support U the K candidates of largest LP-ranked
                           stand-alone profit (K integer)
    prog:<k1,k2,..>        CBC only: nested restrictions of the LP support (top-k by LP revenue),
                           smallest first, each warm-started from the previous incumbent; the
                           best valid incumbent is kept
    highs                  (information only) the unrestricted integer model solved by HiGHS
                           through scipy.optimize.milp - NOT a production solver

Environment: nothing is set here; the production defaults apply (so the pool is the
production default).  ``T16_FILTER`` is read by the tree under test, not by this tool.
"""
import hashlib
import json
import math
import os
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))
OUT = Path(sys.argv[2])
SEED = int(sys.argv[3])
TL = float(sys.argv[4])
STRATS = sys.argv[5:]

import pulp                                                            # noqa: E402

import src.network.network_milp as nm                                  # noqa: E402
import src.network.plan as planmod                                     # noqa: E402
from src.agents.regional_agent import RegionalAgent                    # noqa: E402
from src.agents.service_generator_agent import ServiceGeneratorAgent   # noqa: E402
from src.data.network_loader import NetworkLoader                      # noqa: E402
from src.decomposition.port_clustering import PortClustering           # noqa: E402
from src.decomposition.regional_splitter import RegionalSplitter       # noqa: E402
from src.network.metrics import canonical_network_economics            # noqa: E402
from src.network.reconcile import canonical_rotation, collect_candidates, reconcile  # noqa: E402
from src.optimization.adaptive_budget import (                         # noqa: E402
    AdaptiveBudget, compute_complexity_signals,
)
from src.optimization.data import Problem                              # noqa: E402

ORIG_SOLVE = nm.solve_network
REGIONS = ["Asia", "Europe", "Americas"]            # orchestrator: regional_agents[:3]
DIAG = {}                                           # strategy diagnostics of the current solve
FILTER_LOG = []                                     # per-region filter decisions (Task 16)

if os.environ.get("T16_FILTER"):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import t16_filter_variants as _t16                                  # noqa: E402
    from src.network.economics import assumptions_for_problem as _afp  # noqa: E402
    from src.services.class_screening import ClassScreener as _CS, ClassScreeningConfig as _CSC  # noqa: E402

    def _log(region, variant, rows, cap):
        FILTER_LOG.append({"region": region, "variant": variant, "cap": cap, "candidates": rows})

    _t16.install(RegionalAgent, _CS, _CSC, _afp, _log)

ws = ROOT / "data" / "raw" / "WorldSmall"
_L = NetworkLoader()
_ports = _L.load_ports(ws / "ports.csv")
_demands = _L.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
_dist = _L.load_distance_matrix(ws / "dist_dense.csv")
_fleet = _L.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")
for _p in _ports:
    _dist.setdefault(_p.id, {})


def fresh_problem() -> Problem:
    return Problem(ports=_ports, services=[], demands=_demands, distance_matrix=_dist, fleet=_fleet)


# ----------------------------------------------------------------------------- pool
def build_pools(seed: int) -> dict:
    base = fresh_problem()
    clusters = PortClustering(n_clusters=3).cluster_ports(base.ports)
    regional = RegionalSplitter(base).split(clusters)
    pools, gen, region_of_od = {}, {}, {}
    for idx, (ci, rp) in enumerate(sorted(regional.items())):
        region = REGIONS[idx]
        for d in rp.demands:
            region_of_od[(d.origin, d.destination)] = region
        random.seed(seed * 100 + idx)
        agent = ServiceGeneratorAgent(name=f"svc_gen_{region}", model="none")
        services = agent.generate_services(rp, archetype_params=None)
        prefix = region.lower().replace(" ", "_")
        for i, s in enumerate(services):
            s.id = f"{prefix}_svc_{i:03d}"
        rp.services = services
        sig = compute_complexity_signals(num_ports=len(rp.ports), demands=rp.demands, fleet=rp.fleet)
        budget = AdaptiveBudget.from_signals(sig)
        ra = RegionalAgent(f"regional_{prefix}", region, "none")
        n_generated = len(services)
        rp = ra._filter_services(rp, budget)
        pools[region] = [
            {"id": str(s.id), "ports": list(s.ports), "vessel_class": s.vessel_class,
             "section": getattr(s, "origin_section", "unknown")}
            for s in rp.services]
        gen[region] = {"generated": n_generated, "after_filter": len(rp.services),
                       "filter_max_services": budget.filter_max_services,
                       "by_class_after_filter": dict(Counter(s.vessel_class for s in rp.services))}
    return {"pools": pools, "gen": gen, "region_of_od": region_of_od}


def pool_identity(pools: dict) -> dict:
    h = hashlib.sha256()
    for region in sorted(pools):
        for c in pools[region]:
            h.update(f"{region}|{c['id']}|{','.join(c['ports'])}|{c['vessel_class']}\n".encode())
    cands, _ = collect_candidates({k: [dict(c) for c in v] for k, v in pools.items()})
    u = hashlib.sha256()
    for c in cands:
        u.update(f"{','.join(c.ports)}|{c.vessel_class}\n".encode())
    return {"regional_pool_sha256": h.hexdigest(), "unique_candidates": len(cands),
            "unique_order_sha256": u.hexdigest(),
            "regional_sizes": {k: len(v) for k, v in pools.items()}}


# ----------------------------------------------------------------------------- strategies
def _finish(res, sol, t0, models=None):
    """Fill a NetworkSolution from a ``_build_and_solve`` result exactly as the production
    ``solve_network`` does (status / values / objective components)."""
    prob = res["prob"]
    sol.n_variables = len(res["f"]) + len(res["n"]) + len(res["q"]) + len(res["u"])
    sol.n_constraints = len(prob.constraints)
    sol.runtime_sec = time.perf_counter() - t0
    if res["error"]:
        sol.status, sol.message = "solver_error", res["error"]
        return sol
    sol.solver_status = pulp.LpStatus.get(prob.status, str(prob.status))
    if prob.status == pulp.LpStatusInfeasible:
        sol.status = "infeasible"
        return sol
    if prob.status != pulp.LpStatusOptimal:
        sol.status, sol.message = "not_solved", f"solver status {sol.solver_status}"
        return sol
    f, n, q, u = res["f"], res["n"], res["q"], res["u"]
    if any(v.varValue is None for v in list(f.values()) + list(q.values())):
        sol.status, sol.message = "not_solved", "no variable values"
        return sol
    closed = getattr(prob, "sol_status", 1) == pulp.LpSolutionOptimal
    sol.status = "optimal" if closed else "feasible"      # as solve_network does
    sol.objective_value = float(pulp.value(prob.objective) or 0.0)
    sol.frequencies = {si: int(round(f[si].varValue or 0)) for si in res["active"]}
    sol.vessels = {si: int(round(n[si].varValue or 0)) for si in res["active"]}
    for (di, k), v in q.items():
        val = float(v.varValue or 0.0)
        if val > getattr(nm, "FLOW_NOISE_TEU", 1e-9):      # Task 15 noise cut (if present)
            sol.flows.append((di, k, val))
    sol.unserved = {di: float(u[di].varValue or 0.0) for di in u}
    t = res["terms"]
    sol.objective_components = {
        "revenue": float(pulp.value(t["revenue"]) or 0.0),
        "per_teu_port_cost": float(pulp.value(t["per_teu_port"]) or 0.0),
        "vessel_cost": float(pulp.value(t["vessel_cost"]) or 0.0),
        "fuel_cost": float(pulp.value(t["fuel_cost"]) or 0.0),
        "port_fixed_cost": float(pulp.value(t["port_fixed"]) or 0.0),
        "unserved_penalty": float(pulp.value(t["pen"]) or 0.0),
    }
    trim = getattr(nm, "_trim_slack_vessels", None)        # Task 15 patch A (if present)
    if trim is not None and models is not None:
        trim(models, sol, res["active"])
    return sol


def _base_kwargs(kw):
    return dict(penalty=kw.get("unserved_penalty_per_teu", 0.0), fixed=None,
                max_departures_cap=kw.get("max_departures_cap"), threads=kw.get("threads"),
                total_vessel_limit=kw.get("total_vessel_limit"),
                port_capacity=kw.get("port_capacity"),
                min_served_fraction=kw.get("min_served_fraction"))


def _lp(models, demands, paths, limits, services, kw, tl):
    return nm._build_and_solve(models, demands, paths, limits, services, integer=False,
                               initial=None, time_limit_sec=tl, **_base_kwargs(kw))


def strat_prod(models, demands, paths, limits, **kw):
    return ORIG_SOLVE(models, demands, paths, limits, **kw)


def strat_fullint(models, demands, paths, limits, **kw):
    kw = dict(kw)
    kw["lp_guided"] = False
    return ORIG_SOLVE(models, demands, paths, limits, **kw)


def polished_objective(models, sol):
    """Objective of the SAME plan with the minimum vessels ``ceil(T f / 7)`` on every
    service.  A time-limited incumbent may carry slack vessels (the solver stops before
    removing them); the independent ledger always uses the minimum, so this is the
    ledger-comparable value of the incumbent."""
    if not sol.usable:
        return float("-inf")
    excess = 0.0
    for si, n in sol.vessels.items():
        f = sol.frequencies.get(si, 0)
        excess += max(0, int(n) - models[si].vessels(int(f))) * models[si].vessel_week_cost
    return sol.objective_value + excess


def make_two_stage(t1):
    def f(models, demands, paths, limits, **kw):
        t0 = time.perf_counter()
        total = float(kw["time_limit_sec"])
        s1 = ORIG_SOLVE(models, demands, paths, limits, **{**kw, "time_limit_sec": min(t1, total)})
        used = time.perf_counter() - t0
        rem = max(1.0, total - used)
        init = {si: fr for si, fr in s1.frequencies.items() if fr > 0} if s1.usable \
            else kw.get("initial_frequencies")
        s2 = ORIG_SOLVE(models, demands, paths, limits,
                        **{**kw, "time_limit_sec": rem, "lp_guided": False,
                           "initial_frequencies": init})
        DIAG["stage1"] = {"status": s1.status, "objective": s1.objective_value,
                          "bound": s1.relaxation_bound, "runtime": s1.runtime_sec,
                          "restricted_to": s1.n_services_restricted_to}
        DIAG["stage2"] = {"status": s2.status, "objective": s2.objective_value,
                          "runtime": s2.runtime_sec, "budget": rem,
                          "solver_status": s2.solver_status}
        o1, o2 = polished_objective(models, s1), polished_objective(models, s2)
        DIAG["stage1"]["polished_objective"] = o1
        DIAG["stage2"]["polished_objective"] = o2
        take2 = s2.usable and (not s1.usable or o2 >= o1 - 1e-6)
        best = s2 if take2 else s1
        if best.relaxation_bound is None:
            best.relaxation_bound = s1.relaxation_bound
        DIAG["kept"] = "stage2" if take2 else "stage1"
        best.runtime_sec = time.perf_counter() - t0
        return best
    return f


def _standalone_profit(models, demands, port_lookup=None):
    """Stand-alone weekly profit of every modelled candidate at f=1 (own capacity, direct
    cargo only, LP per candidate)."""
    import numpy as np
    from scipy.optimize import linprog
    dem = {(d.origin, d.destination): d for d in demands if d.weekly_teu > 0}
    out = {}
    for si, m in enumerate(models):
        legs = len(m.ports)
        ods = []
        for a in m.ports:
            for b in m.ports:
                d = dem.get((a, b)) if a != b else None
                if d is None:
                    continue
                r = m.ride(a, b)
                if r is None:
                    continue
                if d.max_transit_days is not None and r[1] > d.max_transit_days + 1e-9:
                    continue
                ods.append((d, r[0]))
        fixed = m.weekly_fixed_cost(1)
        if not ods:
            out[si] = -fixed
            continue
        c = -np.array([x[0].revenue_per_teu for x in ods])
        A = np.zeros((legs, len(ods)))
        for j, (_, lg) in enumerate(ods):
            for l in lg:
                A[l, j] = 1.0
        res = linprog(c, A_ub=A, b_ub=np.full(legs, m.capacity_teu),
                      bounds=[(0, x[0].weekly_teu) for x in ods], method="highs")
        out[si] = (-res.fun if res.success else 0.0) - fixed
    return out


def make_restricted(kind):
    """LP-guided restriction variants (Strategy A)."""
    def f(models, demands, paths, limits, **kw):
        t0 = time.perf_counter()
        total = float(kw["time_limit_sec"])
        referenced = sorted({s for pl in paths.values() for p in pl for s in p.services})
        sol = nm.NetworkSolution(status="not_solved", n_services_considered=len(referenced),
                                 n_paths=sum(len(v) for v in paths.values()))
        lp = _lp(models, demands, paths, limits, referenced, kw, min(60.0, max(1.0, total) * 0.4))
        if lp["error"] or lp["prob"].status != pulp.LpStatusOptimal:
            return ORIG_SOLVE(models, demands, paths, limits, **kw)
        sol.relaxation_bound = float(pulp.value(lp["prob"].objective) or 0.0)
        support = [si for si in lp["active"] if (lp["f"][si].varValue or 0.0) > 1e-6]
        chosen = set(support)
        t_sel = time.perf_counter()
        extra_note = {}
        if kind == "A_sa":
            sa = _standalone_profit(models, demands)
            extra = {si for si in referenced if sa.get(si, -1) > 0}
            chosen |= extra
            extra_note["standalone_profitable"] = len(extra)
        elif kind.startswith("A_top"):
            # smaller restriction: keep only the K LP-support services that carry the most
            # LP revenue (path revenue split evenly over the services of the path)
            k = int(kind[len("A_top"):])
            value = defaultdict(float)
            for (di, kk), v in lp["q"].items():
                qv = v.varValue or 0.0
                if qv > 1e-9:
                    pth = paths[di][kk]
                    share = qv * demands[di].revenue_per_teu / max(1, len(set(pth.services)))
                    for si in set(pth.services):
                        value[si] += share
            ranked = sorted(support, key=lambda si: (-value[si], si))[:k]
            chosen = set(ranked)
            extra_note["top_k"] = k
        elif kind.startswith("A_pool"):
            k = int(kind[len("A_pool"):])
            sa = _standalone_profit(models, demands)
            ranked = sorted(referenced, key=lambda si: -sa.get(si, -1e18))[:k]
            chosen |= set(ranked)
            extra_note["top_k"] = k
        elif kind == "A_pert":
            import copy
            for scale in (0.8, 1.2):
                pm = []
                for m in models:
                    pm.append(type(m)(**{**m.__dict__, "vessel_week_cost": m.vessel_week_cost * scale}))
                lp2 = _lp(pm, demands, paths, limits, referenced, kw, min(30.0, total * 0.2))
                if not lp2["error"] and lp2["prob"].status == pulp.LpStatusOptimal:
                    chosen |= {si for si in lp2["active"] if (lp2["f"][si].varValue or 0.0) > 1e-6}
            extra_note["perturbed_lps"] = 2
        services = sorted(chosen)
        DIAG["restriction"] = {"lp_support": len(support), "chosen": len(services),
                               "referenced": len(referenced), "lp_active": len(lp["active"]),
                               "selection_sec": round(time.perf_counter() - t_sel, 1), **extra_note}
        dropped = len(services) < len(lp["active"])
        sol.n_services_restricted_to = len(services)
        budget = max(1.0, total - (time.perf_counter() - t0))
        res = nm._build_and_solve(models, demands, paths, limits, services, integer=True,
                                  initial=kw.get("initial_frequencies"), time_limit_sec=budget,
                                  fixed=None, penalty=kw.get("unserved_penalty_per_teu", 0.0),
                                  max_departures_cap=kw.get("max_departures_cap"),
                                  threads=kw.get("threads"),
                                  total_vessel_limit=kw.get("total_vessel_limit"),
                                  port_capacity=kw.get("port_capacity"),
                                  min_served_fraction=kw.get("min_served_fraction"))
        sol = _finish(res, sol, t0, models)
        if sol.status == "optimal" and dropped:
            sol.status = "feasible"          # a service was dropped: not a proof
        return sol
    return f


def make_progressive(ks):
    """CBC only: solve nested restrictions of the LP support, smallest first, each warm-started
    from the previous incumbent; the best valid incumbent is always kept.  The support is ranked
    by the LP revenue each service carries (path revenue split over its services)."""
    def f(models, demands, paths, limits, **kw):
        t0 = time.perf_counter()
        total = float(kw["time_limit_sec"])
        referenced = sorted({s for pl in paths.values() for p in pl for s in p.services})
        proto = dict(n_services_considered=len(referenced),
                     n_paths=sum(len(v) for v in paths.values()))
        lp = _lp(models, demands, paths, limits, referenced, kw, min(60.0, max(1.0, total) * 0.4))
        if lp["error"] or lp["prob"].status != pulp.LpStatusOptimal:
            return ORIG_SOLVE(models, demands, paths, limits, **kw)
        bound = float(pulp.value(lp["prob"].objective) or 0.0)
        support = [si for si in lp["active"] if (lp["f"][si].varValue or 0.0) > 1e-6]
        value = defaultdict(float)
        for (di, kk), v in lp["q"].items():
            qv = v.varValue or 0.0
            if qv > 1e-9:
                pth = paths[di][kk]
                share = qv * demands[di].revenue_per_teu / max(1, len(set(pth.services)))
                for si in set(pth.services):
                    value[si] += share
        ranked = sorted(support, key=lambda si: (-value[si], si))
        stages = [ranked[:k] for k in ks if k < len(ranked)] + [ranked]
        best, best_obj, init, log, last = None, float("-inf"), kw.get("initial_frequencies"), [], None
        for i, services in enumerate(stages):
            remaining = total - (time.perf_counter() - t0)
            if remaining < 1.0:
                break
            is_last = i == len(stages) - 1
            tl = remaining if is_last else remaining * (0.2 if i == 0 else 0.3)
            t_s = time.perf_counter()
            res = nm._build_and_solve(models, demands, paths, limits, sorted(services), integer=True,
                                      initial=init, time_limit_sec=tl, fixed=None,
                                      penalty=kw.get("unserved_penalty_per_teu", 0.0),
                                      max_departures_cap=kw.get("max_departures_cap"),
                                      threads=kw.get("threads"),
                                      total_vessel_limit=kw.get("total_vessel_limit"),
                                      port_capacity=kw.get("port_capacity"),
                                      min_served_fraction=kw.get("min_served_fraction"))
            sol = nm.NetworkSolution(status="not_solved", **proto)
            sol = _finish(res, sol, t0, models)
            sol.relaxation_bound = bound
            sol.n_services_restricted_to = len(services)
            if sol.status == "optimal" and len(services) < len(lp["active"]):
                sol.status = "feasible"
            obj = polished_objective(models, sol)
            log.append({"stage": i, "services": len(services), "budget": round(tl, 1),
                        "sec": round(time.perf_counter() - t_s, 1), "status": sol.status,
                        "objective": None if obj == float("-inf") else round(obj)})
            last = sol
            if sol.usable and obj > best_obj + 1e-6:
                best, best_obj = sol, obj
                init = {si: fr for si, fr in sol.frequencies.items() if fr > 0}
        DIAG["stages"] = log
        out = best if best is not None else last
        out.runtime_sec = time.perf_counter() - t0
        return out
    return f


def strat_highs(models, demands, paths, limits, **kw):
    """Information only: the unrestricted integer model through HiGHS (scipy.optimize.milp).
    Builds the same PuLP model, extracts the sparse matrices, solves, writes the values back
    onto the PuLP variables so the production ledger path is unchanged."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import lil_matrix
    t0 = time.perf_counter()
    total = float(kw["time_limit_sec"])
    referenced = sorted({s for pl in paths.values() for p in pl for s in p.services})
    sol = nm.NetworkSolution(status="not_solved", n_services_considered=len(referenced),
                             n_paths=sum(len(v) for v in paths.values()))
    sol.n_services_restricted_to = len(referenced)
    # Build the model WITHOUT solving: reuse _build_and_solve with an immediate return by
    # temporarily replacing the solver launcher.
    orig_solver = nm._solver
    nm._solver = lambda *a, **k: None
    orig_solve_method = pulp.LpProblem.solve
    pulp.LpProblem.solve = lambda self, solver=None, **k: None
    try:
        res = nm._build_and_solve(models, demands, paths, limits, referenced, integer=True,
                                  initial=None, time_limit_sec=total, fixed=None,
                                  penalty=kw.get("unserved_penalty_per_teu", 0.0),
                                  max_departures_cap=kw.get("max_departures_cap"), threads=None,
                                  total_vessel_limit=kw.get("total_vessel_limit"),
                                  port_capacity=kw.get("port_capacity"),
                                  min_served_fraction=kw.get("min_served_fraction"))
    finally:
        nm._solver = orig_solver
        pulp.LpProblem.solve = orig_solve_method
    prob = res["prob"]
    vars_ = prob.variables()
    idx = {v.name: i for i, v in enumerate(vars_)}
    nvar = len(vars_)
    c = np.zeros(nvar)
    for v, coef in prob.objective.items():
        c[idx[v.name]] = -coef                                 # maximise -> minimise
    lo = np.array([-np.inf if v.lowBound is None else v.lowBound for v in vars_], float)
    hi = np.array([np.inf if v.upBound is None else v.upBound for v in vars_], float)
    integrality = np.array([1 if v.cat == pulp.LpInteger else 0 for v in vars_])
    names = list(prob.constraints)
    A = lil_matrix((len(names), nvar))
    lb = np.full(len(names), -np.inf)
    ub = np.full(len(names), np.inf)
    for r, nme in enumerate(names):
        con = prob.constraints[nme]
        for v, coef in con.items():
            A[r, idx[v.name]] = coef
        rhs = -con.constant
        if con.sense == pulp.LpConstraintLE:
            ub[r] = rhs
        elif con.sense == pulp.LpConstraintGE:
            lb[r] = rhs
        else:
            lb[r] = ub[r] = rhs
    options = {"time_limit": max(1.0, total - (time.perf_counter() - t0)), "disp": False}
    r = milp(c, constraints=LinearConstraint(A.tocsr(), lb, ub), integrality=integrality,
             bounds=Bounds(lo, hi), options=options)
    DIAG["highs"] = {"status": int(r.status), "message": str(r.message),
                     "mip_gap": getattr(r, "mip_gap", None),
                     "mip_dual_bound": (-r.mip_dual_bound if getattr(r, "mip_dual_bound", None)
                                        is not None else None)}
    if r.x is None:
        sol.status, sol.message = "not_solved", str(r.message)
        sol.runtime_sec = time.perf_counter() - t0
        return sol
    for v in vars_:
        v.varValue = float(r.x[idx[v.name]])
    prob.status = pulp.LpStatusOptimal
    prob.sol_status = pulp.LpSolutionOptimal if r.status == 0 else pulp.LpSolutionIntegerFeasible
    sol = _finish(res, sol, t0, models)
    sol.status = "optimal" if r.status == 0 else "feasible"
    sol.relaxation_bound = DIAG["highs"]["mip_dual_bound"]
    sol.n_services_restricted_to = len(referenced)
    return sol


def strategy_fn(name: str):
    if name == "prod":
        return strat_prod
    if name == "fullint":
        return strat_fullint
    if name.startswith("two:"):
        return make_two_stage(float(name.split(":")[1]))
    if name == "highs":
        return strat_highs
    if name.startswith("prog:"):
        return make_progressive([int(x) for x in name.split(":")[1].split(",") if x])
    if name in ("A_sa", "A_pert") or name.startswith(("A_pool", "A_top")):
        return make_restricted(name)
    raise SystemExit(f"unknown strategy {name}")


# ----------------------------------------------------------------------------- metrics
def stage_metrics(stage, wall: float) -> dict:
    out = {"ok": stage.ok, "status": stage.status, "message": stage.message,
           "wall_sec_total": round(wall, 1)}
    plan = stage.plan
    if plan is None or plan.solution is None:
        return out
    sol, led = plan.solution, plan.ledger
    out["solver"] = {
        "solution_status": sol.status, "solver_status": sol.solver_status,
        "objective_usd_per_week": sol.objective_value, "relaxation_bound": sol.relaxation_bound,
        "gap_to_bound_usd": (sol.relaxation_bound - sol.objective_value)
        if sol.relaxation_bound is not None else None,
        "gap_to_bound_pct": (100.0 * (sol.relaxation_bound - sol.objective_value)
                             / abs(sol.relaxation_bound))
        if sol.relaxation_bound not in (None, 0) else None,
        "runtime_sec": round(sol.runtime_sec, 1),
        "services_considered": sol.n_services_considered,
        "services_in_integer_problem": sol.n_services_restricted_to,
        "variables": sol.n_variables, "constraints": sol.n_constraints, "paths": sol.n_paths,
        "message": sol.message,
    }
    out["diag"] = dict(DIAG)
    out["modelled"] = len(plan.models)
    if plan.path_stats is not None:
        out["path_model"] = plan.path_stats.to_dict()
    out["rejected_candidates"] = len(plan.rejected_candidates)
    if led is not None:
        by_kind = defaultdict(float)
        for di, k, teu in sol.flows:
            by_kind[plan.paths[di][k].kind] += teu
        classes = Counter(r["vessel_class"] for r in led.service_rows.values())
        out["ledger"] = {
            "valid": led.valid, "violations": list(led.violations),
            "revenue": led.revenue, "vessel_cost": led.vessel_cost, "fuel_cost": led.fuel_cost,
            "port_call_fixed_cost": led.port_call_fixed_cost, "handling_cost": led.handling_cost,
            "transshipment_cost": led.transshipment_cost,
            "port_variable_cost": led.port_variable_cost, "total_cost": led.operating_cost,
            "profit": led.operating_profit,
            "margin_pct": 100.0 * led.operating_profit / led.revenue if led.revenue > 0 else None,
            "coverage_pct": led.coverage * 100.0, "served_teu": led.served_teu,
            "unserved_teu": led.unserved_teu, "total_demand_teu": led.total_demand_teu,
            "services": len(led.service_rows), "vessels": sum(led.vessels_by_class.values()),
            "vessels_by_class": dict(led.vessels_by_class),
            "services_by_class": dict(classes),
            "services_by_n_ports": dict(Counter(len(r["ports"]) for r in led.service_rows.values())),
            "flow_teu_by_path_kind": dict(by_kind),
            "reconciliation": dict(plan.reconciliation),
        }
        out["selected"] = [{"id": sid, "ports": list(r["ports"]), "class": r["vessel_class"],
                            "f": int(r["frequency"]), "vessels": int(r["vessels"]),
                            "load": float(r["load"]), "revenue": float(r["revenue"]),
                            "cost": float(r["vessel_cost"] + r["fuel_cost"] + r["port_cost"])}
                           for sid, r in led.service_rows.items()]
    if stage.region_updates:
        regs = list(stage.region_updates.values())
        econ = canonical_network_economics(regs, stage.network_ledger)
        out["regional_reconciliation"] = {
            "accounting_status": econ["accounting_status"],
            "accounting_verified": econ["accounting_verified"],
            "issues": econ["accounting_issues"],
            "sum_regional_profit": sum(r["weekly_profit"] for r in regs),
            "sum_regional_cost": sum(r["total_cost"] for r in regs),
            "ledger_profit": led.operating_profit if led is not None else None,
            "ledger_cost": led.operating_cost if led is not None else None,
        }
    return out


# ----------------------------------------------------------------------------- main
def solver_banner() -> dict:
    info = {"pulp": pulp.__version__}
    try:
        path = pulp.PULP_CBC_CMD().path
        info["cbc_path"] = str(path)
        r = subprocess.run([path, "-quit"], capture_output=True, text=True, timeout=20)
        info["cbc_banner"] = (r.stdout.strip().splitlines() or [""])[0:3]
    except Exception as exc:                                    # noqa: BLE001
        info["cbc_banner_error"] = f"{type(exc).__name__}: {exc}"
    try:
        import scipy
        info["scipy"] = scipy.__version__
    except Exception:                                           # noqa: BLE001
        pass
    return info


result = {"seed": SEED, "time_limit_sec": TL, "strategies": STRATS, "tree": str(ROOT),
          "python": sys.version.split()[0], "solver": solver_banner(),
          "env": {k: v for k, v in os.environ.items()
                  if k.startswith(("LINER_", "BUNKER_", "T15_", "T16_", "NETWORK_MILP", "PYTHONHASHSEED"))},
          "cbc_threads": None, "runs": []}
t0 = time.perf_counter()
HINTS = None
CAPTURED = os.environ.get("T15_CAPTURED")
if CAPTURED:
    # production-representative input: a pool AND the regional hints exactly as the
    # orchestrator passed them to the global stage (captured by the Tasks 8-10 harness)
    import pickle
    _pkl, _idx = CAPTURED.rsplit(":", 1)
    _call = pickle.loads(Path(_pkl).read_bytes())["captured"][int(_idx)]
    built = {"pools": _call["pools"], "gen": {"captured": f"{_pkl}:{_idx}"},
             "region_of_od": _call["region_of_od"]}
    HINTS = _call["kw"].get("hints")
    result["captured_input"] = {"pickle": _pkl, "call": int(_idx),
                                "hints_nonzero": sum(1 for v in (HINTS or {}).values() if v)}
else:
    built = build_pools(SEED)
result["pool_generation_sec"] = round(time.perf_counter() - t0, 1)
result["pool"] = {**pool_identity(built["pools"]), "generator": built["gen"]}
if FILTER_LOG:
    result["filter_decisions"] = FILTER_LOG
print(f"seed={SEED} pool unique={result['pool']['unique_candidates']} "
      f"gen={result['pool_generation_sec']}s", flush=True)

problem = fresh_problem()


def candidate_diagnostics(pools):
    """Stand-alone economics of every unique candidate (canonical model, direct cargo,
    best frequency) - the same function the Task 10 class screening uses."""
    from src.network.economics import assumptions_for_problem
    from src.services.class_screening import ClassScreener, ClassScreeningConfig
    scr = ClassScreener(problem, problem.fleet, assumptions_for_problem(problem),
                        ClassScreeningConfig(k=1))
    section = {}
    for region in sorted(pools):
        for c in pools[region]:
            section.setdefault((canonical_rotation(c["ports"]), c["vessel_class"]),
                               c.get("section", "unknown"))
    cands, _ = collect_candidates({k: [dict(c) for c in v] for k, v in pools.items()})
    rows = []
    for c in cands:
        ev = scr.evaluate_class(list(c.ports), problem.fleet.get_class(c.vessel_class))
        rows.append({"id": c.service_id, "ports": list(c.ports), "class": c.vessel_class,
                     "section": section.get((canonical_rotation(c.ports), c.vessel_class), "unknown"),
                     "feasible": ev.feasible, "reasons": ev.reasons,
                     "standalone_profit": ev.standalone_profit_best, "best_f": ev.best_frequency,
                     "vessels_at_best": ev.vessels_at_best, "served_teu_best": ev.served_teu_best,
                     "direct_ride_feasible_teu": ev.direct_ride_feasible_teu,
                     "fixed_cost_best": ev.fixed_cost_best, "net_revenue_best": ev.net_revenue_best})
    return rows


if os.environ.get("T15_POOL_DIAG") == "1":
    t_d = time.perf_counter()
    result["pool_candidates"] = candidate_diagnostics(built["pools"])
    result["pool_diag_sec"] = round(time.perf_counter() - t_d, 1)
    OUT.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    print(f"seed={SEED} candidate diagnostics for {len(result['pool_candidates'])} candidates "
          f"in {result['pool_diag_sec']}s", flush=True)

for name in STRATS:
    DIAG.clear()
    fn = strategy_fn(name)
    planmod.solve_network = fn
    t1 = time.perf_counter()
    stage = reconcile(problem, {k: [dict(c) for c in v] for k, v in built["pools"].items()},
                      built["region_of_od"], REGIONS, hints=HINTS, time_limit_sec=TL, iteration=0,
                      max_paths_per_od=int(os.environ.get("T15_MAX_PATHS", "10")))
    wall = time.perf_counter() - t1
    row = {"strategy": name, **stage_metrics(stage, wall)}
    result["runs"].append(row)
    led = row.get("ledger", {})
    s = row.get("solver", {})
    print(f"seed={SEED} {name:10s} status={row['status']:9s} profit={led.get('profit', float('nan')):>12,.0f} "
          f"cov={led.get('coverage_pct', float('nan')):5.1f}% svc={led.get('services')} "
          f"ves={led.get('vessels')} bound={s.get('relaxation_bound')} t={s.get('runtime_sec')}s "
          f"viol={len(led.get('violations', []))}", flush=True)
    OUT.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
planmod.solve_network = ORIG_SOLVE
print("wrote", OUT)
