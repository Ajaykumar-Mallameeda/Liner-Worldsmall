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
import datetime as dt
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
    # disruptions (backend/disruption.py): a preset key and/or explicit passages / ports to close
    preset: Optional[str] = None
    closed_passages: List[str] = Field(default_factory=list)
    detour_avoid: List[str] = Field(default_factory=list)
    closed_ports: List[str] = Field(default_factory=list)
    # market inputs (backend/market.py, backend/war_risk.py): #20 freight rate level, #21 bunker by port, #19 war risk
    rate_mode: str = Field("uniform", pattern="^(uniform|wci_lanes)$")
    rate_multiplier: float = Field(1.0, ge=0.2, le=6.0)
    lane_usd_per_feu: Dict[str, float] = Field(default_factory=dict)
    bunker_mode: str = Field("dataset", pattern="^(dataset|market)$")
    war_risk: bool = False
    war_rates_pct: Dict[str, float] = Field(default_factory=dict)
    hull_usd_per_teu: float = Field(15000.0, ge=1000.0, le=60000.0)


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
    """Problem, service models of the recorded plan and the full path set through them (cached per run)."""
    if key in _cache:
        return _cache[key]
    from src.data.problem_json import load_problem_json
    from src.network.economics import assumptions_for_problem

    nl = out.get("network_ledger") or {}
    plan = nl.get("plan") or {}
    services = plan.get("services") or []
    if not services:
        raise HTTPException(status_code=422, detail="this run has no recorded network plan to re-evaluate")
    problem, _meta = load_problem_json(dataset)
    assumptions = assumptions_for_problem(problem)
    a_rec = nl.get("assumptions") or {}
    max_transfers = int(a_rec.get("max_transfers_per_od", 2))
    prep, rejected = _build(problem, assumptions, services, max_transfers, dataset)
    if rejected:
        raise HTTPException(status_code=422, detail=f"recorded services could not be modelled: {rejected[:3]}")
    prep["services_rec"] = services
    prep["key"] = key
    _cache.clear()                     # one run at a time keeps memory bounded (its variants are added below)
    _cache[key] = prep
    return prep


def _build(problem, assumptions, services: List[Dict], max_transfers: int, dataset: str) -> Tuple[Dict, List[Dict]]:
    """Service models of `services` on `problem` and every valid path through them: (prep, rejected services)."""
    from src.network.paths import BUDGET_FIXED, SELECT_FASTEST, PathConfig, build_paths
    from src.network.plan import Candidate, NetworkPlanner

    planner = NetworkPlanner(problem, assumptions)
    cands = [Candidate(s["id"], tuple(s["ports"]), s["vessel_class"]) for s in services]
    models, rejected = planner.build_models(cands)
    f_by_id = {s["id"]: int(s["frequency_per_week"]) for s in services}
    # models holds the accepted services only, so frequencies are matched by id
    freq = {i: f_by_id[m.service_id] for i, m in enumerate(models) if f_by_id.get(m.service_id, 0) > 0}
    # the flow re-optimisation's column set: fastest, fixed budget, every path, two-transfer paths everywhere
    cfg = PathConfig(selection=SELECT_FASTEST, budget=BUDGET_FIXED, max_transfers=max_transfers,
                     multi_hop_min_alternatives=10 ** 9 if max_transfers >= 2 else 1)
    t0 = time.perf_counter()
    paths = {}
    if freq:
        paths, _stats = build_paths(problem.demands, models, planner.port_lookup, assumptions,
                                    max_paths_per_od=10 ** 9, config=cfg, only_services=sorted(freq))
    prep = {"problem": problem, "assumptions": assumptions, "planner": planner, "models": models,
            "freq": freq, "paths": paths, "dataset": dataset, "max_transfers": max_transfers,
            "path_build_sec": round(time.perf_counter() - t0, 2),
            "columns": sum(len(v) for v in paths.values())}
    return prep, rejected


