# REPORT 4A: HEURISTIC vs AI COMPARISON

## Pipeline State at Analysis Point
- **Iteration**: 1 (iteration_audit size = 2)
- **Coverage went from 63.5% to 60.4%** despite coverage weight increasing from 0.25 to 0.465 (a +0.215 increase was _counterproductive_)
- **Profit cratered from $645M to $401M** (38% drop) for zero coverage gain
- **Regional variance**: 55.2pp (min 26.7% Americas, max 81.9%)
- **LLM path status**: BROKEN — `_parse_json_safe` returned empty dict or non-conforming JSON; rule-based fallback fired (confirmed by `notes: "Rule-based fallback..."`)

---

## Dimension-by-Dimension Comparison

| Dimension | Actual (Fallback) | Ideal LLM (if working) | Difference & Impact |
|---|---|---|---|
| **Multi-factor analysis** | Single-factor (coverage_gap only) | Multi-factor (profit, coverage, cost, conflicts, regions, trends, trade-off sensitivity) | **Critical gap**: Fallback ignores that the LAST coverage boost made things worse. LLM could detect this failure mode and REVERSE direction. |
| **Metric grounding** | 1 metric (coverage_gap = 9.57pp) | Reads all 10+ metrics in prompt + weak_regions breakdown | Fallback ignores profit_gap=0 (healthy), variance=55.2pp (severe imbalance), margin=67.2% (healthy), and convergence trajectory (degrading) |
| **Regional awareness** | None (global average only) | Per-region weak_regions list (Asia 69.4%, Europe 44.7%, Americas 26.7%) | **Critical gap**: Fallback applies a uniform global weight shift. This penalizes well-performing regions (81.9% coverage regions get their weights diluted) while barely helping the real problem region (Americas at 26.7% needs targeted help, not global rebalancing) |
| **Trend awareness** | None (static gap) | Can compare iteration-over-iteration deltas | **High-value gap**: Coverage went DOWN 3.1pp while coverage weight went UP -- clear signal the weight adjustment is BROKEN or the GA hasn't had time to respond. LLM could distinguish "the weight change hasn't propagated yet" from "the weight change is counterproductive" |
| **Adaptivity** | Fixed formula (same math every time) | Context-dependent reasoning | LLM could produce non-linear responses: small adjustments when close to target, aggressive when far, reversal when experiments prove counterproductive |
| **Reliability** | 100% (deterministic) | 0% (fails to parse JSON every time) | **Fallback wins here**. LLM produces text the JSON parser cannot consume. Every path through `_parse_json_safe` fails -- even the regex fallback `re.search(r"\{.*\}", text, re.DOTALL)` doesn't salvage the output. |

---

## Root Cause Analysis: Why LLM Fails

From `src/llm/client.py`:
1. The LLM client uses OpenRouter free-tier models (`meta-llama/llama-3.3-70b-instruct:free` and fallbacks are all free tier)
2. The circuit breaker opens after 5 failures -- but since the coordinator prompt requests JSON output, and the free-tier models are instruction-tuned general models (not JSON-specialized), they produce natural-language responses instead of valid JSON
3. `_parse_json_safe` tries markdown fence stripping, then full JSON parse, then regex extraction -- ALL fail

The fundamental issue: **the prompt demands JSON, but the model is a free-tier general LLM that defaults to natural language**. The system is designed to handle this via fallback, but the fallback is too simplistic.

---

## Trace of Actual vs. Ideal Weight Adjustments

### Iteration 0 -> 1 (what ACTUALLY happened):
```
Initial:     profit=0.600  coverage=0.250  cost=0.150  → profit=$645M, coverage=63.5%
Fallback:    profit=0.435  coverage=0.465  cost=0.100  → profit=$401M, coverage=60.4%
Gradient:    profit=0.356  coverage=0.544  cost=0.100  (not applied, would be even worse)
```

### What an IDEAL adaptive system would have done:
```
Observation: coverage went DOWN 3.1pp despite +0.215 coverage boost
             profit dropped 38% (alarm bell)
Signal:      "Coverage-weight increase was counterproductive. Revert toward profit."

Ideal iter 1 weights: profit=0.65  coverage=0.20  cost=0.15  (revert toward profit)
```

The **gradient feedback** actually makes the WRONG call -- it INCREASES coverage weight further (from 0.465 to 0.544) despite evidence it hurts. This is because the gradient formula is purely proportional to the gap, with no "effectiveness memory."

---

## Summary Judgement

The fallback heuristic is **reliable but dangerously simple**. It has no mechanism to:
- Detect that its own previous recommendation was counterproductive
- Consider regional imbalance
- Evaluate profit/coverage trade-off efficiency
- Know when to stop pushing the same direction

The LLM (if working) could do all of these, but **is consistently unreliable** (0% JSON compliance rate).

The gradient formula (`_generate_feedback_signals`) is the most interesting case -- it's slightly more nuanced than the fallback (includes profit_gap), but makes the same fundamental error: it pushes harder in the same direction that already failed.
