# REPOSITORY RUNTIME MAP

This document describes the **actual** runtime execution path of the AI Vessel Routing System, traced from the entry point through every file that participates in a live run. All claims are evidence-based; sources are file paths.

---

## 1. Runtime Entry Point

**Documented entry point:** `python -m tests.test_orchestrator`

**Confirmation:** `tests/test_orchestrator.py` ends with:

```python
if __name__ == "__main__":
    test_orchestrator()
```

The `test_orchestrator()` function is the producer of `pipeline_output.json` (the canonical runtime artifact).

**Helper entry points (also load or re-run):**

* `backend/server.py` and `backend/unified_main.py` — read `pipeline_output.json` from disk on startup; do **not** re-run the pipeline.
* `backend/real_orchestrator_integration.py` — separate driver that re-runs the orchestrator and streams results via WebSocket.

---

## 2. Core Execution Chain (Python)

```
tests/test_orchestrator.py::test_orchestrator()
  │
  │  Loads:
  │   - data/datasets/sample_problem.json (or other) via load_problem()
  │   - Distance matrix via src/data/network_loader.py::NetworkLoader
  │
  ├─ OrchestratorAgent()                        src/agents/orchestrator_agent.py
  │     - self.regional_agents: 5 × RegionalAgent
  │     - self.coordinator:      CoordinatorAgent
  │     - self.consensus_engine: ConsensusEngine
  │     - self.shared_context:   SharedContext
  │     - self.iteration_results: []      (per-iteration snapshots, PROJECT X)
  │     - self.iteration_audit:   []      (per-iteration audit entries)
  │     - MAX_ITERATIONS = 3               (line 25)
  │     - MIN_ITERATIONS = 3               (line 33, hard floor)
  │
  ├─ Iteration loop (mandatory 3 candidates)
  │     │
  │     ├─ RegionalAgent("regional_asia" | "regional_europe" | "regional_americas" |
  │     │                "regional_middle_east" | "regional_africa")    src/agents/regional_agent.py
  │     │     ├─ src/agents/regional_metrics.py
  │     │     ├─ src/agents/regional_policy_mapping.py
  │     │     └─ src/agents/service_generator_agent.py
  │     │           └─ src/services/candidate_service_generator.py
  │     │           └─ src/services/hub_detector.py
  │     │
  │     ├─ src/optimization/frequency_ga.py
  │     ├─ src/optimization/hierarchical_ga.py
  │     ├─ src/optimization/hub_milp.py
  │     ├─ src/optimization/flow_optimizer.py
  │     └─ src/optimization/normalization.py
  │
  │     ├─ CoordinatorAgent()                  src/agents/coordinator_agent.py
  │     │     - COVERAGE_TARGET = 70.0  (%)
  │     │     - PROFIT_FLOOR    = 0.0
  │     │     - MAX_RERUN_ITERATIONS = 3
  │     │     └─ src/validation/consensus_engine.py
  │     │     └─ src/validation/weight_validator.py
  │     │     └─ src/validation/archetype_validator.py
  │     │     └─ src/validation/regional_policy_validator_v2.py
  │     │
  │     └─ Snapshot:  iteration_results.append({iteration, status, metrics,
  │                                              regional_results, weights_used,
  │                                              consensus_result, feedback,
  │                                              decision_output, shared_context,
  │                                              selected_services, candidate_quality})
  │
  ├─ IterationSelector.select(iterations, …)   src/pipeline/iteration_selection.py
  │     - PARETO_OBJECTIVES = [weekly_profit, global_demand_weighted_coverage,
  │                             operating_cost, unserved_demand,
  │                             negative_profit_regions, constraint_violations,
  │                             conflict_count]
  │     - DEFAULT_SCORING_WEIGHTS = {weekly_profit: 0.60,
  │                                   global_demand_weighted_coverage: 0.25,
  │                                   operating_cost: 0.15}
  │     - Selection: LLM (if available) → validate → otherwise deterministic
  │     - Output: best_iteration, final_selected_iteration, scorecards
  │
  └─ Final aggregation → pipeline_output.json (root)
        - Top-level keys: orchestrator, status, problem_analysis, regional_results,
          decision_output, executive_summary, summary_metrics, iteration_audit,
          iterations_run, selected_services, all_selected_services,
          iteration_results, iteration_selection, best_iteration,
          final_selected_iteration, health_status, consensus_result,
          shared_context, llm_runtime_metrics, test_scorecard
```

