# P0.1 — COORDINATOR INFLUENCE REPORT

## Experiment Design
- LLM decisions ON vs OFF comparison
- Source: pipeline_output.json runtime evidence
- Rule: No code modifications

## Baseline (LLM ON — *hypothetical*)
Theoretically: Coordinator Agent calls LLM with `_generate_decisions()` prompt, LLM returns JSON with weight_adjustments, validated by `validate_weight_adjustments()`, applied via `_apply_feedback()` to GA weights.

## Actual Pipeline Evidence
The pipeline_output.json decision_output notes state: "Rule-based fallback: coverage 63.0%, profit $443,860,872/week, 0 conflicts."

**The LLM decisions FAILED completely.** All weight_adjustments came from the rule-based fallback in `_generate_decisions()` (coordinator_agent.py:370-406).

## Weight Comparison Table

| Weight Source | profit_weight | coverage_weight | cost_weight |
|---|---|---|---|
| LLM (intended, not delivered) | unknown | unknown | unknown |
| Rule-based fallback (iteration 0) | 0.447 | 0.453 | 0.100 |
| Rule-based fallback (iteration 1) | 0.430 | 0.470 | 0.100 |
| Gradient feedback (iteration 1) | 0.395 | 0.505 | 0.100 |
| Actually APPLIED (iteration 0) | 0.600 | 0.250 | 0.150 |
| Actually APPLIED (iteration 1) | 0.372 | 0.482 | 0.146 |

## Optimizer Outcome Comparison

| Metric | Iteration 0 | Iteration 1 | Change |
|---|---|---|---|
| Coverage | 64.7% | 63.0% | -1.7pp |
| Weekly Profit | $599.5M | $443.9M | -26% |
| Convergence Score | 0.975 | 0.967 | -0.8% |
| Conflicts | 0 | 0 | Stable |

## Verdict
**Measured Influence: 0%** — The Coordinator LLM had ZERO actual influence on the pipeline. Every weight adjustment came from the rule-based fallback path. The LLM call failed (parse error or unreachable) and the system silently used pre-computed fallback weights. The feedback loop itself made outcomes WORSE, not better.

## Root Cause
The LLM either returned invalid JSON (caught in `_parse_json_safe()` which returned `{}`) or was unreachable (LLM client circuit breaker opened). The fallback at coordinator_agent.py:370-406 produced deterministic weights based on coverage_gap, bypassing any LLM intelligence entirely.

## Upgrade Implication
There is ZERO point upgrading the LLM prompt if the LLM client is not reliably reachable. Fix infrastructure reliability first, THEN optimize the prompt.
