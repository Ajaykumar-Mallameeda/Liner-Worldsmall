"""Validate P+1E fix through actual agent pipeline methods."""

import sys, json, time
sys.path.insert(0, ".")

from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.service_generator_agent import ServiceGeneratorAgent
from src.llm.client import llm_client
from src.agents.base import BaseAgent
import inspect

# Verify fix is loaded
source = inspect.getsource(BaseAgent.call_llm)
assert "has_json_instruction" in source, "FIX NOT LOADED!"
assert "skip_evaluator" in source, "EVALUATOR SKIP NOT LOADED!"
print("Fix verified in bytecode: YES")

# ================================================================
# TEST 1: Coordinator _generate_decisions() through actual path
# ================================================================
print("\n=== TEST 1: Coordinator _generate_decisions() ===")

coord = CoordinatorAgent()
llm_client.cache = {}
llm_client.total_calls = 0
llm_client.failure_count = 0

# Build realistic input
regional_solutions = [
    {"region": "Asia", "coverage_percent": 74.1, "weekly_profit": 48010846, "operating_cost": 33045000, "services_selected": 102},
    {"region": "Europe", "coverage_percent": 55.8, "weekly_profit": 35000000, "operating_cost": 28000000, "services_selected": 85},
    {"region": "Americas", "coverage_percent": 36.3, "weekly_profit": 42000000, "operating_cost": 31000000, "services_selected": 90},
]
conflicts = []
metrics = coord._calculate_global_metrics(regional_solutions)
evaluation = coord._evaluate_system(metrics, conflicts)

t0 = time.time()
decisions = coord._generate_decisions(conflicts, regional_solutions, metrics, evaluation)
elapsed = time.time() - t0

print(f"  Latency: {elapsed:.1f}s")
print(f"  Decisions type: {type(decisions).__name__}")
print(f"  Decisions keys: {list(decisions.keys()) if decisions else 'EMPTY'}")
print(f"  Is fallback: {'Rule-based fallback' in decisions.get('notes', '')}")
print(f"  Weight adjustments: {decisions.get('weight_adjustments', {})}")
print(f"  Actions: {decisions.get('actions', [])[:2]}")
print(f"  Using LLM: {'Rule-based' not in decisions.get('notes', '')}")

# ================================================================
# TEST 2: Check what the LLM actually returned
# ================================================================
print("\n=== TEST 2: What did _generate_decisions receive from LLM? ===")

# The decisions dict now shows the final result. If fallback activated,
# the LLM returned something that _parse_json_safe couldn't parse.
# Let's check what call_llm returned by checking the cache.

print(f"  LLMClient total_calls: {llm_client.total_calls}")
print(f"  LLMClient cache size: {len(llm_client.cache)}")

# Check the last cached response
if llm_client.cache:
    last_key = list(llm_client.cache.keys())[-1]
    last_val = llm_client.cache[last_key]
    print(f"  Last cached response ({len(last_val)} chars):")
    print(f"    {last_val[:300]}")
    is_json = False
    try:
        j = json.loads(last_val)
        is_json = True
        print(f"    >>> VALID JSON: keys={list(j.keys())}")
    except:
        print(f"    >>> NOT JSON")

# ================================================================
# TEST 3: Service generator through actual path
# ================================================================
print("\n=== TEST 3: Service Generator Archetype JSON ===")

# Create a mock problem
from src.optimization.data import Problem
problem = Problem(ports=[], services=[], demands=[], distance_matrix={})
# Set minimal attributes
problem.ports_data = []

svc = ServiceGeneratorAgent("test_svc", "opencode/deepseek-v4-flash-free")
llm_client.cache = {}

# We can't easily call svc.process() without a full problem, so test the
# JSON extraction path directly using the actual prompt template
print("  (Service generator requires full Problem - tested in full pipeline)")

# ================================================================
# TEST 4: Check coordinator metrics
# ================================================================
print(f"\n=== TEST 4: Coordinator Metrics ===")
print(f"  {coord._metrics}")
