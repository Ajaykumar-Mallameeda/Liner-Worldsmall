# REPORT 6: FAILURE MODE ANALYSIS

## 1. CASE-BY-CASE EVIDENCE

### Case 1: Iteration 0 to 1 — Profit Drop ($644.9M to $401.3M, -37.8%)

**Trace of what happened (confirmed from pipeline source):**

*Step 1:* The orchestrator initializes `objective_mode = "profit_first"` with weights from `optimizer_config.py`: profit=0.60, coverage=0.25, cost=0.15.

*Step 2:* The GA runs for 120 generations with these weights, producing iteration 0: profit=$644.9M, coverage=63.5% (average_coverage metric).

*Step 3:* The coordinator evaluates iteration 0. The LLM call in `_generate_decisions()` fails to return valid JSON. The rule-based fallback at line 373-391 of coordinator_agent.py triggers:
```
cov_gap = max(0, 70.0 - 63.52) = 6.48
cov_boost = min(0.2, 6.48/100.0) = 0.0648
profit_weight = max(0.3, 0.5 - 0.0648) = 0.435
coverage_weight = min(0.6, 0.4 + 0.0648) = 0.465
cost_weight = 0.1
```

*Step 4:* The orchestrator's `_apply_feedback()` at line 209-308 applies these weights to the Problem object. The GA is re-run for iteration 1 with the new objective.

*Step 5:* The GA produces iteration 1: profit=$401.3M, coverage=60.4%. BOTH decreased.

*Step 6:* The early-stop condition at line 632 (`iter_coverage - prev_coverage < 1.0`) triggers because 60.4 - 63.5 = -3.1 < 1.0. The pipeline terminates.

**The fundamental mechanism is a convergence disruption:**

The GA had already settled into an optimal region of the solution space under the profit=0.60 objective. Changing the objective function mid-optimization is equivalent to asking the GA to solve a different problem. The population that was optimal for profit is no longer fit for the new objective. The GA must re-explore, but it starts from a population that was already converged (low diversity), making it hard to find the new optimum within the remaining generation budget.

The profit weight was cut by 27.5% (0.60 to 0.435) and the coverage weight was increased by 86% (0.25 to 0.465). This is a large perturbation. A service that contributed $1M to profit but served 100 TEU would have contributed $600K to the old fitness but only $435K to the new fitness -- a 27.5% reduction in its fitness contribution, even if its performance was unchanged.

**Why coverage also dropped (not just profit):**

The GA's search was disrupted for ALL objectives, not just profit. The GA needs diversity to search effectively. When the objective changes, the old population has low diversity (it converged under the old objective), so it cannot effectively explore the new landscape. Coverage dropped because the GA couldn't find good solutions for ANY metric before being terminated.

---

### Case 2: INTEL Benchmark Regression (Profit: $525.5M to $451.7M, -14%)

**Source of baseline values:**

The benchmark script `run_intelligence_benchmark.py` defines hardcoded `DEFAULT_BASELINE` at line 385-404. These values were taken from a prior pipeline run WITHOUT the AI coordinator active (the P1 stable state). The baseline coverage of 48.25% uses the `summary_metrics.coverage` metric (total_satisfied / true_global_demand), not the `average_coverage` metric used by the coordinator for decision-making.

**Why the benchmark regresses:**

All 3 benchmark runs execute the orchestrator with the coordinator active. The coordinator's LLM calls fail (no API key or model failure is expected), so the rule-based fallback triggers. This shifts weights from profit=0.60 toward coverage=0.465, disrupting GA convergence as described in Case 1.

The benchmark uses `summary_metrics.coverage` for comparison, which is different from the `average_coverage` that the coordinator optimizes. This means:
- The coordinator optimizes for `average_coverage` (inflated, simple average of 5 region percentages)
- The benchmark measures `summary_metrics.coverage` (true demand-weighted coverage)
- The baseline (48.25%) is also summary coverage

**The critical finding:** Coverage is essentially unchanged (48.25% baseline vs 48.6% actual), despite the coordinator intentionally shifting weights to improve it. The weight shift sacrificed $73.8M/week in profit with ZERO coverage gain.

**Missing instrumentation:** The benchmark does not record per-iteration LLM success/failure status, so we cannot distinguish "LLM made a bad decision" from "LLM failed, fallback activated." Given the evidence from pipeline_output.json (the fallback notes say "Rule-based fallback"), we can infer ALL benchmark runs used the fallback.

---

### Case 3: Run-to-Run Variance (Profit CV=6.5%, Range $410M-$476M)

