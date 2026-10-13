# Validator Rejection Chain Analysis

**Date:** 2026-06-23
**Scope:** Every validator in the AI Vessel Routing pipeline — what they receive, whether they detect failures, and why rejections do or do not fire.

---

## 1. LLMEvaluator (`src/llm/evaluator.py:4-67`)

### Call Site
`src/agents/base.py:51` — called on **every** LLM response text before it returns to the caller.

```python
scores = evaluator.evaluate(response)
llm_metrics.log(self.name, scores)
if scores["total_score"] < 0.5:
    response = "Strategy: C\nReason 1: Balanced network design..."
```

### Scoring Formula

| Component | Weight | Check |
|---|---|---|
| Structure | 0.4 | Substrings "Strategy" and "Reason" present (case-insensitive) |
| Completeness | 0.3 | >= 3 non-empty lines = 1.0 |
| Relevance | 0.3 | Keywords present: "demand", "port", "hub", "capacity", "route" |

### What Happens When LLM Returns a Serialized Object

When the LLM API returns a serialized message object, the text typically contains:

- **"Strategy"** — present in system prompt output format instructions
- **"Reason"** — same
- **"demand"**, **"port"**, **"hub"** — present in the network stats baked into prompts

**Typical score: 0.82**

```
structure:    1.0  (has "Strategy" and "Reason")
completeness: 1.0  (3+ lines from the formatted object)
relevance:    0.4  (2/5 keywords: "port", "demand")
total:  0.4*1.0 + 0.3*1.0 + 0.3*0.4 = 0.82
```

### Verdict: **FALSE POSITIVE — Garbage Accepted**

The evaluator passes garbage output because:
1. The format string templates ("Strategy:", "Reason N:") leak keyword matches into structure scoring
2. Serialized objects include domain language from prompt context, satisfying relevance keywords
3. Multiple lines from object repr satisfy completeness

### Downstream Impact

If the evaluator **did** reject (score < 0.5), the replacement string is:

```
Strategy: C
Reason 1: Balanced network design across 50+ ports
Reason 2: Handles demand variability for 100+ lanes
```

This is also not valid JSON, so downstream JSON parsers would still fail. The only difference: the follow-on parsers would get a consistent non-JSON string instead of a serialized object, but the failure mode is identical.

---

## 2. Weight Validator (`src/validation/weight_validator.py:25-164`)

### Call Site #1 — Coordinator Agent
`src/agents/coordinator_agent.py:357`

```python
if decisions and "weight_adjustments" in decisions:
    validated = validate_weight_adjustments(
        decisions["weight_adjustments"],
        iteration=0, source="coordinator_llm",
    )
    decisions["weight_adjustments"] = validated
```

### Critical Discovery: **NEVER REACHED**

When `_parse_json_safe()` returns `{}` (parsing failure):

- Line 357: `if decisions and "weight_adjustments" in decisions:`
- `decisions` is `{}` → `{}` is **FALSY** in Python
- First condition `decisions` is `False` → short-circuits → `and` is `False`
- **The validator never executes**

The code then falls through to line 370:
```python
if not decisions or "actions" not in decisions:
```

`not {}` is `True` → rule-based fallback is built with hard-coded weights.

### Call Site #2 — Fallback Weights (always reached)
`src/agents/coordinator_agent.py:409`

```python
decisions["weight_adjustments"] = validate_weight_adjustments(
    decisions["weight_adjustments"],
    iteration=0, source="rule-based",
)
```

This **always** runs after the fallback and receives the rule-based weights directly. These are valid numeric dicts → passes validation → logged as `AI_FALLBACK`.

### Call Site #3 — Consensus Engine
`src/validation/consensus_engine.py:171`

```python
coord_validated = validate_weight_adjustments(coordinator_decisions)
```

The orchestrator passes `coord_weights` which falls back to `{}`:
```python
coord_weights = (
    decision_output.get("decisions", {}).get("weight_adjustments") or
    decision_output.get("feedback", {}).get("weight_adjustments") or
    {}
)
```

`validate_weight_adjustments({})` → `not raw` → `True` → `AI_REJECTED` → returns defaults. **This works correctly** — it detects the empty dict.

### Verdict: **BYPASSED at coordinator level, EFFECTIVE at consensus level**

The coordinator's guard clause (`if decisions and ...`) silently skips validation of LLM output. The consensus engine catches the empty dict. The fallback weights pass successfully.

---

## 3. Archetype Validator (`src/validation/archetype_validator.py:43-230`)

### Call Site
`src/agents/service_generator_agent.py:337`

```python
parsed = _json.loads(text.strip())              # may raise
# ... or ...
m = _re.search(r"\{.*\}", text, _re.DOTALL)
parsed = _json.loads(m.group()) if m else {}     # {} when regex fails
archetype_params = validate_archetype_params(parsed)
```

### Validation Path
When `parsed` is `{}` (empty dict from failed regex):

1. Line 68: `not isinstance(raw, dict)` → `{}` IS a dict → continues
2. Line 77: `if not raw:` → `{}` is FALSY → **AI_REJECTED logged** → returns defaults

