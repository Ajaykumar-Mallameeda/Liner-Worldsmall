"""Run the orchestrator once and pickle the exact inputs of every global-stage call.

usage: python capture_global_inputs.py <project_root> <out_pickle>

The wrapper only records; it calls the real ``reconcile`` unchanged, so the run is the
production pipeline. The pickle lets the global stage be replayed offline with different
solver settings on IDENTICAL candidate pools (the pipeline itself is not seeded).
"""
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
sys.path.insert(0, str(ROOT))

import src.agents.orchestrator_agent as oa                       # noqa: E402
from src.data.network_loader import NetworkLoader                # noqa: E402
from src.optimization.data import Problem                        # noqa: E402

captured = []
_real = oa.reconcile_global_network


def _wrap(problem, pools, region_of_od, region_names, **kw):
    captured.append({"pools": {k: [dict(c) for c in v] for k, v in pools.items()},
                     "region_of_od": dict(region_of_od), "region_names": list(region_names),
                     "kw": {k: v for k, v in kw.items()}})
    return _real(problem, pools, region_of_od, region_names, **kw)


oa.reconcile_global_network = _wrap

ws = ROOT / "data" / "raw" / "WorldSmall"
loader = NetworkLoader()
ports = loader.load_ports(ws / "ports.csv")
demands = loader.load_demands(ws / "Demand_WorldSmall_Fixed_Sep.csv")
dist = loader.load_distance_matrix(ws / "dist_dense.csv")
fleet = loader.load_fleet(ws / "fleet_WorldSmall.csv", ws / "fleet_data.csv")
for p in ports:
    dist.setdefault(p.id, {})
problem = Problem(ports=ports, services=[], demands=demands, distance_matrix=dist, fleet=fleet)

t0 = time.perf_counter()
res = oa.OrchestratorAgent().process({"problem": problem})
print("elapsed", round(time.perf_counter() - t0, 1), "status", res.get("status"),
      "profit", res["summary_metrics"].get("weekly_profit"))
OUT.write_bytes(pickle.dumps({"captured": captured, "final_profit": res["summary_metrics"].get("weekly_profit")}))
print("captured calls:", len(captured), "->", OUT)