The benchmark's 3 runs show:
| Run | Seed | Profit | Coverage | Iterations |
|-----|------|--------|----------|------------|
| 1   | 42   | $475.9M | 49.9% | 2 |
| 2   | 43   | $469.0M | 46.6% | 2 |
| 3   | 44   | $410.3M | 49.4% | 3 |

The profit coefficient of variation (CV = std/mean) is 6.5% (29.4M/451.7M). This is within the normal range for stochastic optimization (GA + MILP) on a problem of this scale. Typical GA variance on large combinatorial problems is 5-15% depending on population size, generations, and mutation rate.

Critically, the regression from baseline ($525.5M - $451.7M = $73.8M) is only 11% larger than the run-to-run range ($475.9M - $410.3M = $65.6M). This means the coordinator effect cannot be cleanly separated from normal GA noise at 3 runs.

The run with 3 iterations (seed 44) produced the lowest profit ($410.3M), suggesting that more iterations cause more weight-shifting disruption. Each additional iteration adds a new weight adjustment, further destabilizing the GA.

---

## 2. AGGREGATION ARTIFACT DEEP DIVE

This is the most consequential finding. The system uses TWO different coverage metrics:

**Metric A: `average_coverage` (used for decision-making)**
- Computed in `CoordinatorAgent._calculate_global_metrics()` at line 235 of coordinator_agent.py
- Formula: `sum(coverage_percent of each region) / number_of_regions`
- This is a SIMPLE AVERAGE of per-region coverage percentages
- All regions weighted equally regardless of their total demand

**Metric B: `summary_metrics.coverage` (used for true reporting and benchmark comparisons)**
- Computed in `OrchestratorAgent.aggregate_results()` at line 176-177 of orchestrator_agent.py
- Formula: `total_satisfied_demand / true_global_demand * 100`
- This is a DEMAND-WEIGHTED coverage metric

**The discrepancy at iteration 1:**
- Metric A: 60.4% (simple average of 5 regions)
- Metric B: 44.9% (demand-weighted)
- Difference: 15.5 percentage points

**Why Metric A is inflated:**

The 5 regions have vastly different total demand:

| Region | Total Demand | Coverage | Weight in Metric A | Weight in Metric B |
|--------|-------------|---------|--------------------|--------------------|
| Asia | 216,372 TEU | 69.4% | 20% (1/5) | 13% |
| Europe | 350,328 TEU | 44.7% | 20% (1/5) | 21% |
| Americas | 827,329 TEU | 26.7% | 20% (1/5) | 50% |
| Africa | 69,312 TEU | 79.5% | 20% (1/5) | 4% |
| Middle East | 203,396 TEU | 81.9% | 20% (1/5) | 12% |

Americas has 50% of total demand but the lowest coverage (26.7%). Under Metric A, it gets only 20% weight. Under Metric B, it gets 50% weight. This artificially inflates Metric A by ~15pp.

**Systemic impact:** The coordinator makes weight-adjustment decisions based on Metric A = 60.4%, calculating a coverage gap of only 9.6pp to target (70.0 - 60.4). Under Metric B, the true coverage gap is 25.1pp (70.0 - 44.9). This means:
1. The system dramatically underestimates how far it is from the coverage target
2. The weight adjustments (cov_boost = cov_gap/100 = 0.096) are too small to address the real gap
3. The early-stop condition checks `average_coverage`, not true coverage, so it may converge prematurely

---

## 3. THEORY EVALUATION MATRIX

### Iteration 0 to 1: Profit Drop (-37.8%)

