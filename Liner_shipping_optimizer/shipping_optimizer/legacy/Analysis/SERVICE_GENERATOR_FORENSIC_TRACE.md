# Service Generator Forensics Trace — Prompt #3 (Archetype JSON)

## Scope

This document traces Prompt #3 (the archetype-JSON prompt) through every pipeline
stage from construction to final output. Prompt #2 (strategy, free-text) is covered
only where its path diverges or intersects.

---

## Step 1 — Prompt Construction

**File:** `src/agents/service_generator_agent.py` lines 290-325

Two distinct prompts are assembled from the same network statistics, archetype label,
and rationale:

### Prompt #2 (strategy, lines 290-303)

- Free-text format: 2-sentence natural language request.
- Consumes: `num_ports`, `num_lanes`, `median_demand`, `total_demand`, `top3_share`,
  `top500_share`, `hub_ids_str`, `corridor_table`, `archetype` label, `rationale`.
- Target output: conversational paragraph confirming archetype and GA retention.

### Prompt #3 (archetype JSON, lines 318-325)

- Strict JSON schema appended to Prompt #2 via string concatenation:

```
"\n\nReturn ONLY valid JSON (no markdown, no preamble):\n"
'{"direct_ratio": <0.05-0.80>, "hub_loop_ratio": <0.05-0.80>, '
'"feeder_ratio": <0.05-0.80>, "trunk_ratio": <0.05-0.80>, '
'"vessel_bias": "small"|"balanced"|"large", '
'"hub_focus": ["PORT_ID", ...], '
'"notes": "<brief rationale>"}'
```

- Prompt #3 is therefore Prompt #2 (which is already verbose — network stats,
  archetype label, rationale, corridor table) **plus** the JSON schema instruction.
- The combined message is well over the structural complexity the LLM receives;
  the JSON instruction appears after ~25 lines of natural-language context.

**Key observation:** The JSON schema instruction does not include default values or
mention that all ratios must sum to 1.0. It only states per-key ranges (0.05-0.80),
leaving proportional normalisation to the downstream validator. This works when the LLM
responds with actual JSON, but when the response degrades, the absence of defaults in
the prompt means there is no guidance for a partial response.

---

## Step 2 — LLM Call for Prompt #2 (line 306)

```
strategy = self.call_llm(prompt, temperature=0.1)
```

The base agent's `call_llm` (base.py lines 27-88):
1. Calls `llm_client.chat()` with the prompt + `"\n\nThink step by step..."` suffix.
2. Receives a response string.
3. Passes through `LLMEvaluator.evaluate()` — checks structure ("Strategy"/"Reason"
   keywords), completeness (>= 3 lines), relevance (domain keywords).
4. If `total_score < 0.5`: substitutes a hardcoded rule-based strategy response
   (base.py lines 67-71).
5. Returns the final string.

Prompt #2 has a **backup path** at lines 307-314: if `call_llm` throws an exception,
a rule-based strategy string is substituted inline. This exception handler provides
resilience independent of the evaluator.

Prompt #2 **may succeed** (it asks for free-text, which is the LLM's natural output
mode, and the evaluator is tuned for keyword presence rather than deep semantics).

---

## Step 3 — LLM Call for Prompt #3 (line 326)

```
raw_json = self.call_llm(json_prompt, temperature=0.1)
```

Same `call_llm()` path as Step 2, but now the prompt is:
- Base prompt (network stats + archetype + rationale + corridor table) +
- JSON schema instruction +
- `"\n\nThink step by step. Follow the output format strictly."`

### Inside `llm_client.chat()` (client.py lines 87-207)

| Sub-step | Code | What happens |
|---|---|---|
| Cache check | client.py:103-109 | Key is `md5(model\|system\|user_message)`. First call: cache miss. |
| Circuit breaker | client.py:112-116 | If `failure_count < 5`: pass. If >= 5 and within 60s timeout: hard fallback. |
| Model chain | client.py:123-145 | Primary model + 4 fallbacks tried sequentially. |
| _try_call | client.py:39-64 | `OpenAI.chat.completions.create(...)` with 2 internal retries. |
| **Response extraction** | client.py:156-169 | THE CRITICAL BLOCK |

### Response extraction logic (client.py lines 156-169)

```python
result = ""
try:
    if response and response.choices:
        message = response.choices[0].message

        if hasattr(message, "content") and message.content:   # line 162
            result = message.content                           # line 163: HAPPY PATH

        elif hasattr(message, "tool_calls") and message.tool_calls:  # line 165
            result = str(message.tool_calls)                         # line 166

        else:                                                         # line 168
            result = str(message)                                     # line 169: FAILURE PATH
```

