# ============================================================================= T22 offline analysis
# Read-only analysis of ONE recorded production plan (state pickled by od_diagnosis_t22_v3.py,
# env T22_STATE).  No solver of the pipeline is run; no production source is changed.
# Paths are enumerated per evaluated service set exactly as the production flow re-optimisation
# does (``build_paths(..., only_services=S)``), so the evaluator's LP is the production LP.
import csv                                                              # noqa: E402
import pickle                                                           # noqa: E402
import numpy as np                                                      # noqa: E402
from scipy.optimize import linprog                                      # noqa: E402
from scipy.sparse import coo_matrix                                     # noqa: E402

from src.network.economics import (ServiceModelError, assumptions_for_problem,   # noqa: E402
                                   build_service_model)
from src.network.paths import (BUDGET_FIXED, SELECT_FASTEST, PathConfig, build_paths)  # noqa: E402
from src.network.plan import NetworkPlanner                             # noqa: E402

CSV_OUT = Path(str(OUT).replace(".json", "_od.csv"))
T_ALL = time.perf_counter()
STATE = pickle.loads(Path(os.environ["T22_STATE"]).read_bytes())
models = list(STATE["models"])
demands = STATE["demands"]
ops = {int(k): int(v) for k, v in STATE["ops"].items() if int(v) > 0}
flows = STATE["flows"]
paths_cap = STATE["paths"]
inventory = {k: int(v) for k, v in STATE["inventory"].items()}
N_BASE = len(models)
problem = fresh_problem()
assump = assumptions_for_problem(problem)
planner = NetworkPlanner(problem, assumptions=assump)
cfg_all = PathConfig(selection=SELECT_FASTEST, budget=BUDGET_FIXED, max_transfers=2,
                     multi_hop_min_alternatives=10 ** 9)
classes = {c.vessel_class: c for c in problem.fleet.classes}

served = defaultdict(float)
for di, k, t in flows:
    served[di] += t
used = Counter()
for si, f in ops.items():
    used[models[si].vessel_class] += models[si].vessels(f)
free = {c: inventory[c] - used.get(c, 0) for c in inventory}
total_demand = sum(d.weekly_teu for d in demands if d.weekly_teu > 0)


def pkey(di, p):
    return (di, tuple(p.services), tuple(p.transfer_ports), tuple(s.legs for s in p.segments))


_pcache = {}


def paths_for(S):
    """All valid time-feasible paths whose services are all in ``S`` (one list of (od, path))."""
    key = frozenset(S)
    if key not in _pcache:
        pl, _ = build_paths(demands, models, planner.port_lookup, assump, max_paths_per_od=10 ** 9,
                            config=cfg_all, only_services=sorted(key))
        _pcache[key] = [(di, p) for di, lst in pl.items() if demands[di].weekly_teu > 0 for p in lst]
    return _pcache[key]


def kept_paths_for(S):
    """Paths the capped model (plus the re-optimisation's additions) held, within ``S``."""
    S = set(S)
    return [(di, p) for di, lst in paths_cap.items() if demands[di].weekly_teu > 0
            for p in lst if set(p.services) <= S]


def lp(freq, cols):
    """max sum (rev - port charges) q  s.t. OD demand, leg capacity cap_s*f_s.  (margin, served)"""
    if not cols:
        return 0.0, 0.0
    od_row, leg_row = {}, {}
    rows, cs, vs, b, cvec = [], [], [], [], []
    for ci, (di, p) in enumerate(cols):
        r = od_row.get(di)
        if r is None:
            r = od_row[di] = len(b)
            b.append(float(demands[di].weekly_teu))
        rows.append(r)
        cs.append(ci)
        vs.append(1.0)
        cvec.append(demands[di].revenue_per_teu - p.port_cost_per_teu)
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
    A = coo_matrix((vs, (rows, cs)), shape=(len(b), len(cols))).tocsr()
    r = linprog(-np.array(cvec), A_ub=A, b_ub=np.array(b), bounds=(0, None), method="highs")
    if not r.success:
        return None, None
    return float(-r.fun), float(r.x.sum())


def fixed(freq):
    return sum(models[s].weekly_fixed_cost(f) for s, f in freq.items())


def vessels_ok(s, f, freq):
    cls = models[s].vessel_class
    other = sum(models[x].vessels(g) for x, g in freq.items() if models[x].vessel_class == cls and x != s)
    return other + models[s].vessels(f) <= inventory[cls]