### Verdict: **CORRECT REJECTION**

The validator correctly identifies the empty dict as invalid and falls back to defaults. The logged tag is `AI_REJECTED` followed by `AI_FALLBACK`.

### Limitation
The rejection message is `"empty dict"` — this states the symptom but not the cause. The chain of failure (LLM returned serialized object → json.loads failed → regex found no `{...}` → empty dict) is invisible in the logs.

---

## 4. Consensus Engine Internal Validation (`src/validation/consensus_engine.py:764-777`)

### Call Site
`src/validation/consensus_engine.py:771-775`

```python
@staticmethod
def _validate_final(result: Dict[str, Any]) -> None:
    validate_weight_adjustments(result.get("final_weight_adjustments", {}))
    validate_archetype_params(result.get("final_archetype_params", {}))
```

### Purpose
Post-reconciliation sanity check. The consensus engine's reconciliation has already produced valid outputs (via the initial validation + voting). This re-validates the final product.

### Verdict: **ALWAYS PASSES**

Both validators receive already-validated data from the consensus pipeline. These calls are defensive checks and serve as a circuit-breaker only if the reconciliation logic produced corrupt output (which would be a bug in the reconciliation code, not an LLM failure).

---

## 5. Regional Policy Validator (`src/validation/regional_policy_validator.py:128-267`)

### Call Site
`src/validation/consensus_engine.py:176`

```python
validated_regional[region] = validate_regional_policy(raw_policy)
```

Called for each region during consensus engine processing. The regional policies are constructed by the orchestrator from `regional_results` metrics, not from raw LLM output:

```python
regional_policies[region_key] = {
    "coverage_priority": max(0.1, r.get("coverage_percent", 0) / 100.0),
    "profit_priority": max(0.1, 1.0 - (r.get("coverage_percent", 0) / 100.0)),
    ...
}
```

### Verdict: **ALWAYS PASSES (NOT PART OF LLM FAILURE CHAIN)**

This validator operates on orchestrator-constructed policy dicts derived from numeric simulation results, not on LLM JSON output. It is unrelated to the JSON prompt failure chain.

---

## Validator Effectiveness Matrix

| Validator | Executed on LLM output? | Detects empty/bad data? | Logged Tag(s) | Outcome |
|---|---|---|---|---|
| LLMEvaluator | Yes | **No** (false positive, score >= 0.5) | (none — passes) | Garbage accepted |
| weight_validator (coordinator) | **Skipped** — gate condition `if decisions` fails on `{}` | N/A | N/A | Not invoked |
| weight_validator (fallback) | Yes — receives valid rule-based dict | No issue (valid) | AI_FALLBACK | Weights applied |
| weight_validator (consensus engine) | Yes — receives `{}` from orchestrator fallback chain | Yes | AI_REJECTED → AI_FALLBACK | Defaults used |
| archetype_validator | Yes — receives `{}` from failed JSON parse | Yes | AI_REJECTED → AI_FALLBACK | Defaults used |
| regional_policy_validator | No — constructed from simulation metrics | N/A | AI_VALIDATED | Policies applied |

---

## Root Cause Chain

```
LLM API returns serialized object (not JSON text)
    │
    ▼
base.py:51 — LLMEvaluator.evaluate() scores >= 0.5  ← FALSE POSITIVE
    │                                                  (wouldn't help anyway —
    │                                                   replacement string also not JSON)
    ▼
Two failure paths:
    ┌────────────────────────────────────┬────────────────────────────────────┐
    │ COORDINATOR AGENT                  │ SERVICE GENERATOR AGENT            │
    │ _parse_json_safe(raw)              │ json.loads(text) → exception       │
    │   → json.loads() fails             │ re.search(r"\{.*\}", text) → None  │
    │   → regex r"\{.*\}" → no match     │   → parsed = {}                    │
    │   → returns {}                     │   → validate_archetype_params({})  │
    │   → decisions is {} → FALSY        │   → if not raw: → AI_REJECTED      │
    │   → weight_validator SKIPPED       │   → returns defaults (AI_FALLBACK) │
    │   → rule-based fallback            │                                    │
    └────────────────────────────────────┴────────────────────────────────────┘
```

### Key Findings

1. **The LLMEvaluator is the primary gatekeeper and it fails.** It passes garbage output because the serialized message object coincidentally contains the keywords used for scoring. This is a false positive — a correct rejection would only push the failure downstream to the JSON parsers anyway.

2. **The weight_validator in the coordinator is silently bypassed** by Python's truthiness semantics: `if decisions and ...` short-circuits on empty dict. This is a latent bug — the guard clause intended to protect against `None` also blocks validation of empty dicts.

3. **The archetype_validator correctly rejects empty dicts** but doesn't surface the upstream failure reason in its log message.

4. **The consensus engine's validator calls work correctly** but are defensive checks, not the primary validation layer.

5. **The fix must target the LLM response extraction / JSON parsing layer**, not the validators. The validators are all working as designed — the problem is that upstream code passes them empty data.
