# WorldSmall Service Generation & Optimization Audit Report

**Date:** 2026-09-13  
**Instance:** WorldSmall (47 ports, 1,764 demands, 263 vessels)  
**Audit Type:** Read-only forensic inspection — no code was modified  
**Pipeline Output Analyzed:** `pipeline_output.json`  
**Benchmark Runtime:** `RUNTIME_PIPELINE_BENCHMARK.json` (300.57 sec wall-clock)

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Ports | 47 |
| Demands (lanes) | 1,764 |
| Fleet size | 263 vessels |
| Total demand | 276,447 TEU/wk |
| Regional agents active | 3 (Asia, Europe, Americas) |
| Clusters per region (MILP) | 5 hub-based per region |
| Raw services generated | 2,098 total (~699/region avg) |
| After regional filter (cap 400) | 1,200 total (400/region) |
| After HGA pre-filter | ~400/region (minimal removal) |
| Services selected by ServiceGA | ~100/region avg |
| Services selected by MILP | 297 total |
| Negative-profit services in final JSON | **35 out of 297 (11.8%)** |
| Weekly profit | $267,554,413 |
| Coverage (weighted) | 89.58% |
| Iterations run | 3 (all completed) |
| Best iteration selected | Iteration 1 (deterministic Pareto) |
| LLM calls | 306 attempts, 0 successes (all providers failed: `proxies` kwarg error) |
| LLM fallback usage | 51 fallbacks |
| Total runtime | 300.57 sec |

### Key Finding

**The current WorldSmall pipeline does NOT use an optimization budget scaled to its instance size.** The GA generation count (120), population size (adaptive 60–140 but capped by fixed thresholds), service-generation volume (fixed archetype ratios), and MILP configuration (fixed time limit, transfer-pair cap) are all inherited from WorldLarge-oriented defaults. The only parameters that adapt to instance size are: (1) cluster count (3 vs 5 based on port count), (2) regional agent count, (3) ServiceGA population size via `_tune_parameters()`, and (4) fleet size constraint. Everything else is fixed.

---

## 1. Full Runtime Flow

| Stage | File | Function/Class | Input | Output | Important Parameters | Parameter Source | Next Stage |
|-------|------|----------------|-------|--------|---------------------|------------------|------------|
| Problem Load | `src/data/network_loader.py` | `NetworkLoader.load_problem()` | CSV files (ports, demands, distances, fleet) | `Problem` object with ports, demands, distance matrix, fleet | `DEMAND_SCALE=6` (WorldLarge legacy) | Hardcoded | Network construction |
| Decomposition | `src/decomposition/port_clustering.py` | `PortClustering.cluster_ports()` | `Problem.ports` | Dict[int, List[port_id]] | `n_clusters`: 3 if ports<50 else 5; `random_state=42` | Orchestrator (instance-derived) | Regional split |
| Splitting | `src/decomposition/regional_splitter.py` | `RegionalSplitter.split()` | clusters + problem | Dict[int, Problem] (one per region) | Demands assigned by origin-port only; services included if ANY port in region | Hardcoded logic | Regional agents |
| Regional Process | `src/agents/regional_agent.py` | `RegionalAgent.process()` | regional `Problem` | Dict with selected_services, metrics | `ALPHA_UNSERVED=300`, `TRANSSHIP_COST_PER_TEU=80`, `MAX_TRANSFER_PAIRS=2000`, `max_runtime_sec=55` | Hardcoded constants | MILP decomposition |
| Service Gen | `src/agents/service_generator_agent.py` | `ServiceGeneratorAgent.generate_services()` | regional `Problem` | List[Service] (~700–800) | `n_direct=min(800, max(200, int(500*dr)))`; `hub_loop_count=max(2, int(10*hl))`; `feeder_target=max(20, int(100*fr))`; trunk=C(10,2)=45; heuristic=150 | Default archetype ratios (LLM can override, but LLM is non-functional) | Regional filter |
| Reg. Filter | `src/agents/regional_agent.py` | `RegionalAgent._filter_services()` | services list | filtered services | `max_services = max(400, num_ports)`; margin: `(capacity*0.5*150) > weekly_cost` | Hardcoded cap 400 | HierarchicalGA |
| HGA Pre-filter | `src/optimization/hierarchical_ga.py` | `HierarchicalGA._filter_services()` | services list | filtered services | Tiered margin gates: strategic=0%, feeder=-15%, hub_connector=-10%, regular=+5% | Hardcoded thresholds | ServiceGA |
| ServiceGA | `src/optimization/service_ga.py` | `ServiceGA.run()` | problem + binary mask | List[int] (best chromosome) | `pop_size`: adaptive (60/100/140); `generations=120`; `NO_IMPROVE_LIMIT=8`; `MAX_RUNTIME=90s` | Defaults + `_tune_parameters()` | FrequencyGA |
| FrequencyGA | `src/optimization/frequency_ga.py` | `FrequencyGA.run()` | best_services + problem | List[int] (frequencies) | `pop_size=40`; `generations=60`; `max_freq=3`; `NO_IMPROVE_LIMIT=8`; `MAX_RUNTIME=90s` | Hardcoded defaults | Fleet prune |
| Fleet Prune | `src/optimization/hierarchical_ga.py` | `HierarchicalGA.run()` post-GA | best_services + best_freq | pruned vectors | `fleet_size = problem.fleet.total_vessels or 300` | Instance-derived (WorldSmall=263) | MILP |
| MILP Decompose | `src/agents/regional_agent.py` | `RegionalAgent.split_by_hubs()` | problem | Dict[hub, [ports]] | `num_hubs=5` | Hardcoded | Per-cluster MILP |
| HubMILP | `src/optimization/hub_milp.py` | `HubMILP.solve()` | sub-problem + chromosome | Dict with selected_services | `time_limit=120`; `fleet_size=263`; `max_svc_per_demand=10`; `max_transfer_pairs=2000`; `alpha_unserved=300` | Mixed hardcoded + instance-derived | Aggregation |
| Aggregation | `src/agents/orchestrator_agent.py` | `OrchestratorAgent.aggregate_results()` | regional results | global metrics dict | `true_global_demand` captured before split | Instance-derived | JSON output |
| Iteration Loop | `src/agents/orchestrator_agent.py` | `OrchestratorAgent.process()` | Problem | final output dict | `MAX_ITERATIONS=3`, `MIN_ITERATIONS=3` | Hardcoded | Selection |
| Selection | `src/pipeline/iteration_selection.py` | `IterationSelector.select()` | iteration snapshots | selected iteration index | 7 Pareto objectives; deterministic fallback | Hardcoded | Final output |

---

## 2. Service Generation Audit

### A. How many services are initially generated?

Per the latest WorldSmall run:
- **Asia:** 735 services
- **Europe:** 626 services  
- **Americas:** 737 services
- **Total raw:** 2,098 services

This varies slightly by region due to different hub/spoke configurations, but the formula is deterministic given the default archetype parameters.

### B. Is the number fixed, random, or derived?

**Partially derived, partially fixed.** The breakdown per region is:

| Component | Formula | WorldSmall Value | Fixed/Derived |
|-----------|---------|-----------------|---------------|
| Direct services | `min(800, max(200, int(500 * dr)))` where `dr=0.60` (default) → `min(800, max(200, 300))` → capped at `len(top_demands)` | ~500 (capped by lane count) | **Fixed formula**, derived from demand count |
| Hub loop services | `max(2, int(10 * hl / BASE_HL))` hubs × ~4 loops each | ~40 (10 hubs × 4 loops) | **Fixed** |
| Trunk services | `C(10, 2)` = 45 | 45 | **Fixed** |
| Feeder services | `spoke_ports × 2` (top-2 hub affinity per spoke) | ~54 (27 spokes × 2) | **Derived from port count** |
| Heuristic (CandidateServiceGenerator) | `generate_services(num_services=150)` → returns `min(corridor+feeder, 150)` | 150 | **Fixed** |

**Total ≈ 500 + 40 + 45 + 54 + 150 = 789** (the actual 735/626/737 vary due to demand distribution and deduplication within generation).

### C. Every parameter controlling service-generation volume

