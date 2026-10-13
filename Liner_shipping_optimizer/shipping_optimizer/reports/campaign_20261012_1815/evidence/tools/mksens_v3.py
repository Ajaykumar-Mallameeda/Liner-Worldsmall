"""Create SENSITIVITY copies of a snapshot (hypothetical scenarios; never production).

usage: python -I mksens.py <base_snapshot_dir> <revised_demand_csv>
Each scenario is a NEW directory D:/liner_scratch/snap_S3_<label>/ (third generation: built from the final snapshot T9) (copy of the base snapshot with ONE
documented edit).  Nothing in the project tree is touched; nothing is deleted or overwritten.

  S1_tt      TransitTime column of Demand_WorldSmall_Fixed_Sep.csv replaced by the upstream LINERLIB revision
             (data/transittime_revision/Demand_WorldSmall_tt.csv); quantities / revenues stay those of the
             project's file (the upstream revised file still carries the truncated demands)
  S2_cap2    "Capacity FFE" of every vessel class x 2   (hypothesis: the column is FFE and TEU = 2 x FFE)
  S3a_port12 / S3b_port48   port stay 12 h / 48 h (model assumption: 24 h)
  S4a_dwell  / S4b_dwell    expected transfer wait 1.75 d / 7.0 d (model assumption: 3.5 d)
"""
import csv
import shutil
import sys
from pathlib import Path

BASE = Path(sys.argv[1])
REV = Path(sys.argv[2])
ROOT = Path(r"D:\liner_scratch")


def fresh(label):
    dst = ROOT / f"snap_S3_{label}"
    if dst.exists():
        raise SystemExit(f"{dst} exists (not overwriting)")
    shutil.copytree(BASE, dst)
    return dst


def edit(path: Path, old: str, new: str, count: int = 1):
    s = path.read_text(encoding="utf-8")
    assert s.count(old) == count, (path, s.count(old), old)
    path.write_text(s.replace(old, new), encoding="utf-8")


# S1: revised transit times
d = fresh("S1_tt")
cur = d / "data/raw/WorldSmall/Demand_WorldSmall_Fixed_Sep.csv"
rev = {}
with open(REV, newline="", encoding="utf-8") as fh:
    for r in csv.DictReader(fh, delimiter="\t"):
        rev[(r["Origin"], r["Destination"])] = r["TransitTime"]
rows = []
with open(cur, newline="", encoding="utf-8") as fh:
    rd = csv.DictReader(fh, delimiter="\t")
    names = rd.fieldnames
    for r in rd:
        r["TransitTime"] = rev[(r["Origin"], r["Destination"])]
        rows.append(r)
with open(cur, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=names, delimiter="\t", lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
print("S1_tt written:", d)

# S2: vessel capacity x 2
d = fresh("S2_cap2")
for name in ("fleet_data.csv",):
    p = d / "data/raw/WorldSmall" / name
    rows, names = [], None
    with open(p, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh, delimiter="\t")
        names = rd.fieldnames
        for r in rd:
            r["Capacity FFE"] = str(float(r["Capacity FFE"]) * 2)
            rows.append(r)
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=names, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
print("S2_cap2 written:", d)

# S3: port stay
for label, hours in (("S3a_port12", "12.0"), ("S3b_port48", "48.0")):
    d = fresh(label)
    edit(d / "src/network/economics.py", "    port_stay_hours: float = 24.0\n", f"    port_stay_hours: float = {hours}\n")
    edit(d / "src/services/service_feasibility.py", "    port_stay_hours: float = 24.0\n", f"    port_stay_hours: float = {hours}\n")
    print(label, "written:", d)

# S4: expected transfer wait
for label, days in (("S4a_dwell", "1.75"), ("S4b_dwell", "7.0")):
    d = fresh(label)
    edit(d / "src/network/economics.py", "    transfer_wait_days: float = 3.5\n", f"    transfer_wait_days: float = {days}\n")
    print(label, "written:", d)
