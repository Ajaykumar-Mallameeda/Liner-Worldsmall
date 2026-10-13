"""Test coordinator after simulating pipeline state (5 prior LLM calls)."""
import sys, json, time
sys.path.insert(0, ".")

from src.agents.coordinator_agent import CoordinatorAgent
from src.llm.client import llm_client

# Step 1: Simulate 5 prior LLM calls (like regional agents do)
print("Step 1: Simulating 5 prior LLM calls...")
from src.agents.base import BaseAgent

class MockAgent(BaseAgent):
    def get_system_prompt(self):
        return "You are a test assistant."

mock = MockAgent("mock_agent", "test", "opencode/deepseek-v4-flash-free")

# Make 5 calls with free-text (like regional strategy prompts)
for i in range(5):
    t0 = time.time()
    r = mock.call_llm(f"Say hello in one sentence. Call {i}.", temperature=0.1)
    print(f"  Call {i+1}: {len(r)} chars, {time.time()-t0:.1f}s, failure_count={llm_client.failure_count}")

print(f"\nState after calls: calls={llm_client.total_calls}, fail={llm_client.failure_count}, cache={len(llm_client.cache)}")

# Step 2: Now call coordinator
print("\nStep 2: Coordinator _generate_decisions()")
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

notes = decisions.get("notes", "")
is_ai = "Rule-based fallback" not in notes
print(f"  Time: {elapsed:.1f}s")
print(f"  AI-generated: {is_ai}")
print(f"  Notes: {notes[:200]}")
print(f"  Weights: {decisions.get('weight_adjustments', {})}")

# Step 3: Now test with a fresh LLMClient instance
print("\nStep 3: Fresh LLMClient instance (control)")
from src.llm.client import LLMClient
fresh_llm = LLMClient()

# We can't easily use fresh_llm with the coordinator since it uses the singleton
# But we can call chat directly
result = fresh_llm.chat(
    model="opencode/deepseek-v4-flash-free",
    system="You are a test assistant.",
    user_message="Return ONLY valid JSON: {\"test\": \"ok\"}",
    temperature=0.1,
)
try:
    j = json.loads(result)
    print(f"  Fresh client result: VALID JSON: {j}")
except:
    print(f"  Fresh client result: NOT JSON: {result[:100]}")
