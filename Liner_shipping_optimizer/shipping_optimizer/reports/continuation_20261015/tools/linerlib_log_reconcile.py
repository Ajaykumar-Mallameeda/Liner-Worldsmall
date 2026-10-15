"""Reconcile the cost equations against the LINERLIB authors' own WorldSmall solution log (primary-source output).

usage: python -I linerlib_log_reconcile.py <WorldSmall_Best_Base.log> <out.json>

The log is the authors' LINERLIB-model solution (speed-optimised services, cubic consumption law).  It is NOT the RL
paper's design-speed model; it is used to check, line by line and from the raw WorldSmall files only, that

  * sailing time = distance / (24 x speed) days, one idle day per port call, class inputs and units  (Target 3.2)
  * weekly time-charter cost = vessels x TC rate x 7                                                  (Target 3.3)
  * port-call cost = sum over calls of (fixed + per-FFE x capacity)                                  (Target 3.4)
  * canal cost = traversals of the closed rotation x class fee                                        (Target 3.5)
  * revenue, rejected-demand penalty (1000 USD/FFE), handling and transshipment from the logged flows (Targets 3.4, 3.6)
  * the objective identity of the log's summary block

No value is taken from the log except what is being checked against it (each comparison prints both numbers).
"""
import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

LOG, OUT = Path(sys.argv[1]), Path(sys.argv[2])
RAW = Path(__file__).resolve().parents[3] / "data" / "raw" / "WorldSmall"
FUEL_PRICE_LOG = 600.0                      # printed by the log itself: "Total bunker cost at 600 USD"
REJECT_PENALTY = 1000.0

ports = pd.read_csv(RAW / "ports.csv", sep="\t").set_index("UNLocode")
dist = pd.read_csv(RAW / "dist_dense.csv", sep="\t")
D = {(r.fromUNLOCODe, r.ToUNLOCODE): (float(r.Distance), int(r.IsPanama), int(r.IsSuez)) for r in dist.itertuples()}
fleet = pd.read_csv(RAW / "fleet_data.csv", sep="\t").set_index("Capacity FFE")
dem = pd.read_csv(RAW / "Demand_WorldSmall_Fixed_Sep.csv", sep="\t")
REV = {(r.Origin, r.Destination): float(r.Revenue_1) for r in dem.itertuples()}
QTY = {(r.Origin, r.Destination): float(r.FFEPerWeek) for r in dem.itertuples()}

text = LOG.read_text(encoding="utf8", errors="replace")
head, _, tail = text.partition("service 0 service id 0")
blocks = re.split(r"\nservice \d+ service id (\d+)\n", "\nservice 0 service id 0\n" + tail.lstrip("\n"))
# blocks: [pre, id0, body0, id1, body1, ...]  (the first element is the leading "service 0 ..." marker)
services = {}
for i in range(1, len(blocks), 2):
    sid, body = int(blocks[i]), blocks[i + 1]
    body = body.split("\nID:")[0] if "\nID:" in body else body
    cap = int(re.search(r"capacity (\d+)", body).group(1))
    nves = int(re.search(r"# vessels (\d+)", body).group(1))
    pts = re.findall(r"^\d+\t(\w+)\t", body, flags=re.M)

    def num(label):
        m = re.search(label + r"\s+([\d.e+-]+)", body)
        return float(m.group(1)) if m else 0.0

    services[sid] = {"cap": cap, "vessels": nves, "ports": pts, "speed": num(r"speed"), "dist": num(r"voyage distance nautical miles"),
                     "weeks": num(r"voyage duration in weeks"), "port_call": num(r"Port call cost"), "idle_t": num(r"Bunker idle burn in Ton"),
                     "fuel_t": num(r"Bunker fuel burn in Ton"), "bunker_usd": num(r"Total bunker cost at 600 USD for one round trip"),
                     "tc": num(r"Total TC cost"), "canal_log": num(r"Canal Cost"),
                     "pan_log": int(num(r"Panama canal traversed")), "sue_log": int(num(r"Suez canal traversed"))}

