# PROJECT X — Runtime Causal Graph

Every edge below is an **actual runtime dependency** (verified by execution + code). No cosmetic arrows.

## 1. Master Causal Chain — main() → pipeline_output.json

```mermaid
flowchart TD
    DR["tests/test_orchestrator.py::test_orchestrator"]
    DS["data/datasets/large_shipping_problem.json"]
    P["Problem\n(333 ports, 9622 demands)"]
    DR --> DS --> P

    ORCH["OrchestratorAgent.process"]
    P -->|"owned + mutated"| ORCH
    ORCH -->|"seeds CONFIG weights"| PW["Problem.profit/coverage/cost_weight"]

    subgraph ITER["for iteration in 0..MAX_ITERATIONS-1"]
        PW -->|"deepcopy → regional problems"| SPLIT["RegionalSplitter.split"]
        SPLIT -->|"thread pool"| RA["RegionalAgent × 5\n(ServiceGen → GA → MILP)"]
        RA -->|"selected_services + metrics"| RR["regional_results[]"]

        PW -->|"runtime weights → ServiceGA fitness"| GA
        RA --> GA["HierarchicalGA → ServiceGA\n(w_profit·profit + w_cov·cov − w_cost·cost)"]
        GA -->|"chromosome {services, frequencies}"| MILP["HubMILP.solve"]
        MILP -->|"optimized services"| RA

        RR --> COORD["CoordinatorAgent.process\n(conflicts + metrics + LLM/rules)"]
        COORD -->|"decisions + feedback"| FEED["feedback\n{needs_rerun, weight_adjustments}"]
        COORD -->|"global_metrics (demand-weighted)"| GM["average_coverage = sat/total_demand"]

        RR --> CONS["ConsensusEngine.process\n(weighted voting)"]
        FEED --> CONS
        CONS -->|"final_weight_adjustments"| PW
        CONS -->|"final_archetype_params"| ARCH["next-iter ServiceGen override"]

        PW -->|"next iteration's GA objective"| ITER
        FEED -->|"APPLIED unconditionally → Problem"| PW
        PW -->|"stop criteria evaluated AFTER feedback applied"| STOP{"needs_rerun?\niteration cap?"}
        STOP -->|"continue"| SPLIT
        STOP -->|"stop"| AGG
    end

    RR --> AGG["aggregate_results\n(demand-weighted coverage)"]
    AGG --> SUM["summary_metrics"]
    SUM --> ES["executive_summary\n(deterministic, runtime-derived)"]
    SUM --> SC["shared_context\n(archetype plan + hub strategy)"]
    AGG --> POP[("pipeline_output.json")]
    ES --> POP
    SC --> POP
    ITER --> AUD["iteration_audit (weights_used, coverage, needs_rerun)"]
    AUD --> POP

    POP -->|"REST /api/pipeline-output"| BE["FastAPI backend"]
    POP -->|"WS /ws/pipeline"| BE
    BE -->|"normalize"| DASH["React dashboard"]
```

## 2. Decision → Propagation → Consumption → Result (per subsystem)

### 2.1 Coordinator (decision) → GA (result)

```
Coordinator._generate_decisions  →  decisions.weight_adjustments
   │  (LLM JSON, validated by WeightValidator, or rule fallback)
   ▼
ConsensusEngine  →  final_weight_adjustments  →  problem.profit/coverage/cost_weight
   ▼
_apply_feedback (unconditional)  →  Problem mutated  →  next iteration split (deepcopy)
   ▼
ServiceGA.evaluate  →  fitness = w_p·profit_norm + w_c·cov_norm − w_cst·cost_norm
   ▼
GA selection / mutation / ranking  →  chromosome  →  HubMILP  →  regional selected_services
   ▼
Different solution  →  different regional metrics  →  different global coverage/profit
```

### 2.2 Consensus (decision) → Service Generation (result)

```
ConsensusEngine  →  final_archetype_params {archetype_mix, vessel_bias, hub_focus}
   ▼  (stored on self._previous_consensus)
next iteration: orchestrator forwards → RegionalAgent → ServiceGeneratorAgent.process
   ▼  (validate_archetype_params, logged CONSENSUS_APPLIED)
generate_services(direct/hub_loop/feeder/trunk counts)  →  candidate pool size/composition
   ▼  (verified: reconciled ratios ≠ defaults)
GA sees a different candidate pool  →  different chromosome  →  different solution
```

### 2.3 Coordinator feedback (signal) → Loop control (result)

```
Coordinator._generate_feedback_signals  →  {needs_rerun, coverage_gap, weight_adjustments}
   ▼
feedback applied to Problem BEFORE stop decision  (verified: unconditional)
   ▼
Stop only on needs_rerun=False OR iteration cap  (coverage-gain rule removed)
   ▼
3 iterations executed (verified)  →  each iteration uses the previous iteration's state
```

### 2.4 GA chromosome (artifact) → MILP (consumer)

```
HierarchicalGA.run → chromosome {services[0/1], frequencies, coverage_estimate, skip_milp}
   │
   ├─ services + frequencies ──► HubMILP(sub, chromosome).solve() → optimized services
   └─ skip_milp=True (coverage_estimate < 30%) ──► GA-only economics path (MILP skipped)
```

### 2.5 Backend (consumer) → Dashboard (result)

```
pipeline_output.json (single source of runtime truth)
   │
   ├─ server.load_pipeline_data_if_stale()  →  /api/metrics/summary, /api/regions, ...
   ├─ /api/pipeline-output (fresh read)     →  runtimeAdapter.normalizeGlobal/Region/Iteration
   └─ /ws/pipeline replay                     →  real-time event stream
```
No simulation pathway shadows this path. The legacy `RealOrchestratorIntegration` is explicitly labeled SIMULATION (State B) and the fake "Gurobi" claim corrected.

## 3. Coverage truth — one number everywhere

```
satisfied = Σ regional satisfied_demand         (from MILP results)
total     = Σ regional total_demand = true global demand  (demand-conserved)
coverage  = satisfied / total × 100
```
Consumed identically by: Coordinator `average_coverage` → `coverage_gap` → feedback weights → audit `coverage` → `summary_metrics.coverage`. Verified in the final run: **40.94 / 40.94 / 40.94** (identical to the decimal across coordinator, iteration audit, and final summary).
