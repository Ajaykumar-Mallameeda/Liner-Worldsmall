"""Dump what NetworkLoader produces from the canonical WorldSmall files, as JSON.

usage: python dump_loaded.py <tree_dir> <out.json>
Uses exactly the calls tests/test_orchestrator.py::load_worldsmall_problem makes.
"""
import dataclasses
import json
import sys
from pathlib import Path

tree = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(tree))

from src.data.network_loader import NetworkLoader  # noqa: E402

ws = tree / "data" / "raw" / "WorldSmall"
loader = NetworkLoader()
ports = loader.load_ports(ws / "ports.csv")
demands = loader.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
dist = loader.load_distance_matrix(ws / "dist_dense.csv")
fleet = loader.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")


def d(o):
    return dataclasses.asdict(o) if dataclasses.is_dataclass(o) else vars(o)


out = {
    "ports": {p.id: d(p) for p in ports},
    "demands": {f"{x.origin}->{x.destination}": d(x) for x in demands},
    "dist": dist,
    "fleet": {c.vessel_class: d(c) for c in fleet.classes},
    "src_file": str(Path(sys.modules["src.data.network_loader"].__file__)),
}
Path(sys.argv[2]).write_text(json.dumps(out, indent=1, sort_keys=True, default=str), encoding="utf-8")
print("dumped", len(ports), "ports", len(demands), "demands", sum(len(v) for v in dist.values()), "pairs",
      len(fleet.classes), "classes from", out["src_file"])