summ = {}
for key, pat in {"objective": r"Objective value: ([\d.e+-]+)", "vessel_class_cost": r"Vessel Class cost: ([\d.e+-]+)",
                 "idle_burn_cost": r"Bunker idle burn cost: ([\d.e+-]+)", "fuel_burn": r"fuel_burn: ([\d.e+-]+)",
                 "port_call": r"Port Call Cost: ([\d.e+-]+)", "canal": r"Canal costs ([\d.e+-]+)", "revenue": r"Revenue: ([\d.e+-]+)",
                 "penalty": r"Penalty: ([\d.e+-]+)", "handling": r"Handling cost: ([\d.e+-]+)"}.items():
    summ[key] = float(re.search(pat, text).group(1))

# ---- per-service checks --------------------------------------------------------------------------------------------
svc_rows = []
for sid, s in sorted(services.items()):
    f = fleet.loc[s["cap"]]
    pts = s["ports"]
    legs = list(zip(pts, pts[1:] + pts[:1]))
    nm = sum(D[l][0] for l in legs)
    ds, fs, fi = float(f["designSpeed"]), float(f["Bunker ton per day at designSpeed"]), float(f["Idle Consumption ton/day"])
    sea_days = nm / (24.0 * s["speed"])
    fuel_t = sea_days * fs * (s["speed"] / ds) ** 3               # cubic law (derived; checked below against every service)
    idle_t = len(pts) * 1.0 * fi                                  # 1 day per port call
    pc = sum(float(ports.loc[p, "PortCallCostFixed"]) + float(ports.loc[p, "PortCallCostPerFFE"]) * s["cap"] for p in pts)
    pan = sum(D[l][1] for l in legs)
    sue = sum(D[l][2] for l in legs)
    pf = f["panamaFee"]
    canal = (0.0 if pd.isna(pf) else pan * float(pf)) + sue * float(f["suezFee"])
    tc = s["vessels"] * float(f["TC rate daily (fixed Cost)"]) * 7.0
    svc_rows.append({"service": sid, "cap": s["cap"], "distance_nm": nm, "distance_log": s["dist"], "sea_days": sea_days,
                     "fuel_t": fuel_t, "fuel_t_log": s["fuel_t"], "idle_t": idle_t, "idle_t_log": s["idle_t"],
                     "bunker_usd": (fuel_t + idle_t) * FUEL_PRICE_LOG, "bunker_usd_log": s["bunker_usd"],
                     "port_call": pc, "port_call_log": s["port_call"], "canal": canal, "canal_log": s["canal_log"],
                     "pan": pan, "pan_log": s["pan_log"], "sue": sue, "sue_log": s["sue_log"],
                     "tc": tc, "tc_log": s["tc"], "vessels": s["vessels"]})
sv = pd.DataFrame(svc_rows)


def worst(a, b):
    d = (sv[a] - sv[b]).abs()
    return {"max_abs_diff": float(d.max()), "max_rel_diff": float((d / sv[b].abs().clip(lower=1e-9)).max())}


checks = {"distance_nm": worst("distance_nm", "distance_log"), "sailing_fuel_t": worst("fuel_t", "fuel_t_log"),
          "idle_fuel_t": worst("idle_t", "idle_t_log"), "bunker_usd_at_600": worst("bunker_usd", "bunker_usd_log"),
          "port_call_usd": worst("port_call", "port_call_log"), "canal_usd": worst("canal", "canal_log"),
          "time_charter_usd_week": worst("tc", "tc_log"),
          "traversal_counts_equal": int(((sv.pan == sv.pan_log) & (sv.sue == sv.sue_log)).sum())}
totals_services = {"vessel_class_cost": float(sv.tc.sum()), "port_call": float(sv.port_call.sum()), "canal": float(sv.canal.sum()),
                   "fuel_burn_usd": float(sv.fuel_t.sum() * FUEL_PRICE_LOG), "idle_burn_usd": float(sv.idle_t.sum() * FUEL_PRICE_LOG)}

