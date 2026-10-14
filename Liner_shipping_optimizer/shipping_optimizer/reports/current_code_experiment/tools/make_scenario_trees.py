"""Scenario trees (src + WorldSmall data) copied from the frozen tree, EXACTLY ONE value changed each.
usage: make_scenario_trees.py <frozen_tree_root> <out_dir>   (never overwrites: an existing tree aborts)
S_canal_off       canal fee charged as 0 (class passability / draft rules unchanged) - SENSITIVITY CONTROL only
S_handling_perTEU CostPerFULL and CostPerFULLTrnsf read as USD per TEU (loaded value, no /2) instead of per FFE
S_rev_transit     canonical demand file with the revised upstream TransitTime on the 105 changed ODs
S_stay12 / S_dwell175 (added later, tool arg 3 = "dwell_stay"): port_stay_hours 24 -> 12 ; transfer_wait_days 3.5 -> 1.75
"""
import shutil
import sys
from pathlib import Path

SRC, OUT = Path(sys.argv[1]), Path(sys.argv[2])
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


ONLY = sys.argv[3] if len(sys.argv) > 3 else "main"
econ = lambda d: d / "src" / "network" / "economics.py"
if ONLY == "canal2":
    # canal fee charged as 0 in BOTH the optimiser's service economics and the independent ledger (S_canal_off charged the
    # ledger but not the optimiser: a canal-blind optimiser, kept as a separate diagnostic called "canal-blind")
    d = base("S_canal_off2")
    edit(d / "src/network/physical_rules.py", "out.canal_fee_per_rotation += n * float(fee)", "out.canal_fee_per_rotation += 0.0 * n * float(fee)")
    edit(d / "src/network/ledger.py", "canal_fee += n_t * float(fee)", "canal_fee += 0.0 * n_t * float(fee)")
    print(sorted(p.name for p in OUT.iterdir())); raise SystemExit(0)
if ONLY == "dwell_stay":
    d = base("S_stay12"); edit(econ(d), "port_stay_hours: float = 24.0", "port_stay_hours: float = 12.0")
    d = base("S_dwell175"); edit(econ(d), "transfer_wait_days: float = 3.5", "transfer_wait_days: float = 1.75")
    print(sorted(p.name for p in OUT.iterdir())); raise SystemExit(0)
d = base("S_canal_off")
edit(d / "src/network/physical_rules.py", "out.canal_fee_per_rotation += n * float(fee)", "out.canal_fee_per_rotation += 0.0 * n * float(fee)")
d = base("S_handling_perTEU")
edit(d / "src/data/network_loader.py",
     '''handling_cost=_non_negative(row["costperfull"], src, "CostPerFULL", label)
                    / TEU_PER_FFE,''', '''handling_cost=_non_negative(row["costperfull"], src, "CostPerFULL", label),''')
edit(d / "src/data/network_loader.py",
     '''row["costperfulltrnsf"], src, "CostPerFULLTrnsf", label
                    ) / TEU_PER_FFE,''', '''row["costperfulltrnsf"], src, "CostPerFULLTrnsf", label
                    ),''')
d = base("S_rev_transit")
shutil.copyfile(REV, d / "data" / "raw" / "WorldSmall" / "Demand_WorldSmall_Fixed_Sep.csv")
print(sorted(p.name for p in OUT.iterdir()))