MAX_VARIANTS = 12
REJECT_REASONS = {      # service-model rejections (src/services/service_feasibility.py, physical_rules.py) in words
    "required_vessels_exceed_class_inventory": "one weekly departure on the longer cycle needs more vessels of its "
                                               "class than the fleet has",
    "canal_not_passable_for_class": "its vessel class cannot pass the canal the detour uses",
    "draft_exceeds_leg_limit": "the new route's draft limit is too shallow for its vessel class",
    "draft_exceeds_port_limit": "a port on the new rotation is too shallow for its vessel class",
    "too_few_ports": "fewer than two ports left",
}


def _variant(base: Dict, closed: Tuple[str, ...], detour_avoid: Tuple[str, ...],
             closed_ports: Tuple[str, ...]) -> Tuple[Dict, Dict]:
    """The recorded plan with passages and / or ports closed (backend/disruption.py): (prep, report). Cached."""
    from backend import disruption
    from src.optimization.data import Problem

    vkey = f"{base['key']}|closed={','.join(closed)}|avoid={','.join(detour_avoid)}|ports={','.join(closed_ports)}"
    if vkey in _cache:
        return _cache[vkey], _cache[vkey]["disruption"]
    problem = base["problem"]
    services = base["services_rec"]
    matrix = problem.distance_matrix
    report: Dict = {"closed_passages": [], "detour_avoid": [], "rerouted_legs": [], "suspended_services": [],
                    "extra_nm_per_week": 0.0, "closed_ports": [], "services_skipping": []}
    if closed:
        matrix, services, rep = disruption.close_passages(base["dataset"], services, matrix, closed, detour_avoid)
        report.update(rep)
    if closed_ports:
        services, rep = disruption.close_ports(services, closed_ports)
        report["closed_ports"] = rep["closed_ports"]
        report["services_skipping"] = rep["services_skipping"]
        report["suspended_services"] = report["suspended_services"] + rep["suspended_services"]
    p2 = Problem(ports=problem.ports, services=[], demands=problem.demands, distance_matrix=matrix, fleet=problem.fleet)
    prep, rejected = _build(p2, base["assumptions"], services, base["max_transfers"], base["dataset"])
    for r in rejected:                  # e.g. a detour a vessel class cannot sail (canal fee / draft rules)
        why = [REJECT_REASONS.get(str(x), str(x).replace("_", " ")) for x in (r.get("reasons") or [])]
        report["suspended_services"].append({"id": r["service"], "reason": "; ".join(why) or "cannot be modelled"})
    report["services_sailing"] = len(prep["freq"])
    prep["disruption"] = report
    if len(_cache) >= MAX_VARIANTS:     # keep the run's own entry, drop the oldest variant
        for k in list(_cache):
            if k != base["key"]:
                del _cache[k]
                break
    _cache[vkey] = prep
    return prep, report


