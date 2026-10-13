"""Independent recomputation of the utilisation metrics from a pipeline_output.json (flows + rotations only).

leg load factor (service) = carried TEU-legs / (capacity_per_departure x frequency x number of legs of the closed rotation)
vessel utilisation        = vessels assigned / vessels owned (per class, and fleet)
Compared with the values the ledger / strategy report / selected_services carry.  usage: script <pipeline_output.json> <out.json>
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

d = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
nl = d["network_ledger"]
rows = {s["id"]: s for s in nl["plan"]["services"]} if "plan" in nl and "services" in nl["plan"] else {}
if not rows:
    rows = {s["id"]: s for s in nl["services"]} if isinstance(nl.get("services"), list) else {}
# services as detailed in the plan block
plan_services = nl["plan"]["services"] if "plan" in nl else []
flows = nl["plan"]["flows"]
svc = {s["id"]: s for s in plan_services}
carried = defaultdict(float)
for f in flows:
    for sid_idx, a, b in f["segments"]:
        # segments reference the service by id (string)
        sid = sid_idx
        ports = svc[sid]["ports"]
        i, j, n = ports.index(a), ports.index(b), len(ports)
        legs = (j - i) % n
        carried[sid] += f["teu"] * legs
sel = {s["id"]: s for s in d["selected_services"]}
worst = 0.0
n_checked = 0
tot_c = tot_o = 0.0
for sid, s in svc.items():
    cap = float(sel[sid]["capacity"])
    f = int(s["frequency"]) if "frequency" in s else int(sel[sid]["frequency_per_week"])
    offered = cap * f * len(s["ports"])
    lf = carried[sid] / offered if offered else None
    rep = sel[sid].get("leg_load_factor")
    if rep is not None and lf is not None:
        worst = max(worst, abs(lf - rep))
        n_checked += 1
    tot_c += carried[sid]
    tot_o += offered
fleet = nl["fleet_by_class"]
used = sum(v["used"] for v in fleet.values())
avail = sum(v["available"] for v in fleet.values())
sr = nl.get("strategy_report", {}).get("utilisation", {})
out = {
    "services_checked": n_checked, "max_abs_difference_leg_load_factor": worst,
    "independent_network_leg_load_factor": tot_c / tot_o,
    "reported_network_leg_load_factor_strategy_report": (sr.get("network") or {}).get("load_factor"),
    "vessels_assigned": used, "vessels_owned": avail, "vessel_inventory_utilisation": used / avail,
    "reported_fleet_inventory_utilisation": (sr.get("fleet") or {}).get("inventory_utilisation"),
    "by_class": {c: {"used": v["used"], "available": v["available"], "utilisation": (v["used"] / v["available"]) if v["available"] else None}
                 for c, v in fleet.items()},
}
Path(sys.argv[2]).write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps({k: out[k] for k in out if k != "by_class"}, indent=1))
