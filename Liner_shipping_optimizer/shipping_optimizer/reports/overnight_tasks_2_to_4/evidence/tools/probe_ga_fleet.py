import math, random, sys, time, json
import numpy as np
from src.data.network_loader import NetworkLoader
from src.optimization.data import Problem
from src.agents.service_generator_agent import ServiceGeneratorAgent
from src.agents.regional_agent import RegionalAgent
from src.optimization.adaptive_budget import (AdaptiveBudget, compute_complexity_signals,
    get_service_ga_params)
from src.optimization.hierarchical_ga import HierarchicalGA

L = NetworkLoader(); net = L.load_network(); fleet = L.load_fleet()
p = Problem(ports=net["ports"], services=[], demands=net["demands"],
            distance_matrix=net["distance_matrix"], fleet=fleet)
random.seed(7); np.random.seed(7)
p.services = ServiceGeneratorAgent(name="probe", model="none").generate_services(p)
cs = compute_complexity_signals(num_ports=len(p.ports), demands=p.demands, fleet=p.fleet)
ab = AdaptiveBudget.from_signals(cs)
ra = RegionalAgent(name="probe", region="all", model="none")
p = ra._filter_services(p, ab)
print("filtered pool:", len(p.services), "fleet:", p.fleet.total_vessels)
sga = get_service_ga_params(ab)
t0 = time.time()
ga = HierarchicalGA(p, pop_size=sga["pop_size"], generations=sga["generations"],
                    max_runtime_sec=30.0, objective_mode="profit_first")
ch = ga.run()
print(f"GA done in {time.time()-t0:.0f}s")
mask, freq = ch["services"], ch["frequencies"]
sel = [i for i, v in enumerate(mask) if v == 1]
zero_sel = [i for i in sel if i >= len(freq) or freq[i] <= 0]
def need(i, f): return math.ceil(p.services[i].cycle_time * f / 7)
v_exact = sum(need(i, freq[i]) for i in sel if i < len(freq) and freq[i] > 0)
v_max1  = sum(need(i, max(1, round(freq[i]) if i < len(freq) else 1)) for i in sel)
print(json.dumps({
  "selected": len(sel), "selected_with_zero_frequency": len(zero_sel),
  "frequency_histogram": {str(k): freq.count(k) for k in sorted(set(freq))},
  "vessels_exact_zero_means_zero": v_exact, "vessels_with_max1_rounding(hub_milp)": v_max1,
  "fleet_size": p.fleet.total_vessels,
  "milp_would_crash": v_max1 > p.fleet.total_vessels,
}, indent=1))
