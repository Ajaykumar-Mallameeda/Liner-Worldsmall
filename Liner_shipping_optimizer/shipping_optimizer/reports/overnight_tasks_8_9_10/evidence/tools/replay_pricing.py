"""Task 8B evidence: replay the captured global-stage inputs under different fuel pricing.

Same demand, same fleet, same CAPTURED candidate pool, same solver strategy: only the
bunker pricing changes.  Reuses the U4 capture of ``capture_global_inputs.py``.

usage:
    python -I replay_pricing.py <project_root> <pickle> <call_index> <out.json> [time_limit_sec] [scenario ...]

scenarios (default: all)
    legacy_600           uniform 600 USD/t (the benchmark-era assumption)
    reference_uniform    every service at the snapshot's global reference (895.5)
    regional             cheapest observed bunkering port on the rotation, else reference
    regional_x0.8 / regional_x1.2   regional snapshot with every price scaled (sensitivity)
    regional_strict      like regional but a rotation with no observed port is an error
                         (shows how many candidates have no source-backed regional price)
    <scenario>@full_int  the same scenario solved WITHOUT the LP-guided restriction (full
                         integer problem over every candidate) to check that an empty
                         production plan is not an artefact of the restriction heuristic
"""
import dataclasses
import json
import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT))

import pickle                                                       # noqa: E402

from src.data.network_loader import NetworkLoader                   # noqa: E402
from src.network.bunker_prices import (                             # noqa: E402
    FALLBACK_ERROR, FALLBACK_REFERENCE, RULE_CHEAPEST_OBSERVED, RULE_REFERENCE_ONLY,
    FuelPricing, load_snapshot,
)
from src.network.economics import assumptions_for_problem          # noqa: E402
from src.network.plan import NetworkPlanner                         # noqa: E402
from src.network.reconcile import collect_candidates                # noqa: E402
from src.optimization.data import Problem                           # noqa: E402

PICKLE, CALL, OUT = Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4])
TL = float(sys.argv[5]) if len(sys.argv) > 5 else 120.0
WANT = sys.argv[6:] or ["legacy_600", "reference_uniform", "regional", "regional_x0.8",
                        "regional_x1.2", "regional_strict"]
SNAP = ROOT / "data" / "pricing" / "bunker_snapshot_2026-10-09_vlsfo.json"


def scaled(snapshot_path: Path, k: float) -> dict:
    raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    for o in raw["observations"]:
        o["price"] = round(o["price"] * k, 4)
        o["provenance"] = "derived"
        o["note"] = f"sensitivity: observed x {k}"
    raw["reference"]["price"] = round(raw["reference"]["price"] * k, 4)
    raw["reference"]["provenance"] = "derived"
    raw["snapshot_id"] = f"{raw['snapshot_id']}_x{k}"
    return raw


def pricing_for(name: str) -> FuelPricing:
    if name == "legacy_600":
        return FuelPricing.legacy_uniform(600.0)
    snap = load_snapshot(SNAP, expected_grade="VLSFO")
    if name == "reference_uniform":
        return FuelPricing.from_snapshot(snap, location_rule=RULE_REFERENCE_ONLY)
    if name == "regional":
        return FuelPricing.from_snapshot(snap, location_rule=RULE_CHEAPEST_OBSERVED,
                                         fallback=FALLBACK_REFERENCE)
    if name == "regional_strict":
        return FuelPricing.from_snapshot(snap, location_rule=RULE_CHEAPEST_OBSERVED,
                                         fallback=FALLBACK_ERROR)
    if name.startswith("regional_x"):
        k = float(name.split("_x")[1])
        return FuelPricing.from_snapshot(load_snapshot(scaled(SNAP, k), expected_grade="VLSFO"),
                                         location_rule=RULE_CHEAPEST_OBSERVED)
    raise SystemExit(f"unknown scenario {name}")


data = pickle.loads(PICKLE.read_bytes())
call = data["captured"][CALL]
ws = ROOT / "data" / "raw" / "WorldSmall"
L = NetworkLoader()
ports = L.load_ports(ws / "ports.csv")
demands = L.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
dist = L.load_distance_matrix(ws / "dist_dense.csv")
fleet = L.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")
for p in ports:
    dist.setdefault(p.id, {})
