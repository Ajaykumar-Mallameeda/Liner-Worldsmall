"""
What-if re-evaluation of a recorded plan (read-only; the optimizer is not re-run).

The run's services, weekly departures and vessels stay exactly as recorded, so every fixed cost
(vessel hire, port calls) is unchanged. Two inputs move:

    demand_multiplier   every OD's weekly TEU x m
    fuel_multiplier     the bunker price x m (the ledger's fuel cost is departures x tonnes x price,
                        so it scales exactly)

With the network fixed, the cargo is re-routed by the LP the engine's flow re-optimisation solves
(src/network/flow_reopt.py: every valid, time-feasible path through the operated services; at most the
demand of each OD; the capacity of every leg) and the result is priced by the engine's independent
ledger (src/network/ledger.compute_ledger). The same re-evaluation at m = 1 is returned as the
baseline, so a scenario is compared with a number computed the same way rather than with the
recorded figure (which can differ slightly: the recorded flows may use paths found by the local
search outside this enumeration).
"""

from __future__ import annotations

import dataclasses
import math
import threading
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import pulp
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend import run_catalog

router = APIRouter()

FLOW_NOISE_TEU = 1e-6
_lock = threading.Lock()
_cache: Dict[str, Dict] = {}          # run key -> problem, models, paths (built once per run)


class WhatIfRequest(BaseModel):
    run: Dict = Field(default_factory=lambda: {"kind": "current"})
    demand_multiplier: float = Field(1.0, ge=0.2, le=3.0)
    fuel_multiplier: float = Field(1.0, ge=0.2, le=4.0)


def _run_output(run: Dict) -> Tuple[str, Dict]:
    kind = run.get("kind", "current")
    if kind == "benchmark":
        ds, seed = str(run.get("dataset")), int(run.get("seed"))
        path = run_catalog._dataset_dir(ds) / "runs" / f"seed_{seed:02d}" / "pipeline_output.json"
        key = f"benchmark:{ds}/{seed}"
    elif kind == "extra":
        path = run_catalog._extra_run_dir(str(run.get("id"))) / "pipeline_output.json"
        key = f"extra:{run.get('id')}"
    else:
        path, key = run_catalog.CURRENT_OUTPUT, "current"
    out = run_catalog._read_json(path)
    if not out:
        raise HTTPException(status_code=404, detail=f"run output not found: {path.name}")
    st = path.stat()
    return f"{key}@{st.st_mtime_ns}", out


def _dataset_of(run: Dict, out: Dict) -> str:
    """The run's dataset: the benchmark key, else dataset_run (top level, or under test_scorecard in runs made by
    the campaign driver), else WorldSmall (the only dataset of runs that predate dataset_run)."""
    if run.get("kind") == "benchmark" and run.get("dataset"):
        return str(run["dataset"])
    for block in (out.get("dataset_run"), (out.get("test_scorecard") or {}).get("dataset_run")):
        if isinstance(block, dict) and block.get("dataset"):
            return str(block["dataset"])
    return "WorldSmall"


def _prepare(key: str, out: Dict, dataset: str) -> Dict:
    """Problem, service models of the recorded plan and the full path set through them (cached)."""
    if key in _cache:
        return _cache[key]
    from src.data.problem_json import load_problem_json
    from src.network.economics import assumptions_for_problem
    from src.network.paths import BUDGET_FIXED, SELECT_FASTEST, PathConfig, build_paths
    from src.network.plan import Candidate, NetworkPlanner

    nl = out.get("network_ledger") or {}
    plan = nl.get("plan") or {}
    services = plan.get("services") or []
    if not services:
        raise HTTPException(status_code=422, detail="this run has no recorded network plan to re-evaluate")
    problem, _meta = load_problem_json(dataset)
    assumptions = assumptions_for_problem(problem)
    a_rec = nl.get("assumptions") or {}
    max_transfers = int(a_rec.get("max_transfers_per_od", 2))

    planner = NetworkPlanner(problem, assumptions)
    cands = [Candidate(s["id"], tuple(s["ports"]), s["vessel_class"]) for s in services]
    models, rejected = planner.build_models(cands)
    if rejected:
        raise HTTPException(status_code=422, detail=f"recorded services could not be modelled: {rejected[:3]}")
    freq = {i: int(s["frequency_per_week"]) for i, s in enumerate(services) if int(s["frequency_per_week"]) > 0}
    # the flow re-optimisation's column set: fastest, fixed budget, every path, two-transfer paths everywhere
    cfg = PathConfig(selection=SELECT_FASTEST, budget=BUDGET_FIXED, max_transfers=max_transfers,
                     multi_hop_min_alternatives=10 ** 9 if max_transfers >= 2 else 1)
    t0 = time.perf_counter()
    paths, _stats = build_paths(problem.demands, models, planner.port_lookup, assumptions,
                                max_paths_per_od=10 ** 9, config=cfg, only_services=sorted(freq))
    prep = {"problem": problem, "assumptions": assumptions, "planner": planner, "models": models,
            "freq": freq, "paths": paths, "dataset": dataset, "max_transfers": max_transfers,
            "path_build_sec": round(time.perf_counter() - t0, 2),
            "columns": sum(len(v) for v in paths.values())}
    _cache.clear()                     # one run at a time keeps memory bounded
    _cache[key] = prep
    return prep


