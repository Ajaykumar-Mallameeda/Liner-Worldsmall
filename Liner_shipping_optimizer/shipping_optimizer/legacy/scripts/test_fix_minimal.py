"""Minimal pipeline test to verify P+1E fix works end-to-end."""
import sys, json, time
sys.path.insert(0, ".")

from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.service_generator_agent import ServiceGeneratorAgent
from src.llm.client import llm_client
from src.optimization.data import Problem

# Reset singletons
llm_client.cache = {}
llm_client.total_calls = 0
llm_client.failure_count = 0

# ====================================
# TEST 1: Coordinator through full path
# ====================================
print("=" * 60)
print("TEST 1: Coordinator _generate_decisions()")
print("=" * 60)

coord = CoordinatorAgent()

regional_solutions = [
    {"region": "Asia", "coverage_percent": 74.1, "weekly_profit": 48010846, "operating_cost": 33045000, "services_selected": 102},
    {"region": "Europe", "coverage_percent": 55.8, "weekly_profit": 35000000, "operating_cost": 28000000, "services_selected": 85},
    {"region": "Americas", "coverage_percent": 36.3, "weekly_profit": 42000000, "operating_cost": 31000000, "services_selected": 90},
]

metrics = coord._calculate_global_metrics(regional_solutions)
evaluation = coord._evaluate_system(metrics, [])

t0 = time.time()
decisions = coord._generate_decisions([], regional_solutions, metrics, evaluation)
elapsed = time.time() - t0

print(f"  Time: {elapsed:.1f}s")
notes = decisions.get("notes", "")
is_ai = "Rule-based fallback" not in notes
print(f"  Is AI-generated: {is_ai}")
print(f"  Notes: {notes[:150]}")
print(f"  Weights: {decisions.get('weight_adjustments', {})}")
print(f"  Actions: {decisions.get('actions', [])}")

# ====================================
# TEST 2: Service Gen needs a real Problem
# Let's check what LLM returns for the exact prompt
# ====================================
print()
print("=" * 60)
print("TEST 2: Service Gen JSON prompt through call_llm")
print("=" * 60)

svc_system = "You are a liner shipping service design specialist. Advise on service archetypes."
svc_prompt = (
    'Liner shipping service design for 333-port network.\n\n'
    'NETWORK STATS:\n'
    '  Ports: 333, Lanes: 9622, Median demand/lane: 60.0 TEU\n'
    '  Total demand: 1,666,738 TEU\n\n'
    'ARCHETYPE: HYBRID\n\n'
    'Return ONLY valid JSON (no markdown, no preamble):\n'
    '{"direct_ratio": <0.05-0.80>, "hub_loop_ratio": <0.05-0.80>, '
    '"feeder_ratio": <0.05-0.80>, "trunk_ratio": <0.05-0.80>, '
    '"vessel_bias": "small"|"balanced"|"large", '
    '"hub_focus": ["PORT_ID", ...], '
    '"notes": "<brief rationale>"}'
)

# Call through BaseAgent.call_llm (which is what ServiceGeneratorAgent uses)
from src.agents.base import BaseAgent

class MockSvcAgent(BaseAgent):
    def get_system_prompt(self):
        return svc_system

mock_svc = MockSvcAgent("mock_svc", "test", "opencode/deepseek-v4-flash-free")
llm_client.cache = {}

t0 = time.time()
result = mock_svc.call_llm(svc_prompt, temperature=0.1)
elapsed = time.time() - t0

print(f"  Time: {elapsed:.1f}s")
print(f"  Result len: {len(result)} chars")
try:
    j = json.loads(result)
    print(f"  VALID JSON: keys={list(j.keys())}")
    print(f"  Ratios: direct={j.get('direct_ratio')}, hub={j.get('hub_loop_ratio')}, feeder={j.get('feeder_ratio')}, trunk={j.get('trunk_ratio')}")
    print(f"  Vessel bias: {j.get('vessel_bias')}")
except:
    is_hf = result == "Service temporarily unavailable. Using default optimization parameters."
    print(f"  NOT JSON. Hard fallback: {is_hf}")
    print(f"  Content: {result[:300]}")

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  Coordinator AI: {is_ai}")