**Current live run values (from root `pipeline_output.json`):**

| Field | Value |
| --- | --- |
| `iterations_run` | 3 |
| `best_iteration` | 2 |
| `final_selected_iteration` | 2 |
| `iteration_selection.selection_method` | `deterministic_multi_objective` |
| `iteration_selection.fallback_used` | `True` |
| `summary_metrics.weekly_profit` | 565,040,785.75 |
| `summary_metrics.coverage` | 42.82 |
| `summary_metrics.total_runtime` | 599.9s |
| `test_scorecard.score` | 98.8 (322/326 assertions passed) |
| `health_status.success_rate` | 1.0 |

---

## 3. Backend Chain

```
pipeline_output.json (root, on disk)
  │
  └─ backend/server.py::load_pipeline_data()        (lines 65–170)
        │
        ├─ Reads root pipeline_output.json
        ├─ Populates current_state["regions"]      (from regional_results)
        ├─ Populates current_state["iterations"]   (from iteration_audit, with coverage & globalCoverage)
        ├─ Populates current_state["iteration_selection"], ["best_iteration"], ["iteration_results"]
        ├─ Populates current_state["metrics"]      (weeklyProfit, annualProfit, totalCost, ...)
        └─ Returns True/False
  │
  └─ backend/unified_main.py                         (parallel logic)
        └─ Same path
  │
  └─ FastAPI app
        ├─ HTTP routes
        │     - routes/pipeline.py
        │     - routes/metrics.py
        │     - routes/regions.py
        ├─ WebSocket routes/websocket.py
        └─ Static files (frontend/dist served by unified_main via StaticFiles)
  │
  └─ WS events: pipeline_started, stage_started, stage_completed,
                pipeline_warning, decision_output, ...
        (Generated by backend/real_orchestrator_integration.py)
```

**Active entry point:** `backend/unified_main.py` (its own docstring: *"Consolidates main.py and server.py into a single production-ready server"*). `backend/main.py` and `backend/server.py` are duplicates kept in the tree; `backend/main_backup.py` is a snapshot of `main.py`.

**Mock / fallback:** `frontend/mock-server.cjs` exists for frontend dev; not used in production.

---

## 4. Frontend Chain

```
frontend/index.html                              (Vite source HTML)
  │
  └─ frontend/src/main.jsx
        └─ <MaritimeDashboard />                 frontend/src/views/MaritimeDashboard.jsx
              │
              ├─ useOptimizationState()           frontend/src/hooks/useOptimizationState.js
              │     └─ runtimeAdapter.js         frontend/src/runtime/runtimeAdapter.js
              │           ├─ reads pipeline_output.json shape
              │           └─ reads WebSocket payload shape
              │
              ├─ Layout
              │     ├─ layout/Header.jsx
              │     ├─ layout/Sidebar.jsx
              │     ├─ layout/Footer.jsx
              │     └─ layout/navItems.js
              │
              ├─ Overview
              │     ├─ overview/KpiCard.jsx
              │     ├─ overview/SummaryView.jsx
              │     ├─ overview/RuntimeHealth.jsx
              │     └─ overview/BackendCertification.jsx
              │
              ├─ Regions
              │     ├─ regions/RegionCard.jsx
              │     ├─ regions/RegionDetails.jsx
              │     └─ regions/RegionalIntelligence.jsx
              │
              └─ Optimization
                    ├─ optimization/PipelineView.jsx (+PipeNode, RegionPipelineNode)
                    ├─ optimization/FunnelView.jsx
                    ├─ optimization/FeedbackView.jsx
                    ├─ optimization/ConflictView.jsx
                    ├─ optimization/FleetPanel.jsx (+FleetDashboard)
                    ├─ optimization/RouteTable.jsx
                    ├─ optimization/PortPanel.jsx
                    ├─ optimization/DecisionTrace.jsx
                    ├─ optimization/DecisionExplanation.jsx
                    ├─ optimization/OptimizationInsights.jsx
                    ├─ optimization/ExportPanel.jsx
                    └─ optimization/ScenarioWorkspace.jsx
```

