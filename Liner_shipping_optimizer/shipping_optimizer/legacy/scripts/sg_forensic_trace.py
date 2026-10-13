"""
SG1-SG4: Complete service generator forensic trace.

Tests the service generator prompt in isolation vs pipeline context
to identify the exact failure point.
"""
import sys, json, time, re
sys.path.insert(0, ".")

from src.llm.client import llm_client
from src.agents.base import BaseAgent
from src.utils.config import Config


def make_llm_call(system: str, prompt: str, model: str = "opencode/deepseek-v4-flash-free",
                  label: str = "") -> dict:
    """Make a single LLM call and return detailed diagnostic info."""
    t0 = time.time()
    result = llm_client.chat(
        model=model,
        system=system,
        user_message=prompt,
        temperature=0.1,
    )
    elapsed = time.time() - t0

    # Check JSON
    json_status = "NO_CONTENT"
    parsed = None
    if result.strip():
        try:
            parsed = json.loads(result)
            json_status = "VALID_JSON"
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", result, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group())
                    json_status = "EMBEDDED_JSON"
                except:
                    json_status = "BRACES_INVALID"
            else:
                json_status = "NO_BRACES"

    is_hf = result == "Service temporarily unavailable. Using default optimization parameters."

    return {
        "label": label,
        "latency": round(elapsed, 1),
        "result_len": len(result),
        "is_hard_fallback": is_hf,
        "json_status": json_status,
        "result_preview": result[:200],
        "parsed": parsed,
    }


print("=" * 80)
print("SG FORENSIC TRACE")
print("=" * 80)

# ============================================================
# SG0: Verify fix is loaded
# ============================================================
import inspect
from src.agents.base import BaseAgent
src_base = inspect.getsource(BaseAgent.call_llm)
has_fix = "has_json_instruction" in src_base
print(f"\nP+1E fix loaded: {has_fix}")
assert has_fix, "FIX NOT LOADED!"

# ============================================================
# SG1: Standalone service gen prompt
# ============================================================
print(f"\n{'='*60}")
print("SG1: STANDALONE SERVICE GEN JSON PROMPT")
print(f"{'='*60}")

# Build the exact prompt the service generator uses
svc_system = (
    "You are a liner shipping service design specialist.\n\n"
    "Advise on service archetypes for a given port network. "
    "Ground every recommendation in the network statistics provided. "
    "Every statement must cite a specific number. "
    "Do not use vague language. Do not repeat the question."
)

# Simulate realistic network stats
prompt_base = (
    "Liner shipping service design for 333-port network.\n\n"
    "NETWORK STATS:\n"
    "  Ports: 333, Lanes: 9622, Median demand/lane: 60.0 TEU\n"
    "  Total demand: 1,666,738 TEU, Avg: 173.2 TEU/lane\n"
    "  Top-3 share: 2.5%, Top-500 share: 51.3%\n"
    "  Hub ports: [USLAX, USEWR, USILM, USCHS, USHOU] (50 detected)\n\n"
    "TOP-5 CORRIDORS:\n"
    "  1. Port CNYTN -> Port USLAX: 21,804 TEU/wk\n"
    "  2. Port CNSHA -> Port DEBRV: 10,584 TEU/wk\n"
    "  3. Port CNSHA -> Port USLAX: 9,135 TEU/wk\n"
    "  4. Port CNYTN -> Port GBFXT: 8,100 TEU/wk\n"
    "  5. Port CNYTN -> Port NLRTM: 8,088 TEU/wk\n\n"
    "ARCHETYPE: HYBRID\n"
    "RATIONALE: Median demand is only 60.0 TEU/lane across 9622 lanes "
    "- consolidation via hubs is essential.\n\n"
    "In 2 sentences: (1) confirm archetype citing median demand 60.0 TEU "
    "and total 1,666,738 TEU; "
    "(2) expected GA retention out of ~800 candidates."
)

json_suffix = (
    "\n\nReturn ONLY valid JSON (no markdown, no preamble):\n"
    '{"direct_ratio": <0.05-0.80>, "hub_loop_ratio": <0.05-0.80>, '
    '"feeder_ratio": <0.05-0.80>, "trunk_ratio": <0.05-0.80>, '
    '"vessel_bias": "small"|"balanced"|"large", '
    '"hub_focus": ["PORT_ID", ...], '
    '"notes": "<brief rationale>"}'
)

json_prompt = prompt_base + json_suffix

llm_client.cache = {}
llm_client.total_calls = 0
llm_client.failure_count = 0
llm_client.last_failure_time = 0

sg1 = make_llm_call(svc_system, json_prompt, label="SG1-standalone")
print(f"  Latency: {sg1['latency']}s")
print(f"  Result len: {sg1['result_len']}")
print(f"  Hard fallback: {sg1['is_hard_fallback']}")
print(f"  JSON: {sg1['json_status']}")
if sg1['parsed']:
    print(f"  Keys: {list(sg1['parsed'].keys())}")
    arch = sg1['parsed'].get('archetype_mix', sg1['parsed'])
    if isinstance(arch, dict):
        print(f"  Ratios: d={arch.get('direct_ratio')}, h={arch.get('hub_loop_ratio')}, "
              f"f={arch.get('feeder_ratio')}, t={arch.get('trunk_ratio')}")
print(f"  State: calls={llm_client.total_calls}, fail={llm_client.failure_count}")

# ============================================================
# SG2: Service gen prompt AFTER pipeline simulation
# ============================================================
print(f"\n{'='*60}")
print("SG2: AFTER PIPELINE SIMULATION (10 prior LLM calls)")
print(f"{'='*60}")

