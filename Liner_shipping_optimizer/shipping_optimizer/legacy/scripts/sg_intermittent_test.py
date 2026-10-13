"""Test if service gen prompt returns consistent JSON or intermittent."""
import sys, json, time, re
sys.path.insert(0, ".")

from src.agents.base import BaseAgent
from src.llm.client import llm_client

svc_system = (
    "You are a liner shipping service design specialist.\n\n"
    "Advise on service archetypes for a given port network. "
    "Ground every recommendation in the network statistics provided. "
    "Every statement must cite a specific number. "
    "Do not use vague language. Do not repeat the question."
)

json_prompt = (
    "Liner shipping service design for 333-port network.\n\n"
    "NETWORK STATS:\n"
    "  Ports: 333, Lanes: 9622, Median demand/lane: 60.0 TEU\n"
    "  Total demand: 1,666,738 TEU, Avg: 173.2 TEU/lane\n"
    "  Top-3 share: 2.5%, Top-500 share: 51.3%\n"
    "  Hub ports: [USLAX, USEWR, USILM, USCHS, USHOU] (50 detected)\n\n"
    "ARCHETYPE: HYBRID\n"
    "RATIONALE: Median demand 60.0 TEU/lane across 9622 lanes.\n\n"
    "Return ONLY valid JSON (no markdown, no preamble):\n"
    '{"direct_ratio": <0.05-0.80>, "hub_loop_ratio": <0.05-0.80>, '
    '"feeder_ratio": <0.05-0.80>, "trunk_ratio": <0.05-0.80>, '
    '"vessel_bias": "small"|"balanced"|"large", '
    '"hub_focus": ["PORT_ID", ...], '
    '"notes": "<brief rationale>"}'
)

class TestSvcAgent(BaseAgent):
    def get_system_prompt(self):
        return svc_system

agent = TestSvcAgent("test_svc", "test", "opencode/deepseek-v4-flash-free")

print("Running 5 sequential tests through call_llm")
print("=" * 60)

for i in range(5):
    # Clear cache to force fresh API call
    llm_client.cache = {}
    llm_client.total_calls = 0
    llm_client.failure_count = 0

    t0 = time.time()
    result = agent.call_llm(json_prompt, temperature=0.1)
    elapsed = time.time() - t0

    is_hf = result == "Service temporarily unavailable. Using default optimization parameters."
    is_json = False
    parsed = None
    try:
        parsed = json.loads(result)
        is_json = True
    except:
        pass

    status = "VALID JSON" if is_json else ("HARD FALLBACK" if is_hf else "OTHER")
    key_info = ""
    if parsed:
        arch = parsed.get('archetype_mix', parsed)
        if isinstance(arch, dict):
            key_info = f" d={arch.get('direct_ratio')} h={arch.get('hub_loop_ratio')}"
    print(f"  Run {i+1}: {elapsed:5.1f}s | {status:15s} | {len(result):4d} chars{key_info}")