**The failure scenario:** When the LLM returns a message where:
- `message.content` is an empty string `""` (or `None`)
- `message.reasoning_content` is populated (typical of reasoning or chain-of-thought models)
- `message.tool_calls` is absent

Then the code falls through to `result = str(message)` which produces a Python repr
string of the entire `ChatCompletionMessage` object, approximately:

```
ChatCompletionMessage(content='', reasoning_content='...',
role='assistant', function_call=None, tool_calls=None, ...)
```

This string is **not valid JSON**. It is a Python object serialization.

### Downstream checks in client.py (lines 177-207)

- Line 177: `if not result or result.lower() == "none":` — the serialized object string
  is truthy (non-empty) and not "none", so no hard fallback is triggered.
- Line 184: `result.strip()` — produces the serialized string unchanged.
- Line 205: `self.cache[cache_key] = result` — caches the broken string for future calls.
- Returns the broken string to `call_llm` in base.py.

### Back in base.py `call_llm()` (lines 48-72)

- Line 48: `response = response.strip()` — the serialized string is stripped.
- Lines 51-61: `evaluator.evaluate(response)` — the evaluator checks for "Strategy"/"Reason"
  keywords, >= 3 lines, domain keywords. The serialized Python object (`ChatCompletionMessage(...)`)
  likely **fails** the structure check (no "Strategy" or "Reason" keyword).
- Line 61: `if scores["total_score"] < 0.5:` — **true** for the serialized object.
- Lines 67-71: **Substitute hardcoded response:**
  ```
  "Strategy: C\n"
  "Reason 1: Balanced network design across 50+ ports\n"
  "Reason 2: Handles demand variability for 100+ lanes"
  ```

So `raw_json` in service_generator_agent.py line 326 receives the **hardcoded fallback
strategy string**, not JSON at all.

---

## Step 4 — JSON Extraction (lines 327-336)

```python
import json as _json
import re as _re
text = raw_json.strip()
text = _re.sub(r"^```[a-zA-Z]*\n?", "", text)
text = _re.sub(r"\n?```$", "", text)
try:
    parsed = _json.loads(text.strip())
except _json.JSONDecodeError:
    m = _re.search(r"\{.*\}", text, _re.DOTALL)
    parsed = _json.loads(m.group()) if m else {}
