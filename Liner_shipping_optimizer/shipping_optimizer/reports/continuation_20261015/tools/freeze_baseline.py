"""Freeze a per-seed baseline table from existing run artifacts, with provenance checks (WorldSmall only).

usage: python -I freeze_baseline.py <per_seed_csv> <arm> <outputs_dir> <out_json> [<out_md>]

Checks performed (nothing is recomputed from a model; every figure comes from the artifacts):
  * sha256 of each output JSON equals the value recorded in the CSV
  * the five input-file hashes recorded in each run equal the hashes of the files on disk now
  * run status counts (solved / not_solved / invalid) - every seed of the CSV is kept, none excluded
Derived (arithmetic only): profit per assigned vessel, profit per owned vessel, deployment ratio,
idle vessels by class, itemised costs.
"""
import csv
import hashlib
import json
import statistics as st
import sys
from pathlib import Path

CSV_PATH, ARM, OUTD, OUT_JSON = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
OUT_MD = Path(sys.argv[5]) if len(sys.argv) > 5 else None
RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "WorldSmall"
CLASSES = ["Feeder_450", "Feeder_800", "Panamax_1200", "Panamax_2400", "Post_panamax", "Super_panamax"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


disk = {n: sha(RAW / n)[:16] for n in ("Demand_WorldSmall_Fixed_Sep.csv", "dist_dense.csv", "fleet_WorldSmall.csv",
                                         "fleet_data.csv", "ports.csv")}


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


rows = [r for r in csv.DictReader(CSV_PATH.open(encoding="utf-8")) if r["arm"] == ARM]
rows.sort(key=lambda r: int(r["seed"]))
per_seed, problems = [], []
for r in rows:
    seed = int(r["seed"])
    p = OUTD / f"{ARM}_seed{seed}.json"
    art_ok = p.exists() and sha(p) == r["output_sha256"]
    if not art_ok:
        problems.append(f"seed {seed}: artifact missing or sha256 differs from the CSV")
    hashes = json.loads(r["input_hashes"]) if r.get("input_hashes") else {}
    inp_ok = bool(hashes) and all(disk.get(k) == v for k, v in hashes.items())
    if not inp_ok:
        problems.append(f"seed {seed}: recorded input hashes differ from the files on disk")
    profit, vused, inv = f(r["profit_usd_wk"]), f(r["vessels_used"]), f(r["inventory"])
    per_seed.append({
        "seed": seed, "status": r["status"], "solver_status_raw": r["solver_status"], "stage_wall_sec": f(r["stage_wall_sec"]),
        "incumbent_usd_wk": f(r["incumbent_usd_wk"]), "lp_bound_usd_wk": f(r["bound_usd_wk"]),
        "legacy_gap_pct_final_vs_bound": f(r["gap_pct"]),
        "profit_usd_wk": profit, "revenue_usd_wk": f(r["revenue_usd_wk"]),
        "cost": {"vessel": f(r["vessel_cost"]), "fuel": f(r["fuel_cost"]), "port_call_fixed_incl_canal": f(r["port_call_fixed"]),
                 "handling": f(r["handling"]), "transshipment": f(r["transshipment"]), "port_variable": f(r["port_variable"]),
                 "total": f(r["total_cost"])},
        "coverage_pct": f(r["coverage_pct"]), "served_teu": f(r["served_teu"]), "unserved_teu": f(r["unserved_teu"]),
        "services": f(r["services"]), "departures_per_week": f(r["departures_per_week"]),
        "vessels_assigned": vused, "vessels_owned": inv, "vessels_idle": f(r["idle_vessels"]),
        "deployment_ratio": (vused / inv) if vused is not None and inv else None,
        "productive_load_factor_network": f(r["load_factor_network"]), "leg_load_factor": f(r["load_factor_leg"]),
        "profit_per_assigned_vessel": (profit / vused) if profit is not None and vused else None,
        "profit_per_owned_vessel": (profit / inv) if profit is not None and inv else None,
        "by_class": {c: {"assigned": f(r[f"used_{c}"]), "owned": f(r[f"inv_{c}"]),
                         "idle": (f(r[f"inv_{c}"]) - f(r[f"used_{c}"])), "services": f(r[f"svc_{c}"])} for c in CLASSES},
        "ledger_valid": r["ledger_valid"], "ledger_violations": f(r["ledger_violations"]), "transit_violations": f(r["transit_violations"]),
        "artifact_sha256_ok": art_ok, "input_hashes_ok": inp_ok, "output_sha256": r["output_sha256"], "env": json.loads(r["env"]),
    })

n = len(per_seed)
status_counts = {}
for s in per_seed:
    status_counts[s["status"]] = status_counts.get(s["status"], 0) + 1


def agg(key):
    v = [s[key] for s in per_seed if s[key] is not None]
    return {"mean": st.mean(v), "median": st.median(v), "min": min(v), "max": max(v), "sd": st.pstdev(v) if len(v) > 1 else 0.0, "n": len(v)} if v else None


summary = {k: agg(k) for k in ("profit_usd_wk", "revenue_usd_wk", "coverage_pct", "services", "departures_per_week", "vessels_assigned",
                                "vessels_idle", "deployment_ratio", "productive_load_factor_network", "profit_per_assigned_vessel",
                                "profit_per_owned_vessel", "stage_wall_sec")}
summary["cost_mean"] = {k: st.mean([s["cost"][k] for s in per_seed]) for k in per_seed[0]["cost"]}
summary["by_class_mean_assigned_idle"] = {c: {"assigned": st.mean([s["by_class"][c]["assigned"] for s in per_seed]),
                                                "owned": per_seed[0]["by_class"][c]["owned"],
                                                "idle": st.mean([s["by_class"][c]["idle"] for s in per_seed])} for c in CLASSES}
out = {"arm": ARM, "source_csv": str(CSV_PATH), "n_seeds": n, "status_counts": status_counts,
       "ledger_violation_seeds": [s["seed"] for s in per_seed if s["ledger_violations"]],
       "transit_violation_seeds": [s["seed"] for s in per_seed if s["transit_violations"]],
       "provenance_problems": problems, "input_hashes_on_disk_16": disk, "summary": summary, "per_seed": per_seed,
       "note": "legacy_gap_pct_final_vs_bound compares the FINAL plan with the capped-model LP bound; it is not an optimality gap "
               "(the solver is time limited: status 'feasible', no optimality claim)."}
OUT_JSON.write_text(json.dumps(out, indent=1), encoding="utf-8")

if OUT_MD:
    L = [f"# Frozen baseline `{ARM}` from `{CSV_PATH.name}` ({n} seeds)", "",
         f"status counts: {status_counts}; ledger-violation seeds: {out['ledger_violation_seeds']}; transit-violation seeds: {out['transit_violation_seeds']}",
         f"provenance problems: {problems or 'none'}", "",
         "| seed | status | profit M | coverage % | services | assigned/owned | idle | prod. load | profit/assigned k | wall s |", "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in per_seed:
        L.append(f"| {s['seed']} | {s['status']} | {s['profit_usd_wk']/1e6:.2f} | {s['coverage_pct']:.1f} | {s['services']:.0f} | "
                 f"{s['vessels_assigned']:.0f}/{s['vessels_owned']:.0f} | {s['vessels_idle']:.0f} | {s['productive_load_factor_network']:.3f} | "
                 f"{s['profit_per_assigned_vessel']/1e3:.0f} | {s['stage_wall_sec']:.0f} |")
    p = summary["profit_usd_wk"]
    L += ["", f"profit mean {p['mean']/1e6:.2f} M, median {p['median']/1e6:.2f}, min {p['min']/1e6:.2f}, max {p['max']/1e6:.2f}, sd {p['sd']/1e6:.2f}",
          f"cost means (M): " + ", ".join(f"{k} {v/1e6:.2f}" for k, v in summary['cost_mean'].items()),
          f"idle by class (mean): " + ", ".join(f"{c} {v['idle']:.1f}/{v['owned']:.0f}" for c, v in summary['by_class_mean_assigned_idle'].items())]
    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
print(json.dumps({"arm": ARM, "n": n, "status": status_counts, "problems": problems,
                  "profit_mean": summary["profit_usd_wk"]["mean"]}, indent=1))
