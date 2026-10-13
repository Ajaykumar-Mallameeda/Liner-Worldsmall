# PROJECT X — Runtime Before vs After Comparison

**Before** = the 2026-08-07 Runtime Bible audit + the pre-integration `pipeline_output.json` (2 iterations).
**After** = post-integration execution (final run, all 19 source changes in place).

## 1. Execution Flow

| Dimension | Before | After |
|---|---|---|
| Iterations run | 2 (coverage-gain early-stop fired at iter 1) | **3** (full `MAX_ITERATIONS` bound; stop only on `needs_rerun=False` or iteration cap) |
| Loop-control rule | `needs_rerun` AND coverage-gain ≥ 1.0 else break | `needs_rerun` / iteration cap only (feedback applied first) |
| Feedback applied on final pass | **No** (lost on early stop) | **Yes** (unconditional, before stop decision) |
| Iteration state evolution | Weights mutated but GA ignored them → iterations re-ran the same effective objective | Weights mutated AND used by GA → each iteration genuinely differs |

## 2. AI Influence

| Dimension | Before | After |
|---|---|---|
| Coordinator weight adjustments reach GA fitness | ❌ (profit_first used hard-coded `PROFIT_FIRST_WEIGHTS`) | ✅ (runtime weights in every mode; verified by smoke test + run) |
| Consensus `final_archetype_params` applied | ❌ (computed, never applied) | ✅ (validated override into next-iteration service generation; reconciled ratios ≠ defaults) |
| `SharedContext.service_archetype_plan` | ❌ (always defaults) | ✅ (populated from consensus) |
| `llm_success` counter | ❌ (always 0) | ✅ (incremented on real LLM decisions) |
| `skip_milp` GA signal | ❌ (dead hand-off, MILP ran unconditionally) | ✅ (gates the MILP on weak solutions) |
| `summary_prompt` | ❌ (built, never sent) | ✅ (removed; deterministic summary is documented) |
| FrequencyGA fuel cost | ❌ (computed, omitted from fitness) | ✅ (subtracted) |
| Dead AI output % (T0.6) | (was nonzero) | **0.0%** |

## 3. Feedback Propagation

| Dimension | Before | After |
|---|---|---|
| Coverage used by feedback | `average_coverage` = mean of per-region percents (68.4%) — inconsistent with final (51.56%) | demand-weighted `satisfied/total_demand` — **exactly** equals audit and summary (43.05 = 43.05 = 43.05) |
| Coverage-gap → weight response | weights changed but had no GA effect | weights change the GA objective; coverage weight climbs 0.25 → 0.52 across iterations |
| Consensus feed-forward | existed (`_previous_consensus`) | retained + now also feeds archetype plan to service generation |

## 4. Optimizer Connectivity

| Dimension | Before | After |
|---|---|---|
| Objective source | static `ObjectiveWeights` mode dicts | live `Problem` weights (CONFIG seed → consensus → feedback) |
| Objective shape | profit_first: cost **added** (bug); legacy: cost subtracted | cost **always subtracted**; one formula every mode |
| GA behavior across iterations | same effective objective every iteration | objective evolves (verified: profit $771M → $644M → $679M; coverage 44.17 → 43.10 → 43.71) |

## 5. Dashboard Integrity

| Dimension | Before | After |
|---|---|---|
| Data source | `pipeline_output.json` (already) | `pipeline_output.json` (unchanged — single source of truth) + `/api/pipeline-output` endpoint + stale-file hot-reload |
| Solver identity | "Gurobi" (fake, from simulation layer) | corrected to `PULP_CBC_CMD (PuLP)`; simulation explicitly labeled |
| `run_actual_pipeline` (unified_main) | crashed on `NetworkLoader.load_problem` (AttributeError) | replays the runtime-truth file directly |
| `MockProblem` fabrication | silent | explicitly-labeled simulation fallback only |

## 6. Runtime Truth Consistency

| Dimension | Before | After |
|---|---|---|
| Weight systems | 2 competing (CONFIG/problem vs `ObjectiveWeights`) | 1 canonical (`Problem` weights; mode dicts are defaults only) |
| Coverage measures | 2 (mean-of-percents vs demand-weighted) → 68% ≠ 51.56% | 1 (demand-weighted) → 43.05 everywhere |
| Authoritative output | `pipeline_output.json` | `pipeline_output.json` (all consumers read it) |
| Backend simulation | hard-coded region numbers shadowed real execution | explicitly labeled SIMULATION; never presented as real |

## 7. Headline Metrics (runtime)

| Metric | Before | After (final run) |
|---|---|---|
| Iterations | 2 | **3** |
| Weekly profit | $798M | $569M |
| Coverage | 51.56% (weighted) / 68.4% (iter, split) | **40.94%** (identical coordinator/audit/summary) |
| Services | 514 | 472 |
| Iteration coverage trace | 68.38% → 64.29% (mean-of-percents) | 44.93% → 43.76% → 40.94% (demand-weighted, consistent) |
| Weights used per iteration | 0.60/0.25/0.15 → 0.459/0.435/0.106 (GA ignored) | 0.60/0.25/0.15 → 0.401/0.473/0.126 → 0.409/0.478/0.113 (GA used) |
| Test score | 309/313 (98.7%) | **311/313 (99.4%)** |
| AI pathways | (partial) | **4/4 PASS** |
| Dead AI outputs | (nonzero) | **0** |
| Runtime | 351s | 487s (3 iterations vs 2) |