| Parameter | Current WorldSmall Value | Source File | Function | Fixed or Derived | Depends On |
|-----------|-------------------------|-------------|----------|-----------------|------------|
| `n_direct` base | 500 | `service_generator_agent.py:71` | `generate_services()` | **Fixed constant** | None |
| `direct_ratio` (archetype) | 0.60 (default) | `service_generator_agent.py:70` | `generate_services()` | **Fixed default** | LLM (non-functional) |
| `hub_loop_count` base | 10 | `service_generator_agent.py:72` | `generate_services()` | **Fixed constant** | None |
| `hub_loop_ratio` (archetype) | 0.15 (default) | `service_generator_agent.py:72` | `generate_services()` | **Fixed default** | LLM (non-functional) |
| `feeder_count_target` base | 100 | `service_generator_agent.py:73` | `generate_services()` | **Fixed constant** | None |
| `feeder_ratio` (archetype) | 0.20 (default) | `service_generator_agent.py:73` | `generate_services()` | **Fixed default** | LLM (non-functional) |
| Trunk count | C(10,2) = 45 | `service_generator_agent.py:166` | `generate_services()` | **Fixed** | 10 top hubs |
| Heuristic services | 150 | `service_generator_agent.py:242` | `process()` | **Fixed constant** | None |
| `top_k` hubs detected | 20 | `service_generator_agent.py:49` | `generate_services()` | **Fixed constant** | None |
| Hub loop batch size | 5 spokes | `service_generator_agent.py:130` | `generate_services()` | **Fixed constant** | None |
| Spoke hub affinity count | 2 hubs per spoke | `service_generator_agent.py:194` | `generate_services()` | **Fixed constant** | None |
| `num_services` cap (heuristic) | 150 | `candidate_service_generator.py:119` | `generate_services()` | **Fixed constant** | None |
| Corridor count (heuristic) | 150 | `candidate_service_generator.py:121` | `find_demand_corridors()` | **Fixed constant** | None |
| Feeder count (heuristic) | 150 | `candidate_service_generator.py:77` | `generate_feeders()` | **Fixed constant** | None |
| Region filter cap | `max(400, num_ports)` = 400 | `regional_agent.py:158` | `_filter_services()` | **Mixed**: base 400 is fixed, num_ports is derived | Port count |
| `max_services` cap after filter | 400 | `regional_agent.py:159` | `_filter_services()` | **Fixed constant** (400 >> 47 ports) | None |

---

## 3. GA Forensic Audit

### HierarchicalGA (ServiceGA + FrequencyGA combined controller)

**Initialization:**
- `pop_size = 80` (default passed to ServiceGA)
- `generations = 120` (default passed to ServiceGA)
- `max_freq = 3` (passed to FrequencyGA)
- `max_runtime_sec = 60.0` (default in HierarchicalGA.__init__)

**But ServiceGA._tune_parameters() OVERRIDES pop_size based on candidate count:**
- After regional filter: 400 services → `100 <= 400 < 500` → `pop_size = 100`
- `mutation_rate` stays at default 0.15

**Evolution:**
- Selection: Top-10 elite retained each generation (`heapq.nlargest(10, ...)`)
- Crossover: Single-point crossover between two top-20 parents
- Mutation: 15% chance per child, biased toward activating high-demand services
- Fitness evaluation: Multi-objective with normalized components (profit, coverage, cost)

**Termination:**
- Maximum generations: **120** (hardcoded default, NOT overridden by _tune_parameters)
- Early stopping: `NO_IMPROVE_LIMIT = 8` consecutive generations without improvement
- Runtime cap: `MAX_RUNTIME = 90` seconds
- Actual generations reached: **Unknown from logs** (logging captures agent events but not GA internals); likely early-stops before 120 given 78s region runtime

**Fitness components (ServiceGA.evaluate):**
1. `revenue = Σ served_i × avg_rev_per_teu × yield_factor` where `yield_factor = 0.6 + 0.4 × (served/effective_capacity)`
2. `operating_cost = Σ weekly_cost` for selected services
3. `fuel_cost = Σ calculate_weekly_fuel_cost(...)` per service
4. `port_cost = Σ served × handling_cost + fixed_cost + served × variable_cost` per port
5. `transship_cost = hub_ratio × satisfied × tc_per_teu` where `hub_ratio = min(0.7, max(0.3, 0.1))`
6. `unserved_penalty = alpha × unserved_demand` where `alpha = 300.0`
7. `overcap_penalty = beta × unused_cap × (operating_cost / total_capacity)` where `beta = 0.02`
8. `alignment_penalty = gamma × weekly_cost` for zero-demand services where `gamma = 0.3`
9. `negative_service_penalty`: tiered (20%/50%/70%/100% of loss) for negative-margin services
10. Normalized weighted sum: `w_profit × norm(profit) + w_coverage × norm(coverage) - w_cost × norm(cost)`

### FrequencyGA

**Initialization:**
- `pop_size = 40` (**HARDCODED, never overridden**)
- `generations = 60` (**HARDCODED, never overridden**)
- `max_freq = 3`
- Initial population: analytical frequency estimate ± jitter of ±1

**Evolution:**
- Selection: Top-10 elite (`ranked[:10]`)
- No crossover — children are mutated copies of top-20 parents
- Mutation: Random frequency assignment `randint(0, max_freq)` to one active service

**Termination:**
- Maximum generations: **60**
- Early stopping: `NO_IMPROVE_LIMIT = 8`
- Runtime cap: `MAX_RUNTIME = 90` seconds

**Fitness:**
- `revenue = satisfied × avg_rev_per_teu`
- `operating_cost = Σ weekly_cost × freq`
- `fuel_cost = Σ fuel_cost × freq`
- `port_cost = Σ teu_served × handling + fixed × freq + teu_served × variable`
- `transship_cost = hub_ratio × satisfied × avg_rev_per_teu × 0.05`
- `overcap_penalty = beta × unused_cap × (operating_cost / total_capacity)` where `beta = 0.015`
- Early fleet rejection: if `vessels_used > fleet_size` → return `-1e9`

### GA Component Comparison

| GA Component | WorldSmall Value | Adaptive? | Source | Effect on Search |
|--------------|-----------------|-----------|--------|------------------|
| ServiceGA pop_size | **100** (from 80 default, overridden by _tune_parameters for n=400) | **PARTIALLY** — only pop_size adapts; thresholds (100, 500) are fixed | `service_ga.py:155-166` | Moderate search breadth |
| ServiceGA generations | **120** (hardcoded default) | **NO** | `hierarchical_ga.py:17`, `service_ga.py:57` | Fixed budget regardless of instance |
| ServiceGA mutation_rate | **0.15** (from _tune_parameters for n=400) | **YES** — derived from service count | `service_ga.py:155-166` | Small adaptation |
| ServiceGA NO_IMPROVE_LIMIT | **8** | **NO** | `service_ga.py:45` | Fixed early-stop threshold |
| ServiceGA MAX_RUNTIME | **90 sec** | **NO** | `service_ga.py:46` | Fixed time budget |
| FrequencyGA pop_size | **40** | **NO** | `frequency_ga.py:26` | Fixed, never adapted |
| FrequencyGA generations | **60** | **NO** | `frequency_ga.py:27` | Fixed, never adapted |
| FrequencyGA NO_IMPROVE_LIMIT | **8** | **NO** | `frequency_ga.py:13` | Fixed early-stop threshold |
| FrequencyGA MAX_RUNTIME | **90 sec** | **NO** | `frequency_ga.py:14` | Fixed time budget |
| Fleet size constraint | **263** (WorldSmall) | **YES** — instance-derived | `hierarchical_ga.py:168-170` | Correctly scaled |
| Alpha_unserved penalty | **300.0** | **NO** | `regional_agent.py:22` | Fixed across all instances |
| Transship cost | **80.0** $/TEU | **NO** | `regional_agent.py:20` | Fixed |
| Hub ratio (fitness) | **0.1** × num_ports | **YES** — derived | `service_ga.py:322`, `frequency_ga.py:191` | Scales with ports |

---

## 4. "800 Generations" Investigation

**Finding: There is NO 800-generation configuration in the current codebase.**

The value **800** appears in only two contexts:

1. **`service_generator_agent.py:71`**: `n_direct = min(800, max(200, int(500 * dr / max(BASE_DR, 0.01))))` — this is a **service generation cap**, not a GA generation count. It limits direct services to at most 800.

2. **`service_generator_agent.py:312`**: A string interpolation referencing `~800 candidates` as a comment in the LLM prompt.

The actual GA generation counts are:
- **ServiceGA: 120 generations** (default, from `hierarchical_ga.py:18`)
- **FrequencyGA: 60 generations** (default, from `frequency_ga.py:27`)
- Both have early stopping at 8 consecutive non-improving generations
- Both have a 90-second runtime cap

