# PHASE P — P2: PROMPT FLOW MAPPING

## Flow Summary

| Prompt | LLM Called | Parser | Validator | Consumer | Optimizer Influence |
|---|---|---|---|---|---|
| #1 Coordinator Decisions | ✓ | `_parse_json_safe()` | `validate_weight_adjustments()` | `_apply_feedback()` → GA weights | HIGH |
| #2 ServiceGen Strategy | ✓ | None | None | Logged only | NONE |
| #3 ServiceGen Archetype JSON | ✓ | `json.loads()` + `re.sub()` | `validate_archetype_params()` | `generate_services()` | HIGH |
| #4 Regional Strategy | ✓ | None | `is_valid_explanation()` | Regional results dict | NONE |
| #5 Regional Explanation | ✓ | None | `is_valid_explanation()` | Regional results dict | NONE |
| #6 Orchestrator Analysis | ✓ | None | `_is_valid_analysis()` | Frontend callbacks | NONE |
| #7 Orchestrator Summary | ✓ | None | `_is_valid_summary()` | Pipeline output JSON | NONE |
| #8 Base LLM Enhancement | N/A | N/A | `LLMEvaluator.evaluate()` | All responses | MODERATE |

## Key Finding: Rule-Based Override Pattern

All 4 display-only/partially-active prompts follow the same anticlimactic pattern:
1. Rule-based logic pre-computes the answer (strategy decision, archetype classification, size label, verdict)
2. LLM is asked to confirm/validate the pre-computed answer
3. LLM output is gated by a keyword checker
4. If gate fails → rule-based fallback (same as pre-computed answer)
5. Pre-computed answer was the real decision all along

## Critical Bug: Executive Summary Flow

The flow for Prompt #7 reveals a serialization vulnerability:
1. LLM returns response with `content=''` but `reasoning_content` populated
2. `LLMClient.chat()` line 163: `message.content` is empty → falls to `result = str(message)` (line 169)
3. `_is_valid_summary()` checks for keywords in the reasoning_content → **passes spuriously**
4. Pipeline output JSON contains ~3KB of system prompt thinking trace instead of executive summary

## Non-LLM Components in the Flow

The flow also contains purely algorithmic components that interact with prompts:
- **Conflict detection/resolution** — No LLM, rule-based overlap resolution
- **Feedback signals** — Gradient computation from coverage/profit gaps, no LLM
- **Consensus Engine** — Weighted voting among coordinator (0.40), regional (0.40), service gen (0.20)
- **Shared Context** — Data aggregation, no LLM