# ---- evaluator validation against the production plan ----------------------------------------
prod_margin = sum((demands[di].revenue_per_teu - paths_cap[di][k].port_cost_per_teu) * t for di, k, t in flows)
prod_fixed = fixed(ops)
prod_profit = prod_margin - prod_fixed
t0 = time.perf_counter()
base_margin, base_served = lp(ops, paths_for(ops))
base_profit = base_margin - prod_fixed
kept_margin, kept_served = lp(ops, kept_paths_for(ops))
print(f"state: services={len(ops)} vessels={sum(used.values())} production profit={prod_profit:,.0f} "
      f"served={sum(t for _, _, t in flows):,.0f}", flush=True)
print(f"evaluator: LP over all valid paths of the operated services = {base_profit:,.0f} "
      f"(>= production flows {prod_profit:,.0f}); LP over held paths only = {kept_margin - prod_fixed:,.0f} "
      f"[{time.perf_counter() - t0:.1f}s]", flush=True)

# ---- full valid path set (for classification) -----------------------------------------------
t0 = time.perf_counter()
ALL = set(range(N_BASE))
full_cols = paths_for(ALL)
full = defaultdict(list)
by_service = defaultdict(set)
for di, p in full_cols:
    full[di].append(p)
    for s in p.services:
        by_service[s].add(di)
kept_keys = {pkey(di, p) for di, lst in paths_cap.items() for p in lst}
print(f"full valid path set: {len(full_cols)} paths ({time.perf_counter() - t0:.1f}s)", flush=True)

# ---- add-one for every unopened service at f in (1, 2) ----------------------------------------
t0 = time.perf_counter()
add_rows = []
unopened = [s for s in range(N_BASE) if s not in ops and s in by_service]
for n_done, s in enumerate(unopened):
    S = set(ops) | {s}
    cols_all = None
    for f in (1, 2):
        if not vessels_ok(s, f, ops):
            continue
        if cols_all is None:
            cols_all = paths_for(S)
            cols_kept = kept_paths_for(S)
        trial = dict(ops)
        trial[s] = f
        m_all, sv_all = lp(trial, cols_all)
        m_kept, _sv_kept = lp(trial, cols_kept)
        fc = models[s].weekly_fixed_cost(f)
        add_rows.append({"service": models[s].service_id, "si": s, "class": models[s].vessel_class,
                         "ports": len(models[s].ports), "f": f, "fixed_cost": fc,
                         "delta_full": m_all - base_margin - fc,
                         "delta_kept": (m_kept - kept_margin - fc) if m_kept is not None else None,
                         "served_gain": sv_all - base_served})
    if n_done % 200 == 0:
        print(f"  add-one {n_done}/{len(unopened)} ({time.perf_counter() - t0:.0f}s)", flush=True)
print(f"add-one: {len(add_rows)} trials over {len(unopened)} unopened services ({time.perf_counter() - t0:.0f}s)",
      flush=True)
best_add = {}
for r in add_rows:
    if r["si"] not in best_add or r["delta_full"] > best_add[r["si"]]["delta_full"]:
        best_add[r["si"]] = r

# ---- drop-one --------------------------------------------------------------------------------
drop_rows = []
for s in ops:
    trial = {x: g for x, g in ops.items() if x != s}
    m, sv = lp(trial, paths_for(trial))
    drop_rows.append({"service": models[s].service_id, "si": s, "class": models[s].vessel_class, "f": ops[s],
                      "delta": (m - base_margin) + models[s].weekly_fixed_cost(ops[s]),
                      "served_loss": base_served - sv})


# ---- greedy local search (add f=1 / drop / f+1 / f-1) with the exact evaluator ----------------
def greedy(max_iter=12, time_budget=480.0, pool_floor=-3.0e5):
    cur = dict(ops)
    cur_m, cur_sv = base_margin, base_served
    cur_profit = cur_m - fixed(cur)
    log, t0g = [], time.perf_counter()
    pool = [r["si"] for r in add_rows if r["f"] == 1 and r["delta_full"] > pool_floor]
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
            cls = models[s].vessel_class
            if f + 1 <= models[s].max_departures(inventory[cls]) and vessels_ok(s, f + 1, cur):
                moves.append(("up", s, f + 1))
            if f > 1:
                moves.append(("down", s, f - 1))
        for kind, s, f in moves:
            trial = dict(cur)
            if kind == "drop":
                trial.pop(s)
            else:
                trial[s] = f
            m, sv = lp(trial, paths_for(trial))
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
    return {"start_profit": base_profit, "end_profit": cur_profit, "moves": log, "start_served": base_served,
            "end_served": cur_sv, "end_services": len(cur),
            "end_vessels": sum(models[s].vessels(f) for s, f in cur.items())}