**No router** (no `react-router` in `frontend/package.json`). Navigation is by `navItems.js` and tab state inside `MaritimeDashboard.jsx`.

**No landing page is currently wired** (per the PROJECT X remediation). The historical `assets/dashboard/landing-dashboard.png` is the only remaining evidence.

---

## 5. Pipeline Output Producer

**Sole producer:** `tests/test_orchestrator.py` (via `test_orchestrator()`).

**Producers by file:line:**

* `tests/test_orchestrator.py:1680` — `def test_orchestrator():`
* `tests/test_orchestrator.py:4059` — `if __name__ == "__main__": test_orchestrator()`

**Schema (top-level keys):** `orchestrator, status, problem_analysis, regional_results, decision_output, executive_summary, summary_metrics, iteration_audit, iterations_run, selected_services, all_selected_services, iteration_results, iteration_selection, best_iteration, final_selected_iteration, health_status, consensus_result, shared_context, llm_runtime_metrics, test_scorecard`.

**`pipeline_output.json` is reproducible** by re-running the test, and it is the runtime truth.

---

## 6. Pipeline Output Consumers

| Consumer | File | How |
| --- | --- | --- |
| Backend (live data) | `backend/server.py::load_pipeline_data()` | Reads from disk; populates `current_state`. |
| Backend (alternative) | `backend/unified_main.py` | Reads from disk; populates equivalent state. |
| Frontend (via API) | `frontend/src/services/apiClient.js` | HTTP. |
| Frontend (via WS) | `frontend/src/services/websocketManager.js` | WS subscription. |
| Frontend (normalization) | `frontend/src/runtime/runtimeAdapter.js` | Normalizes both sources for components. |
| Frontend (state) | `frontend/src/hooks/useOptimizationState.js` | Subscribes to adapter. |
| Components | `frontend/src/components/optimization/*`, etc. | Consume via hook. |

---

## 7. Iteration System

| Property | Value | Source |
| --- | --- | --- |
| MAX_ITERATIONS | 3 | `src/agents/orchestrator_agent.py:25` |
| MIN_ITERATIONS | 3 (hard floor) | `src/agents/orchestrator_agent.py:33` |
| MAX_RERUN_ITERATIONS (per-rerun) | 3 | `src/agents/coordinator_agent.py:33` |
| Snapshot list | `iteration_results` | `src/agents/orchestrator_agent.py:66` |
| Audit list | `iteration_audit` | `src/agents/orchestrator_agent.py:58` |
| Selector | `IterationSelector` (Pareto + LLM + deterministic) | `src/pipeline/iteration_selection.py:576` |
| Termination rule | Only `MAX_ITERATIONS` ceiling or unrecoverable exception | `src/agents/orchestrator_agent.py` (comment lines 26–33) |
| Default scoring weights | profit 0.60, coverage 0.25, cost 0.15 | `src/pipeline/iteration_selection.py:70-74` |
| Pareto objectives | weekly_profit, global_demand_weighted_coverage, operating_cost, unserved_demand, negative_profit_regions, constraint_violations, conflict_count | `src/pipeline/iteration_selection.py:59-67` |
| Selection method (this run) | deterministic_multi_objective (LLM fallback) | `pipeline_output.json.iteration_selection` |

---

## 8. Coverage Metrics

**Two distinct coverage semantics, correctly separated:**