problem = Problem(ports=ports, services=[], demands=demands, distance_matrix=dist, fleet=fleet)
cands, owner = collect_candidates(call["pools"])

results = {"call_index": CALL, "pickle": str(PICKLE), "candidates_offered": len(cands),
           "time_limit_sec": TL, "snapshot": str(SNAP), "scenarios": {}}
for name in WANT:
    base_name, _, variant = name.partition("@")
    pricing = pricing_for(base_name)
    base = assumptions_for_problem(problem)
    a = dataclasses.replace(base, fuel_pricing=pricing)
    planner = NetworkPlanner(problem, assumptions=a)
    t0 = time.perf_counter()
    kw = {"lp_guided": False} if variant == "full_int" else {}
    plan = planner.plan(cands, demands=problem.demands, time_limit_sec=TL, **kw)
    dt = time.perf_counter() - t0
    led = plan.ledger
    sc = {"pricing": pricing.describe(), "status": plan.status, "ok": plan.ok,
          "message": plan.message, "runtime_sec": round(dt, 1),
          "candidates_modelled": len(plan.models),
          "candidates_rejected": len(plan.rejected_candidates),
          "rejected_reasons": sorted({r for b in plan.rejected_candidates for r in b.get("reasons", [])}),
          "basis_counts_modelled": {}}
    for m in plan.models:
        sc["basis_counts_modelled"][m.fuel_price_basis] = sc["basis_counts_modelled"].get(m.fuel_price_basis, 0) + 1
    if led is not None:
        sc.update({
            "profit": led.operating_profit, "revenue": led.revenue, "total_cost": led.operating_cost,
            "vessel_cost": led.vessel_cost, "fuel_cost": led.fuel_cost,
            "port_call_fixed_cost": led.port_call_fixed_cost, "handling_cost": led.handling_cost,
            "transshipment_cost": led.transshipment_cost, "port_variable_cost": led.port_variable_cost,
            "margin_pct": (100 * led.operating_profit / led.revenue) if led.revenue > 0 else None,
            "coverage_pct": led.coverage * 100, "served_teu": led.served_teu,
            "total_demand_teu": led.total_demand_teu,
            "n_services": len(led.service_rows), "vessels": sum(led.vessels_by_class.values()),
            "vessels_by_class": dict(led.vessels_by_class),
            "violations": list(led.violations),
            "reconciled": plan.reconciliation.get("reconciled"),
            "milp_vs_ledger_diff": plan.reconciliation.get("difference"),
            "relaxation_bound": plan.solution.relaxation_bound if plan.solution else None,
            "services": [
                {"id": sid, "ports": r["ports"], "class": r["vessel_class"], "f": r["frequency"],
                 "vessels": r["vessels"], "cycle_days": r["cycle_time_days"],
                 "fuel_cost": r["fuel_cost"], "fuel_tonnes": r["fuel_tonnes"],
                 "fuel_price": r["fuel_price_usd_per_t"],
                 "basis": plan.fuel_prices.get(sid, {}).get("basis"),
                 "bunkering_port": plan.fuel_prices.get(sid, {}).get("bunkering_port"),
                 "revenue": r["revenue"]}
                for sid, r in led.service_rows.items()],
        })
    # per-candidate weekly fuel cost at f = 1 (for service ranking comparisons)
    sc["candidate_fuel_per_rotation"] = {m.service_id: m.fuel_cost_per_rotation for m in plan.models}
    results["scenarios"][name] = sc
    print(f"[{name}] status={plan.status} profit={sc.get('profit')} fuel={sc.get('fuel_cost')} "
          f"cov={sc.get('coverage_pct')} svc={sc.get('n_services')} vessels={sc.get('vessels')} "
          f"modelled={len(plan.models)} rejected={len(plan.rejected_candidates)} {dt:.0f}s", flush=True)

OUT.write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
print("wrote", OUT)
