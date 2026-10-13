"""Step-by-step trace through LLMClient to find the exact failure point."""

import sys, json, time, re
sys.path.insert(0, '.')
from src.utils.config import Config
from openai import OpenAI

client_direct = OpenAI(base_url=Config.LLM_BASE_URL, api_key=Config.LLM_API_KEY)

model = "deepseek-v4-flash-free"
system_coord = "You are a global shipping network decision agent act as maritime analyst from global liner shipping company. You ANALYZE, DECIDE, and CORRECT - not summarise. Rules: - Every decision must cite a specific number. - Actions must be concrete and measurable. - Output valid JSON only when requested. - No hedging language."

metric_context = (
    "Global shipping network decision - iteration results:\n\n"
    "Metrics:\n"
    "  Total profit   : $896,953,334/week\n"
    "  Annual profit  : $46,641,573,368\n"
    "  Avg coverage   : 66.0%\n"
    "  Min coverage   : 32.2%\n"
    "  Coverage variance: 51.4%\n"
    "  Total cost     : $1,982,113,428/week\n"
    "  Profit margin  : 31.1%\n"
    "  Evaluation     : moderate (score 3/5)\n\n"
    "Conflicts detected: 0\n"
    "Weak regions: Europe coverage=55.8%; Americas coverage=36.3%\n\n"
)

json_schema = (
    "Return ONLY valid JSON (no markdown, no preamble):\n"
    '{"actions": [{"region": "<name>", "action": "<verb> <object>", "expected_gain": "<metric change>"}], '
    '"priorities": ["<priority 1>", "<priority 2>"], '
    '"weight_adjustments": {"profit_weight": <0.0-1.0>, "coverage_weight": <0.0-1.0>, "cost_weight": <0.0-1.0>}, '
    '"notes": "<one sentence with specific numbers>"}'
)

coord_prompt = metric_context + json_schema
enhanced = coord_prompt + "\n\nThink step by step. Follow the output format strictly."

print("=== STEP-BY-STEP TRACE THROUGH LLMCLIENT ===")

# Step 1: Direct API call
print("\nStep 1: Direct API call (timeout=30)")
t0 = time.time()
resp = client_direct.chat.completions.create(
    model=model,
    messages=[{"role": "system", "content": system_coord},
              {"role": "user", "content": enhanced}],
    temperature=0.1, max_tokens=2000, timeout=30,
)
print(f"  OK - latency: {time.time()-t0:.1f}s")
msg = resp.choices[0].message
print(f"  content is not None: {msg.content is not None}")
print(f"  content type: {type(msg.content).__name__}")
print(f"  content len: {len(msg.content) if msg.content else 0}")
print(f"  content repr: {repr(msg.content[:300]) if msg.content else 'EMPTY'}")

# Check reasoning
rc = None
for attr in ["reasoning_content", "reasoning", "thinking"]:
    if hasattr(msg, attr) and getattr(msg, attr):
        rc = str(getattr(msg, attr))
        print(f"  Has {attr}: YES ({len(rc)} chars)")
        break
else:
    print(f"  Has reasoning: NO")

# Step 2: Run extraction
print("\nStep 2: _extract_response_content()")
from src.llm.client import LLMClient
lc = LLMClient()
extracted = lc._extract_response_content(resp)
print(f"  Extracted type: {type(extracted).__name__}")
print(f"  Extracted is None: {extracted is None}")
if extracted:
    print(f"  Extracted len: {len(extracted)}")
    print(f"  Extracted repr: {repr(extracted[:300])}")

# Step 3: JSON parse
print("\nStep 3: CoordinateAgent._parse_json_safe()")
from src.agents.coordinator_agent import CoordinatorAgent
coord = CoordinatorAgent()
if extracted:
    decisions = coord._parse_json_safe(extracted)
    print(f"  decisions type: {type(decisions).__name__}")
    print(f"  decisions empty: {not decisions}")
    if decisions:
        print(f"  decisions keys: {list(decisions.keys())}")
        if "weight_adjustments" in decisions:
            print(f"  weight_adjustments: {decisions['weight_adjustments']}")

# Step 4: Fallback check
print("\nStep 4: Fallback check (coordinator logic)")
has_weight = bool(decisions and "weight_adjustments" in decisions) if 'decisions' in dir() else False
needs_fallback = not decisions or "actions" not in decisions
print(f"  decisions truthy: {bool(decisions)}")
print(f"  has weight_adjustments: {has_weight}")
print(f"  needs_fallback: {needs_fallback}")

# Step 5: Now try through the actual LLMClient.chat()
print("\n\n=== TEST 2: Through actual LLMClient.chat() ===")
from src.llm.client import llm_client

# Reset state
llm_client.cache = {}
llm_client.total_calls = 0
llm_client.fallback_uses = 0
llm_client.failure_count = 0

t0 = time.time()
result = llm_client.chat(
    model="opencode/deepseek-v4-flash-free",
    system=system_coord,
    user_message=enhanced,
    temperature=0.1,
)
latency = time.time() - t0
print(f"  Result ({len(result)} chars): {result[:200]}")
print(f"  Latency: {latency:.1f}s")
print(f"  Total calls: {llm_client.total_calls}")
print(f"  Fallback uses: {llm_client.fallback_uses}")
print(f"  Cache hits: {llm_client.cache_hits}")
print(f"  Failure count: {llm_client.failure_count}")

# ============================================================
# Check what _try_call actually returns
# ============================================================
print("\n\n=== TEST 3: _try_call directly ===")
t0 = time.time()
try:
    resp2 = lc._try_call(
        model, system_coord, enhanced,
        temperature=0.1, max_tokens=2000,
    )
    print(f"  OK - latency: {time.time()-t0:.1f}s")
    msg2 = resp2.choices[0].message
    print(f"  content type: {type(msg2.content).__name__}")
    print(f"  content len: {len(msg2.content) if msg2.content else 0}")
    print(f"  content repr: {repr(msg2.content[:300]) if msg2.content else 'EMPTY'}")
except Exception as e:
    print(f"  ERROR: {str(e)[:300]}")
    print(f"  Latency: {time.time()-t0:.1f}s")
