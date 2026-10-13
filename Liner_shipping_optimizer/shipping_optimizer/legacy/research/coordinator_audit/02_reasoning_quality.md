# REPORT 2: REASONING QUALITY ASSESSMENT

## Weight Change Summary

| Metric | Iteration 0 Weight | Iteration 1 Weight | Absolute Change | % Change |
|---|---|---|---|---|
| profit_weight | 0.60 (profit-first config) | 0.435 (rule-based fallback) | -0.165 | -27.5% |
| coverage_weight | 0.25 (profit-first config) | 0.465 (rule-based fallback) | +0.215 | +86.0% |
| cost_weight | 0.15 (profit-first config) | 0.10 (hardcoded constant) | -0.050 | -33.3% |

### Outcome of the weight change

| Metric | Iteration 0 Result | Iteration 1 Result | Delta |
|---|---|---|---|
| Weekly profit | $644,979,613 | $401,270,616 | -37.8% |
| Coverage | 63.5% | 60.4% | -3.1pp (worsened) |
| Coverage gap to 70% | 6.48pp | 9.57pp | +3.09pp (worsened) |

**The weight change made both objectives worse.** Coverage declined despite the massive (+86%) increase in coverage weight. The pipeline stopped because coverage declined, triggering the early-stopping condition at `orchestrator_agent.py` line 632 (`iter_coverage - prev_coverage < 1.0`).

**Critical flow fact:** The LLM path never produced valid weight adjustments. The "AI-driven" weight changes are actually a deterministic rule-based fallback that activates when the LLM fails to return parseable JSON. The trace log tag `AI_GENERATED` fires with `tag=AI_FALLBACK, source="rule"`.

---

## WEIGHT-BY-WEIGHT REASONING ANALYSIS

### 1. profit_weight: 0.60 to 0.435

#### Why it decreased

The decrease is driven by a SINGLE metric: the coverage gap of 6.48pp (coverage 63.5% vs target 70%). The formula, from `coordinator_agent.py` line 382-386:

```python
cov_gap = max(0, COVERAGE_TARGET - metrics["average_coverage"])  # 6.48
cov_boost = min(0.2, cov_gap / 100.0)  # 0.0648
profit_weight = max(0.3, 0.5 - cov_boost)  # 0.435
```

The logic is simple arithmetic: move weight from profit to coverage proportional to the coverage deficit. There is no evaluation of whether profit emphasis is working or failing.

#### Metrics considered

| Metric | Considered? | How |
|---|---|---|
| Coverage gap (6.48pp) | YES | The sole input to cov_boost |
| Actual profit ($645M/wk) | NO | Profit is $645M -- massively above PROFIT_FLOOR of $0, but this is ignored |
| Profit-per-service/$M breakdown | NO | Regional profit ranges from -$48M to +$390M, ignored |
| Negative-margin services | NO | Several services operate at -62% to -254% margin, ignored |
| Revenue per TEU ($3,017) | NO | Revenue efficiency not considered |
| Starting weight (0.60) | NO | Formula adjusts from 0.50 default, not from 0.60 actual |

#### Key reasoning flaw

The formula assumes the starting point is the "legacy" default (profit=0.50), but the actual starting point was profit-first mode (profit=0.60). This means the formula is already one step behind: it reduces profit from 0.50 when the actual value was 0.60. The total reduction is 0.165, but the formula only "knows about" 0.065 of it. The extra 0.10 reduction is an artifact of switching from profit-first mode to the legacy default baseline that the formula uses.

---

### 2. coverage_weight: 0.25 to 0.465

#### Why it increased

Again, driven by the SINGLE metric of coverage_gap = 6.48pp:

```python
coverage_weight = min(0.6, 0.4 + cov_boost)  # 0.465 for gap=6.48
```

#### Metrics considered

| Metric | Considered? | How |
|---|---|---|
| Coverage gap (6.48pp) | YES | The sole input |
| Regional coverage disparity | NO | Americas at 26.7% vs Asia at 69.4% (range of 55.2pp variance) is ignored |
| Why coverage is low (capacity, connectivity) | NO | No root cause analysis |
| Starting weight (0.25) | NO | Formula jumps from 0.40 default, ignoring that coverage started at 0.25 |
| Marginal value of additional coverage weight | NO | No assessment of whether GA responds to weight changes |

