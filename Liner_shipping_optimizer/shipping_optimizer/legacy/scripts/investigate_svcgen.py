"""Investigate why service generator still uses defaults despite fix."""
import sys, json
sys.path.insert(0, ".")

from src.agents.service_generator_agent import ServiceGeneratorAgent
from src.optimization.data import Problem, Port, Demand
from src.llm.client import llm_client
import time

# Create a minimal problem
ports = [Port(id=i, name=f"Port_{i}", handling_cost=100,
              port_call_cost=10000, variable_port_call_cost=50,
              transshipment_cost=200, x=0, y=0) for i in range(20)]

demands = [Demand(origin=0, destination=1, weekly_teu=5000, revenue_per_teu=2000),
           Demand(origin=1, destination=2, weekly_teu=3000, revenue_per_teu=2000),
           Demand(origin=2, destination=3, weekly_teu=1000, revenue_per_teu=2000),
           Demand(origin=0, destination=3, weekly_teu=2000, revenue_per_teu=2000)]

problem = Problem(ports=ports, services=[], demands=demands, distance_matrix={})

# Create service gen agent
svc = ServiceGeneratorAgent("test_svc", "opencode/deepseek-v4-flash-free")

# Clear singleton state
llm_client.cache = {}
llm_client.total_calls = 0
llm_client.failure_count = 0

print("Calling ServiceGeneratorAgent.process()...")
t0 = time.time()
try:
    result = svc.process({"problem": problem})
    elapsed = time.time() - t0
    print(f"  Time: {elapsed:.1f}s")
    ap = result.get("archetype_params", {})
    arch = ap.get("archetype_mix", {}) if isinstance(ap, dict) else {}
    print(f"  Archetype mix: {arch}")
    is_default = arch.get("direct_ratio") == 0.60 and arch.get("hub_loop_ratio") == 0.15
    print(f"  Is default: {is_default}")
    print(f"  Strategy: {result.get('strategy', '')[:200]}")
    print(f"  Services generated: {result.get('services_generated', 0)}")
    print(f"  Metrics: {svc._metrics}")
except Exception as e:
    elapsed = time.time() - t0
    print(f"  ERROR ({elapsed:.1f}s): {str(e)[:500]}")
