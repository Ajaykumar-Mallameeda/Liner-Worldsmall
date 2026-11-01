# File inventory for the C3 configuration (2026-10-16)

Method: static import closure (AST, lazy imports included) from `tests/test_orchestrator.py` (the C3 pipeline driver),
from `backend/server.py` (the real API entry, per `Dockerfile` CMD and `scripts/verify_start_backend.ps1`) and from the
frontend entry `index.html -> src/main.jsx`; data files from the loader's explicit path table. Nothing was deleted or moved
except the already-announced archive of the three experiments. "Not needed" means NOT REACHED by a C3 run; it is a
candidate list for the owner, not an instruction.

Verification: the orchestrator test (C3 flags applied) passed 373/373 on the full tree (profit 44.61 M, run 2). A run on a tree
holding ONLY the section-A files (78 files: 71 `src/`, the driver, 5 data files, the freeze JSON; no backend, frontend, maritime, legacy,
scripts, other tests) also passed: 372/372, exit 0, profit 45.70 M, coverage 45.8 %, 28 services, 162/263 vessels, 380 s
(`D:\liner_scratch_continuation\orchestrator_minimal_run1.log`). The one assertion fewer than the full tree is run-dependent
(that run's local search applied no move, so its move-only checks did not execute), not a missing file. The frontend/backend
parts of section A were established by import analysis only; they were not run in a browser.

## A. Operational for C3 (keep)

**Entry / driver:** `tests/test_orchestrator.py` (+ `tests/__init__.py`).
**Data (5 files, `data/raw/WorldSmall/`):** `ports.csv`, `Demand_WorldSmall_Fixed_Sep.csv`, `dist_dense.csv`, `fleet_WorldSmall.csv`, `fleet_data.csv`.
**Reference for the new comparison section:** `reports/continuation_20261015/ws1_provenance/C3_baseline_freeze.json` (optional: a warning if absent).

**`src/` (71 files):**
- `src/__init__.py`, `src/config/optimizer_config.py`, `src/data/network_loader.py`
- `src/agents/`: `__init__, base, coordinator_agent, orchestrator_agent, regional_agent, service_generator_agent`
- `src/decomposition/`: `port_clustering, regional_splitter`
- `src/network/` (C3 core): `__init__, assumption_register, bunker_prices, class_variants, economics, flow_reopt, ledger, local_search, metrics, network_milp, paths, physical_rules, plan, reconcile, solve_semantics, strategy_report, trunk_candidates`
  - C3 flags live in: `network_milp.py` (VUB, support cap), `local_search.py`, `trunk_candidates.py`, wired by `plan.py` / `reconcile.py`
- `src/optimization/`: `__init__, adaptive_budget, data, frequency_ga, hierarchical_ga, hub_milp, normalization, service_ga`
- `src/pipeline/iteration_selection.py`
- `src/services/`: `candidate_service_generator, class_screening, demand_coherent, hub_detector, regional_filter, route_operators, service_feasibility`
- `src/utils/`: `__init__, config, fuel_cost, health_tracker, logger, rng, shared_context`
- `src/validation/`: `__init__, archetype_validator, consensus_engine, regional_policy_validator, weight_validator`
- `src/llm/`: `__init__, actuation, client, evaluator, evaluator_manager, metrics` and `providers/{__init__, base, cerebras_provider, google_provider, groq_provider, openrouter_provider, registry, router, types}` (imported by the agents; with no `.env` they fall back, no external call)

**Serving the result (not needed to compute C3, needed to show it):**
- `backend/server.py` (+ `maritime/` 33 files it imports; maritime features are gated by `MARITIME_INTELLIGENCE_ENABLED`, default off)
- `pipeline_output.json` (written by the test), `frontend/public/pipeline_output.json`
- Frontend: `index.html`, `package.json`, `package-lock.json`, `vite.config.js`, `tailwind.config.js`, `postcss.config.js`, and the 71 `src/` files reached from `src/main.jsx` (main chain: `main.jsx -> views/MaritimeDashboard.jsx -> views/console/*`)

## B. Keep (supports correctness / the work that worked, not part of the run)

- `src/benchmark/{__init__, paper_ledger, paper_evaluator}.py` (paper-cost parity; used by tests)
- `tests/` (all except those listed in C): C3-relevant: `test_milp*`, `test_local_search`, `test_trunk_candidates`, `test_bound_semantics`, `test_solver_status_semantics`, `test_network_*`, `test_paper_cost_parity`, `test_paper_evaluator`, `test_worldsmall_*`, `test_unit_contract`, `test_rng_control` ...
- `reports/continuation_20261015/`, `reports/final_campaign_audit/CONTINUATION_2026_10_15_REPORT.md` (evidence for the verdict)
- `archive/experimental_not_retained_2026-10-15/` (the three experiments, pytest-ignored)
- `RL_paper.pdf` (source of the six parity targets), `requirements.txt`, `Dockerfile`, `LICENSE`, `README.md`

## C. Not needed for a C3 run (candidates; none deleted)

**C1. `src/` files never imported by the C3 path (18):**
- Unreferenced anywhere: `src/data/graph_builder.py`, `src/data/preprocess.py`, `src/pipeline/optimization_pipeline.py`, `src/pipeline/orchestration.py`, `src/utils/fuel_cost_legacy.py`, `src/utils/sample.py`
- Superseded versions kept "verbatim", referenced only in docstrings: `src/optimization/{frequency_ga_legacy, hierarchical_ga_legacy, hub_milp_legacy, service_ga_legacy}.py`
- Used only by tests: `src/agents/regional_metrics.py`, `src/agents/regional_policy_mapping.py`, `src/validation/regional_policy_validator_v2.py`, `src/network/opportunities.py` (keep if you keep their tests)
- Used only by the alternate backends: `src/optimization/flow_optimizer.py`

**C2. Backend (18 of 19 files; only `server.py` is the entry):** `backend/{main, unified_main, api_models, event_schemas, event_validator, pipeline_streamer, real_orchestrator_integration, websocket_manager, __init__}.py`, `backend/models/schemas.py`, `backend/routes/{metrics, pipeline, regions, websocket}.py`, `backend/services/{__init__, optimization_service, pipeline_service, pipeline_streamer}.py`, `backend/optimization_results.db`

**C3. Frontend (42 of 113 `src/` files not reached from `main.jsx`):** `components/common/{BenchmarkBadge, Counter, Sparkline}`, `components/console/{CommandCenterShell, Drawer, EventStream, IdentityBar, MetricStrip, NetworkIntelligenceCanvas, RegionRail, Sparkline, SystemStateBar, TelemetryRail}`, `components/layout/{Footer, Header, Sidebar}`, `components/maritime/{AgentTopology, SourceLayerRail}`, `components/optimization/{ConflictView, DecisionExplanation, DecisionTrace, ExportPanel, FeedbackView, FleetDashboard, FleetPanel, FunnelView, OptimizationInsights, PipeNode, PipelineView, PortPanel, RegionPipelineNode, RouteTable, ScenarioWorkspace}`, `components/overview/{BackendCertification, KpiCard, RuntimeHealth, SummaryView}`, `components/regions/{RegionCard, RegionDetails, RegionalIntelligence}`, `utils/fleetStats.js`, `views/MaritimeCommandCenter.jsx`; plus `frontend/mock-server.cjs`, `frontend/test_api.js`. (`fleetStats.js` has a test, `frontend/tests/fleetStats.test.mjs`.)

**C4. Data:**
- `data/raw/WorldLarge/` (9 files; WorldLarge must not be read), `data/datasets/large_shipping_problem.json`
- Duplicate lower-case WorldSmall files read only by tests / audit scripts: `data/raw/WorldSmall/{demand_world_small.csv, fleet_world_small.csv}`
- `data/datasets/worldsmall_shipping_problem.json` (backend models / tests only), `data/scenarios/WorldSmall_revised_transit_v1/` (referenced by no code; evidence for the transit-file decision), `data/pricing/bunker_snapshot_*.json` (opt-in bunker pricing, tests only), `data/maritime/snapshots/` (maritime only)

**C5. Root documents and artefacts (no code reads them as input):** `MA_01..MA_09_*` (13 audit files), `MULTI_AGENT_INDEPENDENT_*.md`, `PHASE_MULTI_AGENT_*.md`, `RUNTIME_*_REPORT.json`, `RUNTIME_PIPELINE_BENCHMARK.json`, `PROVIDER_HEALTH_REPORT.json`, `optimization_results.db`, `convert_tables.py`, `CHANGELOG.md`, `CITATION.cff`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, `SECURITY.md`, `docs/`, `assets/`, `logs/`. `SYSTEM_TRUTH_REPORT.md` and `P2_DIAGNOSTIC_RUNTIME_VALIDATION_REPORT.md` are OUTPUTS rewritten by the orchestrator test (they are modified in your working tree).

**C6. Other trees:** `legacy/` (140 files, self-declared archive), `maritime/` (optional live-data package; only `backend/server.py` imports it), `scripts/` (audit/benchmark helpers; none on the C3 path), `verification/`, `venv/`, `reports/` older campaign folders (230 MB of evidence; keep unless you decide otherwise).

**C7. Tests tied to things in C** (would need to go with them): `tests/test_regional_policy_validator_v2.py`, `tests/test_opportunities.py`, `tests/maritime/*`, `tests/test_provider_system/`, and the 29 failing documentation tests in `tests/test_economic_metric_documentation.py` (decision D-11).