def _evaluate(prep: Dict, demand_m: float, fuel_m: float, od_flows_for: Optional[int] = None,
              keep_flows: bool = False, keep_paths: bool = False, rev_m: Optional[List[float]] = None,
              fuel_pricing=None, extra_cost: Optional[Dict[str, float]] = None) -> Dict:
    """Flow LP + ledger of `prep` at the given multipliers. `od_flows_for` (a demand index) adds that OD's routed
    TEU per path as "od_flows" (the transit finder, backend/transit.py); `keep_flows` adds every routed flow as
    "flows" [(od index, ((service, from, to), ...), TEU)] (port activity, backend/port_activity.py); `keep_paths` adds
    "path_flows" [(od index, OdPath, TEU)] with the legs each segment rides (reliability, backend/reliability.py).
    Market inputs: `rev_m` multiplies each demand's revenue per TEU (freight index, so the LP re-routes on the new
    rates), `fuel_pricing` replaces the assumptions' bunker pricing (engine FuelPricing, e.g. a market snapshot),
    `extra_cost` adds a weekly cost per service id (war-risk premiums), reported as "war_risk_cost"."""
    from src.network.ledger import LedgerFlow, LedgerService, compute_ledger

    problem, models, freq, paths = prep["problem"], prep["models"], prep["freq"], prep["paths"]
    demands = [dataclasses.replace(d, weekly_teu=d.weekly_teu * demand_m,
                                   revenue_per_teu=d.revenue_per_teu * (rev_m[i] if rev_m else 1.0))
               for i, d in enumerate(problem.demands)]

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
    if columns:                        # every service suspended leaves nothing to route
        prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=30))
    lp_sec = round(time.perf_counter() - t0, 2)
    if columns and prob.status != pulp.LpStatusOptimal:
        raise HTTPException(status_code=500, detail=f"flow LP status {pulp.LpStatus.get(prob.status, prob.status)}")

    flows = []
    od_flows = []
    path_flows = []
    for j, (di, p) in enumerate(columns):
        v = float(q[j].varValue or 0.0)
        if di == od_flows_for and v > FLOW_NOISE_TEU:
            od_flows.append((p, v))
        if v > FLOW_NOISE_TEU and keep_paths:
            path_flows.append((di, p, v))
        if v > FLOW_NOISE_TEU:
            flows.append(LedgerFlow(di, tuple((models[s.service].service_id, s.from_port, s.to_port)
                                              for s in p.segments), v))
    services = [LedgerService(models[si].service_id, models[si].ports, models[si].vessel_class, f)
                for si, f in freq.items()]
    a = prep["assumptions"]
    pricing = fuel_pricing or a.effective_fuel_pricing
    fuel_prices, fuel_resolution = {}, {}
    for s in services:
        r = pricing.resolve(s.ports)
        fuel_prices[s.service_id] = {"price": r.price_usd_per_t}
        fuel_resolution[s.service_id] = {"price": r.price_usd_per_t, "basis": r.basis, "port": r.bunkering_port,
                                         "observed_on": r.observed_on}
    led = compute_ledger(
        services, flows, demands, problem.fleet, problem.distance_matrix, prep["planner"].port_lookup,
        port_stay_hours=a.port_stay_hours, transshipment_min_hours=a.transshipment_min_hours,
        transfer_wait_days=a.transfer_wait_days,
        bunker_price_usd_per_t=(pricing.reference_price_usd_per_t
                                if pricing.reference_price_usd_per_t is not None else float("nan")),
        speed_factor=a.speed_factor, fuel_prices=fuel_prices, max_transfers=prep["max_transfers"])
    fuel = led.fuel_cost * fuel_m
    extra_cost = extra_cost or {}
    war = float(sum(extra_cost.get(s.service_id, 0.0) for s in services))
    cost = led.operating_cost - led.fuel_cost + fuel + war
    profit = led.revenue - cost
    per_service = []
    for sid, r in led.service_rows.items():
        c = r["vessel_cost"] + r["fuel_cost"] * fuel_m + r["port_cost"] + float(extra_cost.get(sid, 0.0))
        per_service.append({"id": sid, "revenue": r["revenue"], "cost": c, "profit": r["revenue"] - c,
                            "fuel_price": fuel_prices.get(sid, {}).get("price"),
                            "war_risk_cost": float(extra_cost.get(sid, 0.0)),
                            "leg_load_factor": r["leg_load_factor"], "vessels": led.vessels_by_service.get(sid),
                            "cycle_days": led.cycle_time_days.get(sid),
                            "legs": [{"from": lg["from"], "to": lg["to"], "nm": round(lg["distance_nm"], 1),
                                      "load_teu": round(lg["load_teu"], 1)} for lg in r.get("legs") or []]})
    return {
        "valid": led.valid, "violations": led.violations[:5],
        "revenue": led.revenue, "vessel_cost": led.vessel_cost, "fuel_cost": fuel,
        "port_call_fixed_cost": led.port_call_fixed_cost, "handling_cost": led.handling_cost,
        "transshipment_cost": led.transshipment_cost, "port_variable_cost": led.port_variable_cost,
        "war_risk_cost": war, "fuel_resolution": fuel_resolution,
        "total_cost": cost, "profit": profit,
        "margin_pct": (profit / led.revenue * 100.0) if led.revenue > 0 else None,
        "demand_teu": led.total_demand_teu, "served_teu": led.served_teu, "unserved_teu": led.unserved_teu,
        "coverage_pct": led.coverage * 100.0, "vessels": sum(led.vessels_by_class.values()),
        "lp_sec": lp_sec, "per_service": per_service,
        "transshipment": _transship_summary(flows, prep["planner"].port_lookup),
        **({"od_flows": od_flows} if od_flows_for is not None else {}),
        **({"flows": [(f.od, f.segments, f.teu) for f in flows]} if keep_flows else {}),
        **({"path_flows": path_flows} if keep_paths else {}),
    }