| Metric | Where produced | What it is | Where it is consumed |
| --- | --- | --- | --- |
| `coverage_percent` | `src/agents/regional_agent.py` | **Regional** coverage (per region). | `summary_metrics`, iteration scorecard. |
| `average_regional_coverage` | orchestrator | Average of `coverage_percent` across regions. | iteration scorecard, `pipeline_output.json`. |
| `global_demand_weighted_coverage` | `src/pipeline/iteration_selection.py` (line 46) and producer | **Network demand-weighted** coverage. The PROJECT X canonical metric. | iteration scorecard, iteration selection weight, frontend `globalCoverage`. |
| `coverage` (in `summary_metrics`) | producer | Equals `global_demand_weighted_coverage` (the network-level summary). | backend `current_state["metrics"]["coverage"]`, frontend. |

**Backend mapping (`backend/server.py:109-117`):**

```python
"coverage":      i.get("coverage", 0),                            # regional average
"globalCoverage": i.get("global_coverage", i.get("coverage", 0)), # demand-weighted
```

No semantic collision in code; the metric names distinguish the two values.

---

## 9. Final Selection Path

```
iteration_results (list of 3 snapshots) → IterationSelector.select(...)
  → candidate_iterations = [0, 1, 2]
  → pareto_optimal_iterations = [0, 1, 2]
  → weighted scorecards (0: 0.526, 1: 0.15, 2: 0.803)
  → selection_method = "deterministic_multi_objective"
  → fallback_used = True
  → selected_iteration = 2
  → best_iteration = 2
  → final_selected_iteration = 2
```

The final pipeline output's `regional_results`, `summary_metrics`, `decision_output`, and `selected_services` are constructed from the **selected iteration's snapshot**, never from the last iteration.

---

## 10. Dashboard Data Path

```
test_orchestrator.py
   ↓
pipeline_output.json (root, 2.4MB)
   ↓
backend/server.py::load_pipeline_data()  (or backend/unified_main.py)
   ↓
in-memory current_state (dict)
   ↓
┌─ /api/* (HTTP)               ┐
└─ /ws   (WebSocket)            │
   ↓                            │
frontend API/WS clients         │
   ↓                            │
runtime/runtimeAdapter.js       │
   ↓                            │
useOptimizationState hook       │
   ↓                            │
MaritimeDashboard + components  │
   ↓                            │
KPI cards, panels, dashboards   │
```

---

## 11. Summary

| Question | Answer | Source |
| --- | --- | --- |
| Who runs the optimization? | `tests/test_orchestrator.py::test_orchestrator()` | file itself |
| What is the runtime entry? | `python -m tests.test_orchestrator` | docstring + line 4059 |
| What is the runtime truth? | `pipeline_output.json` (root) | `backend/server.py:69` |
| What is the active backend? | `backend/unified_main.py` | its own docstring |
| What is the active frontend? | `frontend/src/main.jsx → MaritimeDashboard.jsx` | `frontend/src/main.jsx` |
| How are iterations selected? | `IterationSelector` (Pareto + LLM + deterministic) | `src/pipeline/iteration_selection.py` |
| How many iterations? | MAX=3, MIN=3 (hard floor) | `src/agents/orchestrator_agent.py:25,33` |
| What is the difference between regional and global coverage? | `coverage_percent` = regional; `global_demand_weighted_coverage` = network demand-weighted | `src/agents/regional_agent.py` + `src/pipeline/iteration_selection.py:46` |
| Where are iterations stored? | `iteration_results` list in orchestrator; serialized into `pipeline_output.json.iteration_results` | `src/agents/orchestrator_agent.py:66` + output schema |
| Where is the final iteration chosen? | `IterationSelector` selects from `iteration_results` | `src/pipeline/iteration_selection.py` |
| Are there duplicate `pipeline_output.json` files? | Yes: 3 copies (root, `frontend/public/`, `frontend/dist/`); only root is canonical | file existence + diff |

---

END OF RUNTIME MAP.
