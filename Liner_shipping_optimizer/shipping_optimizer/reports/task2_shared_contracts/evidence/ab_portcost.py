"""A/B: does the port-cost unit basis change what ServiceGA selects?

Same candidates, same seeds, same GA parameters. Only Port cost fields differ:
  basis "div2": loader as corrected (per-FFE / 2)
  basis "x2"  : legacy (per-FFE * 2) == corrected * 4
Read-only with respect to the project.
"""
import copy
import os
import random
import sys
import time

import numpy as np

sys.path.insert(0, os.getcwd())
from src.data.network_loader import NetworkLoader   # noqa: E402
from src.optimization.data import Problem, Service   # noqa: E402
from src.optimization.service_ga import ServiceGA    # noqa: E402
from src.agents.service_generator_agent import ServiceGeneratorAgent   # noqa: E402
from src.utils.fuel_cost import map_capacity_to_vessel_class, calculate_weekly_fuel_cost   # noqa: E402

ld = NetworkLoader()
net = ld.load_network()
fleet = ld.load_fleet()


def mk_problem(port_scale):
    ports = copy.deepcopy(net["ports"])
    for p in ports:
        p.handling_cost *= port_scale
        p.transshipment_cost *= port_scale
        p.variable_port_call_cost *= port_scale
    return Problem(ports=ports, services=[], demands=net["demands"],
                   distance_matrix=net["distance_matrix"], fleet=fleet)


random.seed(7)
np.random.seed(7)
gen_problem = mk_problem(1.0)
raw = ServiceGeneratorAgent(name="ab", model="none").generate_services(gen_problem)
services = []
for i, s in enumerate(raw):
    if isinstance(s, Service):
        services.append(s)
    else:
        cap = s.get("capacity", 5000)
        services.append(Service(id=i, ports=s["ports"], capacity=cap,
                                weekly_cost=s.get("weekly_cost", 150_000),
                                cycle_time=s.get("cycle_time", 14),
                                vessel_class=s.get("vessel_class", map_capacity_to_vessel_class(cap))))
print("candidates:", len(services))

results = {}
for basis, scale in (("div2 (corrected)", 1.0), ("x2 (legacy)", 4.0)):
    for seed in (1, 2, 3):
        pb = mk_problem(scale)
        pb.services = services
        random.seed(seed)
        np.random.seed(seed)
        t0 = time.time()
        ga = ServiceGA(pb, generations=40, alpha_unserved=300.0, transship_cost_per_teu=80.0,
                       port_cost_per_teu=0.0, objective_mode="profit_first")
        sol = ga.run()
        sel = [i for i, v in enumerate(sol) if v == 1]
        fuel = sum(calculate_weekly_fuel_cost(services[i].ports, net["distance_matrix"],
                                              services[i].vessel_class or "Post_panamax",
                                              services[i].cycle_time or 7) for i in sel)
        results.setdefault(basis, []).append((len(sel), fuel, time.time() - t0))
        print(f"{basis:18s} seed={seed} selected={len(sel):4d} fuel/wk=${fuel/1e6:8.1f}M  ({time.time()-t0:4.0f}s)", flush=True)

print()
for basis, rows in results.items():
    n = [r[0] for r in rows]
    f = [r[1] / 1e6 for r in rows]
    print(f"{basis:18s} selected mean={sum(n)/len(n):6.1f} (min {min(n)}, max {max(n)})   fuel mean=${sum(f)/len(f):7.1f}M")
