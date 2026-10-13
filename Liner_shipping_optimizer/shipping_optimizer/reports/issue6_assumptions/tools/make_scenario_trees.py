"""Build scratch copies of the tree (src + WorldSmall data only) with exactly ONE assumption changed each.
The production tree is never touched.  usage: make_scenario_trees.py <out_dir>"""
import csv
import re
import shutil
import sys
from pathlib import Path

PROJ = Path(r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer")
OUT = Path(sys.argv[1])
REV = Path(r"C:\Users\WINDOWS\Downloads\LINERLIB-master (1)\LINERLIB-master\data\transittime_revision\Demand_WorldSmall_tt.csv")


def base(name):
    d = OUT / name
    if d.exists():
        raise SystemExit(f"{d} exists - choose a new directory")
    shutil.copytree(PROJ / "src", d / "src", ignore=shutil.ignore_patterns("__pycache__"))
    (d / "data" / "raw").mkdir(parents=True)
    shutil.copytree(PROJ / "data" / "raw" / "WorldSmall", d / "data" / "raw" / "WorldSmall")
    return d


def edit(path, old, new, count=1):
    s = path.read_text(encoding="utf-8")
    assert s.count(old) == count, (path, old, s.count(old))
    path.write_text(s.replace(old, new), encoding="utf-8")


# 1 revised transit times: keep the canonical Fixed_Sep quantities / revenues, take TransitTime from the upstream revision
d = base("T_rev")
rev = {}
with REV.open(encoding="utf-8-sig") as fh:
    for r in csv.DictReader(fh, delimiter="\t"):
        rev[(r["Origin"].strip(), r["Destination"].strip())] = r["TransitTime"].strip()
p = d / "data" / "raw" / "WorldSmall" / "Demand_WorldSmall_Fixed_Sep.csv"
rows = list(csv.reader(p.open(encoding="utf-8-sig"), delimiter="\t"))
hdr = rows[0]
ti = hdr.index("TransitTime")
changed = 0
for r in rows[1:]:
    k = (r[0].strip(), r[1].strip())
    if k in rev and rev[k] != r[ti].strip():
        r[ti] = rev[k]
        changed += 1
with p.open("w", encoding="utf-8", newline="") as fh:
    csv.writer(fh, delimiter="\t", lineterminator="\n").writerows(rows)
print("T_rev: TransitTime changed on", changed, "ODs")

econ = lambda d: d / "src" / "network" / "economics.py"
d = base("T_dwell175"); edit(econ(d), "transfer_wait_days: float = 3.5", "transfer_wait_days: float = 1.75")
d = base("T_dwell70"); edit(econ(d), "transfer_wait_days: float = 3.5", "transfer_wait_days: float = 7.0")
d = base("T_stay12"); edit(econ(d), "port_stay_hours: float = 24.0", "port_stay_hours: float = 12.0")
d = base("T_stay48"); edit(econ(d), "port_stay_hours: float = 24.0", "port_stay_hours: float = 48.0")
# port cost columns read as USD per TEU instead of per FFE (no division)
d = base("T_costTEU")
ld = d / "src" / "data" / "network_loader.py"
s = ld.read_text(encoding="utf-8")
n = len(re.findall(r"/ TEU_PER_FFE", s))
s = s.replace("/ TEU_PER_FFE", "/ 1.0")
ld.write_text(s, encoding="utf-8")
print("T_costTEU: divisions removed:", n)