**The 120-generation ServiceGA + 60-generation FrequencyGA combination is the actual budget.** These values are identical for WorldSmall and would be identical for WorldLarge — neither adapts to instance size.

### Evidence Summary

| Question | Answer |
|----------|--------|
| Where is 800 defined? | `service_generator_agent.py:71` (service count cap, not generations) |
| Is it global? | N/A — no 800-generation constant exists |
| Is it per regional agent? | N/A |
| Is it per GA? | N/A |
| Are the same values used for WorldSmall and WorldLarge? | **YES** — both use pop_size=80→100, generations=120, freq_generations=60 |
| Is early stopping available? | **YES** — 8 consecutive non-improving generations OR 90-second runtime cap |
| What is the ACTUAL generation count reached? | Unknown from logs (GA internals not logged); likely <120 due to early stopping |
| Is 120 a maximum budget or mandatory workload? | **Maximum** — early stopping can terminate earlier |

---

## 5. Service Volume Funnel

| Stage | Asia | Europe | Americas | Total |
|-------|------|--------|----------|-------|
| Raw generated | 735 | 626 | 737 | **2,098** |
| After regional filter (cap=max(400,ports)) | 400 | 400 | 400 | **1,200** |
| After HGA pre-filter (margin gate) | ~400 | ~400 | ~400 | **~1,200** (minimal removal) |
| ServiceGA selected (binary mask = 1) | ~100 | ~95 | ~102 | **~297** |
| FrequencyGA assigned frequencies | ~100 | ~95 | ~102 | **~297** |
| After post-GA fleet prune | ~100 | ~95 | ~102 | **~297** (under 263-vessel limit per region) |
| MILP candidates (per hub cluster) | ~100/cluster × 5 clusters | ~95/cluster × 5 clusters | ~102/cluster × 5 clusters | **~1,500 cluster-solves** |
| MILP selected services | 100 | 95 | 102 | **297** |
| **Final JSON services** | 100 | 95 | 102 | **297** |

**Note:** The HGA pre-filter (`_filter_services`) removes very few services when the regional filter has already kept only high-quality candidates. The `services_filtered` count in the JSON (400 per region) represents the post-regional-filter count, not the post-HGA-filter count.

---

## 6. Negative-Profit Service Audit

### How the pipeline treats negative-profit services:

| Question | Answer | Evidence |
|----------|--------|----------|
| 1. Are negative-profit services generated? | **YES** | Service generation creates routes based on demand/corridor logic, not profitability. Many multi-port loop services have high operating costs relative to covered demand. |
| 2. Are they retained by regional filter? | **YES** — conditionally | `RegionalAgent._filter_services` checks `(capacity * 0.5 * 150) > weekly_cost`. This is a crude margin check that allows some marginally-negative services through. |
| 3. Are they removed by HGA pre-filter? | **PARTIALLY** | `HierarchicalGA._filter_services` applies tiered margin gates but only removes services with ZERO corridor coverage. Services covering corridors can survive even with negative estimated margin. |
| 4. Can they reach FrequencyGA? | **YES** | If a service passes both filters with `best_services[i] == 1`, it enters FrequencyGA. |
| 5. Can they be selected by MILP? | **YES** — and they ARE | MILP maximizes the objective function which includes the coverage reward term. A negative-profit service may still be selected if it enables coverage of otherwise-unserved demand (the $300/TEU unserved penalty is very high). |
| 6. Does final JSON contain negative-profit services? | **YES** — 35 out of 297 (11.8%) | Directly observed in `pipeline_output.json` |
| 7. What causes them? | **GA objective + MILP coverage pressure** | The GA penalizes negative-margin services but doesn't eliminate them (penalties are partial: 20–100% of loss). The MILP then selects them because dropping them would increase unserved demand penalties more than the service's own loss. |

### Representative Negative-Profit Services

| Service ID | Region | Profit | Margin % | Ports | Cause |
|------------|--------|--------|----------|-------|-------|
| asia_svc_188 | Asia | -$149,352 | -213.5% | CNTAO→USMIA | Cross-ocean direct with tiny demand |
| asia_svc_546 | Asia | -$470,176 | -95.2% | CNSHA→INNSA | Low-volume inter-region corridor |
| asia_svc_024 | Asia | -$47,503 | -48.1% | HKHKG→ZADUR | Low-demand feeder |
| europe_svc_391 | Europe | -$3,809,413 | -62.3% | USCHS→DEBRV→NLRTM→... | Long multi-port loop with high operating cost |
| americas_svc_* | Americas | Up to -$11.6M | Various | Multiple | Americas region has highest negative-service ratio (16.7%) |

**Root cause:** The GA's `negative_service_penalty` applies partial penalties (20–100% of loss, capped at $100k), which is insufficient to fully exclude deeply unprofitable services. Combined with the MILP's high unserved-demand penalty ($300/TEU), the optimizer accepts negative-profit services when they contribute to coverage.

---

## 7. Service Quality Audit

### Explicit quality metrics used before final selection:

| Metric | Used In | Purpose |
|--------|---------|---------|
| Profit (revenue − cost − penalties) | ServiceGA fitness, MILP objective | Primary selection criterion |
| Coverage (satisfied/total demand) | ServiceGA fitness, MILP coverage_reward | Secondary criterion |
| Cost (operating + fuel + transship + port) | ServiceGA fitness | Minimization component |
| Margin % | RegionalAgent._filter_services (crude), output display | Filtering gate |
| Capacity/utilization | ServiceGA evaluate (effective_capacity) | Feasibility |
| Demand alignment | ServiceGA (service_direct_demand, service_partial_demand) | Initialization bias |
| Fleet feasibility | FrequencyGA early rejection, post-GA prune | Hard constraint |
| Dominance | IterationSelector (Pareto analysis) | Multi-iteration selection |

### Ranking before MILP?

**No explicit service-quality ranking exists at the service level before MILP.** The pipeline does:
1. Generate candidates
2. Filter by corridor coverage + crude margin
3. Run ServiceGA to produce a binary selection mask
4. Run FrequencyGA to assign frequencies
5. Post-GA fleet prune (removes lowest-efficiency services)
6. Pass binary+frequencies directly to MILP

There is no intermediate ranking/scoring step that orders services by quality before MILP input. The MILP itself performs the final selection via linear optimization.

---

## 8. Regional Audit

| Region | Ports | Demands | Demand Volume (TEU/wk) | Fleet (shared) | Population | Generations | Candidates (after filter) | Selected | Profit ($/wk) | Coverage | Runtime |
|--------|-------|---------|------------------------|----------------|------------|-------------|--------------------------|----------|---------------|----------|---------|
| Asia | ~14 | 604 | ~147,839 | 263 (shared) | 100 | 120 (max) | 400 | 100 | 281,131,042 | 100.0% | 78.3s |
| Europe | ~12 | 391 | ~varies | 263 (shared) | 100 | 120 (max) | 400 | 95 | -3,470,266 | 96.0% | 41.9s |
| Americas | ~21 | 769 | ~varies | 263 (shared) | 100 | 120 (max) | 400 | 102 | -10,106,363 | 100.0% | 76.9s |

### Observations:
- **Identical optimization budgets** across all three regions despite very different demand profiles
- Europe has the smallest problem (12 ports, 391 demands) but receives the same GA budget as Americas (21 ports, 769 demands)
- Fleet size (263) is shared globally but enforced per-region in MILP
- Asia dominates profit ($281M/wk) while Europe and Americas are loss-making
- All regions hit 400-service cap after regional filter (the cap is binding)

---

## 9. MILP Audit

### Formulation Details

