## REPORT 3: CAUSALITY ANALYSIS -- AI VESSEL ROUTING COORDINATOR

### Overview

This report analyzes five causal chains in the coordinator-driven weight-adjustment pipeline, tracing every recommendation from detection through weight change to measured outcome. The evidence draws from `pipeline_output.json` (single-run iteration audit), `INTEL_BENCHMARK_RESULTS.json` (3-run benchmark), and the decision-output records.

---

### CHAIN 1: COVERAGE DETECTION TO WEIGHT SHIFT (Iteration 0 to Iteration 1)

**Evidence:**
- Iteration 0: profit=$644.9M, coverage=63.5% (region-average), weights=0.60/0.25/0.15, convergence=0.969
- Coordinator correctly detects coverage gap of 6.48pp below 70% target
- LLM invoked but returns invalid JSON (not parseable) -- this is an infrastructure failure
- Rule-based fallback computes cov_boost=0.0648 and produces weight recommendation
- Orchestrator applies weights: profit=0.435, coverage=0.465, cost=0.1
- Iteration 1: profit=$401.3M (-37.8%), coverage=60.4% (-3.1pp), convergence=0.954, gap=9.57pp (WIDER)

**Analysis of the weight computation:**
The rule-based fallback converted a 6.48pp gap (0.0648) into coverage weight of 0.465 -- an 86% increase from the original 0.25. The freed 0.05 from cost weight (0.15 to 0.1) plus 0.165 taken from profit weight (0.6 to 0.435) were both transferred to coverage. This represents a 3.3x amplification of the raw cov_boost. The adjustment was disproportionate to the gap magnitude.

**Causality:**
The diagnostic reasoning (coverage below target --> prioritize coverage) is logically sound. However, the implementation was flawed in two ways: (a) the LLM failed, bypassing any context-aware adjustment, and (b) the rule-based fallback applied an extreme magnitude that the optimizer could not productively use.

- **Classification:** INCORRECT
- **Primary cause:** INCORRECT WEIGHT MAGNITUDE
- **Secondary cause:** INCORRECT REASONING (fallback assumed larger weight always yields more coverage, ignoring optimizer stability constraints)

---

### CHAIN 2: LLM FAILURE TO FALLBACK WEIGHT FORMULA (Sub-chain of Chain 1)

**Evidence:**
- The LLM was invoked to generate a context-aware weight adjustment for the 6.48pp gap
- LLM returned invalid JSON -- the response could not be parsed
- The rule-based fallback formula executed with cov_boost=0.0648 (the gap as fraction)
- The fallback scaled coverage weight from 0.25 to 0.465, profit from 0.6 to 0.435, cost from 0.15 to 0.1
- The decision_output shows a different weight recommendation (0.404/0.496/0.1) than what was actually applied (0.435/0.465/0.1), indicating the orchestrator further transformed the recommendation before applying