greedy_res = greedy()

# ---- class-variant availability for inventory-blocked ODs (candidate-gap test) -----------------
vmax = max(float(c.design_speed) for c in problem.fleet.classes if c.design_speed) * assump.speed_factor
_alt_cache = {}


def alt_model(s, cls):
    key = (s, cls)
    if key not in _alt_cache:
        try:
            m = build_service_model(f"alt_{models[s].service_id}_{cls}", models[s].ports,
                                    problem.fleet.get_class(cls), problem.distance_matrix,
                                    planner.port_lookup, assump, known_ports=planner.known_ports,
                                    capacity_unit_status=getattr(problem.fleet, "capacity_unit_status",
                                                                 "provisional"))
        except (ServiceModelError, KeyError, ValueError):
            m = None
        _alt_cache[key] = m
    return _alt_cache[key]


def alt_class_for(di, p):
    """Another class (with enough free vessels for one weekly sailing) that could run the same
    rotation of the direct path ``p`` of OD ``di`` inside the OD's transit limit."""
    if len(p.segments) != 1:
        return []
    s = p.segments[0].service
    d = demands[di]
    out = []
    for cls in classes:
        if cls == models[s].vessel_class:
            continue
        m = alt_model(s, cls)
        if m is None or m.vessels(1) > free.get(cls, 0):
            continue
        r = m.ride(p.segments[0].from_port, p.segments[0].to_port)
        if r is None:
            continue
        lim = getattr(d, "max_transit_days", None)
        if lim is not None and r[1] > lim + 1e-9:
            continue
        out.append(cls)
    return out


# ---- per-OD classification ---------------------------------------------------------------------
od_rows = []
CAT, CAT_TEU, SUB = Counter(), defaultdict(float), Counter()
alt_blocked_rot = defaultdict(float)             # (service idx, class) -> unserved TEU it would unlock
for di, d in enumerate(demands):
    if not d.weekly_teu > 0:
        continue
    got = served.get(di, 0.0)
    rem = d.weekly_teu - got
    valid = full.get(di, [])
    kept = paths_cap.get(di, [])
    row = {"od": di, "origin": d.origin, "destination": d.destination, "demand_teu": d.weekly_teu,
           "served_teu": got, "unserved_teu": max(rem, 0.0), "valid_paths": len(valid),
           "kept_paths": len(kept), "revenue_per_teu": d.revenue_per_teu}
    if rem <= 1e-6 * max(1.0, d.weekly_teu):
        row.update(category="served", secondary="")
        od_rows.append(row)
        continue
    sec = []
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
            cat = ("C7_per_TEU_margin_not_positive"
                   if d.revenue_per_teu - best_p.port_cost_per_teu <= 1e-9
                   else "C6_leg_capacity_of_operated_services")
        else:
            openable = [p for p in valid if all((s in ops) or vessels_ok(s, 1, ops) for s in p.services)]
            if not openable:
                cat = "C5_fleet_inventory_or_class_compatibility"
                alts = []
                for p in valid:
                    for cls in alt_class_for(di, p):
                        alts.append((p.services[0], cls))
                if alts:
                    sec.append("alt_class_variant_available")
                    for key in set(alts):
                        alt_blocked_rot[key] += rem / max(1, len(set(alts)))
            else:
                kept_open = [p for p in openable if pkey(di, p) in kept_keys]
                if not kept_open:
                    cat = "C4_excluded_by_path_cap"
                else:
                    new1 = []
                    for p in kept_open:
                        news = sorted({s for s in p.services if s not in ops})
                        if len(news) == 1:
                            new1.append(news[0])
                    ev = [(best_add[s]["delta_full"], s) for s in new1 if s in best_add]
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
    row.update(category=cat, secondary=";".join(sec))
    od_rows.append(row)
    CAT[cat] += 1
    CAT_TEU[cat] += rem
    for sx in sec:
        SUB[(cat, sx)] += rem