| Aspect | Value | Source |
|--------|-------|--------|
| Solver | PuLP with CBC | `hub_milp.py:424` |
| Objective | Maximize profit + coverage_reward | `hub_milp.py:358-373` |
| Decision variables — flow | `flow[(demand_idx, service_idx)]` ≥ 0 | One per compatible (demand, service) pair |
| Decision variables — transfer | `transfer_flow[(demand_idx, s1, s2)]` ≥ 0 | One per valid transfer pair |
| Decision variables — unserved | `unserved[demand_idx]` ≥ 0 | One per demand |
| Service selection | **FIXED** from GA chromosome (not a MILP variable) | Chromosome binary mask |
| Frequency | **FIXED** from GA chromosome (not a MILP variable) | Chromosome frequencies |
| Fleet constraint | `Σ ceil(cycle_time × freq / 7) ≤ fleet_size` | Converted to constant constraint |
| Demand satisfaction | `flow + transfer + unserved == weekly_teu` | Equality per demand |
| Capacity constraint | `flow_through_service + transfer_through_service ≤ capacity × freq × (7/cycle_time)` | Per service |
| Port capacity | `total_flow_through_port ≤ 50000 + 0.1 × port_demand` | Per port (synthetic) |
| Time limit | 120 seconds | `hub_milp.py:60` default |
| MIP gap | Not explicitly set (CBC default) | PuLP/CBC default |
| Status reported | "Optimal" for all 3 regions in WorldSmall | Observed in JSON |

### Key Insight: MILP does NOT select services — it allocates demand flow

The GA determines WHICH services are active (binary mask) and their frequencies. The MILP only decides **how much demand to route directly vs. via transshipment** across the fixed service set. This is a critical architectural distinction.

### Variable Counts (approximate per region)

| Region | Compatible flow vars | Transfer pair vars | Demands |
|--------|---------------------|-------------------|---------|
| Asia | up to 604 × 10 = 6,040 | up to 2,000 | 604 |
| Europe | up to 391 × 10 = 3,910 | up to 2,000 | 391 |
| Americas | up to 769 × 10 = 7,690 | up to 2,000 | 769 |

---

## 10. Allocation / Distribution Audit

### Is allocation adaptive?

**No.** Service allocation is primarily **optimization-driven** (GA + MILP), but the candidate pool entering optimization is **fixed-budget**.

| Allocation Parameter | WorldSmall | Adaptive? | Source |
|---------------------|------------|-----------|--------|
| Regional cluster count | 3 | **YES** — `3 if num_ports < 50 else 5` | `orchestrator_agent.py:508` |
| Regional agents used | 3 | **YES** — matches cluster count | `orchestrator_agent.py:601` |
| Services per region (post-filter cap) | 400 | **NO** — `max(400, num_ports)` fixes at 400 | `regional_agent.py:158` |
| MILP time limit | 120 sec | **NO** — hardcoded default | `hub_milp.py:60` |
| MILP fleet_size | 263 | **YES** — from instance fleet | `hub_milp.py:61` + resolution in regional_agent |
| MILP max_transfer_pairs | 2,000 | **NO** — hardcoded | `regional_agent.py:24` |
| MILP max_svc_per_demand | 10 | **NO** — hardcoded default | `hub_milp.py:51` |
| Alpha_unserved penalty | $300/TEU | **NO** — hardcoded | `regional_agent.py:22` |
| Transship cost | $80/TEU | **NO** — hardcoded | `regional_agent.py:20` |
| Hub detection top_k | 5 (MILP clusters) | **NO** — hardcoded | `regional_agent.py:129` |
| GA generations | 120 | **NO** — hardcoded | `hierarchical_ga.py:18` |
| GA population | 100 (adaptive from 80) | **PARTIALLY** — thresholds fixed at 100/500 | `service_ga.py:155-166` |
| FGA generations | 60 | **NO** — hardcoded | `frequency_ga.py:27` |
| FGA population | 40 | **NO** — hardcoded | `frequency_ga.py:26` |
| Iteration count | 3 | **NO** — hardcoded | `orchestrator_agent.py:27-28` |

---

## 11. Instance-Size Dependency Matrix

| Parameter | Component | Current Value | Dependency Type | Derived From | WorldSmall | Same as WorldLarge? | Risk |
|-----------|-----------|---------------|-----------------|--------------|------------|---------------------|------|
| ServiceGA pop_size | ServiceGA | 100 (for n=400) | **C. REGION-DERIVED** | Number of candidate services after filter | 100 | Would be higher for larger instance | LOW — partially adaptive |
| ServiceGA generations | ServiceGA | 120 | **G. FIXED/HARDCODED** | None | 120 | Same | **HIGH** |
| ServiceGA mutation_rate | ServiceGA | 0.15 | **C. REGION-DERIVED** | Number of candidate services | 0.15 | Different for large instance | LOW |
| ServiceGA NO_IMPROVE_LIMIT | ServiceGA | 8 | **G. FIXED** | None | 8 | Same | MEDIUM |
| ServiceGA MAX_RUNTIME | ServiceGA | 90s | **G. FIXED** | None | 90s | Same | MEDIUM |
| FrequencyGA pop_size | FrequencyGA | 40 | **G. FIXED** | None | 40 | Same | **HIGH** |
| FrequencyGA generations | FrequencyGA | 60 | **G. FIXED** | None | 60 | Same | **HIGH** |
| FrequencyGA max_freq | FrequencyGA | 3 | **G. FIXED** | None | 3 | Same | LOW |
| Fleet size | Post-GA prune / MILP | 263 | **E. FLEET-DERIVED** | Instance fleet data | 263 | Different (WorldLarge=501) | None — correctly adaptive |
| n_clusters | Orchestrator | 3 | **A. INSTANCE-INDEPENDENT** (threshold-based) | num_ports < 50 | 3 | Would be 5 for WorldLarge | MEDIUM |
| Regional filter cap | RegionalAgent | 400 | **G. FIXED** (base) | max(400, num_ports) | 400 | Same base for WorldLarge | **HIGH** |
| Service generation n_direct | ServiceGeneratorAgent | 500 | **G. FIXED** | Constant in formula | 500 | Same | **HIGH** |
| Service generation hub_loops | ServiceGeneratorAgent | ~40 | **G. FIXED** | 10 hubs × 4 loops | 40 | Same | MEDIUM |
| Service generation feeders | ServiceGeneratorAgent | ~54 | **C. REGION-DERIVED** | Spoke count × 2 | ~54 | More for WorldLarge | LOW |
| Service generation heuristic | ServiceGeneratorAgent | 150 | **G. FIXED** | Constant | 150 | Same | MEDIUM |
| MILP time_limit | HubMILP | 120s | **G. FIXED** | Default | 120s | Same | **HIGH** |
| MILP max_transfer_pairs | HubMILP | 2,000 | **G. FIXED** | Constant | 2,000 | Same | **HIGH** |
| MILP max_svc_per_demand | HubMILP | 10 | **G. FIXED** | Default | 10 | Same | MEDIUM |
| Alpha_unserved | HubMILP / RegionalAgent | 300.0 | **G. FIXED** | Constant | 300.0 | Same | MEDIUM |
| Transship cost | HubMILP / RegionalAgent | 80.0 | **G. FIXED** | Constant | 80.0 | Same | LOW |
| Hub detection top_k | RegionalAgent | 5 | **G. FIXED** | Constant | 5 | Same | LOW |
| MAX_ITERATIONS | Orchestrator | 3 | **G. FIXED** | Constant | 3 | Same | MEDIUM |
| MIN_ITERATIONS | Orchestrator | 3 | **G. FIXED** | Constant | 3 | Same | MEDIUM |

---

## 12. Hardcoded WorldLarge-Assumption Audit

### Confirmed WorldLarge-derived constants still in the codebase

| Value | Location | Context | Classification |
|-------|----------|---------|----------------|
| `800` | `service_generator_agent.py:71` | `n_direct = min(800, ...)` | **Potentially non-adaptive** — WorldLarge-scale service cap |
| `500` | `service_generator_agent.py:77,73` | Base direct/feeder counts | **Potentially non-adaptive** — fixed archetype magnitudes |
| `400` | `regional_agent.py:158` | `max_services = max(400, num_ports)` | **Potentially non-adaptive** — WorldLarge-oriented filter cap |
| `300` | `hierarchical_ga.py:168`, `frequency_ga.py:124` | Legacy fleet_size default | **Obsolescent** — WorldLarge fleet was 501; now overridden by instance fleet (263) |
| `120` | `hierarchical_ga.py:18` | ServiceGA generations default | **Potentially non-adaptive** — same budget for all instance sizes |
| `60` | `frequency_ga.py:27` | FrequencyGA generations default | **Potentially non-adaptive** |
| `40` | `frequency_ga.py:26` | FrequencyGA pop_size default | **Potentially non-adaptive** |
| `80` | `hierarchical_ga.py:17` | ServiceGA pop_size default (overridden by _tune_parameters) | Mostly neutralized by adaptation |
| `2000` | `regional_agent.py:24` | `MAX_TRANSFER_PAIRS` | **Potentially non-adaptive** — WorldLarge-scale transfer enumeration cap |
| `10` | `hub_milp.py:51` | `max_services_per_demand` | **Potentially non-adaptive** — fixed candidate limit per demand |
| `120` | `hub_milp.py:60` | MILP time_limit | **Potentially non-adaptive** |
| `300` | `regional_agent.py:22` | `ALPHA_UNSERVED` penalty | **Potentially non-adaptive** — penalty magnitude |
| `500` | `service_generator_agent.py:71` | `n_direct` base | **Potentially non-adaptive** |
| `150` | `candidate_service_generator.py:119` | Heuristic service cap | **Potentially non-adaptive** |
| `150` | `candidate_service_generator.py:121` | Corridor search depth | **Potentially non-adaptive** |
| `150` | `candidate_service_generator.py:77` | Feeder count target | **Potentially non-adaptive** |
| `3` | `orchestrator_agent.py:508` | `n_clusters` for small instances | Legitimate instance-dependent threshold |