```

| Sub-step | Input | Result |
|---|---|---|
| `raw_json` | `"Strategy: C\nReason 1: ..."` (hardcoded fallback) | — |
| After markdown fence removal | Same (no fences) | — |
| `json.loads()` | Not JSON | Raises `JSONDecodeError` |
| Regex `\{.*\}` | No `{` character in the string | `m` is `None` |
| Fallback | `m` is None → `parsed = {}` | **Empty dict** |

**Logging:** The code at line 340 originally called `logger.info(..., tag="AI_FALLBACK")`
inside the `except` block. At line 338, if parsing succeeds but validation fails,
`tag="AI_VALIDATED"` would be logged with default params.

Wait — re-reading lines 337-341:

```python
archetype_params = validate_archetype_params(parsed)
logger.info("archetype_params_generated", tag="AI_VALIDATED", params=archetype_params)
```

If parsed = {}, validate_archetype_params will reject it (see Step 5) and return
defaults. Then line 338 will log the **validated result** (which is actually defaults)
with tag `AI_VALIDATED`. This is **misleading logging** — the tag says AI_VALIDATED
but the parameters are completely synthetic.

Wait, let me re-check. The archetype_validator logs internally. Let me trace that.

---

## Step 5 — Archetype Validator (line 337)

```
archetype_params = validate_archetype_params(parsed)
```

Where `parsed = {}` (empty dict).

### Inside `validate_archetype_params` (archetype_validator.py lines 43-230)

| Check | Line | Input | Verdict |
|---|---|---|---|
| `isinstance(raw, dict)` | 68 | `{}` is dict | Pass |
| `if not raw:` | 77 | `not {}` is True | **AI_REJECTED — empty dict** |
| Returns | 84 | `_fallback_archetype_params(reason="empty dict")` | — |

### `_fallback_archetype_params` (archetype_validator.py lines 268-282)

```python
def _fallback_archetype_params(reason=""):
    fallback = {
        "archetype_mix": {"direct_ratio": 0.60, "hub_loop_ratio": 0.15,
                          "feeder_ratio": 0.20, "trunk_ratio": 0.05},
        "vessel_bias": "balanced",
        "hub_focus": [],
        "notes": "",
    }
    logger.info("archetype_param_validation", tag="AI_FALLBACK",
                reason=reason, default_params=fallback)
    return fallback
```

Logs **AI_FALLBACK** with the default parameters.

### Back in service_generator_agent.py line 338

```python
logger.info("archetype_params_generated", tag="AI_VALIDATED", params=archetype_params)
```

This logs `AI_VALIDATED` even though the validator returned defaults. The inner
validator already logged `AI_FALLBACK`, but the outer code overwrites the tag.
This creates **ambiguous log output**: two log entries — one `AI_FALLBACK` from
the validator, one `AI_VALIDATED` from the outer code — for the same parameters.

---

## Step 6 — Service Generation (lines 343-344)

```
services = self.generate_services(problem, archetype_params=archetype_params)
problem.services = services
```

### Inside `generate_services` (lines 33-95+)

The archetype_params dict has:
```python
{
    "archetype_mix": {
        "direct_ratio": 0.60,
        "hub_loop_ratio": 0.15,
        "feeder_ratio": 0.20,
        "trunk_ratio": 0.05,
    },
    "vessel_bias": "balanced",
    "hub_focus": [],
    "notes": "",
}
```

At line 48-56:
```python
params = archetype_params or {}
arch_mix = params.get("archetype_mix", {})
# arch_mix = {"direct_ratio": 0.60, "hub_loop_ratio": 0.15, "feeder_ratio": 0.20, "trunk_ratio": 0.05}
# ratios_valid = True (all 4 keys present)
```

So the **default ratios produce default service counts:**

| Service type | Count | Rule |
|---|---|---|
| Direct services | 500 | `n_direct = min(800, max(200, int(500 * 0.60 / 0.60)))` = 500 |
| Hub loop services | 10 hubs * 4 loops = ~40 | `hub_loop_count = max(2, int(10 * 0.15 / 0.15))` = 10 |
| Feeder services | 100 | `feeder_count_target = max(20, int(100 * 0.20 / 0.20))` = 100 |
| Trunk services | hub-to-hub pairs | Rule-based, not driven by arch_mix directly |

**All services are generated purely by rule-based logic.** The LLM archetype prompt
had zero influence over service count, mix, or vessel bias. The defaults are identical
to what would be used if the LLM call were never made.

---

## Step 7 — Regional Result Export (regional_agent.py:167, 468)

```
svc_archetype_params = svc_result.get("archetype_params", {})
# ...
return {
    # ...
    "archetype_params": svc_archetype_params,
    # ...
}
```

Every regional agent (asia, europe, na, latam, africa) independently calls
`ServiceGeneratorAgent.process()`, and each one independently takes the same
content='' → str(message) → JSON parse failure → default fallback path.

**The `pipeline_output.json` for all 5 regions contains:**
```json
"archetype_params": {
    "archetype_mix": {"direct_ratio": 0.60, "hub_loop_ratio": 0.15,
                      "feeder_ratio": 0.20, "trunk_ratio": 0.05},
    "vessel_bias": "balanced",
    "hub_focus": [],
    "notes": ""
}
```

All 5 regions are **identical**, all are **defaults**, none reflect LLM reasoning.

---

## Question-by-Question Answer Table

| # | Question | Answer | Evidence (file:line) | Explanation |
|---|---|---|---|---|
| 1 | Was the prompt actually sent? | YES | service_generator_agent.py:326 | `raw_json = self.call_llm(json_prompt, ...)` calls through to `llm_client.chat()` which calls `OpenAI.chat.completions.create()` |
| 2 | Was a response received? | YES | client.py:158-169 | `response.choices[0].message` exists; code enters the extraction block |
| 3 | Was `response.content` populated? | LIKELY NO | client.py:162-163 | `hasattr(message, "content") and message.content` — if `content=""` (empty string), the truthiness check fails |
| 4 | Was `reasoning_content` populated? | YES (inferred) | client.py:162-169 | The only way to reach `result = str(message)` (line 169) from a non-exceptional response is for content to be falsy and tool_calls absent. Reasoning models populate `reasoning_content` alongside empty `content`. |
| 5 | Was JSON present? | NO | client.py:169 → service_generator_agent.py:329-336 | `str(message)` produces a Python repr like `ChatCompletionMessage(content='', reasoning_content='...', role='assistant', ...)` — not JSON |
| 6 | Did parsing fail? | YES | service_generator_agent.py:333-336 | `json.loads(text.strip())` raises `JSONDecodeError`; regex `\{.*\}` finds no braces → returns `{}` |
| 7 | Did validation fail? | YES | archetype_validator.py:77-84 | `if not raw:` → True for empty dict `{}` → `AI_REJECTED` → `_fallback_archetype_params()` |
| 8 | Did fallback activate? | YES | archetype_validator.py:268-282 | Returns `DEFAULT_ARCHETYPE_PARAMS` with `direct_ratio=0.60, hub_loop_ratio=0.15, feeder_ratio=0.20, trunk_ratio=0.05`, `vessel_bias="balanced"` |
| 9 | Did circuit breaker activate? | NO | client.py:66-76 | Circuit opens after 5 failures; service generator sees at most 4 prompts (1 global + maybe retries). Historical failure count unlikely to reach 5. |
| 10 | Did cache affect behavior? | NO | client.py:103-109 | First-time prompts produce cache miss. Even if cached, the cached entry is the broken string — same failure path. |
| 11 | Did consensus override output? | NO | consensus_engine.py:1-50 | Consensus resolves conflicts between coordinator, regional, and service generator — but all three produced default archetype params, so no conflict exists. |
| 12 | Did downstream logic ignore valid output? | N/A | — | There was never valid output to ignore. |

---

## Root Cause

The root cause is identical to the Coordinator Agent's Prompt #5 failure:

1. **The LLM returns a message with `content=""` and `reasoning_content` populated.**
2. **client.py:162-169** treats falsy `content` as "no content" and falls through to
   `result = str(message)`, producing a Python object serialization string.
3. **The serialized string is not JSON** and cannot be parsed by `json.loads()`.
4. **The regex fallback** at service_generator_agent.py:335 finds no `{...}` braces in
   the serialized string (the repr uses `<...>` or `(...)` for nested objects).
5. **`parsed = {}`** is passed to the validator.
6. **The validator rejects the empty dict** and returns DEFAULT_ARCHETYPE_PARAMS.
7. **Service generation proceeds with 100% rule-based defaults** — the LLM had zero
   influence on the output.

**Secondary finding — Log tag collision at line 338:**
After `validate_archetype_params(parsed)` returns defaults (which internally logs
`AI_FALLBACK`), line 338 logs `archetype_params_generated` with `tag="AI_VALIDATED"`.
This means a log reader sees `AI_FALLBACK` followed by `AI_VALIDATED` for the same
parameter set — misleading.

---

## Fix Requirements

1. **client.py:162** — Change the truthiness check from `message.content` (falsy on `""`)
   to `message.content is not None`, so empty string content is preserved rather than
   triggering the `str(message)` fallback.

2. **service_generator_agent.py:338** — Remove or correct the `tag="AI_VALIDATED"` to
   reflect the actual path taken; validator already logs its own tag.

3. **service_generator_agent.py:327-336** — Add a more robust JSON extraction that
   handles the `str(message)` repr or uses `message.model_extra` / `message.reasoning_content`
   to recover actual structured data.

4. **base.py:61-71** — The evaluator's auto-reject for non-strategy prompts (like the
   JSON prompt) substitutes a strategy string that is itself not JSON. The archetype
   prompt should have its own evaluation path or bypass the strategy evaluator entirely.

---

## Call Chain Summary

```
service_generator_agent.py:326  call_llm(json_prompt)
  └─ base.py:41                 llm_client.chat(...)
       └─ client.py:130         _try_call(model, system, user_message, ...)
            └─ client.py:49     OpenAI.chat.completions.create(...)
       └─ client.py:158-169    response extraction → content='' → str(message) → garbage
  └─ base.py:51-61              evaluator.evaluate(garbage) → score < 0.5
  └─ base.py:67-71              substitute hardcoded strategy string
service_generator_agent.py:329-336  json.loads(strategy_string) → JSONDecodeError → parsed = {}
service_generator_agent.py:337  validate_archetype_params({})
  └─ archetype_validator.py:77  not raw → True → AI_REJECTED
  └─ archetype_validator.py:268 _fallback_archetype_params() → AI_FALLBACK
service_generator_agent.py:343  generate_services(problem, DEFAULT_ARCHETYPE_PARAMS)
  └─ 100% rule-based service generation
```

---

*Generated 2026-06-23. Trace artifacts corroborated against source code at
commits 792c040 and 2a171cc.*
