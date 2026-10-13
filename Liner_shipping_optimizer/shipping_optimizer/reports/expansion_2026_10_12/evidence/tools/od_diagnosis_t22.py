"""T22 read-only per-OD diagnosis of the production plan of one controlled seed.
usage: python od_diagnosis_t22.py <tree_root> <out.json> <seed> <time_limit_sec>
header = Tasks 19-21 harness (pool construction); body = od_diagnosis_body.py"""
"""Controlled global-stage experiment for Tasks 15, 16 and 19-21 (WorldSmall only).

(Tasks 19-21 copy of the Tasks 14-16 harness; additions: path-set identity, transfer-count
histogram, strategy report, per-run path configuration from the environment.)

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


# ============================================================================= T22 diagnosis
# Read-only per-OD diagnosis of the PRODUCTION plan of one controlled seed (no production source
# is changed; the plan is produced by the unmodified global stage ``reconcile``).
# This block is appended to the header of the Tasks 19-21 controlled harness (imports, pool
# construction) by ``assemble_od_diagnosis.py``.
import csv                                                              # noqa: E402
import numpy as np                                                      # noqa: E402
from scipy.optimize import linprog                                      # noqa: E402
from scipy.sparse import coo_matrix                                     # noqa: E402

from src.network.economics import assumptions_for_problem               # noqa: E402
from src.network.paths import (BUDGET_FIXED, SELECT_FASTEST, PathConfig, build_paths)  # noqa: E402
from src.network.plan import NetworkPlanner                             # noqa: E402

CSV_OUT = Path(str(OUT).replace(".json", "_od.csv"))
t_all = time.perf_counter()
built = build_pools(SEED)
problem = fresh_problem()
print(f"seed={SEED} pool unique={pool_identity(built['pools'])['unique_candidates']}", flush=True)
t1 = time.perf_counter()
stage = reconcile(problem, {k: [dict(c) for c in v] for k, v in built["pools"].items()},
                  built["region_of_od"], REGIONS, hints=None, time_limit_sec=TL, iteration=0,
                  max_paths_per_od=10)
plan = stage.plan
wall = time.perf_counter() - t1
models, demands, sol, led = plan.models, plan.demands, plan.solution, plan.ledger
print(f"production global stage: status={stage.status} wall={wall:.0f}s profit={led.operating_profit:,.0f} "
      f"coverage={led.coverage * 100:.2f}% services={len(led.service_rows)} ledger_valid={led.valid}", flush=True)

ops = {si: int(f) for si, f in sol.frequencies.items() if f > 0}
served = defaultdict(float)
for di, k, t in sol.flows:
    served[di] += t
inventory = {c.vessel_class: int(c.quantity) for c in problem.fleet.classes}
used = Counter()
for si, f in ops.items():
    used[models[si].vessel_class] += models[si].vessels(f)
free = {c: inventory[c] - used.get(c, 0) for c in inventory}

assump = assumptions_for_problem(problem)
planner = NetworkPlanner(problem, assumptions=assump)
cfg_all = PathConfig(selection=SELECT_FASTEST, budget=BUDGET_FIXED, max_transfers=2,
                     multi_hop_min_alternatives=10 ** 9)
t2 = time.perf_counter()
full, fstats = build_paths(demands, models, planner.port_lookup, assump, max_paths_per_od=10 ** 9,
                           config=cfg_all)
print(f"full valid path set: {sum(len(v) for v in full.values())} paths for {len(full)} ODs "
      f"({time.perf_counter() - t2:.1f}s)", flush=True)


def pkey(di, p):
    return (di, tuple(p.services), tuple(p.transfer_ports), tuple(s.legs for s in p.segments))


# paths the solved model (capped set + the paths the flow re-optimisation appended) could use
kept_keys = {pkey(di, p) for di, pl in plan.paths.items() for p in pl}
# columns of the full valid set: (od, path, services, margin per TEU, held by the capped model)
cols = []
by_service = defaultdict(list)
for di, pl in full.items():
    if not demands[di].weekly_teu > 0:
        continue
    for p in pl:
        j = len(cols)
        cols.append((di, p, frozenset(p.services), demands[di].revenue_per_teu - p.port_cost_per_teu,
                     pkey(di, p) in kept_keys))
        for s in set(p.services):
            by_service[s].append(j)
col_services = [c[2] for c in cols]


def columns_for(service_set, kept_only):
    out, seen = [], set()
    for s in service_set:
        for j in by_service.get(s, ()):
            if j in seen:
                continue
            seen.add(j)
            if col_services[j] <= service_set and (cols[j][4] or not kept_only):
                out.append(j)
    return out


def flow_lp(freq, kept_only=False):
    """Max cargo margin (USD/wk) of the fixed network ``freq`` over the valid paths (all of the
    full set, or only those the capped model held).  Same LP as src/network/flow_reopt.py
    (solved with HiGHS LP here: a diagnostic, not the production solver).
    Returns (margin, served TEU) or (None, None)."""
    S = frozenset(freq)
    ids = columns_for(S, kept_only)
    if not ids:
        return 0.0, 0.0
    od_row, leg_row = {}, {}
    rows, cs, vs, b = [], [], [], []
    for ci, j in enumerate(ids):
        di, p = cols[j][0], cols[j][1]
        r = od_row.get(di)
        if r is None:
            r = od_row[di] = len(b)
            b.append(float(demands[di].weekly_teu))
        rows.append(r)
        cs.append(ci)
        vs.append(1.0)
        for seg in p.segments:
            for leg in seg.legs:
                key = (seg.service, leg)
                r = leg_row.get(key)
                if r is None:
                    r = leg_row[key] = len(b)
                    b.append(float(models[seg.service].capacity_teu * freq[seg.service]))
                rows.append(r)
                cs.append(ci)
                vs.append(1.0)
    A = coo_matrix((vs, (rows, cs)), shape=(len(b), len(ids))).tocsr()
    c = -np.array([cols[j][3] for j in ids])
    r = linprog(c, A_ub=A, b_ub=np.array(b), bounds=(0, None), method="highs")
    if not r.success:
        return None, None
    return float(-r.fun), float(r.x.sum())


def fixed(freq):
    return sum(models[s].weekly_fixed_cost(f) for s, f in freq.items())


base_margin, base_served = flow_lp(ops, False)
base_profit = base_margin - fixed(ops)
base_capped_margin, base_capped_served = flow_lp(ops, True)
print(f"evaluator check: LP profit over full paths {base_profit:,.0f} | ledger {led.operating_profit:,.0f} | "
      f"LP over the capped model's paths only {base_capped_margin - fixed(ops):,.0f}", flush=True)

# ---- LP relaxation support of the production restriction (what CBC could choose from) ------
lp_support = None
try:
    t3 = time.perf_counter()
    limits = {c.vessel_class: int(c.quantity) for c in problem.fleet.classes}
    referenced = sorted({s for pl in plan.paths.values() for p in pl for s in p.services})
    lp = nm._build_and_solve(models, demands, plan.paths, limits, referenced, integer=False,
                             penalty=0.0, fixed=None, initial=None, max_departures_cap=None,
                             time_limit_sec=60.0, threads=None, total_vessel_limit=None,
                             port_capacity=None, min_served_fraction=None)
    if not lp["error"] and lp["prob"].status == pulp.LpStatusOptimal:
        lp_support = {si for si in lp["active"] if (lp["f"][si].varValue or 0.0) > 1e-6}
        lp_bound = float(pulp.value(lp["prob"].objective) or 0.0)
        print(f"LP relaxation of the (reopt-extended) path set: support={len(lp_support)} "
              f"bound={lp_bound:,.0f} ({time.perf_counter() - t3:.0f}s)", flush=True)
except Exception as exc:                                                 # noqa: BLE001
    print("LP support unavailable:", type(exc).__name__, exc, flush=True)


def vessels_ok(s, f, freq):
    cls = models[s].vessel_class
    other = sum(models[x].vessels(g) for x, g in freq.items() if models[x].vessel_class == cls and x != s)
    return other + models[s].vessels(f) <= inventory[cls]


# ---- add-one / drop-one marginal values at the incumbent -----------------------------------
t4 = time.perf_counter()
add_rows = []
candidates_unopened = [s for s in range(len(models)) if s not in ops and by_service.get(s)]
for s in candidates_unopened:
    for f in (1, 2):
        if not vessels_ok(s, f, ops):
            continue
        trial = dict(ops)
        trial[s] = f
        m_full, sv_full = flow_lp(trial, False)
        m_kept, sv_kept = flow_lp(trial, True)
        if m_full is None:
            continue
        fc = models[s].weekly_fixed_cost(f)
        add_rows.append({"service": models[s].service_id, "si": s, "class": models[s].vessel_class,
                         "ports": len(models[s].ports), "f": f, "fixed_cost": fc,
                         "delta_full": m_full - base_margin - fc,
                         "delta_kept": (m_kept - base_capped_margin - fc) if m_kept is not None else None,
                         "served_gain": sv_full - base_served,
                         "in_lp_support": (s in lp_support) if lp_support is not None else None})
print(f"add-one evaluated for {len(candidates_unopened)} unopened services x f in (1,2): {len(add_rows)} trials "
      f"({time.perf_counter() - t4:.0f}s)", flush=True)

drop_rows = []
for s in ops:
    trial = {x: g for x, g in ops.items() if x != s}
    m, sv = flow_lp(trial, False)
    drop_rows.append({"service": models[s].service_id, "si": s, "class": models[s].vessel_class, "f": ops[s],
                      "delta": (m - base_margin) + models[s].weekly_fixed_cost(ops[s]),
                      "served_loss": base_served - sv})


# ---- greedy local-search simulation (add f=1 / drop / f+1 / f-1), exact LP, full path set -----
def greedy(max_iter=12, time_budget=300.0):
    cur = dict(ops)
    cur_m, cur_sv = flow_lp(cur, False)
    cur_profit = cur_m - fixed(cur)
    log, t0g = [], time.perf_counter()
    pool = [r["si"] for r in add_rows if r["f"] == 1 and r["delta_full"] > -2.0e5]
    for it in range(max_iter):
        if time.perf_counter() - t0g > time_budget:
            break
        best = None
        moves = []
        for s in pool:
            if s not in cur and vessels_ok(s, 1, cur):
                moves.append(("add", s, 1))
        for s, f in list(cur.items()):
            moves.append(("drop", s, 0))
            if f + 1 <= models[s].max_departures(inventory[models[s].vessel_class]) and vessels_ok(s, f + 1, cur):
                moves.append(("up", s, f + 1))
            if f > 1:
                moves.append(("down", s, f - 1))
        for kind, s, f in moves:
            trial = dict(cur)
            if kind == "drop":
                trial.pop(s)
            else:
                trial[s] = f
            m, sv = flow_lp(trial, False)
            if m is None:
                continue
            pr = m - fixed(trial)
            if best is None or pr > best[0]:
                best = (pr, kind, s, f, trial, sv)
        if best is None or best[0] <= cur_profit + 1000.0:
            break
        cur_profit, cur, cur_sv = best[0], best[4], best[5]
        log.append({"iter": it, "move": best[1], "service": models[best[2]].service_id, "f": best[3],
                    "profit": round(cur_profit), "served_teu": round(cur_sv),
                    "elapsed_s": round(time.perf_counter() - t0g, 1)})
        print("  greedy", log[-1], flush=True)
    return {"start_profit": base_profit, "end_profit": cur_profit, "moves": log,
            "start_served": base_served, "end_served": cur_sv,
            "end_services": len(cur), "end_vessels": sum(models[s].vessels(f) for s, f in cur.items())}


greedy_res = greedy()

# ---- per-OD classification -------------------------------------------------------------------
vmax = max(float(c.design_speed) for c in problem.fleet.classes if c.design_speed) * assump.speed_factor
add_by_s = defaultdict(list)
for r in add_rows:
    add_by_s[r["si"]].append(r)
best_add = {s: max(rs, key=lambda r: r["delta_full"]) for s, rs in add_by_s.items()}
od_rows = []
CAT = Counter()
CAT_TEU = defaultdict(float)
for di, d in enumerate(demands):
    if not d.weekly_teu > 0:
        continue
    got = served.get(di, 0.0)
    rem = d.weekly_teu - got
    valid = full.get(di, [])
    kept = plan.paths.get(di, [])
    row = {"od": di, "origin": d.origin, "destination": d.destination, "demand_teu": d.weekly_teu,
           "served_teu": got, "unserved_teu": max(rem, 0.0), "valid_paths": len(valid), "kept_paths": len(kept),
           "revenue_per_teu": d.revenue_per_teu}
    if rem <= 1e-6 * max(1.0, d.weekly_teu):
        row.update(category="served", secondary="")
        od_rows.append(row)
        continue
    cat, sec = None, []
    if not valid:
        lim = getattr(d, "max_transit_days", None)
        nm_ = (problem.distance_matrix.get(d.origin) or {}).get(d.destination)
        if lim is not None and isinstance(nm_, (int, float)) and nm_ > 0 and nm_ / (vmax * 24.0) > lim + 1e-9:
            cat = "C2_transit_limit_below_sailing_time"
        else:
            cat = "C3_no_compatible_candidate_in_pool"
    else:
        op_paths = [p for p in valid if all(s in ops for s in p.services)]
        if op_paths:
            best_p = max(op_paths, key=lambda p: d.revenue_per_teu - p.port_cost_per_teu)
            if d.revenue_per_teu - best_p.port_cost_per_teu <= 1e-9:
                cat = "C7_per_TEU_margin_not_positive"
            else:
                cat = "C6_leg_capacity_of_operated_services"
        else:
            openable = [p for p in valid if all((s in ops) or vessels_ok(s, 1, ops) for s in p.services)]
            if not openable:
                cat = "C5_fleet_inventory_or_class_compatibility"
            else:
                kept_open = [p for p in openable if pkey(di, p) in kept_keys]
                if not kept_open:
                    cat = "C4_excluded_by_path_cap"
                else:
                    new1 = []
                    for p in kept_open:
                        news = sorted({s for s in p.services if s not in ops})
                        if len(news) == 1:
                            new1.append((p, news[0]))
                    ev = [(best_add[s]["delta_full"], s) for _p, s in new1 if s in best_add]
                    if not ev:
                        cat = "C8b_needs_two_or_more_new_services_not_evaluated"
                    else:
                        top = max(ev)
                        row["best_single_service"] = models[top[1]].service_id
                        row["best_single_service_delta"] = top[0]
                        if top[0] > 0:
                            cat = "C8a_opening_one_service_raises_profit_at_incumbent"
                        else:
                            cat = "C7_not_justified_at_incumbent_single_service_view"
                            sec.append("network_role_via_multi_service_not_excluded")
    row.update(category=cat, secondary=";".join(sec))
    od_rows.append(row)
    CAT[cat] += 1
    CAT_TEU[cat] += rem

total_demand = sum(d.weekly_teu for d in demands if d.weekly_teu > 0)
cat_table = {k: {"ods": CAT[k], "unserved_teu": round(CAT_TEU[k], 1),
                 "share_of_total_demand_pct": round(100 * CAT_TEU[k] / total_demand, 2)} for k in sorted(CAT)}
pos_add = sorted([r for r in add_rows if r["delta_full"] > 0], key=lambda r: -r["delta_full"])
pos_add_kept = [r for r in add_rows if r["delta_kept"] is not None and r["delta_kept"] > 0]
result = {
    "seed": SEED, "time_limit_sec": TL, "tree": str(ROOT),
    "stage": {"status": stage.status, "wall_s": round(wall, 1), "profit": led.operating_profit,
              "coverage_pct": led.coverage * 100, "served_teu": led.served_teu, "services": len(ops),
              "vessels": sum(used.values()), "ledger_valid": led.valid,
              "solver_status": sol.status, "relaxation_bound": sol.relaxation_bound,
              "reopt": plan.flow_reopt},
    "evaluator_check": {"lp_profit_full_paths": base_profit, "ledger_profit": led.operating_profit,
                        "lp_profit_capped_model_paths_only": base_capped_margin - fixed(ops)},
    "fleet": {"inventory": inventory, "used": dict(used), "free": free},
    "paths": {"valid_total": sum(len(v) for v in full.values()),
              "kept_total_incl_reopt_added": sum(len(v) for v in plan.paths.values()),
              "path_stats_capped_build": plan.path_stats.to_dict() if plan.path_stats else None},
    "categories": cat_table,
    "add_one": {"trials": len(add_rows), "positive_delta_full": len(pos_add),
                "positive_delta_capped_paths_only": len(pos_add_kept),
                "positive_in_lp_support": sum(1 for r in pos_add if r["in_lp_support"]),
                "positive_not_in_lp_support": sum(1 for r in pos_add if r["in_lp_support"] is False),
                "top20": pos_add[:20], "sum_top5_positive": sum(r["delta_full"] for r in pos_add[:5])},
    "drop_one": {"positive": [r for r in drop_rows if r["delta"] > 0],
                 "n_operated": len(drop_rows),
                 "worst5": sorted(drop_rows, key=lambda r: -r["delta"])[:5]},
    "greedy_local_search": greedy_res,
    "lp_support_size": None if lp_support is None else len(lp_support),
    "elapsed_s": round(time.perf_counter() - t_all, 1),
}
OUT.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
with open(CSV_OUT, "w", newline="", encoding="utf-8") as fh:
    keys = sorted({k for r in od_rows for k in r})
    w = csv.DictWriter(fh, fieldnames=keys)
    w.writeheader()
    w.writerows(od_rows)
print(json.dumps({"categories": cat_table,
                  "add_one": {k: v for k, v in result["add_one"].items() if k != "top20"},
                  "greedy": {k: v for k, v in greedy_res.items() if k != "moves"}}, indent=1, default=str),
      flush=True)
print("wrote", OUT, CSV_OUT)