#### Key reasoning flaw

The +86% increase in coverage weight was massive, yet coverage DECLINED. The reasoning assumed a positive correlation between coverage weight and actual coverage that does not hold empirically. The formula does not learn from iteration history -- the same formula would produce the same adjustment regardless of past failures.

---

### 3. cost_weight: 0.15 to 0.10

#### Why it decreased

There is NO reasoning. The cost weight is a hardcoded constant of 0.1 in the rule-based fallback (`coordinator_agent.py` line 386). The gradient path also hardcodes it:

```python
# Rule-based fallback: cost_weight = 0.1
# Gradient path: cost_weight = max(0.05, 0.10 - prof_boost) → stays 0.10
```

The decrease from 0.15 to 0.10 is purely because the formula always sets cost=0.1, and the starting config had cost=0.15. No cost metric (operating cost, fuel cost, transship cost, port cost, cost per TEU) factors into the decision.

#### Metrics considered

| Metric | Considered? | How |
|---|---|---|
| Total operating cost ($196M) | NO | Ignored |
| Cost per TEU ($2,484) | NO | Ignored |
| Profit margin (67.2%) | NO | Ignored |
| Fuel vs transship vs port cost mix | NO | Ignored |
| Cost per service ($4.5M) | NO | Ignored |
| Any cost metric | NO | None whatsoever |

#### Classification of cost_weight: UNGROUNDED

---

## REASONING QUALITY TABLE

| Weight Decision | Target Objective | Reasoning Quality | Multi-Factor? | Proportional to Gap? | Classification |
|---|---|---|---|---|---|
| profit_weight 0.60 -> 0.435 | Shift emphasis from profit to coverage | LOW -- single-metric tunnel vision, ignores $645M actual profit, ignores starting point | NO | YES (linear: cov_boost = gap/100) | PARTIALLY GROUNDED (gap metric is valid but other metrics ignored) |
| coverage_weight 0.25 -> 0.465 | Increase coverage toward 70% target | LOW -- assumes weight increase guarantees coverage increase, ignores regional disparities, no root cause | NO | YES (linear: cov_boost = gap/100) | GROUNDED IN GAP (proportional to the measured gap, but empirically incorrect) |
| cost_weight 0.15 -> 0.10 | (None declared) | NONE -- no reasoning, hardcoded constant | NO | NO (not derived from any gap) | UNGROUNDED (no metric basis) |

---

## AGGREGATE ASSESSMENT

### Is the reasoning MULTI-FACTOR or SINGLE-FACTOR?

**SINGLE-FACTOR.** All three weight changes are driven by a single numeric gap (coverage_gap). Even the multi-dimensional nature of the problem is acknowledged in `_evaluate_system` (which checks 5 dimensions: coverage, profit, cost, conflicts, variance), but the weight formulas do not use this evaluation. The evaluation score of 3/5 at iteration 0 flagged profit as okay, cost as okay, conflicts as okay, but coverage AND variance as problems -- yet the weight adjustment only responds to average coverage, ignoring variance entirely.

### Does the reasoning consider trade-offs between objectives?

**NO.** The reasoning assumes a zero-sum trade-off between profit and coverage weights (every 0.01 shifted from profit to coverage improves coverage by some amount). But:
- The actual result showed BOTH metrics declining (profit -37.8%, coverage -3.1pp)
- There is no model of the relationship between weight changes and outcome changes
- There is no mechanism to detect that the trade-off is not working and revert
- No coordination between the three weight adjustments (cost is just set to a constant)

### Is the weight magnitude proportional to the gap?

**YES, for profit/coverage; NO, for cost.**
- profit and coverage: proportional via `cov_boost = gap/100`, clamped to [0, 0.2] for the fallback path and [0, 0.25] for the gradient path
- cost: hardcoded to 0.1 regardless of any gap or performance metric

However, "proportional" in a linear sense (gap/100) is chosen arbitrarily. There is no calibration showing that a 6.48pp gap should shift weights by 6.48% of the control range. The multiplier 1/100 and the clamps [0.3, 0.6] are engineering guesses.

