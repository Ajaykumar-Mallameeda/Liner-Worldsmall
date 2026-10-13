# FRONTEND RUNTIME INTEGRATION MASTER PLAN

**Phase F1 — Frontend Runtime Integration & Product Foundation**

| Attribute | Value |
|---|---|
| **Date** | 2026-06-30 |
| **Project** | AI Vessel Routing System — Multi-Agent Liner Shipping Optimizer |
| **Status** | <span style="color:orange">AUDIT COMPLETE — PLAN READY</span> |
| **Backend Status** | **FROZEN** — 309/313 assertions passing, pipeline_output.json is the ONLY runtime truth |
| **Frontend Status** | **NOT RUNTIME-ALIGNED** — Multiple inconsistencies, dead code, dual implementations |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Runtime Truth Mapping](#2-runtime-truth-mapping)
3. [Dashboard Architecture](#3-dashboard-architecture)
4. [API Audit](#4-api-audit)
5. [WebSocket Audit](#5-websocket-audit)
6. [Data Flow Map](#6-data-flow-map)
7. [Component Inventory](#7-component-inventory)
8. [Dashboard Quality Score](#8-dashboard-quality-score)
9. [Missing Intelligence](#9-missing-intelligence)
10. [Commercial Gap Analysis](#10-commercial-gap-analysis)
11. [Product Vision](#11-product-vision)
12. [Sprint Roadmap](#12-sprint-roadmap)
13. [Risks](#13-risks)
14. [Final Verdict](#14-final-verdict)
15. [Freeze Decision](#15-freeze-decision)

---

## 1. Executive Summary

### Current State
The frontend is a **monolithic, single-file React application** (`MaritimeDashboard.jsx`, 2,509 lines) that contains **all views, all components, all state management, and WebSocket logic** in one module. It was built rapidly for demos and has **drifted significantly from the frozen backend runtime**.

### Critical Problems

| # | Issue | Severity |
|---|---|---|
| 1 | **Dual API clients** — `apiClient.ts` (TypeScript) and `client.js` (JavaScript) both exist, both partially used | HIGH |
| 2 | **Dual Zustand stores** — `dashboardStore.js` (JS, default export) and `dashboardStore.ts` (TS, named exports) with different fields | HIGH |
| 3 | **Dual WebSocket implementations** — inline WebSocket hook in MaritimeDashboard + `WebSocketClient` class + `apiClient.ts` WebSocket | HIGH |
| 4 | **Monolithic component** — 2,509-line MaritimeDashboard.jsx with 10 views inline | HIGH |
| 5 | **Field name mismatches** — backend `snake_case` vs frontend `camelCase` not consistently mapped | CRITICAL |
| 6 | **Hardcoded fallback data** — MapView corridor defaults, benchmark configs hardcoded | HIGH |
| 7 | **Coverage display error** — backend offers both 63.7% (average) and 49.7% (OD-based); frontend picks wrong one | CRITICAL |
| 8 | **Import chain broken** — `DashboardProvider.tsx` imports `'../store/dashboardStore'` which resolves to `.ts` not `.js` | MEDIUM |
| 9 | **No loading states** — components show "—" or zeros while data loads | MEDIUM |
| 10 | **Dead components** — `Dashboard.jsx`, `LiveDashboard.jsx/`, `TestComponent.jsx` likely unused | LOW |

### Key Metric: Coverage Display Bug

The backend produces TWO coverage values:
- `summary_metrics.coverage` = **49.7%** (true OD-based coverage, the correct metric)
- `decision_output.global_metrics.average_coverage` = **63.7%** (simple average of 5 regional coverages)

The frontend displays **63.7%** (the wrong one) because `mock-server.cjs` averages regional coverages. This is a **critical data flow defect** that misrepresents system performance.

### Action Required
**Complete frontend rewrite** — not an architecture change, but a **re-implementation against the frozen backend schema**. This is the only viable path because:
1. The current codebase has two parallel implementations for every layer
2. Direct field name mapping is inconsistent across all components
3. The monolithic structure prevents incremental fixes
4. The mock-server.cjs is the only thing making it work today

---

## 2. Runtime Truth Mapping

### 2.1 Pipeline Output Schema (THE TRUTH)

```
pipeline_output.json
├── orchestrator: str
├── status: str ("complete")
├── problem_analysis: str (LLM narrative)
├── regional_results: [{}]
│   ├── region: str
│   ├── status: str
│   ├── services_generated: int
│   ├── services_filtered: int
│   ├── services_selected: int
│   ├── weekly_profit: float
│   ├── annual_profit: float
│   ├── operating_cost: float
│   ├── fuel_cost: float
│   ├── transship_cost: float
│   ├── port_cost: float
│   ├── total_cost: float
│   ├── coverage_percent: float
│   ├── satisfied_demand: float
│   ├── unserved_demand: float
│   ├── total_demand: float
│   ├── profit_margin_pct: float
│   ├── profit_per_service: float
│   ├── cost_per_service: float
│   ├── uncovered_teu: float
│   ├── hub_ports: [str]
│   ├── archetype_params: {}
│   ├── regional_policy: {}
│   ├── strategy: str (LLM)
│   ├── explanation: str (LLM)
│   └── selected_services: [{}] (95-103 per region)
├── decision_output: {}
│   ├── agent: str
│   ├── iteration: int
│   ├── status: str
│   ├── global_metrics: {}
│   │   ├── total_services: 442
│   │   ├── total_profit: 597,103,144
│   │   ├── annual_profit: 31,049,363,520
│   │   ├── average_coverage: 63.69%
│   │   ├── min_coverage: 33.22%
│   │   ├── max_coverage: 84.76%
│   │   ├── coverage_variance: 51.54
│   │   ├── total_cost: 210,561,250
│   │   ├── total_satisfied_demand: 828,397
│   │   ├── total_unserved_demand: 1,066,833
│   │   └── profit_margin_pct: 73.9
│   ├── evaluation: {score: 3/5, status: "good", reasons: [...]}
│   ├── conflicts: []
│   ├── resolution_log: []
│   ├── decisions: []
│   ├── feedback: {needs_rerun, coverage_gap, weight_adjustments, convergence_score, ...}
│   └── llm_runtime_metrics: {}
├── executive_summary: str (LLM narrative)
├── summary_metrics: {}
│   ├── weekly_profit: 597,103,144
│   ├── annual_profit: 31,049,363,520
│   ├── revenue: 2,615,734,124
│   ├── operating_cost: 210,561,250
│   ├── transship_cost: 57,476,256
│   ├── port_cost: 72,348,690
│   ├── fuel_cost: 1,678,244,784
│   ├── total_cost: 2,018,630,980
│   ├── total_services: 442
│   ├── satisfied_demand: 828,397
│   ├── unserved_demand: 1,066,833
│   ├── coverage: 49.70% ← CORRECT COVERAGE METRIC
│   └── total_runtime: 405.7
├── iteration_audit: [{}] (2 entries)
│   ├── iteration: int
│   ├── weights_used: {}
│   ├── profit: float
│   ├── coverage: float
│   ├── convergence_score: float
│   ├── coverage_gap: float
│   ├── conflict_severity: int
│   ├── needs_rerun: bool
│   └── rerun_reason: str
├── iterations_run: int
├── selected_services: [{}] (439 total)
│   ├── id, ports[], load, capacity, vessel_class
│   ├── vessel_cost, fuel_cost, port_cost, revenue, cost
│   ├── weekly_profit, margin_pct, region
├── health_status: {status, runtime_seconds, iterations, ...}
├── consensus_result: {final_weight_adjustments, confidence_score, ...}
├── shared_context: {global_objectives, regional_priorities, ...}
├── llm_runtime_metrics: {llm_calls, coordinator_* , servicegen_* , ...}
└── test_scorecard: {assertions_passed: 309, assertions_failed: 4, ...}
```

### 2.2 Component-to-Runtime Mapping Table

| Frontend Component | Field Used | Backend Source | Correct? | Notes |
|---|---|---|---|---|
| **Header: Ports** | `global.ports` | mock: `problem_stats.ports` | ✅ | 435, hardcoded in mock but passed |
| **Header: Lanes** | `global.lanes` | mock: `problem_stats.lanes` | ✅ | 9,622 |
| **Header: Services** | `global.services` | mock: `problem_stats.services` | ⚠️ | Mock has 1,200; actual is 442 |
| **Header: Weekly TEU** | `global.weeklyDemand` | mock: `problem_stats.weekly_demand` | ⚠️ | Mock has 833,484; actual is 1,666,738 |
| **Header: Runtime** | `global.runtime` | `summary_metrics.total_runtime` | ✅ | Correct field mapping |
| **Header: Convergence** | `global.convergence` | `decision_output.feedback.convergence_score` | ✅ | 0.97 |
| **Landing: Weekly Profit** | `global.weeklyProfit` | `summary_metrics.weekly_profit` | ✅ | $597M |
| **Landing: Coverage** | `global.coverage` | From `initial_state` → metrics | **⚠️ CRITICAL** | Gets 63.7% (regional avg), should use 49.7% (OD-based) |
| **Landing: Margin** | `global.margin` | `summary_metrics` has no margin | ⚠️ | Computed elsewhere; field may be missing |
| **Landing: Executive Summary** | `g.executive_summary` | `executive_summary` | ✅ | Correct |
| **Overview: Weekly Profit** | `global.weeklyProfit` | `summary_metrics.weekly_profit` | ✅ | |
| **Overview: Annual Profit** | `global.annualProfit` | `summary_metrics.annual_profit` | ✅ | |
| **Overview: Demand Coverage** | `global.coverage` | `summary_metrics.coverage` vs `decision_output.global_metrics.average_coverage` | **⚠️ CRITICAL** | Uses wrong coverage value |
| **Overview: Services Deployed** | `global.totalServices` | `summary_metrics.total_services` | ✅ | 442 |
| **Overview: Profit Margin** | `global.margin` | `decision_output.global_metrics.profit_margin_pct` | ✅ | 73.9% |
| **Overview: Convergence** | `global.convergence` | `decision_output.feedback.convergence_score` | ✅ | 0.97 |
| **Pipeline: Pipeline Stats** | `g.runtime`, `convergence`, `totalServices` | Various | ✅ | Correct wiring |
| **Pipeline: Conflicts** | `g.decision_output.conflicts.length` | `decision_output.conflicts` | ✅ | 0 |
| **Regional: RegionCard** | `r.profit`, `r.coverage`, `r.services`, `r.margin` | `regional_results[i].weekly_profit`, `.coverage_percent`, `.services_selected`, `.profit_margin_pct` | ⚠️ | Field naming mismatch: `profit` vs `weekly_profit`, `coverage` vs `coverage_percent` |
| **Regional: Strategy** | `r.strategy` | `regional_results[i].strategy` | ✅ | |
| **Regional: Hubs** | `r.hubs` | `regional_results[i].hub_ports` | ⚠️ | Field name: `hubs` vs `hub_ports` |
| **Regional: Cost** | `sel.operating_cost`, `sel.cost` | `regional_results[i].operating_cost`, `.total_cost` | ⚠️ | `cost` maps correctly but computed from multiple sources |
| **Regional: Annual Profit** | `sel.profit * 52` | computed | ⚠️ | `annual_profit` field exists but frontend recomputes |
| **Funnel: Region metrics** | `r.generated`, `r.filtered`, `r.selected`, `r.profit` | `regional_results[i].services_generated`, `.services_filtered`, `.services_selected`, `.weekly_profit` | ⚠️ | Naming mismatch |
| **Feedback: Iterations** | `optimizationState.iterations[i].profit`, `.coverage`, `.score` | `iteration_audit[i].profit`, `.coverage`, `.convergence_score` | ⚠️ | `score` maps to `convergence_score` |
| **Conflict: Conflicts** | `state.global.decision_output.conflicts` | `decision_output.conflicts` | ✅ | 0 conflicts |
| **Conflict: Severity** | `decision.feedback?.conflict_severity` | `decision_output.feedback.conflict_severity` | ✅ | |
| **Map: Services** | `optimizationState.global.selected_services` | `selected_services` (439 items) | ✅ | Correct mapping |
| **Map: Corridors** | `optimizationState.corridors` | `corridors` field | ⚠️ | Backend doesn't have a corridors field; mock only |
| **Summary: Verdict** | `state.global.executive_summary.includes("Verdict: Good")` | `executive_summary` | ✅ | String parsing works |
| **Sidebar: Assertions** | `optimizationState.global.status.assertions_passed` | `test_scorecard.assertions_passed` | ⚠️ | Deep-nested access, may be `undefined` |
| **Sidebar: Score** | computed from assertions | `test_scorecard.score` | ⚠️ | Exist in backend but frontend recomputes |
| **Sidebar: Warnings** | `optimizationState.global.status.warnings` | `test_scorecard.warnings` | ⚠️ | May not be populated |

### 2.3 Critical Field Mapping Errors

```diff
- current coverage = 63.7% (regional average from decision_output)
+ correct coverage = 49.70% (OD-based from summary_metrics.coverage)

- region profit field = "profit"
+ actual backend field = "weekly_profit"

- region hubs field = "hubs"
+ actual backend field = "hub_ports"

- region coverage field = "coverage"
+ actual backend field = "coverage_percent"

- mock problem_stats.weekly_demand = 833,484
+ actual pipeline total_demand = 1,666,738 (differs by 2x)
```

---

## 3. Dashboard Architecture

### 3.1 Current Architecture (Monolithic)

```
main.jsx
  └── ErrorBoundary.jsx
      └── MaritimeDashboard.jsx (2,509 lines — ALL logic inline)
           ├── useOptimizationState() hook (inline — WebSocket + state)
           ├── LandingView
           ├── OverviewView (inline in renderMain switch)
           ├── PipelineView (architecture diagram)
           ├── RegionalView
           ├── FunnelView
           ├── FeedbackView
           ├── ConflictView
           ├── MapView (react-simple-maps)
           ├── SummaryView
           ├── KpiCard
           ├── Sparkline
           ├── PulseDot
           ├── ProgressBar
           ├── BenchmarkBadge
           ├── Counter
           └── PipeNode / RegionPipelineNode
```

### 3.2 Secondary Architecture (Unused/Partial)

```
  DashboardProvider.tsx ──→ dashboardStore.ts (TS named-export store)
      └── useWebSocket.ts
      └── apiClient.ts
      └── types.ts
      
  api/client.js ──→ REST endpoints (JS, singleton)
  
  services/websocketService.js ──→ WebSocketClient class
  
  store/dashboardStore.js (JS, default-export store, different shape)
  
  components/live/
    ├── LiveDashboard.jsx
    ├── LiveKPICards.jsx
    ├── LivePipelineGraph.jsx
    └── LiveRegionalCards.jsx
```

### 3.3 Migration Strategy

| Phase | Action | Target |
|---|---|---|
| **Sprint 1** | Delete dead code — both stores, both API clients, mock server, dead components | Clean slate |
| **Sprint 1** | Define canonical types from `pipeline_output.json` schema | `src/types/index.ts` |
| **Sprint 2** | Build API layer — one HTTP client, one WS client, field mapping layer | `src/api/` |
| **Sprint 2** | Build Zustand store — exactly matching backend schema | `src/store/` |
| **Sprint 3** | Extract each view to own file with proper field mappings | `src/views/` |
| **Sprint 3** | Extract reusable components (KpiCard, Sparkline, etc.) | `src/components/` |
| **Sprint 4** | Wire everything via DashboardProvider | Integration |
| **Sprint 5** | Polish — loading, errors, responsive, accessibility | Production |

**DO NOT**: Delete old files until Sprint 5. Keep MaritimeDashboard.jsx as reference, but stop serving it.

---

## 4. API Audit

### 4.1 REST Endpoints

| Endpoint (Expected) | In `apiClient.ts`? | In `client.js`? | Backend Exists? | Match? |
|---|---|---|---|---|
| `GET /api/health` | ✅ `getHealth()` | — | Unknown | ⚠️ |
| `GET /api/status` | ✅ `getStatus()` | — | Unknown | ⚠️ |
| `GET /api/problem-stats` | ✅ `getProblemStats()` | — | Unknown | ⚠️ |
| `GET /api/regions` | ✅ `getRegions()` | `GET /regions/` | Unknown | ⚠️ Mismatch |
| `GET /api/metrics` | ✅ `getMetrics()` | `GET /metrics/summary` | Unknown | ⚠️ Mismatch |
| `GET /api/iterations` | ✅ `getIterations()` | `GET /pipeline/iterations` | Unknown | ⚠️ Mismatch |
| `GET /api/corridors` | ✅ `getCorridors()` | — | Unknown | ⚠️ |
| `GET /api/export` | ✅ `exportResults()` | — | Unknown | ⚠️ |
| `POST /api/optimize` | ✅ `startPipeline()` | `POST /pipeline/start` | Unknown | ⚠️ Mismatch |
| — | — | `GET /pipeline/stages` | Unknown | Dead? |
| — | — | `GET /pipeline/conflicts` | Unknown | Dead? |
| — | — | `POST /pipeline/stop` | Unknown | Dead? |
| — | — | `GET /metrics/profit-trends` | Unknown | Dead? |
| — | — | `GET /metrics/coverage-metrics` | Unknown | Dead? |
| — | — | `GET /metrics/service-stats` | Unknown | Dead? |
| — | — | `GET /regions/{id}/services` | Unknown | Dead? |
| — | — | `GET /regions/{id}/hubs` | Unknown | Dead? |

### 4.2 API Issues

| Issue | Impact | Priority |
|---|---|---|
| **Two API clients** with different endpoint paths | Both may be broken; no single source of truth | HIGH |
| No backend confirmed serving these endpoints | The `mock-server.cjs` is the only thing serving data | CRITICAL |
| `client.js` uses `/pipeline/start`, `apiClient.ts` uses `/api/optimize` | Confusion; no backend route may exist | HIGH |
| No auth/error standardization across clients | Mixed error handling patterns | MEDIUM |

### 4.3 Required API Layer

The frontend needs a backend that serves the `pipeline_output.json` contents as REST + WebSocket. If the backend does not currently serve an HTTP API, the frontend must either:
1. Read `pipeline_output.json` directly (simplest, fully runtime-truthful)
2. Build a thin server that wraps the file

**Recommendation**: **Read `pipeline_output.json` directly** for initial state, then layer WebSocket for live updates. This eliminates all HTTP endpoint uncertainty.

---

## 5. WebSocket Audit

### 5.1 WebSocket Implementations

| Implementation | File | URL | Protocol | Used? |
|---|---|---|---|---|
| Inline hook | `MaritimeDashboard.jsx` (line 4-242) | `ws://localhost:8000/ws/pipeline` | Custom message types | ✅ ACTIVE |
| WebSocketClient class | `services/websocketService.js` | `ws://localhost:8000/ws/pipeline` | Custom message types | ❌ Unused |
| apiClient WebSocket | `api/apiClient.ts` | `ws://localhost:8000/ws` | Custom types | ❌ Partial |
| Mock server | `mock-server.cjs` | Port 8000 | Sends `initial_state` + `pipeline_update` | 🧪 Dev only |

### 5.2 Message Type Mapping

| Inline Hook (Active) | `apiClient.ts` | `websocketService.js` | Backend Message |
|---|---|---|---|
| `initial_state` | `initial_state` | N/A | ✅ |
| `pipeline_started` | `pipeline_started` | `pipeline_started` | ✅ |
| `stage_started` | N/A | `stage_started` | ✅ |
| `stage_progress` | `stage_progress` | `stage_progress` | ✅ |
| `region_update` / `region_updated` | `region_started` | `region_update` | ✅ |
| `iteration_completed` | `iteration_complete` | `iteration_update` | ⚠️ Mismatch |
| `map_updated` | `map_update` | `map_update` | ✅ |
| `pipeline_completed` | `pipeline_complete` | `pipeline_completed` | ⚠️ Capitalization |
| `pipeline_error` | `pipeline_error` | `pipeline_error` | ✅ |
| N/A | `problem_analyzed` | N/A | ❌ Missing in inline |

### 5.3 Issues

| Issue | Impact | Priority |
|---|---|---|
| Three WebSocket implementations share no code | Maintenance burden, bug-prone | HIGH |
| `pipeline_completed` vs `pipeline_complete` (t vs d) | Events missed on one implementation | MEDIUM |
| `region_updated` vs `region_update` (ed vs e) | Events missed | MEDIUM |
| No heartbeat/ping in inline hook | Disconnects may go undetected | LOW |
| No reconnect between different WS instances | Multiple reconnect loops fighting | MEDIUM |
| `mock-server.cjs` sends wrong field names (`coveragePercentage` not `coverage_percent`) | Feeds bad data to frontend | CRITICAL |

---

## 6. Data Flow Map

### 6.1 Complete Field Trace

```
pipeline_output.json                 Frontend Display
═══════════════════                  ═══════════════════

summary_metrics.weekly_profit        → Landing: "$XXX.XM"
summary_metrics.annual_profit        → Overview: "$X.XB"
summary_metrics.coverage             → NOT displayed (wrong value used)
summary_metrics.operating_cost       → Overview subtext
summary_metrics.total_services       → Overview/Header: "442"
summary_metrics.total_runtime        → Header: "405.7s"
summary_metrics.satisfied_demand     → Not displayed
summary_metrics.unserved_demand      → Not displayed directly
summary_metrics.revenue              → Not displayed
summary_metrics.fuel_cost            → Not displayed
summary_metrics.transship_cost       → Not displayed
summary_metrics.port_cost            → Not displayed
summary_metrics.total_cost           → Not displayed

decision_output.feedback.convergence_score  → Header/Overview: "0.970"
decision_output.feedback.coverage_gap       → Feedback: "6.31pp"
decision_output.feedback.weight_adjustments → Not displayed
decision_output.feedback.needs_rerun        → Feedback iteration badges
decision_output.feedback.conflict_severity  → Conflict: "0"
decision_output.global_metrics.*            → Various (wrong coverage used)

regional_results[i].weekly_profit           → RegionCard: "$XX.XM"
regional_results[i].services_generated      → Funnel: "781"
regional_results[i].services_filtered       → Funnel: "400"
regional_results[i].services_selected       → RegionCard: 95
regional_results[i].coverage_percent        → RegionCard: "68.2%"
regional_results[i].profit_margin_pct       → RegionCard: "13.1%"
regional_results[i].hub_ports               → RegionCard: pills
regional_results[i].strategy                → RegionCard: strategy code
regional_results[i].explanation             → RegionCard: report text
regional_results[i].operating_cost          → RegionalView details
regional_results[i].fuel_cost               → Not displayed
regional_results[i].transship_cost          → RegionalView: "Transshipment Cost"
regional_results[i].port_cost               → Not displayed
regional_results[i].uncovered_teu           → RegionalView: "Uncovered TEU"
regional_results[i].selected_services       → Map: route lines

iteration_audit[i].profit                   → Feedback cards
iteration_audit[i].coverage                 → Feedback cards
iteration_audit[i].convergence_score         → Feedback convergence graph
iteration_audit[i].weights_used             → Not displayed

test_scorecard.assertions_passed            → Sidebar: "309/313"
test_scorecard.score                        → Sidebar: "98.7%"
test_scorecard.warnings                     → Sidebar: "4"

health_status.runtime_seconds               → Not displayed (redundant)
health_status.success_rate                   → Not displayed

consensus_result.final_weight_adjustments    → Not displayed
consensus_result.confidence_score            → Not displayed

executive_summary                           → Landing/Summary: LLM report

llm_runtime_metrics.*                       → Not displayed
selected_services[].*                       → Map routes
```

### 6.2 Field Coverage Summary

| Category | Fields in Backend | Fields Displayed | Coverage |
|---|---|---|---|
| Global Metrics | 14 | 7 | 50% |
| Per-Region Metrics | 22 | 14 | 64% |
| Iteration Audit | 10 | 5 | 50% |
| Decision Output | 10 fields, ~30 sub-fields | ~8 | 27% |
| Test Scorecard | 5 | 3 | 60% |
| LLM Metrics | 10 | 0 | 0% |
| Consensus | 6+ | 0 | 0% |
| Selected Services | ~15 per service | ~5 | 33% |

---

## 7. Component Inventory

### 7.1 All Components

| Component | File | Type | Status | Used By |
|---|---|---|---|---|
| `MaritimeDashboard` (App) | `MaritimeDashboard.jsx` | Page | ✅ Active | `main.jsx` |
| `PipelineView` | Inline in MaritimeDashboard | View | ✅ Active | App routing |
| `RegionalView` | Inline in MaritimeDashboard | View | ✅ Active | App routing |
| `FunnelView` | Inline in MaritimeDashboard | View | ✅ Active | App routing |
| `FeedbackView` | Inline in MaritimeDashboard | View | ✅ Active | App routing |
| `ConflictView` | Inline in MaritimeDashboard | View | ✅ Active | App routing |
| `MapView` | Inline in MaritimeDashboard | View | ✅ Active | App routing |
| `LandingView` | Inline in MaritimeDashboard | View | ✅ Active | App routing |
| `SummaryView` | Inline in MaritimeDashboard | View | ✅ Active | App routing |
| `KpiCard` | Inline in MaritimeDashboard | Component | ✅ Active | Overview, Landing |
| `Sparkline` | Inline in MaritimeDashboard | Component | ✅ Active | KpiCard |
| `PulseDot` | Inline in MaritimeDashboard | Component | ✅ Active | Header, Map |
| `ProgressBar` | Inline in MaritimeDashboard | Component | ✅ Active | RegionCard |
| `BenchmarkBadge` | Inline in MaritimeDashboard | Component | ✅ Active | KpiCard |
| `Counter` | Inline in MaritimeDashboard | Component | ✅ Active | Not used in main? |
| `PipeNode` | Inline in MaritimeDashboard | Component | ✅ Active | PipelineView |
| `RegionPipelineNode` | Inline in MaritimeDashboard | Component | ✅ Active | PipelineView |
| `RegionCard` | Inline in MaritimeDashboard | Component | ✅ Active | RegionalView |
| `ErrorBoundary` | `ErrorBoundary.jsx` | Component | ✅ Active | `main.jsx` |
| #### **Secondary/Dead** | | | | |
| `DashboardProvider` | `DashboardProvider.tsx` | Provider | ⚠️ NOT WIRED | Not in main.jsx |
| `Dashboard` | `Dashboard.jsx` | Page | ❌ Dead | No import |
| `LiveDashboard` | `LiveDashboard.jsx` | Page | ❌ Dead | No import |
| `LiveDashboard` | `live/LiveDashboard.jsx` | Page | ❌ Dead | No import |
| `LiveKPICards` | `live/LiveKPICards.jsx` | Component | ❌ Dead | No import |
| `LivePipelineGraph` | `live/LivePipelineGraph.jsx` | Component | ❌ Dead | No import |
| `LiveRegionalCards` | `live/LiveRegionalCards.jsx` | Component | ❌ Dead | No import |
| `TestComponent` | `TestComponent.jsx` | Test | ❌ Dead | No import |
| `KpiCard` | `ui/KpiCard.jsx` | Component | ❌ Dead | ui/index.jsx wrappers |
| `Counter` | `ui/Counter.jsx` | Component | ❌ Dead | ui/index.jsx |
| `ProgressBar` | `ui/ProgressBar.jsx` | Component | ❌ Dead | ui/index.jsx |
| `PulseDot` | `ui/PulseDot.jsx` | Component | ❌ Dead | ui/index.jsx |
| `Sparkline` | `ui/Sparkline.jsx` | Component | ❌ Dead | ui/index.jsx |
| Full MapView | `views/MapView.jsx` | View | ❌ Dead | No import |
| Full PipelineView | `views/PipelineView.jsx` | View | ❌ Dead | No import |
| Full RegionalView | `views/RegionalView.jsx` | View | ❌ Dead | No import |
| Full SummaryView | `views/SummaryView.jsx` | View | ❌ Dead | No import |
| Full ConflictView | `views/ConflictView.jsx` | View | ❌ Dead | No import |
| Full FeedbackView | `views/FeedbackView.jsx` | View | ❌ Dead | No import |
| Full FunnelView | `views/FunnelView.jsx` | View | ❌ Dead | No import |
| Full LiveMapView | `views/LiveMapView.jsx` | View | ❌ Dead | No import |
| Full LivePipelineView | `views/LivePipelineView.jsx` | View | ❌ Dead | No import |

### 7.2 Dead Code Impact

**Approximately 60% of the frontend source files are dead code** — they exist on disk but are never imported by the active application. The active app is entirely `MaritimeDashboard.jsx` (2,509 lines) + `ErrorBoundary.jsx` + `main.jsx`.

### 7.3 Dependency Graph

```
MaritimeDashboard.jsx ←── main.jsx
    ↓ (self-contained, no file imports)
    ├── react-simple-maps (ComposableMap, Geographies, Geography, Line, Marker)
    ├── port_coordinates.json (data import for MapView)
    └── WebSocket connects to ws://localhost:8000/ws/pipeline (no import needed)

ErrorBoundary.jsx ←── main.jsx
```

The active dependency graph is trivially flat. All components are monolithic.

---

## 8. Dashboard Quality Score

### 8.1 Per-Page Scoring

| Page | Correct-ness | UX | Visual | Perf | Code Quality | State Mgmt | Error Handling | Loading | Access. | Responsive | Maintain. | **Avg** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Landing** | 6 | 7 | 8 | 8 | 3 | 4 | 3 | 2 | 3 | 4 | 4 | **4.7** |
| **Overview** | 5 | 7 | 8 | 8 | 3 | 4 | 3 | 2 | 3 | 4 | 3 | **4.5** |
| **Pipeline** | 7 | 7 | 9 | 7 | 3 | 4 | 3 | 2 | 2 | 3 | 2 | **4.5** |
| **Regional** | 6 | 7 | 7 | 8 | 3 | 4 | 3 | 2 | 3 | 4 | 3 | **4.5** |
| **Funnel** | 6 | 7 | 7 | 8 | 3 | 4 | 3 | 2 | 3 | 4 | 3 | **4.5** |
| **Feedback** | 7 | 7 | 8 | 8 | 3 | 4 | 3 | 2 | 3 | 4 | 3 | **4.7** |
| **Conflict** | 7 | 6 | 6 | 9 | 3 | 4 | 3 | 2 | 3 | 4 | 3 | **4.5** |
| **Map** | 6 | 8 | 9 | 6 | 3 | 4 | 3 | 2 | 2 | 4 | 2 | **4.5** |
| **Summary** | 6 | 6 | 6 | 9 | 3 | 4 | 3 | 2 | 3 | 4 | 3 | **4.5** |
| **Architecture** | 7 | 6 | 8 | 8 | 3 | 4 | 3 | 2 | 3 | 3 | 3 | **4.5** |

**Overall Score: 4.5 / 10** — Strength in visual design (dark theme, animations, charts) but severe weaknesses in correctness, maintainability, and error handling.

### 8.2 Scoring Breakdown

**Strengths (7-9):**
- Visual design is excellent — consistent dark maritime theme with cyan accents
- MapView has sophisticated features (region filters, load sliders, mode toggles)
- Sparklines and animated counters add polish
- Pipeline architecture diagram is beautiful and informative
- Fast rendering on modern hardware

**Critical Weaknesses (2-3):**
- **Runtime correctness**: Uses wrong coverage value, wrong field names
- **Loading states**: No skeleton screens; data appears as zeros/dashes then populates
- **Error handling**: Only shows "Connection error" — no retry guidance, no graceful degradation
- **Accessibility**: No ARIA labels, no keyboard navigation, no screen reader support
- **Maintainability**: 2,509-line file, no tests, dual implementations everywhere
- **Responsiveness**: `scale()` transform on PipelineView may cut off content; no mobile breakpoints

---

## 9. Missing Intelligence

### 9.1 Runtime Fields Never Visualized

Ranking: **Critical** = directly impacts investor/user confidence, **High** = valuable operational insight, **Medium** = analytical depth, **Low** = nice to have

| # | Field | Backend Location | Value Example | Rank | Business Value | Demo Value | Investor Value | Academic Value | Complexity | Recommended Location |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **OD-based coverage (49.7%)** | `summary_metrics.coverage` | 49.7% | **Critical** | HIGH | CRITICAL | CRITICAL | HIGH | 1 line | Replace current coverage display everywhere |
| 2 | **Weight adjustments** | `decision_output.feedback.weight_adjustments` | profit: 0.405, coverage: 0.495, cost: 0.1 | **High** | MEDIUM | HIGH | HIGH | MEDIUM | Easy | Feedback View — new "Weight Tuning" panel |
| 3 | **Convergence trajectory** | `iteration_audit[i].convergence_score` | [0.979, 0.97] | **High** | HIGH | HIGH | MEDIUM | MEDIUM | Easy | Feedback View (partial exists already) |
| 4 | **Revenue breakdown** | `summary_metrics.revenue` | $2.62B | **High** | HIGH | HIGH | HIGH | MEDIUM | Easy | Overview — add revenue KPI |
| 5 | **Cost breakdown** | `summary_metrics.{fuel,port,transship}_cost` | fuel: $1.68B, port: $72M, transship: $57M | **High** | HIGH | HIGH | MEDIUM | MEDIUM | Easy | Overview — cost breakdown chart |
| 6 | **Satisfied/Unserved demand** | `summary_metrics.{satisfied,unserved}_demand` | 828K / 1,067K TEU | **High** | HIGH | HIGH | MEDIUM | HIGH | Easy | Overview — demand coverage breakdown |
| 7 | **Test scorecard** | `test_scorecard.*` | 309/313, 98.7% | **High** | HIGH | HIGH | CRITICAL | MEDIUM | Easy | Sidebar (partial exists) + dedicated page |
| 8 | **LLM Runtime Metrics** | `llm_runtime_metrics.*` | 7 calls, 2 coordinator calls, 0 fallbacks | **High** | MEDIUM | HIGH | HIGH | HIGH | Easy | Pipeline or Architecture view — "AI Usage" panel |
| 9 | **Consensus confidence** | `consensus_result.confidence_score` | 1.0 | **Medium** | MEDIUM | MEDIUM | MEDIUM | HIGH | Easy | Conflict View |
| 10 | **Min/max coverage** | `decision_output.global_metrics.{min,max}_coverage` | 33.2% / 84.8% | **Medium** | MEDIUM | MEDIUM | LOW | MEDIUM | Easy | Overview — coverage range indicator |
| 11 | **Coverage variance** | `decision_output.global_metrics.coverage_variance` | 51.54 | **Medium** | MEDIUM | LOW | LOW | HIGH | Easy | Regional view — imbalance indicator |
| 12 | **Service-level data** | `selected_services[i].*` | Load, capacity, vessel class, profit | **Medium** | HIGH | MEDIUM | LOW | HIGH | Hard | New Service Detail View |
| 13 | **Archetype params** | `regional_results[i].archetype_params` | direct_ratio: 0.6 | **Medium** | MEDIUM | LOW | LOW | HIGH | Easy | Regional View |
| 14 | **Regional policy** | `regional_results[i].regional_policy` | coverage_priority: 0.45 | **Low** | LOW | LOW | LOW | MEDIUM | Easy | Regional View |
| 15 | **Health status** | `health_status.*` | 405.7s, 100% success | **Low** | LOW | MEDIUM | LOW | LOW | Easy | Footer or hidden panel |
| 16 | **Problem analysis** | `problem_analysis` | LLM narrative | **Low** | LOW | MEDIUM | MEDIUM | LOW | Easy | Pipeline View — expandable |
| 17 | **Shared context** | `shared_context.*` | Global objectives, hub strategy | **Low** | LOW | LOW | LOW | MEDIUM | Easy | Architecture View |
| 18 | **Decision output details** | `decision_output.decisions` | Array of decisions | **Low** | LOW | LOW | LOW | MEDIUM | Medium | Conflict View |

### 9.2 Top 5 Most Valuable Additions

1. **✅ Fix OD-based coverage** — Cost: <1 hour. Impact: Correctness of all reporting.
2. **📊 Cost breakdown chart** — Cost: 4 hours. Impact: Shows where $2B goes (fuel dominates).
3. **📋 Test scorecard** — Cost: 2 hours. Impact: Investor confidence via 309/313, 98.7%.
4. **🤖 AI Usage Panel** — Cost: 3 hours. Impact: Demonstrates AI integration visibly.
5. **📈 Weight tuning visualization** — Cost: 4 hours. Impact: Shows adaptive optimization.

---

## 10. Commercial Gap Analysis

### 10.1 Comparison Tier

| Capability | Competitors | Our System | Gap | Priority |
|---|---|---|---|---|
| **Live KPI dashboard** | Flexport, Oracle OTM | ✅ Present | No real-time delta tracking | Must Have |
| **Route map visualization** | Veson, Navtor | ✅ Present | No AIS overlay, no port congestion | Should Have |
| **What-if analysis** | Quintiq, AIMMS | ❌ Missing | No scenario comparison | Must Have |
| **Vessel deployment plan** | Veson IMOS | ⚠️ Partial | Services shown but no vessel-level Gantt | Must Have |
| **Constraint visualization** | Supply chain towers | ❌ Missing | No fleet constraint UI | Should Have |
| **Cost breakdown (waterfall)** | Oracle OTM | ❌ Missing | Fuel/port/transship not separated | Must Have |
| **Export to PDF/XLSX** | All | ⚠️ Partial | Canvas-based PNG only, needs real export | Must Have |
| **Multi-run comparison** | Optym, Quintiq | ❌ Missing | No side-by-side run comparison | Should Have |
| **Alerts & notifications** | Control towers | ❌ Missing | No coverage drop alerts | Nice to Have |
| **Role-based views** | Enterprise software | ❌ Missing | Same view for all users | Nice to Have |
| **Drill-down hierarchy** | BI tools | ⚠️ Partial | Can click to region, but no service drill-down | Should Have |
| **Historical trends** | Any BI | ❌ Missing | Only current run, no history | Should Have |
| **Interactive filters** | Tableau, Power BI | ⚠️ Partial | Map has region toggles, no global filter | Should Have |
| **Mobile responsive** | Modern SaaS | ❌ Missing | Desktop only | Nice to Have |

### 10.2 Primary Gaps (Must Have for V1)

1. **What-if / Scenario Comparison** — Users need to compare "current vs optimized"
2. **Cost Breakdown Visualization** — Waterfall/stacked bar showing fuel vs port vs transship
3. **Real Export** — Working PDF/CSV/XLSX export, not canvas screenshot
4. **Vessel Deployment Table** — Service-level view showing vessel class assignments
5. **Constraint Visualization** — Fleet limit (300 vessels) visualization

---

## 11. Product Vision

### AI Vessel Routing System — Frontend Vision Statement

> **A single-page, runtime-truthful operations dashboard** that transforms the frozen backend's pipeline_output.json into an **executive-ready, investor-grade visualization** of the world's most advanced AI-powered liner shipping optimizer.

### Key Principles

1. **Runtime is Truth** — Every pixel originates from `pipeline_output.json`. No mock data. No hardcoded values.
2. **Read pipeline_output.json directly** — Skip HTTP API uncertainty; the file is the API.
3. **One implementation per concept** — One API client, one store, one WebSocket handler, one component.
4. **Extract before you build** — Each view and component gets its own file.
5. **Investor-ready from Sprint 1** — The first working build must show the correct 49.7% coverage.

### Target Architecture

```
main.jsx
  └── App.tsx
      ├── DashboardProvider.tsx (WebSocket + file-based data)
      └── Sidebar.tsx
      └── Header.tsx
      └── Main Content
          ├── LandingView.tsx
          ├── OverviewView.tsx
          ├── PipelineView.tsx
          ├── RegionalView.tsx
          ├── FunnelView.tsx
          ├── FeedbackView.tsx
          ├── ConflictView.tsx
          ├── MapView.tsx
          └── SummaryView.tsx
      └── Footer.tsx

Shared:  types.ts, store.ts, apiClient.ts, useWebSocket.ts
Data:    pipeline_output.json (read at startup)
Views:   One file per view (no inline)
Components: KpiCard, Sparkline, ProgressBar, etc. in ui/
```

---

## 12. Sprint Roadmap

### Sprint 1 — Foundation & Cleanup (Estimated: 3-4 days)

**Goal**: Establish single source of truth; fix critical coverage bug.

**Files to Create**:
- `src/types/index.ts` — canonical types mirroring `pipeline_output.json` structure
- `src/data/pipelineLoader.ts` — reads `pipeline_output.json` and serves as initial state
- `src/store/useStore.ts` — Zustand store with exhaustive, flat schema matching backend fields

**Files to Delete**:
- `src/store/dashboardStore.js`
- `src/store/dashboardStore.ts` (kept as reference, not imported)
- `src/api/client.js` (JS client)
- `mock-server.cjs`
- `services/websocketService.js`
- `components/Dashboard.jsx`, `components/LiveDashboard.jsx` + folder
- `components/TestComponent.jsx`
- All `views/*.jsx`
- All `ui/*.jsx`
- `components/live/*`

**Acceptance Criteria**:
- ✅ Single Zustand store has all backend fields with correct types
- ✅ Coverage displayed is 49.7% (OD-based), not 63.7%
- ✅ All field names match backend snake_case exactly
- ✅ No dead code files remain
- ✅ MaritimeDashboard.jsx unchanged (reference copy created)

**Demo Improvement**: Coverage correction from 63.7% → 49.7% — honest metric displayed.

**Risk**: Low — mostly deletions and TypeScript definitions.

**Effort**: 3-4 days

---

### Sprint 2 — API & Data Layer (Estimated: 2-3 days)

**Goal**: Build the data pipeline from `pipeline_output.json` to store.

**Files to Create**:
- `src/api/usePipelineData.ts` — hook that loads pipeline_output.json at startup
- `src/api/useWebSocket.ts` — single WebSocket hook (consolidate all 3)
- `src/api/dataTransformers.ts` — field mapping layer (snake_case ↔ camelCase if needed)

**Acceptance Criteria**:
- ✅ App reads `pipeline_output.json` on mount via file loader
- ✅ WebSocket connects on mount and updates store incrementally
- ✅ Field transformers map correctly between backend and display
- ✅ Pipeline error/complete/started events update store correctly
- ✅ Region updates update individual region, not full reset

**Demo Improvement**: Data flowing end-to-end through the store. Can see real 49.7% coverage.

**Risk**: Medium — WebSocket events may not match; file reading path must work in both dev and prod.

**Effort**: 2-3 days

---

### Sprint 3 — Component Extraction (Estimated: 3-5 days)

**Goal**: Extract all views and shared components to their own files. Remove inline implementations.

**Files to Create**:
- `src/components/ui/KpiCard.tsx`
- `src/components/ui/Sparkline.tsx`
- `src/components/ui/ProgressBar.tsx`
- `src/components/ui/PulseDot.tsx`
- `src/components/ui/Counter.tsx`
- `src/components/ui/BenchmarkBadge.tsx`
- `src/views/LandingView.tsx`
- `src/views/OverviewView.tsx`
- `src/views/PipelineView.tsx`
- `src/views/RegionalView.tsx`
- `src/views/FunnelView.tsx`
- `src/views/ConflictView.tsx`
- `src/views/FeedbackView.tsx`
- `src/views/MapView.tsx`
- `src/views/SummaryView.tsx`
- `src/components/Header.tsx`
- `src/components/Sidebar.tsx`
- `src/components/Footer.tsx`

**Acceptance Criteria**:
- ✅ Every view renders with correct runtime data
- ✅ KpiCard, Sparkline, ProgressBar all accept correct props from store
- ✅ All views use the shared store, not inline state hooks
- ✅ MapView shows 439 services with proper region coloring
- ✅ PipelineView reads actual iteration count, not hardcoded

**Demo Improvement**: Maintainable, debuggable codebase. Each view testable in isolation.

**Risk**: Medium — bugs in prop threading, store selectors may return undefined.

**Effort**: 3-5 days

---

### Sprint 4 — Missing Intelligence & Polish (Estimated: 4-6 days)

**Goal**: Add the 5 most valuable missing fields; improve UX.

**Files to Modify**:
- `src/views/OverviewView.tsx` — add cost breakdown chart, revenue display
- `src/views/FeedbackView.tsx` — add weight tuning visualization, convergence trajectory
- `src/views/ConflictView.tsx` — add consensus confidence, resolution log
- `src/components/Header.tsx` — add test scorecard display
- `src/components/Sidebar.tsx` — add LLM runtime metrics, AI usage indicator

**New Files**:
- `src/components/ui/CostBreakdownChart.tsx` — stacked bar: fuel + port + transship
- `src/components/ui/CoverageRange.tsx` — min/max/avg coverage bar
- `src/components/panels/AIUsagePanel.tsx` — LLM call counts, success rates
- `src/components/panels/TestScorecardPanel.tsx` — assertion pass/fail/warnings

**Acceptance Criteria**:
- ✅ Cost breakdown chart shows fuel ($1.68B) → port → transship
- ✅ Revenue ($2.62B) displayed on Overview
- ✅ Test scorecard (309/313, 98.7%) prominent on sidebar
- ✅ LLM metrics visible (7 calls, 2 coordinator, 0 fallbacks)
- ✅ Weight adjustments visualized (profit/coverage/cost)
- ✅ Loading states shown while data loads
- ✅ Error states handle WS disconnection gracefully

**Demo Improvement**: Massively expanded data visibility. Fuel cost alone tells a compelling story.

**Risk**: Low-Medium — new charts are UI work, not data flow changes.

**Effort**: 4-6 days

---

### Sprint 5 — Production Readiness (Estimated: 4-6 days)

**Goal**: Performance, accessibility, export, responsive.

**Files to Modify**:
- All view files — add loading skeletons, error boundaries per view
- `src/App.tsx` — code-split views with React.lazy
- `src/components/ui/*` — add ARIA labels, keyboard navigation
- `vite.config.js` — configure code splitting, bundle analysis

**New Files**:
- `src/utils/exportService.ts` — real PDF/CSV/XLSX export using backend data
- `src/hooks/useAutoRefresh.ts` — configurable polling interval
- `src/hooks/useResponsive.ts` — breakpoint detection

**Acceptance Criteria**:
- ✅ Bundle size < 500KB (currently ~350KB for JS + CSS)
- ✅ Each view lazy-loaded (no initial download of all views)
- ✅ Lighthouse accessibility score > 85
- ✅ Export generates proper CSV/JSON from pipeline_output.json
- ✅ Page works on tablet-sized screens (768px+)
- ✅ No render-blocking operations on main thread
- ✅ All text accessible via screen reader

**Demo Improvement**: Professional-quality, production-viable dashboard.

**Risk**: Medium — code splitting may introduce loading flash; accessibility changes may need design input.

**Effort**: 4-6 days

---

### Total Estimated Effort: 16-26 days (3-5 weeks)

| Sprint | Days | Cost (Engineering) | Risk |
|---|---|---|---|
| Sprint 1 — Foundation | 3-4 | Low (deletions + types) | Low |
| Sprint 2 — Data Layer | 2-3 | Medium (file + WS loading) | Medium |
| Sprint 3 — Extraction | 3-5 | Medium (refactoring) | Medium |
| Sprint 4 — Intelligence | 4-6 | Medium (new charts) | Low-Med |
| Sprint 5 — Production | 4-6 | Medium-High (perf + a11y) | Medium |
| **Total** | **16-26** | | |

---

## 13. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **No backend HTTP/WS server exists** | HIGH | CRITICAL | Read pipeline_output.json directly; add thin server only if needed |
| 2 | **WebSocket protocol has undocumented messages** | MEDIUM | HIGH | Decode from mock-server.cjs and pipeline output logs; defensive parsing |
| 3 | **Field maps change between runs** | MEDIUM | MEDIUM | Validate against schema; add CI assertion tests |
| 4 | **Coverage fix reveals system underperformance** | HIGH | MEDIUM | 49.7% is honest; position as "OD-based true coverage" vs "regional average" |
| 5 | **Team lacks TypeScript expertise** | LOW | MEDIUM | Sprint 1 types can start as JSDoc; migrate to TS gradually |
| 6 | **New pipeline runs add unexpected fields** | LOW | MEDIUM | PipelineLoader uses `...[field] ?? null` fallbacks |
| 7 | **Monolithic refactor breaks working demo** | MEDIUM | HIGH | Keep MaritimeDashboard.jsx serving until Sprint 4; serve new app from different route |
| 8 | **Third-party map library (react-simple-maps) limitations** | LOW | LOW | Only cosmetic; fallback to simple SVG if needed |

---

## 14. Final Verdict

### Frontend Readiness: ⚠️ NOT READY FOR V1

| Dimension | Score | Explanation |
|---|---|---|
| **Runtime Correctness** | 3/10 | Critical coverage bug; multiple field name mismatches |
| **Code Quality** | 2/10 | 2,509-line file; dual implementations at every layer |
| **Visual Quality** | 8/10 | Excellent dark maritime theme; beautiful maps and animations |
| **Data Coverage** | 4/10 | ~50% of backend fields displayed; LLM metrics completely missing |
| **Maintainability** | 2/10 | No tests; no separation of concerns; dead code everywhere |
| **Production Readiness** | 2/10 | No loading states; no error handling; no accessibility; no export |

**Overall**: 3.5/10 — Visually impressive but structurally unsound and factually incorrect on key metrics.

### What Must Happen Before V1 Freeze

1. **Fix coverage display** (Sprint 1) — Non-negotiable. 49.7% is the truth.
2. **Consolidate to one store** (Sprint 1) — Eliminates dual-state bugs.
3. **Kill dead code** (Sprint 1) — 60% of files are unused.
4. **Extract to separate files** (Sprint 3) — 2,509-line file is a blocker.
5. **Add test scorecard** (Sprint 4) — Shows 309/313, 98.7% to investors.
6. **Add cost breakdown** (Sprint 4) — Essential for operational credibility.

---

## 15. Freeze Decision

### ⏸️ FRONTEND NOT FROZEN — ENTERING PHASE F1 IMPLEMENTATION

The backend is **FROZEN** (309/313 assertions, `pipeline_output.json` only truth).

The frontend is **NOT FROZEN** — it requires the 5-sprint plan above to reach V1 quality.

**The frontend must adapt to the frozen backend. No backend changes.**

### Freeze Conditions

The frontend will be declared FROZEN when:

1. ✅ All displayed data originates from `pipeline_output.json` (no mocks, no hardcodes)
2. ✅ OD-based coverage (49.7%) correctly displayed everywhere
3. ✅ All field names match backend schema
4. ✅ Single API client, single store, single WebSocket handler
5. ✅ Each view in its own file
6. ✅ Loading + error + empty states on every view
7. ✅ Test scorecard prominent
8. ✅ Cost breakdown visible
9. ✅ Bundle size under 500KB
10. ✅ Lazy-loaded views

**Target: End of Sprint 5 = Phase F1 Freeze**

---

## Appendix A: Quick-Fix Cheat Sheet

For immediate fixes before the full sprint plan:

```javascript
// 1. FIX COVERAGE — Change this in the mocked initial_state or data load
// Extract summary_metrics.coverage from pipeline_output.json
const correctCoverage = pipelineOutput.summary_metrics.coverage; // 49.7%

// 2. In the WebSocket handler, map correct fields:
setState(prev => ({
  ...prev,
  global: {
    ...prev.global,
    weeklyProfit: message.data.summary_metrics?.weekly_profit,
    coverage: message.data.summary_metrics?.coverage, // NOT average_coverage
    annualProfit: message.data.summary_metrics?.annual_profit,
    totalServices: message.data.summary_metrics?.total_services,
    operatingCost: message.data.summary_metrics?.operating_cost,
    runtime: message.data.summary_metrics?.total_runtime
  }
}));

// 3. Region field mapping:
// backend: coverage_percent → display: coverage
// backend: weekly_profit → display: profit  
// backend: hub_ports → display: hubs
// backend: services_selected → display: services
// backend: services_generated → display: generated
// backend: services_filtered → display: filtered
// backend: profit_margin_pct → display: margin
```

---

## Appendix B: Backend Schema Reference (Frozen)

**File**: `pipeline_output.json` (root of shipping_optimizer)
**Format**: JSON, snake_case keys
**Verification**: 309/313 assertions passing, score 98.7%

### Key Fields for Frontend Display

```typescript
interface PipelineOutput {
  // Use summary_metrics for GLOBAL display values
  summary_metrics: {
    weekly_profit: number;      // $597,103,144.62
    annual_profit: number;      // $31,049,363,520.12
    revenue: number;            // $2,615,734,124.41
    operating_cost: number;     // $210,561,250.00
    fuel_cost: number;          // $1,678,244,784.29
    transship_cost: number;     // $57,476,255.99
    port_cost: number;          // $72,348,689.51
    total_cost: number;         // $2,018,630,979.80
    total_services: number;     // 442
    satisfied_demand: number;   // 828,396.63 TEU
    unserved_demand: number;    // 1,066,832.97 TEU
    coverage: number;           // 49.70% ← TRUE COVERAGE
    total_runtime: number;      // 405.7 seconds
  };

  // Use regional_results[i] for per-region display
  regional_results: Array<{
    region: string;             // "Asia" | "Europe" | "Americas" | "Middle East" | "Africa"
    status: string;
    services_generated: number;
    services_filtered: number;
    services_selected: number;
    weekly_profit: number;
    annual_profit: number;
    operating_cost: number;
    fuel_cost: number;
    transship_cost: number;
    port_cost: number;
    total_cost: number;
    coverage_percent: number;
    satisfied_demand: number;
    unserved_demand: number;
    total_demand: number;
    profit_margin_pct: number;
    profit_per_service: number;
    cost_per_service: number;
    uncovered_teu: number;
    hub_ports: string[];
    strategy: string;           // LLM-generated strategy text
    explanation: string;        // LLM-generated region report
    selected_services: Service[];
  }>;

  // Use decision_output for coordinator/feedback display
  decision_output: {
    feedback: {
      needs_rerun: boolean;
      coverage_gap: number;
      convergence_score: number;
      weight_adjustments: {
        profit_weight: number;
        coverage_weight: number;
        cost_weight: number;
      };
      conflict_severity: number;
    };
    evaluation: {
      score: number;            // e.g., 3/5
      max: number;
      status: string;
      reasons: string[];
    };
    conflicts: Array<any>;
    resolution_log: Array<any>;
  };

  // Use test_scorecard for quality metrics
  test_scorecard: {
    assertions_passed: number;  // 309
    assertions_failed: number;  // 4
    assertions_total: number;   // 313
    warnings: number;           // 4
    score: number;              // 98.7
  };

  // Use llm_runtime_metrics for AI activity display
  llm_runtime_metrics: {
    llm_calls: number;          // 7
    coordinator_llm_calls: number;    // 2
    coordinator_json_parse_success: number;  // 2
    coordinator_fallback_count: number;      // 0
    coordinator_ai_generated: boolean;       // true
    servicegen_ai_count: number;      // 0
    servicegen_fallback_count: number; // 5
  };
}
```

---

*End of FRONTEND_RUNTIME_INTEGRATION_MASTER_PLAN.md — This report is the authoritative implementation document for all remaining frontend development until V1 Product Freeze.*