# Simulate the sequential calls from 5 regional agents
# Each agent does: 1 strategy + 1 JSON archetype prompt
prior_system = "You are a helpful assistant."
for i in range(10):
    prior_prompt = f"Explain the concept of shipping network optimization. Response {i}."
    # Use a different prompt each time to avoid cache
    llm_client.chat(
        model="opencode/deepseek-v4-flash-free",
        system=prior_system,
        user_message=prior_prompt,
        temperature=0.1,
    )

print(f"  State before SG2 call: calls={llm_client.total_calls}, fail={llm_client.failure_count}")
print(f"  last_failure_time: {llm_client.last_failure_time}")
print(f"  cache size: {len(llm_client.cache)}")

sg2 = make_llm_call(svc_system, json_prompt, label="SG2-after-pipeline")
print(f"\n  Latency: {sg2['latency']}s")
print(f"  Result len: {sg2['result_len']}")
print(f"  Hard fallback: {sg2['is_hard_fallback']}")
print(f"  JSON: {sg2['json_status']}")
if sg2['parsed']:
    print(f"  Keys: {list(sg2['parsed'].keys())}")
    arch = sg2['parsed'].get('archetype_mix', sg2['parsed'])
    if isinstance(arch, dict):
        print(f"  Ratios: d={arch.get('direct_ratio')}, h={arch.get('hub_loop_ratio')}, "
              f"f={arch.get('feeder_ratio')}, t={arch.get('trunk_ratio')}")
print(f"  State after: calls={llm_client.total_calls}, fail={llm_client.failure_count}")

# ============================================================
# SG3: Service gen prompt through BaseAgent.call_llm (simulates pipeline)
# ============================================================
print(f"\n{'='*60}")
print("SG3: THROUGH BaseAgent.call_llm (exact pipeline path)")
print(f"{'='*60}")

class TestSvcAgent(BaseAgent):
    def get_system_prompt(self):
        return svc_system

agent = TestSvcAgent("test_svc", "test", "opencode/deepseek-v4-flash-free")
llm_client.cache = {}
llm_client.total_calls = 0
llm_client.failure_count = 0

t0 = time.time()
sg3_result = agent.call_llm(json_prompt, temperature=0.1)
sg3_time = time.time() - t0

print(f"  Latency: {sg3_time:.1f}s")
print(f"  Result len: {len(sg3_result)}")
is_hf = sg3_result == "Service temporarily unavailable. Using default optimization parameters."
print(f"  Hard fallback: {is_hf}")
try:
    j = json.loads(sg3_result)
    print(f"  VALID JSON: keys={list(j.keys())}")
    arch = j.get('archetype_mix', j)
    if isinstance(arch, dict):
        print(f"  Ratios: d={arch.get('direct_ratio')}, h={arch.get('hub_loop_ratio')}, "
              f"f={arch.get('feeder_ratio')}, t={arch.get('trunk_ratio')}")
except:
    print(f"  NOT JSON")
    print(f"  Content: {sg3_result[:200]}")

# ============================================================
# SG4: What does ServiceGeneratorAgent.process() produce?
# ============================================================
print(f"\n{'='*60}")
print("SG4: FULL PROCESS THROUGH SERVICE GENERATOR")
print(f"{'='*60}")

from src.agents.service_generator_agent import ServiceGeneratorAgent
from src.optimization.data import Problem, Port, Demand

# Create minimal valid problem for service gen
ports = [Port(id=i, name=f"Port_{i}", handling_cost=100,
              port_call_cost=10000, variable_port_call_cost=50,
              transshipment_cost=200, x=float(i), y=float(i*2))
         for i in range(50)]

demands = []
for i in range(min(200, len(ports)-1)):
    d = Demand(origin=i % 50, destination=(i+1) % 50,
               weekly_teu=1000 + (i * 50) % 5000,
               revenue_per_teu=1500 + (i * 100) % 1000)
    demands.append(d)

problem = Problem(ports=ports, services=[], demands=demands, distance_matrix={})

svc = ServiceGeneratorAgent("forensic_svc", "opencode/deepseek-v4-flash-free")
llm_client.cache = {}
llm_client.total_calls = 0
llm_client.failure_count = 0

t0 = time.time()
try:
    result = svc.process({"problem": problem})
    svg_time = time.time() - t0
    ap = result.get("archetype_params", {})
    arch = ap.get("archetype_mix", {}) if isinstance(ap, dict) else {}
    is_default = arch.get("direct_ratio", 0) == 0.60

    print(f"  Latency: {svg_time:.1f}s")
    print(f"  Archetype mix: {arch}")
    print(f"  Is default: {is_default}")
    print(f"  Metrics: {svc._metrics}")
    print(f"  Services generated: {result.get('services_generated', 0)}")
    print(f"  Strategy (first 200): {result.get('strategy', '')[:200]}")

except Exception as e:
    print(f"  ERROR: {str(e)[:500]}")

# ============================================================
# SUMMARY
# ============================================================
print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
print(f"  SG1 (standalone):   JSON={sg1['json_status']} | HF={sg1['is_hard_fallback']} | {sg1['latency']}s")
print(f"  SG2 (pipeline ctx): JSON={sg2['json_status']} | HF={sg2['is_hard_fallback']} | {sg2['latency']}s")
print(f"  SG3 (call_llm):     HF={is_hf} | {sg3_time:.1f}s")
print(f"  SG4 (full process): Metrics={svc._metrics}")