| Theory | Evidence | Probability |
|--------|----------|-------------|
| **A: Incorrect Reasoning** | The rule-based fallback assumes shifting weight FROM profit TO coverage will increase coverage. This is the standard GA assumption. However, the GA had already converged to a population optimized for profit=0.60. Changing the objective mid-run disrupts convergence. The weight shift was intended to help coverage, but BOTH metrics decreased. This is a classic failure mode in dynamic multi-objective optimization: changing the Pareto-front weighting after convergence requires restarting the population, not just rerunning with new weights. | **HIGH** |
| **B: Incorrect Magnitude** | The weight shift was 0.60 -> 0.435 on profit (27.5% reduction) and 0.25 -> 0.465 on coverage (86% increase). This is a large single-step perturbation. A gentler shift (e.g., 0.50/0.35/0.15) might have preserved more profit while still modestly adjusting coverage. However, the fallback formula's cov_boost parameter (cov_gap/100.0 for decisions, cov_gap/100.0*1.5 for gradient) is calibrated to produce small adjustments for small gaps. For a 6.48pp gap, the boost is only 0.065-0.097, which IS moderate. The problem is less the magnitude and more that ANY significant weight shift disrupts a converged GA population. | **MEDIUM** |
| **C: Optimizer Noise** | The benchmark shows normal GA profit variance of CV=6.5% ($29.4M std). The observed profit drop ($244M) is 8.3 standard deviations below the iteration 0 profit. This is far beyond normal noise. GA noise alone cannot explain a 37.8% profit drop. | **LOW** |
| **D: Capacity Constraint** | Coverage dropped by 3.1pp (from 63.5% to 60.4%) — it did NOT stay fixed. If the system had hit a hard capacity constraint, coverage would have remained constant regardless of weight shifts. The fact that coverage DECREASED suggests GA disruption, not a fundamental constraint. The capacity constraint theory fails to explain the drop in profit — increasing coverage weight should increase costs (by deploying more services) but should not inherently destroy profit from EXISTING services. | **LOW** |
| **E: Aggregation Artifact** | The iteration 0 coverage (63.5%) and iteration 1 coverage (60.4%) are both the same metric (average of per-region percentages), so the RELATIVE comparison is valid. However, the COVERAGE GAP computed by the system (6.48pp at iteration 0) is approximately half the TRUE gap under the demand-weighted metric (~25pp). This causes the system to apply insufficient corrective force. The 63.5% figure is artificially inflated by averaging small high-coverage regions (Africa, Middle East, Asia) equally with the large low-coverage region (Americas). | **HIGH** |

**ROOT CAUSE (Profit Drop):** A combination of A and E. The incorrect reasoning that weight-shifting alone improves coverage (Theory A) failed because the GA was disrupted. This was compounded by the aggregation artifact (Theory E) that systematically understated the coverage gap, causing the system to apply incorrectly calibrated corrections. With the TRUE coverage gap (25pp instead of 6.5pp), the fallback formula would have applied a stronger coverage boost (cov_boost = 0.25 instead of 0.065), potentially producing very different weights. But even then, the fundamental convergence-disruption problem would remain.

### Iteration 0 to 1: Coverage Drop (-3.1pp)

| Theory | Evidence | Probability |
|--------|----------|-------------|
| **A: Incorrect Reasoning** | Same as above. The weight shift was specifically intended to increase coverage, yet coverage decreased. The reasoning that increasing the coverage weight in the GA objective drives higher coverage FAILS when the GA has already converged on a different objective. The mechanism: the old population was Pareto-optimal for the old objective; the new objective reorders the fitness landscape; high-fitness individuals for the new objective are rare in the old population; the GA cannot find them before the search terminates. | **HIGH** |
| **B: Incorrect Magnitude** | The coverage weight increased by 86% (0.25 to 0.465). This is a dramatic increase. A smaller increase (e.g., 0.25 to 0.35) might have been less disruptive while still providing directional guidance. However, the fallback formula is proportional to the gap, so a smaller gap would produce a smaller increase. The fundamental issue is that ANY weight change disrupts the converged GA population, regardless of magnitude. | **MEDIUM** |
| **C: Optimizer Noise** | Coverage CV = 1.44pp absolute / 48.6% mean = ~3% relative. A 3.1pp drop is ~2 standard deviations below the iteration 0 coverage. While this COULD be noise (p ~ 0.05), the fact that it coincides directionally with the weight shift makes noise an unlikely sole cause. | **MEDIUM-LOW** |
| **D: Capacity Constraint** | If coverage were at a hard capacity limit, it would stay constant. It dropped, so this does not explain the drop. However, capacity constraints DO explain why the weight shift failed to INCREASE coverage — the system may be operating near the capacity frontier where additional coverage requires disproportionately more resources, and the GA couldn't find those solutions before terminating. | **MEDIUM** |
| **E: Aggregation Artifact** | The 3.1pp drop (63.5% → 60.4%) is in Metric A (simple average). Under Metric B (demand-weighted), the iteration 1 coverage was only 44.9%, but we don't have the iteration 0 Metric B value because the `aggregate_results()` method is only called once at the end of the pipeline, not after each iteration. The iteration_audit only records Metric A. The system uses Metric A for decision-making, so even if the true coverage metric was unaffected by the weight shift, the system would think coverage dropped. We cannot determine whether the Metric B coverage also dropped or stayed stable between iterations. | **HIGH** |

**ROOT CAUSE (Coverage Drop):** Primarily Theory A (Incorrect Reasoning) amplified by Theory E (Aggregation Artifact). The system made decisions based on an inflated coverage metric and assumed weight-shifting would improve it, not accounting for the convergence-disruption effect. The 3.1pp drop in Metric A may or may not correspond to an actual drop in true coverage — we have no iteration 0 Metric B reading to compare.

