"""Scratch scenario trees (src + WorldSmall data) copied from a frozen commit tree, ONE value changed each.
usage: make_trees.py <frozen_tree_root> <out_dir>"""
import shutil
import sys
from pathlib import Path

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
PROJ = Path(r"C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer")
REV = PROJ / "data" / "scenarios" / "WorldSmall_revised_transit_v1" / "Demand_WorldSmall_Fixed_Sep_revised_tt.csv"


def base(name):
    d = OUT / name
    if d.exists():
        raise SystemExit(f"{d} exists")
    shutil.copytree(SRC / "src", d / "src", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(SRC / "data", d / "data")
    return d


def edit(path, old, new):
    s = path.read_text(encoding="utf-8")
    assert s.count(old) == 1, (path, old, s.count(old))
    path.write_text(s.replace(old, new), encoding="utf-8")


econ = lambda d: d / "src" / "network" / "economics.py"
d = base("T_rev")
shutil.copyfile(REV, d / "data" / "raw" / "WorldSmall" / "Demand_WorldSmall_Fixed_Sep.csv")
d = base("T_dwell175"); edit(econ(d), "transfer_wait_days: float = 3.5", "transfer_wait_days: float = 1.75")
d = base("T_dwell70"); edit(econ(d), "transfer_wait_days: float = 3.5", "transfer_wait_days: float = 7.0")
d = base("T_stay12"); edit(econ(d), "port_stay_hours: float = 24.0", "port_stay_hours: float = 12.0")
d = base("T_stay48"); edit(econ(d), "port_stay_hours: float = 24.0", "port_stay_hours: float = 48.0")
print("trees:", sorted(p.name for p in OUT.iterdir()))