**Analysis:**
The fallback formula is a simple proportional mapping from coverage gap to weight adjustment. It does not account for the non-linear relationship between GA objective weights and solution outcomes. A 6.48pp gap does not justify nearly doubling the coverage weight. The expected gains recorded in decisions (0.6% for Asia, 25.3% for Europe, 43.3% for Americas) were unrealistic -- the system expected the weight change alone to add 1,290 TEU/week (the 25.3% on Europe's baseline) without considering structural constraints like vessel availability and port capacity.

**Causality:**
The LLM failure is an infrastructure/code quality issue, not a reasoning issue per se. But the fallback formula is the chain's causal mechanism, and it produced an inappropriate response.

- **Classification:** PARTIALLY CORRECT (direction was correct; magnitude was wrong)
- **Primary cause:** INCORRECT WEIGHT MAGNITUDE
- **Secondary cause:** INCORRECT REASONING (fallback assumes linear, assumption-free relationship between weight and coverage)

---

### CHAIN 3: GA OPTIMIZER RESPONSE TO WEIGHT CHANGE (Sub-chain of Chain 1)

**Evidence:**
- Iteration 0: GA ran with profit-first weights (0.60/0.25/0.15), convergence=0.969, coverage=63.5%
- Iteration 1: GA ran with balanced weights (0.435/0.465/0.1), convergence=0.954, coverage=60.4%
- GA population=80, generations=120 (same settings both iterations)
- Despite coverage being the dominant objective, the GA found 3.1pp LESS coverage
- The GA also found 37.8% LESS profit

**Analysis of the counterintuitive result:**

Three mechanisms explain why higher coverage weight produced less coverage:

1. **Search trajectory disruption.** The GA was 120 generations into a search optimized for profit-first weights. When weights changed, the fitness landscape shifted -- individuals that were high-fitness under the old weights became low-fitness, and vice versa. The population had to re-evolve under the new fitness function, effectively restarting from a less-adapted state. This explains both the lower convergence score (0.969 to 0.954) and the worse outcome.

2. **Positive correlation between profit and coverage.** In shipping network design, serving more demand (coverage) generates more revenue (profit), up to the capacity constraint. The optimal solutions under profit-first weights are likely also the best coverage solutions. Reducing profit weight does not free the GA to find "more coverage" -- it simply removes the signal that guided the GA toward capacity-efficient service structures. The GA may respond by selecting lower-value routes that happen to have high capacity but low utilization, consuming resources without improving actual demand coverage.

3. **Insufficient generations for re-adaptation.** 120 generations is the same budget given to the first search. But the first search started from random individuals; the second search started from a population adapted to a different objective. This is a harder starting point -- the GA must actively unlearn prior adaptations before it can learn new ones. 120 generations is likely insufficient for this re-adaptation.

**Causality:**
The GA's response to the weight change was predictable given these mechanisms. The weight change did not cause the GA to "fail"; it caused the GA to need to restart its search, and it was not given enough budget to complete the new search.

- **Classification:** INCORRECT (the optimizer did not produce the intended effect)
- **Primary cause:** OPTIMIZER NOISE (search trajectory disruption)
- **Secondary cause:** INCORRECT WEIGHT MAGNITUDE (the aggressive shift amplified reset cost)

---

### CHAIN 4: AI COORDINATOR MODE BENCHMARK (3-run aggregate vs baseline)

**Evidence from INTEL_BENCHMARK_RESULTS.json:**

| Metric | AI Mode (mean, n=3) | Baseline (profit-first) | Deviation | Status |
|--------|---------------------|------------------------|-----------|--------|
| Weekly profit | $451.7M | $525.5M | -14.0% | FAIL |
| Coverage | 48.6% | 48.25% | +0.35pp | PASS |
| Profit margin | 18.3% | 20.85% | -2.5pp | FAIL |
| Convergence | 0.967 | 1.0 | -0.033 | PASS |
| Test score | 0% | 100% | -100% | FAIL |

**Overall: REGRESSION**

Individual run details:
- Run 1 (seed=42): profit=$475.9M, coverage=49.9%, 2 iterations
- Run 2 (seed=43): profit=$469.0M, coverage=46.6%, 2 iterations
- Run 3 (seed=44): profit=$410.3M, coverage=49.4%, 3 iterations

**Analysis:**
The 0.35pp coverage improvement over baseline is practically negligible and well within the noise band of GA stochasticity (+/- 1.4% std on coverage). The -14% profit degradation is economically significant and outside tolerance. The sequential investigation (`pipeline_output.json`) explains why: the weight shift destroyed the profit-maximizing solution structure without finding equivalent replacements, and the GA budget was insufficient to recover.

**Contradiction with experiment_analysis.py demo:**
The experiment_analysis.py script reported AI mode +15.6% profit and -13.7% coverage, with +3.02 contribution score -- but these are synthetic results from a demo script, not actual pipeline runs. The contradiction is resolved by noting different data sources. The real benchmark shows regression.

**Causality:**
The AI coordinator mode caused a clear profit regression with negligible coverage benefit. The causal mechanism is the aggressive and inappropriate weight shifts applied across iterations, which destabilize the GA search without producing compensating coverage gains.

- **Classification:** INCORRECT
- **Primary cause:** OPTIMIZER NOISE (search trajectory destabilization dominates the weight-change signal)
- **Secondary cause:** INCORRECT WEIGHT MAGNITUDE

---

### CHAIN 5: COVERAGE METRIC AGGREGATION ARTIFACT

**Evidence:**
- Iteration audit reports coverage as region-average percentage: iter0=63.5%, iter1=60.4%
- Summary metrics reports coverage as demand-weighted aggregate: final=44.9%
- The difference is ~15pp in the same run
- The coordinator evaluates its decisions against the region-average metric (63.5% vs 70% target)
- But the system's overall performance is reported as the aggregate (44.9%)
- Example demonstrating the arithmetic: if Region A has 1M TEU demand at 40% coverage and Region B has 100K TEU at 80%, region-average=60% but aggregate=43.6% -- matching the observed pattern

**Analysis:**
The region-average metric overweights small regions and underweights large ones. A system that optimizes region-average coverage will preferentially improve coverage in small regions where the denominator is small, achieving high region-average scores while leaving large-demand regions underserved. This is exactly what happened: the final aggregate (44.9%) is lower than the region-average (60.4%) because larger-demand regions (likely Americas at 26.7% coverage) have disproportionately lower coverage.

This is a measurement and goal-design issue, not a weight-change causality. But it affects the interpretation of all chains above: the coordinator was optimizing the wrong metric.

- **Classification:** INCONCLUSIVE (cannot separate from other effects in this analysis)
- **Primary cause:** AGGREGATION ARTIFACT
- **Note:** This artifact means the system may have been working at cross-purposes -- optimizing one metric while being evaluated on another, with the gap between them (15pp) larger than the gap being targeted (6.48pp).

---

### SUMMARY CAUSALITY TABLE

| # | Chain | From | To | Weight Change | Classification | Primary Cause | Evidence Source |
|---|-------|------|----|---------------|----------------|---------------|----------------|
| 1 | Coverage detection --> weight shift applied | Iter 0 | Iter 1 | profit 0.60->0.435 (-27.5%), coverage 0.25->0.465 (+86%), cost 0.15->0.1 (-33%) | INCORRECT | INCORRECT WEIGHT MAGNITUDE | pipeline_output.json iteration_audit[0]->[1]: profit $644.9M->$401.3M, coverage 63.5%->60.4% |
| 2 | LLM failure --> rule-based fallback | Iter 0 | Iter 1 | cov_boost=0.0648 scaled into 86% coverage weight increase | PARTIALLY CORRECT | INCORRECT WEIGHT MAGNITUDE | decision_output notes: "Rule-based fallback: coverage 60.4%"; LLM returned invalid JSON |
| 3 | GA optimizer response to weight shift | Iter 0 | Iter 1 | Coverage weight 0.25->0.465 (dominant objective) | INCORRECT | OPTIMIZER NOISE | convergence 0.969->0.954; coverage dropped despite higher weight; 120 gen insufficient for re-adaptation |
| 4 | AI coordinator mode (3-run benchmark vs baseline) | 0 | 3 | Coordinator-active weights vs profit-first rule-based | INCORRECT | OPTIMIZER NOISE | INTEL_BENCHMARK: profit $451.7M vs $525.5M baseline (-14% FAIL), coverage +0.35pp (negligible PASS), overall REGRESSION |
| 5 | Coverage metric aggregation artifact | 0 | 1 | N/A (measurement methodology) | INCONCLUSIVE | AGGREGATION ARTIFACT | Region-avg 60.4% vs aggregate 44.9% (~15pp gap); coordinator optimizes one, system reports other |

---

### ROOT CAUSE DIAGRAM

```
LLM fails (invalid JSON)
    |
    v
Fallback formula (cov_boost = gap = 0.0648)
    |
    v
Coverage weight jumps 0.25 -> 0.465 (+86%)
    |--- INCORRECT WEIGHT MAGNITUDE
    |--- (3.3x amplification of cov_boost)
    v
GA search trajectory disrupted
    |--- OPTIMIZER NOISE
    |--- Convergence drops 0.969 -> 0.954
    |--- 120 generations insufficient to re-adapt
    v
BOTH metrics decline:
    Profit: $644.9M -> $401.3M (-37.8%)
    Coverage: 63.5% -> 60.4% (-3.1pp)
    Coverage gap: 6.48pp -> 9.57pp (WIDENED)
    |
    v
Coordinator re-evaluates, still below target
    |
    v
Iteration cap (max 3, ran 2) stops further attempts
```

### RECOMMENDATIONS

1. **Fix LLM JSON parsing** to ensure the primary analytical engine works end-to-end.
2. **Cap single-iteration weight change magnitude** at 10-15% of current weight value, not an 86% leap. A marginal adjustment from (0.60/0.25/0.15) to approximately (0.55/0.30/0.15) would have been a safer first step.
3. **Increase GA generations on weight-change iterations** or implement population seeding that preserves high-fitness individuals from the prior search.
4. **Align the optimization metric with the evaluation metric.** If the business cares about demand-weighted aggregate coverage, the GA objective should also use aggregate coverage, not region-average.
5. **Add a "minimum regret" guard:** if a weight change causes degradation across ALL primary metrics (as it did here), revert to the previous weights before proceeding.