def _evaluate(prep: Dict, demand_m: float, fuel_m: float) -> Dict:
    from src.network.ledger import LedgerFlow, LedgerService, compute_ledger

    problem, models, freq, paths = prep["problem"], prep["models"], prep["freq"], prep["paths"]
    demands = [dataclasses.replace(d, weekly_teu=d.weekly_teu * demand_m) for d in problem.demands]

    columns = [(di, p) for di, plist in paths.items() if demands[di].weekly_teu > 0 for p in plist]
    prob = pulp.LpProblem("WhatIfFlows", pulp.LpMaximize)
    q = [pulp.LpVariable(f"q_{j}", lowBound=0) for j in range(len(columns))]
    prob += pulp.lpSum((demands[di].revenue_per_teu - p.port_cost_per_teu) * q[j] for j, (di, p) in enumerate(columns))
    by_od: Dict[int, List[int]] = defaultdict(list)
    by_leg: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for j, (di, p) in enumerate(columns):
        by_od[di].append(j)
        for seg in p.segments:
            for leg in seg.legs:
                by_leg[(seg.service, leg)].append(j)
    for di, js in by_od.items():
        prob += pulp.lpSum(q[j] for j in js) <= float(demands[di].weekly_teu), f"od_{di}"
    for (si, leg), js in by_leg.items():
        prob += pulp.lpSum(q[j] for j in js) <= models[si].capacity_teu * freq[si], f"cap_{si}_{leg}"
    t0 = time.perf_counter()
    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=30))
    lp_sec = round(time.perf_counter() - t0, 2)
    if prob.status != pulp.LpStatusOptimal:
        raise HTTPException(status_code=500, detail=f"flow LP status {pulp.LpStatus.get(prob.status, prob.status)}")

    flows = []
    for j, (di, p) in enumerate(columns):
        v = float(q[j].varValue or 0.0)
        if v > FLOW_NOISE_TEU:
            flows.append(LedgerFlow(di, tuple((models[s.service].service_id, s.from_port, s.to_port)
                                              for s in p.segments), v))
    services = [LedgerService(models[si].service_id, models[si].ports, models[si].vessel_class, f)
                for si, f in freq.items()]
    a = prep["assumptions"]
    fuel_prices = {}
    for s in services:
        r = a.resolve_fuel_price(s.ports)
        fuel_prices[s.service_id] = {"price": r.price_usd_per_t}
    led = compute_ledger(
        services, flows, demands, problem.fleet, problem.distance_matrix, prep["planner"].port_lookup,
        port_stay_hours=a.port_stay_hours, transshipment_min_hours=a.transshipment_min_hours,
        transfer_wait_days=a.transfer_wait_days,
        bunker_price_usd_per_t=(a.effective_fuel_pricing.reference_price_usd_per_t
                                if a.effective_fuel_pricing.reference_price_usd_per_t is not None else float("nan")),
        speed_factor=a.speed_factor, fuel_prices=fuel_prices, max_transfers=prep["max_transfers"])
    fuel = led.fuel_cost * fuel_m
    cost = led.operating_cost - led.fuel_cost + fuel
    profit = led.revenue - cost
    per_service = []
    for sid, r in led.service_rows.items():
        c = r["vessel_cost"] + r["fuel_cost"] * fuel_m + r["port_cost"]
        per_service.append({"id": sid, "revenue": r["revenue"], "cost": c, "profit": r["revenue"] - c,
                            "leg_load_factor": r["leg_load_factor"]})
    return {
        "valid": led.valid, "violations": led.violations[:5],
        "revenue": led.revenue, "vessel_cost": led.vessel_cost, "fuel_cost": fuel,
        "port_call_fixed_cost": led.port_call_fixed_cost, "handling_cost": led.handling_cost,
        "transshipment_cost": led.transshipment_cost, "port_variable_cost": led.port_variable_cost,
        "total_cost": cost, "profit": profit,
        "margin_pct": (profit / led.revenue * 100.0) if led.revenue > 0 else None,
        "demand_teu": led.total_demand_teu, "served_teu": led.served_teu, "unserved_teu": led.unserved_teu,
        "coverage_pct": led.coverage * 100.0, "vessels": sum(led.vessels_by_class.values()),
        "lp_sec": lp_sec, "per_service": per_service,
    }


@router.post("/api/whatif")
def whatif(req: WhatIfRequest):
    """Re-evaluate the recorded plan of ``run`` under scaled demand and fuel price (see module docstring)."""
    with _lock:                         # CBC runs one LP at a time; a slider drag queues, it does not pile up
        key, out = _run_output(req.run)
        prep = _prepare(key, out, _dataset_of(req.run, out))
        base = _evaluate(prep, 1.0, 1.0)
        scen = base if (req.demand_multiplier == 1.0 and req.fuel_multiplier == 1.0) \
            else _evaluate(prep, req.demand_multiplier, req.fuel_multiplier)
    wk = (out.get("network_ledger") or {}).get("weekly_usd") or {}
    dm = (out.get("network_ledger") or {}).get("demand_teu_per_week") or {}
    return {
        "run": req.run, "dataset": prep["dataset"],
        "demand_multiplier": req.demand_multiplier, "fuel_multiplier": req.fuel_multiplier,
        "recorded": {"profit": wk.get("operating_profit"), "revenue": wk.get("revenue"),
                     "total_cost": wk.get("total_operating_cost"), "fuel_cost": wk.get("fuel_cost"),
                     "coverage_pct": dm.get("coverage_pct"), "served_teu": dm.get("served")},
        "baseline": base, "scenario": scen,
        "model": {"services": len(prep["freq"]), "path_columns": prep["columns"],
                  "path_build_sec": prep["path_build_sec"], "max_transfers": prep["max_transfers"],
                  "method": "fixed services/frequencies/vessels; cargo re-routed by the flow LP over every valid "
                            "path through the operated services; priced by src/network/ledger.compute_ledger"},
    }