### Does the reasoning correctly handle edge cases?

| Edge Case | Handled? | Details |
|---|---|---|
| Already converged (coverage >= 70%) | PARTIALLY | If no rerun needed, the pipeline stops before applying feedback. But if a run converges in one dimension while failing another, weights still shift. |
| Capped iterations | PARTIALLY | The coordinator does stop producing rerun requests at iteration cap (MAX_RERUN_ITERATIONS - 1 = 2), but the weight adjustment doesn't taper as the cap approaches. |
| Zero conflicts | YES | Correctly produces no conflict-related actions. |
| Widening gap (coverage worsens after weight change) | NO | The system detected coverage declined to 60.4% and stopped. But the weight formula itself has no hysteresis or correction mechanism. |
| Negative profit services in portfolio | NO | Several services at -62% to -254% margin are ignored by the weight formula. |
| Regional imbalance (55pp variance) | NO | The evaluation flags it ("coverage variance 55.2% -- regions imbalanced") but weight adjustments ignore it. |
| LLM failure | PARTIALLY | The fallback produces usable weights, but the source tag in _apply_feedback says "decisions (LLM)" even when it's the rule-based path, mislabeling the decision provenance. |

---

## CONTEXTUAL FINDINGS

### The LLM never successfully produced weights

The `_generate_decisions` method at `coordinator_agent.py` line 353 calls `self.call_llm(prompt, temperature=0.1)`, then `_parse_json_safe(raw)`. For both iteration 0 and iteration 1, the LLM failed to return valid JSON containing an `actions` key, so the fallback on lines 357-402 was used exclusively. This means the system has never actually exercised the LLM-driven weight decision path in production -- all weight adjustments to date are from the deterministic rule-based fallback.

### The gradient path was never applied

The `_apply_feedback` method in `orchestrator_agent.py` always prefers `decisions["weight_adjustments"]` (line 233-235) over `feedback["weight_adjustments"]` (line 236-238). Since the decisions dict always has weight_adjustments (from the fallback), the feedback gradient path is never reached. The gradient values (profit=0.356, coverage=0.544 for the alternative path) exist in the output but are never used.

### Benchmark evidence contradicts the assumptions

The INTEL benchmark shows:
- Run 1 (seed 42): profit $475.9M, coverage 49.9%, 2 iterations
- Run 2 (seed 43): profit $469.0M, coverage 46.6%, 2 iterations
- Run 3 (seed 44): profit $410.3M, coverage 49.4%, 3 iterations

All three runs produce coverage below 50%, far from the 70% target. Profit averages $452M vs a golden baseline of $526M (REGRESSION). The experiment_analysis.py demo mode showing "+3.02 contribution score for AI" was based on synthetic data assuming AI was better -- it is not reflective of actual performance.

### Root cause diagnosis

The weight adjustment formula has a fundamental design flaw: it assumes the GA objective weights are the primary lever for improving coverage, but:
1. The GA's response to weight changes is nonlinear and unpredictable
2. Coverage may be constrained by real factors (capacity, port connectivity, fleet mix) that no weight change can fix
3. The formula has no feedback loop to detect when its own adjustments are counterproductive
4. The formula ignores the starting point (profit-first mode) and uses the legacy default (0.5/0.4/0.1) as its baseline, creating an unaccounted -0.10 drift in profit weight

---

## FINAL CLASSIFICATION SUMMARY

| Decision | Classification | Rationale |
|---|---|---|
| profit_weight decrease | PARTIALLY GROUNDED | Uses coverage gap as input (grounded), but ignores $645M profit, starting configuration, regional variance, and negative-margin services (ungrounded) |
| coverage_weight increase | PARTIALLY GROUNDED | Proportional to measured coverage gap, but assumes linear GA response that empirically failed; ignores why coverage is low |
| cost_weight decrease | UNGROUNDED | Hardcoded constant; no cost metric of any kind informed this decision |
| System-level decision framework | PARTIALLY GROUNDED | The evaluation function (_evaluate_system) uses 5 metrics properly, but the weight adjustment formulas collapse this to a single metric. The LLM path (intended to provide multi-factor reasoning) has never successfully executed. |