cat_table = {k: {"ods": CAT[k], "unserved_teu": round(CAT_TEU[k], 1),
                 "share_of_total_demand_pct": round(100 * CAT_TEU[k] / total_demand, 2)} for k in sorted(CAT)}
sub_table = {f"{a}|{b}": {"unserved_teu": round(v, 1), "share_of_total_demand_pct": round(100 * v / total_demand, 2)}
             for (a, b), v in SUB.items()}

# ---- add-one value of the most useful alternative-class variants ------------------------------
t0 = time.perf_counter()
alt_rows = []
for (s, cls), teu in sorted(alt_blocked_rot.items(), key=lambda kv: -kv[1])[:80]:
    m = alt_model(s, cls)
    if m is None:
        continue
    models.append(m)
    idx = len(models) - 1
    S = set(ops) | {idx}
    if not vessels_ok(idx, 1, ops):
        models.pop()
        continue
    cols = paths_for(S)
    trial = dict(ops)
    trial[idx] = 1
    mm, sv = lp(trial, cols)
    fc = m.weekly_fixed_cost(1)
    alt_rows.append({"rotation_of": models[s].service_id, "class": cls, "ports": len(m.ports),
                     "blocked_teu_attributed": round(teu, 1), "fixed_cost": fc,
                     "delta_full": mm - base_margin - fc, "served_gain": sv - base_served,
                     "vessels_needed": m.vessels(1), "free_in_class": free.get(cls, 0)})
    models.pop()                                   # keep indices of the base models stable
    _pcache.pop(frozenset(S), None)
print(f"alternative-class variants evaluated: {len(alt_rows)} ({time.perf_counter() - t0:.0f}s)", flush=True)

pos_add = sorted([r for r in add_rows if r["delta_full"] > 0], key=lambda r: -r["delta_full"])
pos_alt = sorted([r for r in alt_rows if r["delta_full"] > 0], key=lambda r: -r["delta_full"])
result = {
    "state": os.environ["T22_STATE"], "tree": str(ROOT),
    "plan": {"services": len(ops), "vessels": sum(used.values()), "profit_from_flows": prod_profit,
             "served_teu": sum(t for _, _, t in flows), "coverage_pct": 100 * sum(t for _, _, t in flows) / total_demand},
    "evaluator": {"lp_profit_all_valid_paths_of_operated": base_profit, "production_flows_profit": prod_profit,
                  "lp_profit_held_paths_only": kept_margin - prod_fixed,
                  "cap_value_under_operated_services": base_margin - kept_margin},
    "fleet": {"inventory": inventory, "used": dict(used), "free": free},
    "categories": cat_table, "category_subtags": sub_table,
    "add_one": {"unopened_services_evaluated": len(unopened), "trials": len(add_rows),
                "positive_delta_all_paths": len(pos_add),
                "positive_delta_held_paths_only": sum(1 for r in add_rows if r["delta_kept"] is not None and r["delta_kept"] > 0),
                "sum_best_positive_per_service": sum(max(r["delta_full"] for r in add_rows if r["si"] == s)
                                                     for s in {r["si"] for r in pos_add}),
                "top25": pos_add[:25]},
    "drop_one": {"n_operated": len(drop_rows), "positive": [r for r in drop_rows if r["delta"] > 0],
                 "worst5": sorted(drop_rows, key=lambda r: -r["delta"])[:5]},
    "greedy_local_search": greedy_res,
    "alt_class_variants": {"evaluated": len(alt_rows), "positive": len(pos_alt), "top15": pos_alt[:15],
                           "all": alt_rows},
    "elapsed_s": round(time.perf_counter() - T_ALL, 1),
}
OUT.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
with open(CSV_OUT, "w", newline="", encoding="utf-8") as fh:
    keys = sorted({k for r in od_rows for k in r})
    w = csv.DictWriter(fh, fieldnames=keys)
    w.writeheader()
    w.writerows(od_rows)
print(json.dumps({"categories": cat_table, "subtags": sub_table, "evaluator": result["evaluator"],
                  "add_one": {k: v for k, v in result["add_one"].items() if k != "top25"},
                  "greedy": {k: v for k, v in greedy_res.items() if k != "moves"},
                  "alt": {k: v for k, v in result["alt_class_variants"].items() if k not in ("all", "top15")}},
                 indent=1, default=str), flush=True)
print("wrote", OUT, CSV_OUT)