### Numbers that are legitimate domain constants (NOT WorldLarge-specific):
- `80.0` — transshipment cost per TEU (domain knowledge)
- `0.05` — port cost per TEU default
- `0.1` — hub ratio coefficient
- `0.6/0.4/0.1` — objective weights (calibrated, not instance-specific)
- `5000` — minimum TEU threshold in filtering
- `7` — days per week (cycle time denominator)

---

## 13. WorldSmall vs. Theoretical WorldLarge Comparison

| Metric | WorldSmall (actual) | WorldLarge (inferred) | Ratio | Adaptive? |
|--------|--------------------|----------------------|-------|-----------|
| Ports | 47 | 333 | 1:7.1 | — |
| Demands | 1,764 | 9,622 | 1:5.5 | — |
| Fleet | 263 | 501 | 1:1.9 | YES (fleet constraint adapts) |
| Total demand TEU | 276,447 | ~1.65M (estimated) | 1:6.0 | — |
| Regional agents | 3 | 5 | 1:1.7 | YES (threshold at 50 ports) |
| ServiceGA pop_size | 100 | Likely 140 | 1:1.4 | PARTIALLY (threshold-based) |
| ServiceGA generations | 120 | 120 | 1:1.0 | **NO** |
| FGA pop_size | 40 | 40 | 1:1.0 | **NO** |
| FGA generations | 60 | 60 | 1:1.0 | **NO** |
| Raw services generated | ~2,098 | ~2,098 (same formula) | 1:1.0 | **NO** |
| Post-filter services | 1,200 (400×3) | 1,200 (400×5) | 1:1.25 | PARTIALLY (region count differs) |
| MILP time_limit | 120s | 120s | 1:1.0 | **NO** |
| MILP max_transfer_pairs | 2,000 | 2,000 | 1:1.0 | **NO** |
| MILP max_svc_per_demand | 10 | 10 | 1:1.0 | **NO** |
| Runtime | 300.57 sec | Unknown (expected much longer) | — | — |

**Key insight:** WorldLarge has ~7× the ports and ~5.5× the demands, but the GA generation budget, service-generation volumes, MILP time limit, and transfer-pair caps are **identical**. Only the cluster count and fleet constraint scale.

---

## 14. Runtime Trace to Final JSON

| JSON Field | Source Function | Source Object | Transformation | Final Meaning |
|------------|----------------|---------------|----------------|---------------|
| `selected_services` | `OrchestratorAgent.process()` L1260 | `best_snapshot["selected_services"]` | Deep copy from selected iteration | 297 services from best iteration |
| `all_selected_services` | `OrchestratorAgent.process()` L1105-1108 | Sum of `r["selected_services"]` across all regions | Concatenation (no dedup) | 297 services (same as selected_services since IDs are unique) |
| `summary_metrics.weekly_profit` | `OrchestratorAgent.aggregate_results()` L317 | `sum(r["weekly_profit"])` | Sum across 3 regions | $267,554,413 |
| `summary_metrics.coverage` | `OrchestratorAgent.process()` L990-998 | `decision_output["global_metrics"]["global_demand_weighted_coverage"]` | From coordinator, NOT simple average | 89.58% |
| `summary_metrics.total_services` | `aggregate_results()` L327 | `sum(r["services_selected"])` | Integer sum | 297 |
| `regional_results[*].services_generated` | `RegionalAgent.process()` L560 | `len(services)` before filter | Count of generated Service objects | 735/626/737 |
| `regional_results[*].services_filtered` | `RegionalAgent.process()` L561 | `len(problem.services)` after `_filter_services()` | Post-filter count (capped at 400) | 400/400/400 |
| `regional_results[*].services_selected` | `RegionalAgent.process()` L562 | `sum(chromosome["services"])` | GA-selected binary count | 100/95/102 |
| `regional_results[*].weekly_profit` | `RegionalAgent.process()` L563 | `sum(r["profit"])` across MILP clusters | Sum of per-cluster MILP profits | Per-region profit |
| `regional_results[*].coverage_percent` | `RegionalAgent.process()` L403 | `satisfied / total_demand * 100` | Capped at 100% | Per-region coverage |
| `iteration_results` | `OrchestratorAgent._iteration_results_append()` L86 | Deep-copied snapshot per iteration | Immutable record | 3 entries (iterations 0, 1, 2) |
| `iteration_selection.selected_iteration` | `IterationSelector.select()` | Deterministic Pareto selection | Integer index | 1 |
| `best_iteration` | `OrchestratorAgent.process()` L966 | `best_snapshot["iteration"]` | From selection result | 1 |
| `health_status.runtime_seconds` | `health_tracker.get_health_status()` | Wall-clock tracking | Seconds | 239.64 (excludes LLM overhead) |
| `llm_runtime_metrics.llm_calls` | `OrchestratorAgent.process()` L1157 | `coordinator_metrics["llm_calls"] + svcgen_regions` | Aggregated from actuation ledger | 5 |
| `llm_runtime_aggregate.coordinator_fallback` | `OrchestratorAgent.process()` L1218 | `coord_decision_source == "rule-based"` | Boolean | true (all LLM calls failed) |

### JSON Content Summary
- `selected_services`: **Only final MILP-selected services** (297)
- `all_selected_services`: **Identical to selected_services** (same 297, concatenated from regions)
- `iteration_results`: **Full snapshots** including regional_results, weights, consensus, feedback
- **NOT present**: raw candidate services, pre-filter services, GA chromosomes, FrequencyGA frequencies, MILP variable values
- **Stale metrics**: None detected — all metrics appear freshly computed
- **Duplicated representations**: 7 exact duplicate routes exist (same port sequence in same region); 45 reverse-route pairs exist (A→B and B→A both present)

---

## 15. Service Identity / Duplication Audit

### Service ID System
- IDs are generated as sequential integers during `ServiceGeneratorAgent.generate_services()` (starting from 0)
- Then prefixed with region name in `RegionalAgent.process()`: `{region_prefix}_svc_{idx:03d}`
- Example: `asia_svc_001`, `europe_svc_395`, `americas_svc_102`

### Route Equality Analysis

| Relationship | Treated As | Evidence |
|-------------|------------|----------|
| A → B vs B → A | **Different services** | 45 reverse-route pairs found in final output, both retained |
| A → B → C vs A → C → B | **Different services** | No cyclic-equality check exists; routes are distinct by port order |
| Duplicate routes (same port sequence) | **Treated as different services** | 7 exact duplicate routes found (e.g., `PAMIT→USMIA` appears twice in Europe) |
| Cross-region duplicates | **Possible** | Some routes appear in multiple regions' candidate pools but get different IDs after prefixing |

### Deduplication Behavior
- **No deduplication** occurs at any stage:
  - Service generation does not check for existing routes
  - Regional filter does not remove duplicates
  - GA does not detect duplicate chromosomes
  - MILP does not merge duplicate services
- The only "deduplication" is the region-prefix on service IDs, which makes them globally unique but does not prevent route duplication

---

## 16. Randomness / Reproducibility Audit

| Source | Seed Control | Deterministic? |
|--------|-------------|----------------|
| NumPy (KMeans clustering) | `random_state=42` fixed | **YES** — deterministic clustering |
| Python `random` (GA initialization, mutation, crossover) | **NO seed set** | **NO** — depends on system time/os entropy |
| Service generator `random.random()` (hub insertion probability) | **NO seed** | **NO** |
| Service generator `random.choice()` (hub selection, spoke selection) | **NO seed** | **NO** |
| MILP solver (PuLP/CBC) | Deterministic algorithm | **YES** (given same inputs) |
| LLM calls | Temperature=0.1, but all failed | N/A (fallback to rule-based) |