def _transship_summary(flows, port_lookup) -> Dict:
    """Where the routed cargo changes ship: TEU and cost per transfer port, by the ledger's rule (TEU x the port's
    transshipment_cost at every port between two segments of a flow). Same split the frontend draws for the recorded
    plan (frontend/src/utils/transshipment.js), so baseline and scenario hubs compare like for like."""
    hubs: Dict[str, Dict] = {}
    teu = moves = cost = 0.0
    for f in flows:
        if len(f.segments) < 2:
            continue
        teu += f.teu
        for k in range(len(f.segments) - 1):
            port = f.segments[k][2]
            rate = float(getattr(port_lookup.get(port), "transshipment_cost", 0.0) or 0.0)
            h = hubs.setdefault(port, {"port": port, "teu": 0.0, "cost": 0.0, "cost_per_teu": rate})
            h["teu"] += f.teu
            h["cost"] += f.teu * rate
            moves += f.teu
            cost += f.teu * rate
    return {"teu": teu, "moves": moves, "cost": cost,
            "hubs": sorted(hubs.values(), key=lambda h: (-h["teu"], h["port"]))}


def _market_inputs(req: WhatIfRequest, sprep: Dict, report: Optional[Dict]):
    """(report, per-demand revenue multipliers or None, FuelPricing or None, war-risk costs or None) for the
    scenario's market inputs (backend/market.py, backend/war_risk.py). The baseline never takes them."""
    from backend import market, war_risk

    problem = sprep["problem"]
    out: Dict = {}
    # #20 freight rate level
    rev_m = None
    lanes = market.lane_ratios(problem, lane_usd_per_feu=req.lane_usd_per_feu)
    snap = market.freight_snapshot()
    if req.rate_mode == "wci_lanes" or req.rate_multiplier != 1.0:
        rev_m, used = market.revenue_multipliers(problem, sprep["planner"].port_lookup, req.rate_mode,
                                                 req.rate_multiplier, lanes)
    else:
        used = {}
    out["freight"] = {"mode": req.rate_mode, "uniform_multiplier": req.rate_multiplier, "lanes": lanes,
                      "lanes_applied": used, "composite": snap["composite"], "as_of": snap["as_of"],
                      "index": snap["index"], "lane_source": snap["lane_source"], "lane_urls": snap["lane_urls"],
                      "per_teu_rule": snap["per_teu_rule"]}
    # #21 bunker price by port
    pricing = None
    if req.bunker_mode == "market":
        prices = market.bunker_prices()
        try:
            pricing, bsnap = market.market_pricing(prices)
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI, never priced at zero
            raise HTTPException(status_code=503, detail=f"bunker prices unavailable: {exc}")
        age = (dt.date.today() - dt.date.fromisoformat(bsnap["as_of"])).days
        out["bunker"] = {"mode": "market", "snapshot_id": bsnap["snapshot_id"], "as_of": bsnap["as_of"],
                         "age_days": age, "stale": age > bsnap["max_age_days"], "status": prices["status"],
                         "fetched_on": prices["fetched_on"], "reference": bsnap["reference"],
                         "ports": [{"hub": o["hub"], "price": o["price"], "location": o.get("bunkering_location"),
                                    "url": o.get("source_url")} for o in bsnap["observations"]],
                         "averages": prices.get("averages"), "dropped_stale": bsnap.get("dropped_stale", []),
                         "rule": pricing.describe().get("location_assumption")}
    else:
        out["bunker"] = {"mode": "dataset", "describe": sprep["assumptions"].effective_fuel_pricing.describe()}
    # #19 war risk
    war = None
    if req.war_risk:
        avoid = tuple(sorted(set((report or {}).get("closed_passages") or []) | set((report or {}).get("detour_avoid") or [])))
        war = war_risk.service_costs(sprep, war_risk.rates_with(req.war_rates_pct), req.hull_usd_per_teu, avoid)
    out["war_risk"] = {"enabled": req.war_risk, **(war or {}), "definitions": war_risk.describe()}
    return out, rev_m, pricing, war