### Benchmark Regression (Profit: -14%, Coverage: Flat)

| Theory | Evidence | Probability |
|--------|----------|-------------|
| **A: Incorrect Reasoning** | The coordinator's weight-shifting logic assumes that (1) changing GA weights improves coverage and (2) this is worth the tradeoff in profit. Both assumptions failed. Coverage was flat (48.25% baseline → 48.6% actual) while profit dropped 14%. The coordinator-intended optimization direction did not produce the intended result. | **HIGH** |
| **B: Incorrect Magnitude** | The benchmark aggregates across 3 runs with different seeds. Each run experienced weight shifts as the fallback triggered. The total profit impact ($74M/week, 14% below baseline) exceeds normal GA variance. A gentler weight-adjustment strategy might have produced smaller profit loss, but the weight-magnitude theory cannot explain why coverage also failed to improve. | **LOW** |
| **C: Optimizer Noise** | With only 3 runs and profit CV=6.5%, there is a ~15% probability that the observed mean ($451.7M) could arise from noise alone if the true mean were $525.5M (given n=3, expected std of mean = 29.4M/sqrt(3) = 17.0M; z = (525.5-451.7)/17.0 = 4.3). This is 4.3 sigma, p < 0.001. Not noise alone. | **LOW** |
| **D: Capacity Constraint** | The flat coverage (48.25% → 48.6%) is consistent with hitting a capacity constraint. The GA cannot increase coverage beyond what the fleet and port infrastructure allow, regardless of weight settings. This is the strongest theory for why coverage did NOT improve. The Americas region, at 26.7% coverage with 827k TEU demand, may be fundamentally constrained by available vessel capacity or port throughput. | **MEDIUM** |
| **E: Aggregation Artifact** | The benchmark uses the true demand-weighted coverage (Metric B) for comparison. The coordinator optimizes for the simple-average coverage (Metric A). This mismatch means the coordinator was optimizing a different objective than what the benchmark measures. The coordinator thought it needed a 9.6pp improvement (to reach 70% Metric A), but the actual coverage gap to the benchmark baseline was only ~22pp (to reach 70% Metric B). Wait — that's not the issue. The BASELINE coverage (48.25%) already uses Metric B, and the ACTUAL coverage (48.6%) also uses Metric B. So the comparison is consistent within Metric B. The issue is that the COORDINATOR uses Metric A for its decisions, with a target of 70% metric A. The system was trying to achieve 70% of an inflated metric, which might not even be achievable, and was making decisions based on the wrong signal. | **HIGH** |

**ROOT CAUSE (Benchmark Regression):** The coordinator introduced weight-shifting that disrupted GA convergence on the profit objective without improving coverage (whose flatness is best explained by capacity constraint + metric mismatch). The LLM fallback was triggered, so no "intelligence" was actually applied — only a heuristic weight-shift that made things worse. The 14% profit regression is the measurable cost of adding the coordinator to the pipeline in its current form.

---

## 4. ROOT CAUSE SUMMARY

| | Case 1: Iter 0→1 Profit | Case 1: Iter 0→1 Coverage | Case 2: Benchmark |
|---|---|---|---|
| **Primary** | A (Incorrect Reasoning) | A (Incorrect Reasoning) | A + E (Aggregation Artifact) |
| **Contributing** | E (Aggregation Artifact) | E (Aggregation Artifact) | D (Capacity Constraint) |
| **Underlying mechanism** | Weight-shifting disrupts converged GA | Same as profit + inflated metric | LLM falls back to weight heuristic; no intelligence applied |

**The three cases share a common root cause:** The coordinator's weight-adjustment logic (both rule-based fallback and gradient-based feedback) assumes that changing GA objective weights during an optimization run will move the solution in the intended direction. This assumption is false when the GA has already converged. Changing weights mid-run disrupts the GA population, causing it to lose ground on ALL objectives, not just the one being de-emphasized.

Additionally, the system uses a systematically inflated coverage metric (simple average of per-region percentages) for decision-making, while the true metric (demand-weighted) tells a much worse story. This means the system consistently underestimates the coverage problem.

**Recommended fixes:**
1. Replace `average_coverage` (simple average) with demand-weighted coverage in ALL coordinator evaluation logic
2. Implement population restart or re-seeding when weights are changed, rather than continuing from the converged population
3. Add termination criteria based on true coverage (Metric B), not Metric A
4. Implement LLM success/failure logging in the benchmark to distinguish "AI made bad decision" from "AI was not available"
5. Increase benchmark iteration count (n >= 10) to separate coordinator effects from optimizer noise