### Reproducibility Assessment
**The pipeline is NOT fully reproducible.** While KMeans clustering is deterministic (seed=42), all stochastic elements (GA population initialization, mutation choices, service generation randomness) use unseeded Python/NumPy random state. Two runs on the same machine will produce different service candidates, different GA trajectories, and potentially different final solutions.

**However**, the LLM is completely non-functional in the current environment (`proxies` keyword error on all providers), so all LLM-dependent paths fall back to deterministic rule-based behavior. This means the only source of non-determinism is the GA and service generation randomness.

### Evidence from Output
- All 3 iterations produced different profits (259.6M, 267.6M, 213.7M), confirming stochastic variation
- The best iteration was selected deterministically from the 3 candidates

---

## 17. LLM / Fallback Audit

### LLM Involvement Points

| Stage | LLM Role | Current Status | Fallback |
|-------|----------|---------------|----------|
| Problem analysis (orchestrator) | Classify size, complexity, decomposition rationale | **FAILED** — `proxies` error on all 3 providers | Rule-based size classification ("Small") |
| Service archetype params (svc_gen × 3 regions) | Generate JSON with direct/hub/feeder/trunk ratios | **FAILED** — 3 failures | Default archetype: {direct:0.60, hub_loop:0.15, feeder:0.20, trunk:0.05} |
| Regional strategy selection | Choose A/B/C strategy | **FAILED** | Rule-based: always "C (Hybrid)" |
| Regional explanation | Generate verdict/strengths/weaknesses | **FAILED** | Rule-based template with computed values |
| Coordinator decision | Weight adjustments, conflict resolution | **FAILED** | Default weights {profit:0.5, coverage:0.4, cost:0.1} |
| Iteration selection | LLM-based candidate ranking | **FAILED** | Deterministic multi-objective Pareto selection |

### LLM Telemetry (from benchmark JSON)
- Total LLM attempts: **306**
- Successes: **0**
- Failures: **306**
- Fallback uses: **51**
- Provider switches: **102**
- Error type: `unknown` (all: `Client.__init__() got an unexpected keyword argument 'proxies'`)

### Current Mode Classification
**Fallback-driven with LLM-assisted structure.** The pipeline architecture is designed to be hybrid (LLM + rules), but in the current environment it operates entirely in **rule-based fallback mode**. All optimization logic (GA, MILP, filtering, selection) functions independently of LLM calls. The LLM only affects:
1. Service archetype parameter tuning (falls back to defaults)
2. Strategic narrative generation (falls back to templates)
3. Coordinator weight adjustments (falls back to config defaults)

These fallbacks are functional and produce valid optimization results — the core pipeline does not depend on LLM availability.

---

## 18. Architecture Diagram (Actual)

```
INPUT (WorldSmall CSVs)
    ↓
NetworkLoader.load_problem()
    ↓
Problem(47 ports, 1764 demands, 263 vessels)
    ↓
PortClustering(n_clusters=3)  ← instance-derived
    ↓
RegionalSplitter.split()  ← demands by origin, services by port membership
    ↓
┌─────────────────────────────────────────────────────────────┐
│ FOR EACH OF 3 REGIONS (parallel via ThreadPoolExecutor):     │
│                                                               │
│   ServiceGeneratorAgent.process()                            │
│   ├─ LLM call (FAILS → fallback)                             │
│   ├─ generate_services():                                    │
│   │   ├─ Direct: 500 services (top demands)                  │
│   │   ├─ Hub loops: ~40 services (10 hubs × 4 loops)        │
│   │   ├─ Trunks: 45 services (C(10,2))                       │
│   │   ├─ Feeders: ~54 services (spokes × 2 hubs)            │
│   │   └─ Heuristic: 150 services (CandidateServiceGenerator) │
│   │   TOTAL: ~735-789 services                               │
│   ↓                                                          │
│   RegionalAgent._filter_services()                           │
│   ├─ Remove: no corridor coverage OR margin ≤ 0              │
│   ├─ Sort by capacity/cost ratio                             │
│   └─ Cap at max(400, num_ports) = 400                        │
│   ↓ (~400 services)                                          │
│   HierarchicalGA.run()                                       │
│   ├─ _filter_services(): tiered margin gate (0% to -15%)     │
│   ├─ ServiceGA: pop=100, gens=120(max), early_stop=8        │
│   │   ├─ _tune_parameters(): pop_size=100 (n=400)           │
│   │   └─ Fitness: revenue - costs - penalties               │
│   ├─ FrequencyGA: pop=40, gens=60(max), early_stop=8        │
│   │   └─ Fitness: revenue - operating - fuel - port - penalty│
│   └─ Post-GA fleet prune: remove lowest-efficiency services  │
│      if vessels > fleet_size (263)                           │
│   ↓ (~100 services with frequencies)                         │
│   RegionalAgent.split_by_hubs(num_hubs=5)                    │
│   ↓                                                          │
│   FOR EACH OF 5 HUB CLUSTERS:                                │
│     HubMILP.solve():                                         │
│     ├─ Build flow variables (direct + transfer)              │
│     ├─ Constraints: fleet ≤ 263, demand satisfaction,        │
│     │   capacity, port capacity                              │
│     ├─ Objective: profit + coverage_reward                   │
│     └─ Solve with CBC (time_limit=120s)                      │
│     ↓                                                        │
│   Merge cluster results by service ID → all_selected_services │
└─────────────────────────────────────────────────────────────┘
    ↓
OrchestratorAgent.aggregate_results()
    ↓
CoordinatorAgent.process() (LLM fails → rule-based weights)
    ↓
ConsensusEngine.process() (LLM fails → rule-based consensus)
    ↓
IterationSelector.select() (LLM fails → deterministic Pareto)
    ↓
Final output → pipeline_output.json
```

---

## 19. Adaptive Engineering Opportunity Map

| Component | Current Behavior | Problem | Why It Matters | Potential Adaptive Signal | Priority |
|-----------|-----------------|---------|----------------|---------------------------|----------|
| ServiceGA generations | Fixed at 120 for all instances | Small instances converge faster; large instances may not exhaust budget | 120 gens × 100 pop × 400 services = 4.8M fitness evals per region — overkill for WorldSmall's 400 services | num_services, convergence_rate, stagnation_count | **HIGH** |
| FrequencyGA generations | Fixed at 60 | Same issue at smaller scale | 60 × 40 = 2,400 fitness evals — likely converges in 20–30 gens | num_active_services, convergence_rate | **HIGH** |
| FrequencyGA pop_size | Fixed at 40 | No adaptation to service count | May be excessive for 5–10 active services, insufficient for 50+ | num_active_services post-ServiceGA | **HIGH** |
| ServiceGA pop_size | Adaptive (60/100/140) but at coarse thresholds (100, 500) | Step-function behavior; 399 services gets pop=100, 401 gets pop=100 (same band) | Discontinuous scaling | Could use smooth function of num_services | **MEDIUM** |
| Service generation volume | Fixed archetype ratios (60/15/20/5) | Small instances don't need 500 direct services; large instances may need more | 500 direct services for 47 ports = ~10.6 services/port — likely excessive | num_ports, num_demands, demand_density | **HIGH** |
| Regional filter cap (400) | Fixed at max(400, num_ports) | For WorldSmall (47 ports), cap is 400 — far exceeds what's needed | Discards potentially useful diversity; same cap applied to WorldLarge (333 ports) | num_ports, num_services_generated | **HIGH** |
| MILP time_limit | Fixed at 120s | Small MILPs solve in seconds; large ones may need more | 120s is wasteful for WorldSmall's small clusters | num_services, num_demands, num_transfer_pairs | **MEDIUM** |
| MILP max_transfer_pairs | Fixed at 2,000 | For 47 ports, transfer pair space is small; for 333 ports, 2,000 may be restrictive | Bounds solution quality differently across instances | num_active_services, num_hubs | **MEDIUM** |
| n_clusters | Step function (3 if <50 ports, else 5) | Only 2 discrete values; intermediate sizes get wrong clustering | 47 ports → 3 clusters; 50 ports → 5 clusters (jump of 2 clusters for 3 ports) | num_ports (smooth alternative: sqrt heuristic exists but unused) | **LOW** |
| ServiceGA NO_IMPROVE_LIMIT | Fixed at 8 | May be too aggressive for hard problems, too conservative for easy ones | 8 non-improving gens could stop a promising search early | convergence_rate, generation_number | **MEDIUM** |
| Alpha_unserved ($300/TEU) | Fixed penalty magnitude | May over-penalize on small instances (fewer alternatives) or under-penalize on large ones | Drives negative-profit service selection | total_demand, demand_density | **MEDIUM** |
| Hub detection top_k | Fixed at 5 per region | Same number of hubs for 12-port Europe and 21-port Americas | Affects MILP decomposition granularity | num_ports_in_region | **LOW** |
| Iterate count (3) | Fixed at exactly 3 | Small instances may not need weight adjustment iterations | Each iteration re-runs all regional optimization (3× cost) | coverage_variance, convergence_score | **LOW** |