@router.post("/api/whatif")
def whatif(req: WhatIfRequest):
    """Re-evaluate the recorded plan of ``run`` under scaled demand and fuel price (see module docstring)."""
    from backend import disruption
    try:
        closed, detour_avoid, preset = disruption.resolve(req.preset, req.closed_passages, req.detour_avoid)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    closed_ports = tuple(sorted({str(p).strip().upper() for p in req.closed_ports if str(p).strip()}))
    report = None
    with _lock:                         # CBC runs one LP at a time; a slider drag queues, it does not pile up
        key, out = _run_output(req.run)
        prep = _prepare(key, out, _dataset_of(req.run, out))
        base = _evaluate(prep, 1.0, 1.0)
        sprep = prep
        if closed or closed_ports:
            unknown = [p for p in closed_ports if p not in prep["planner"].port_lookup]
            if unknown:
                raise HTTPException(status_code=422, detail=f"unknown port(s) {unknown} in dataset {prep['dataset']}")
            sprep, report = _variant(prep, closed, detour_avoid, closed_ports)
        market_out, rev_m, pricing, war = _market_inputs(req, sprep, report)
        unchanged = (sprep is prep and req.demand_multiplier == 1.0 and req.fuel_multiplier == 1.0
                     and rev_m is None and pricing is None and war is None)
        scen = base if unchanged else _evaluate(sprep, req.demand_multiplier, req.fuel_multiplier, rev_m=rev_m,
                                                fuel_pricing=pricing, extra_cost=(war or {}).get("per_service"))
    if report is not None:
        report = {**report, "preset": req.preset, "preset_label": preset["label"] if preset else None,
                  "preset_note": preset["note"] if preset else None,
                  "vessels_before": base["vessels"], "vessels_after": scen["vessels"],
                  "method": "legs crossing a closed passage take searoute's shortest open detour; distance from the "
                            "LINERLIB alternative record matching the detour's canals, else LINERLIB distance x the "
                            "detour / normal sea-lane ratio; services with no open lane are suspended"}
    wk = (out.get("network_ledger") or {}).get("weekly_usd") or {}
    dm = (out.get("network_ledger") or {}).get("demand_teu_per_week") or {}
    return {
        "run": req.run, "dataset": prep["dataset"],
        "demand_multiplier": req.demand_multiplier, "fuel_multiplier": req.fuel_multiplier,
        "presets": {k: {"label": v["label"], "closed": v["closed"], "detour_avoid": v["detour_avoid"], "note": v["note"]}
                    for k, v in disruption.PRESETS.items()},
        "recorded": {"profit": wk.get("operating_profit"), "revenue": wk.get("revenue"),
                     "total_cost": wk.get("total_operating_cost"), "fuel_cost": wk.get("fuel_cost"),
                     "coverage_pct": dm.get("coverage_pct"), "served_teu": dm.get("served")},
        "baseline": base, "scenario": scen, "disruption": report, "market": market_out,
        "model": {"services": len(prep["freq"]), "path_columns": prep["columns"],
                  "path_build_sec": prep["path_build_sec"], "max_transfers": prep["max_transfers"],
                  "method": "fixed services/frequencies/vessels; cargo re-routed by the flow LP over every valid "
                            "path through the operated services; priced by src/network/ledger.compute_ledger"},
    }