# ---- flows: revenue, handling, transshipment, penalty ---------------------------------------------------------------
flows = []
cur = None
for line in text.splitlines():
    m = re.match(r"ID:(\d+) (\w+)->(\w+) Transported ([\d.e+-]+), trans in %: ([\d.e+-]+)", line)
    if m:
        cur = {"id": int(m.group(1)), "o": m.group(2), "d": m.group(3), "q": float(m.group(4)), "path": []}
        flows.append(cur)
        continue
    m = re.match(r"ID:(\d+) (\w+)->(\w+) Rejected ([\d.e+-]+)", line)
    if m:
        cur = None
        continue
    if cur is not None:
        m = re.match(r"\s*(?:Path )?(\w+?)_(\d+)->(\w+?)_(\d+)\s*$", line)
        if m:
            cur["path"].append((m.group(1), int(m.group(2)), m.group(3)))
rej = [(m.group(2), m.group(3), float(m.group(4))) for m in re.finditer(r"ID:(\d+) (\w+)->(\w+) Rejected ([\d.e+-]+)", text)]
revenue = sum(f["q"] * REV[(f["o"], f["d"])] for f in flows)
penalty = REJECT_PENALTY * sum(r[2] for r in rej)


def transfer_ports(f):
    """Ports where the logged path changes service (the destination of one hop equals the origin of the next)."""
    out = []
    for h1, h2 in zip(f["path"], f["path"][1:]):
        if h1[2] == h2[0] and h1[1] != h2[1]:
            out.append(h1[2])
    return out


def handling_of(f):
    return f["q"] * (float(ports.loc[f["o"], "CostPerFULL"]) + float(ports.loc[f["d"], "CostPerFULL"])
                     + sum(float(ports.loc[p, "CostPerFULLTrnsf"]) for p in transfer_ports(f)))


handling_total = sum(handling_of(f) for f in flows)
n_transfers = sum(len(transfer_ports(f)) for f in flows)
transfer_cost_only = sum(f["q"] * sum(float(ports.loc[p, "CostPerFULLTrnsf"]) for p in transfer_ports(f)) for f in flows)
served = sum(f["q"] for f in flows)
rej_ffe = sum(r[2] for r in rej)
objective_from_recomputed = (revenue - penalty - handling_total - totals_services["vessel_class_cost"] - totals_services["port_call"]
                             - totals_services["canal"] - totals_services["fuel_burn_usd"] - totals_services["idle_burn_usd"])
objective_from_log_terms = (summ["revenue"] - summ["penalty"] - summ["handling"] - summ["vessel_class_cost"] - summ["port_call"]
                            - summ["canal"] - summ["fuel_burn"] - summ["idle_burn_cost"])
demand_total = sum(QTY.values())
res = {
    "log": str(LOG), "services": len(services), "flows": len(flows), "rejected_demands": len(rej),
    "service_level_checks": checks, "log_summary": summ,
    "recomputed_totals": {**totals_services, "revenue": revenue, "penalty": penalty, "handling_incl_transshipment": handling_total,
                          "transshipment_part": transfer_cost_only, "transfers_counted": n_transfers, "served_ffe": served,
                          "rejected_ffe": rej_ffe, "demand_ffe_file": demand_total, "served_plus_rejected": served + rej_ffe},
    "objective": {"recomputed_from_raw_files_and_logged_flows": objective_from_recomputed, "from_log_terms": objective_from_log_terms,
                  "log_objective_line": summ["objective"]},
    "term_vs_log": {k: {"recomputed": v, "log": summ[l], "diff": v - summ[l], "rel": (v - summ[l]) / summ[l] if summ[l] else None}
                    for k, (v, l) in {"vessel_class_cost": (totals_services["vessel_class_cost"], "vessel_class_cost"),
                                      "port_call": (totals_services["port_call"], "port_call"), "canal": (totals_services["canal"], "canal"),
                                      "fuel_burn": (totals_services["fuel_burn_usd"], "fuel_burn"),
                                      "idle_burn": (totals_services["idle_burn_usd"], "idle_burn_cost"),
                                      "revenue": (revenue, "revenue"), "penalty": (penalty, "penalty"),
                                      "handling": (handling_total, "handling")}.items()},
    "per_service": svc_rows,
}
OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps({"checks": checks, "term_vs_log": res["term_vs_log"], "objective": res["objective"],
                  "flows": len(flows), "rej": len(rej), "served_ffe": served, "rejected_ffe": rej_ffe}, indent=1))