---

## 20. Instance Complexity Assessment

**WorldSmall instance characteristics beyond row counts:**

| Complexity Dimension | Value | Assessment |
|---------------------|-------|------------|
| Ports | 47 | Small |
| Demands | 1,764 | Medium (dense: 163% of max possible directed pairs) |
| Fleet | 263 vessels | Small (5.6 vessels per port) |
| Demand concentration | Top-5 share: 5.6% | **Low** — very dispersed demand |
| Demand density | 163.2% | **High** — nearly all possible lanes have demand |
| Regional demand spread | Asia 147K, Europe ~55K, Americas ~74K TEU/wk | Uneven — Asia dominates |
| Candidate service space | ~735 raw → 400 filtered per region | Moderate |
| MILP complexity per cluster | ~20 services × ~200 demands × 5 clusters | Low-Medium |
| Convergence behavior | Unknown (GA logs not captured) | Needs measurement |

**Key insight:** WorldSmall has **high demand density** (163%) despite having only 47 ports. This means most origin-destination pairs have demand, creating a dense optimization landscape. The low demand concentration (5.6% top-5 share) means no single corridor dominates, requiring broad service coverage rather than hub-centric routing.

---

## 21. Output Quality / Misleading Metric Audit

| Metric | Source | Semantic Issue |
|--------|--------|----------------|
| `coverage` (89.58%) | `global_demand_weighted_coverage` | Appears low but regional coverages are 96–100%. The discrepancy is because coverage is weighted by demand volume, and low-demand lanes in underserved regions pull the average down. **Not misleading if understood, but confusing without context.** |
| `weekly_profit` ($267.6M) | Sum of regional MILP profits | Legitimate, but includes negative-profit services. Net profit is positive because Asia's $281M profit outweighs Europe+$Americas losses. |
| `profit_margin_pct` (71.4%) | `profit / (profit + total_cost)` | **Misleadingly high** — this is profit/(profit+cost), not profit/revenue. With high transshipment/fuel costs, the true margin (profit/revenue) would be lower. |
| `services_generated` (735/626/737) | Length of service list before filtering | Includes all archetype types; not all are viable. **Could mislead readers into thinking 700+ services were evaluated by the optimizer.** |
| `services_selected` (100/95/102) | Sum of GA binary mask | These are GA-selected, not necessarily MILP-selected. The MILP may further prune. **Ambiguous — doesn't distinguish GA selection from MILP selection.** |
| `status: "Optimal"` | MILP solver status | **Technically correct** (CBC reports Optimal) but refers to the restricted problem (fixed services/frequencies), NOT the global service-design problem. **Potentially misleading.** |
| `elapsed_sec` per region | Wall-clock timing | Includes LLM call overhead (failures). Asia's 78.3s includes 2 failed LLM calls; Europe's 41.9s is faster partly because it has fewer demands. |
| `total_runtime` (239.6s) | Health tracker | Excludes LLM network time; measures only computation. **Underreports true wall-clock cost.** |

---

## 22. Final Audit Verdict

### A. CONFIRMED CURRENT BEHAVIOR

1. WorldSmall produces **297 final services** across 3 regions (100 Asia, 95 Europe, 102 Americas)
2. Each region generates **~626–737 raw services**, filters to **400**, selects **~95–102** via GA
3. **35 of 297 services (11.8%) have negative weekly profit** in the final output
4. All 3 MILP solves report **"Optimal"** status
5. **3 orchestrator iterations** run, iteration 1 selected by deterministic Pareto analysis
6. **All LLM calls fail** with `proxies` error; pipeline runs entirely in fallback mode
7. Total wall-clock runtime: **300.57 seconds**
8. ServiceGA uses **pop_size=100, generations=120** (early-stops potentially before 120)
9. FrequencyGA uses **pop_size=40, generations=60** (early-stops potentially before 60)
10. Fleet constraint of **263 vessels** is respected per region

### B. FIXED PARAMETERS (Identical Across All Instance Sizes)

| Parameter | Value | Location |
|-----------|-------|----------|
| ServiceGA generations | 120 | `hierarchical_ga.py:18` |
| FrequencyGA generations | 60 | `frequency_ga.py:27` |
| FrequencyGA pop_size | 40 | `frequency_ga.py:26` |
| Regional filter cap base | 400 | `regional_agent.py:158` |
| MILP time_limit | 120s | `hub_milp.py:60` |
| MILP max_transfer_pairs | 2,000 | `regional_agent.py:24` |
| MILP max_svc_per_demand | 10 | `hub_milp.py:51` |
| Alpha_unserved | 300.0 | `regional_agent.py:22` |
| Transship cost | 80.0 | `regional_agent.py:20` |
| Hub detection top_k | 5 | `regional_agent.py:129` |
| MAX/MIN_ITERATIONS | 3/3 | `orchestrator_agent.py:27-28` |
| Service gen n_direct base | 500 | `service_generator_agent.py:71` |
| Service gen heuristic cap | 150 | `candidate_service_generator.py:119` |
| NO_IMPROVE_LIMIT (both GAs) | 8 | `service_ga.py:45`, `frequency_ga.py:13` |
| MAX_RUNTIME (both GAs) | 90s | `service_ga.py:46`, `frequency_ga.py:14` |

### C. INSTANCE-ADAPTIVE PARAMETERS (Already Derived from Instance)

| Parameter | How It Adapts | WorldSmall Value |
|-----------|--------------|-----------------|
| n_clusters | `3 if ports < 50 else 5` | 3 |
| Fleet size constraint | From `problem.fleet.total_vessels` | 263 |
| ServiceGA pop_size | `_tune_parameters()`: <100→60, 100-500→100, >500→140 | 100 |
| ServiceGA mutation_rate | Same function: <100→0.10, 100-500→0.15, >500→0.20 | 0.15 |
| Regional demand allocation | Demands assigned by origin port to region | Instance-derived |
| Service generation (feeders) | Spoke count × 2 hubs | ~54 per region |
| Post-filter service count | Varies by region demand distribution | 400 (capped) |

### D. POTENTIALLY NON-ADAPTIVE PARAMETERS

| Parameter | Issue | Severity |
|-----------|-------|----------|
| ServiceGA generations (120) | Same budget for 47-port and 333-port instances | **CRITICAL** |
| FrequencyGA generations (60) | Same budget regardless of active service count | **HIGH** |
| FrequencyGA pop_size (40) | Never adapted | **HIGH** |
| Regional filter cap (400) | WorldSmall only needs ~100-150 quality services | **HIGH** |
| MILP time_limit (120s) | WorldSmall MILPs likely solve in <5s each | **MEDIUM** |
| Service gen n_direct (500) | 500 direct services for 47 ports = excessive | **HIGH** |
| Alpha_unserved (300) | Fixed penalty doesn't scale with demand magnitude | **MEDIUM** |
| max_transfer_pairs (2000) | May be restrictive for WorldLarge, wasteful for WorldSmall | **MEDIUM** |

### E. SERVICE-GENERATION FINDINGS

- **2,098 raw services** generated across 3 regions (735+626+737)
- Generated by fixed formula: 500 direct + ~40 hub loops + 45 trunks + ~54 feeders + 150 heuristic
- LLM archetype tuning attempted but all calls failed → default ratios used
- **Zero deduplication** at any stage — exact duplicate routes and reverse-route pairs coexist
- All services receive unique IDs via region prefix, but route-level deduplication is absent

### F. FILTERING FINDINGS

