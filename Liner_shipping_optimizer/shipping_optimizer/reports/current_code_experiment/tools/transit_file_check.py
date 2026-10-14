"""Workstream C: hash + compare canonical and revised transit files; test the upstream statement
"revised where a direct sailing at 14 knots is not possible within the allowed transit time" against dist_dense.csv.
Direct sailing days = distance_nm / (14 kn x 24 h).  Read-only."""
import csv, hashlib, json
from pathlib import Path
P = Path(__file__).resolve().parents[3]
R = P / "data" / "raw" / "WorldSmall"; S = P / "data" / "scenarios" / "WorldSmall_revised_transit_v1"
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"))
can = rd(R / "Demand_WorldSmall_Fixed_Sep.csv"); rev = rd(S / "Demand_WorldSmall_Fixed_Sep_revised_tt.csv")
dist = {(r["fromUNLOCODe"], r["ToUNLOCODE"]): float(r["Distance"]) for r in rd(R / "dist_dense.csv")}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
key = lambda r: (r["Origin"], r["Destination"])
cm = {key(r): r for r in can}; rm = {key(r): r for r in rev}
assert set(cm) == set(rm), "OD sets differ"
changed = [k for k in cm if cm[k]["TransitTime"] != rm[k]["TransitTime"]]
other = [k for k in cm if any(cm[k][c] != rm[k][c] for c in ("FFEPerWeek", "Revenue_1"))]
def direct(k): return dist.get(k, dist.get((k[1], k[0])))/ (14 * 24) if dist.get(k, dist.get((k[1], k[0]))) else None
rows = []
for k in changed:
    d = direct(k); c, v = float(cm[k]["TransitTime"]), float(rm[k]["TransitTime"])
    rows.append({"od": "-".join(k), "canon": c, "revised": v, "direct_days_14kn": d, "canon_below_direct": (d is not None and c < d), "revised_ge_direct": (d is not None and v >= d),
                 "ffe": float(cm[k]["FFEPerWeek"])})
unchanged_below = [k for k in cm if k not in changed and direct(k) and float(cm[k]["TransitTime"]) < direct(k)]
out = {"canonical_sha256": sha(R / "Demand_WorldSmall_Fixed_Sep.csv"), "revised_sha256": sha(S / "Demand_WorldSmall_Fixed_Sep_revised_tt.csv"),
       "ods": len(cm), "ods_changed": len(changed), "ods_with_quantity_or_revenue_change": len(other),
       "changed_demand_ffe": sum(r["ffe"] for r in rows), "total_demand_ffe": sum(float(r["FFEPerWeek"]) for r in can),
       "changed_loosened": sum(r["revised"] > r["canon"] for r in rows), "changed_tightened": sum(r["revised"] < r["canon"] for r in rows),
       "mean_change_days": sum(r["revised"] - r["canon"] for r in rows) / len(rows),
       "canon_below_direct_among_changed": sum(r["canon_below_direct"] for r in rows), "revised_ge_direct_among_changed": sum(r["revised_ge_direct"] for r in rows),
       "unchanged_ods_with_canon_below_direct": len(unchanged_below), "unchanged_below_direct_ffe": sum(float(cm[k]["FFEPerWeek"]) for k in unchanged_below),
       "missing_values": sum(1 for r in can for c in ("FFEPerWeek", "Revenue_1", "TransitTime") if r[c] in ("", None))}
Path(__file__).with_name("transit_file_check.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