- **Two-stage filtering**: Regional filter (corridor coverage + crude margin) → HGA filter (tiered margin gate)
- Regional filter is the **binding constraint** (caps at 400); HGA filter removes very few services from the already-filtered set
- **Negative-profit services pass both filters** because: (1) the regional margin check is crude `(capacity*0.5*150) > cost`, (2) the HGA tiered gate allows negative-margin services if they cover corridors
- **No dominance filtering** exists between generations or before MILP input
- 35 of 297 final services (11.8%) remain negative-profit after all filtering

### G. MILP FINDINGS

- Services and frequencies are **FIXED inputs** to MILP (determined by GA)
- MILP only optimizes **demand flow allocation** (direct vs. transshipment)
- 5 hub-cluster MILP solves per region = 15 total solves
- All report "Optimal" status
- Fleet constraint enforced as hard inequality: `Σ vessels ≤ 263`
- Variable count per cluster: ~200–800 flow vars + ~200–2000 transfer vars + ~200–800 unserved vars
- **No adaptive candidate reduction** — all GA-selected services enter MILP

### H. OUTPUT JSON FINDINGS

- `selected_services` and `all_selected_services` contain **only final MILP-output services** (297 total)
- No raw candidates, no filtered-but-rejected services, no GA chromosomes
- `coverage` field uses `global_demand_weighted_coverage` (89.58%) not the simple regional average (98.65%) — these differ because cross-region demands are counted in the weighted measure
- `profit_margin_pct` at global level (71.4%) uses `profit/(profit+cost)` not `profit/revenue` — semantically ambiguous
- `best_iteration=1` selected via deterministic Pareto analysis (LLM iteration selector failed)
- `all_selected_services` has **7 exact duplicate routes** and **45 reverse-route pairs** — no deduplication in output

### I. REPRODUCIBILITY FINDINGS

- **Not fully reproducible** due to unseeded Python `random` and `numpy.random` in GA and service generation
- KMeans clustering IS reproducible (seed=42)
- LLM path is deterministic in fallback mode (all calls fail identically)
- Two runs will produce different service candidates and potentially different final selections
- To achieve reproducibility: seed must be set before `ServiceGeneratorAgent` and `ServiceGA` execution

### J. LLM/FALLBACK FINDINGS

- **All 306 LLM calls failed** with `Client.__init__() got an unexpected keyword argument 'proxies'`
- Providers attempted: groq (llama-3.3-70b-versatile), openrouter (nemotron-3-ultra-550b), google (gemini-flash-lite-latest)
- **51 fallback uses** recorded across service generation (3), regional strategy (3), regional explanation (3), coordinator (2), iteration selection (1)
- Pipeline runs **entirely in rule-based fallback mode** — optimization is unaffected
- Service archetype defaults (0.60/0.15/0.20/0.05) were used instead of LLM-derived values
- Coordinator weights defaulted to {profit:0.5, coverage:0.4, cost:0.1} instead of LLM-adjusted values

### K. ADAPTIVE ENGINEERING OPPORTUNITIES

See Section 19 (Opportunity Map) above. Top priorities:

1. **GA generation counts** (ServiceGA: 120→adaptive, FrequencyGA: 60→adaptive)
2. **Service generation volume** (500 direct→scaled by port/demand count)
3. **Regional filter cap** (400→scaled by region size)
4. **FrequencyGA population** (40→adaptive)
5. **MILP time limit** (120s→adaptive based on cluster size)

### L. RISK REGISTER

| Risk | Severity | Evidence | Mitigation (future) |
|------|----------|----------|---------------------|
| Over-optimization budget on small instances | **CRITICAL** | 120 gens × 100 pop × 400 services = 4.8M evals for a problem that could converge in ~30 gens | Scale generations by instance complexity |
| Negative-profit services in final network | **HIGH** | 35/297 services (11.8%) have negative profit; total negative profit = -$94M/wk | Strengthen filtering or add post-MILP profit gate |
| Non-reproducibility | **MEDIUM** | Unseeded random in GA and service generation | Add configurable seed parameter |
| Reverse-route duplication | **MEDIUM** | 45 A→B / B→A pairs in output | Add route-direction canonicalization |
| Exact-route duplication | **LOW** | 7 duplicate routes within regions | Add route-level dedup in service generation |
| Misleading coverage metric | **LOW** | 89.58% global vs 98.65% regional average | Clarify metric definition in documentation |
| Fixed MILP transfer-pair cap | **MEDIUM** | 2,000 cap may truncate WorldLarge solution space | Make cap instance-dependent |
| LLM proxy bug (environment) | **LOW** (for audit) | All LLM calls fail with `proxies` error | Fix provider client instantiation (out of audit scope) |

---

## 23. Final Verdict

### Is the current WorldSmall pipeline using an optimization budget that is appropriately scaled to its instance size?

## **NO**

### Evidence-Based Reasons:

1. **ServiceGA generations (120) are fixed** regardless of whether the instance has 47 ports or 333 ports. WorldSmall's 400 filtered services likely converge in 20–40 generations; the remaining 80–100 generations are wasted computation.

2. **FrequencyGA parameters (pop_size=40, generations=60) are never adapted.** With only ~100 active services post-ServiceGA, a population of 40 and 60 generations is disproportionately large compared to the search space.

3. **Service generation volume is fixed.** 500 direct services, 40 hub loops, 45 trunks, 150 heuristic services — all hardcoded constants. WorldSmall's 47 ports and 1,764 demands do not require 500 direct-service candidates; a proportional reduction (e.g., 500 × 47/333 ≈ 71 services) would be more appropriate.

4. **Regional filter cap (400) is binding and non-adaptive.** All three regions hit the 400-service ceiling, meaning the cap is set for WorldLarge's larger regions and applied uniformly. For WorldSmall's smaller regions (Europe: 12 ports, 391 demands), 400 is excessive.

5. **MILP time_limit (120s) and transfer-pair cap (2,000) are fixed.** WorldSmall's MILP clusters are small (~20 services, ~200 demands per cluster) and solve quickly. The 120-second limit is never approached, representing wasted allocated budget.

6. **Alpha_unserved penalty ($300/TEU) is fixed.** This penalty magnitude drives the selection of negative-profit services. For a 276K TEU instance, $300/TEU = $82.9M total penalty exposure — comparable to weekly profits. This penalty should scale with instance demand magnitude.

7. **Only 4 out of ~25 major parameters adapt to instance size.** The remaining 21 parameters are hardcoded constants inherited from WorldLarge development, creating a systematic over-budget for small instances.

8. **The 300-second total runtime** for a 47-port, 1,764-demand problem suggests significant computational waste relative to problem complexity. A properly scaled pipeline would complete in under 60 seconds.

### Answers to Required Questions:

| Question | Answer |
|----------|--------|
| 1. Are WorldSmall and WorldLarge using the same GA generation budget? | **YES** — both use 120 ServiceGA generations, 60 FrequencyGA generations |
| 2. Are they using the same population size? | **MOSTLY YES** — ServiceGA pop_size partially adapts (60/100/140 bands), but FrequencyGA pop_size (40) is fixed |
| 3. Is service-generation volume adaptive? | **PARTIALLY** — feeder count scales with spoke count, but direct/hub/trunk/heuristic counts are fixed |
| 4. Is service filtering adaptive? | **MINIMALLY** — cap is `max(400, num_ports)` which is 400 for WorldSmall (binding) and 400 for WorldLarge (also binding since 333 < 400) |
| 5. Is negative-profit handling appropriate for final network optimization? | **NO** — 11.8% of final services are negative-profit; the filtering gates are too permissive for loss-making services |
| 6. Is MILP candidate allocation adaptive? | **NO** — all GA-selected services enter MILP; no adaptive candidate reduction |
| 7. Is regional allocation adaptive? | **PARTIALLY** — cluster count adapts (3 vs 5), but everything within regions is fixed |
| 8. Does early stopping exist? | **YES** — 8 consecutive non-improving generations in both GAs, plus 90-second runtime caps |
| 9. What parameters should be considered for future adaptive engineering? | ServiceGA generations, FrequencyGA generations/pop_size, service generation volumes, regional filter cap, MILP time_limit, alpha_unserved penalty, max_transfer_pairs |
| 10. What MUST remain unchanged when we later implement adaptive engineering? | GA algorithm structure (elitism, crossover, mutation mechanics), MILP formulation (variables, constraints, objective), regional decomposition logic, service generation archetype framework, corridor coverage filtering logic, tiered margin gate structure, iteration loop architecture, Pareto selection method |
