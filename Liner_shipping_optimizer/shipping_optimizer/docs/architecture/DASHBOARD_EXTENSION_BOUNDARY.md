# Dashboard Extension Boundary

**Phase:** 0 (Architecture Lock & Regression Baseline) · **Date:** 2026-08-26 · **Baseline:** `a44b987`

Purpose: freeze the existing dashboard architecture as the baseline for the future
Crucix-inspired maritime operations console. **Phase 0 changes nothing in `frontend/`.**
Future UX work extends within this boundary; it does not redesign it.

> We are NOT copying Crucix. This document establishes what exists so future
> enhancement cannot break current functionality.

---

## 1. Stack (verified from `frontend/package.json`)

| Concern | Library | Status |
|---|---|---|
| UI framework | React ^18.2.0 | Active |
| Map rendering | react-simple-maps ^3.0.0 + d3-geo ^3.1.1 (`WorldMap.jsx`) | Active |
| Styling | tailwindcss ^3.4.19 (+autoprefixer) | Active |
| Build | vite ^4.5.0 + @vitejs/plugin-react | Active |
| Dev WS replay | ws ^8.20.0 (`mock-server.cjs` only) | Dev convenience |
| framer-motion / @tanstack/react-query / zustand | declared, ZERO imports | Unused — do not adopt implicitly; adding state/animation libraries is a CHANGE_CONTROL decision |

Known quirk: `scripts.server` points to nonexistent `../backend/main.js` (backend is Python).

## 2. Data acquisition chain (the spine — do not restructure)

```
pipeline_output.json
   │ fetch(RUNTIME_TRUTH_URL='/pipeline_output.json')      runtimeAdapter.js:6
   ▼
normalizeRuntime()  snake→camel, ?? fallback chains       runtimeAdapter.js:23-99
   │ tolerates server.py / mock-server.cjs / main.py dialects; UNKNOWN FIELDS PASS THROUGH INERTLY
   ▼
useOptimizationState (single React state source:           useOptimizationState.js
   {global, regions, iterations, corridors, connection, pipeline})
   ▼
40 JSX/JS files · MaritimeDashboard.jsx orchestrates navItems.js
```

- WebSocket: `services/websocketManager.js` → `ws://localhost:8000/ws/pipeline`;
  reconnect exponential backoff 1s×2ⁿ cap 30 s, max 5 attempts.
- Merged events: `initial_state`, `stage_*`, `region_update(ed)`, `iteration_completed`, `map_updated`, `pipeline_completed/error`.
- Trigger: `startOptimization()` sends `start_pipeline {dataset_path:'data/datasets/large_shipping_problem.json'}` over WS → backend replays file (no live compute exists).
- REST `services/apiClient.js` has zero component callers (UI is fetch+WS).
- Client-side derivations: `utils/fleetStats.js` (fleet stats from `selected_services`), margin recomputation.

## 3. Routes / views (13 tabs — `components/layout/navItems.js`, rendered by `views/MaritimeDashboard.jsx`)

overview · fleet (Fleet Explorer) · routes (Route Explorer) · ports (Port Intelligence) ·
pipeline · regional (Regional Agents) · funnel (GA · MILP Analytics) · feedback (Feedback Loop) ·
conflict (Conflict Resolution) · map (Maritime Map) · scenarios · export · summary (Executive Summary)

Component inventory (40 files): `common/` BenchmarkBadge, Counter, ProgressBar, PulseDot, Sparkline ·
`layout/` Header, Sidebar, Footer, navItems · `overview/` SummaryView, KpiCard, RuntimeHealth, BackendCertification ·
`regions/` RegionalIntelligence, RegionCard, RegionDetails · `optimization/` PipelineView, PipeNode,
RegionPipelineNode, FunnelView, FleetDashboard, FleetPanel, PortPanel, RouteTable, ScenarioWorkspace,
ExportPanel, DecisionTrace, DecisionExplanation, ConflictView, FeedbackView, OptimizationInsights ·
`map/` WorldMap · root ErrorBoundary.

Map implementation notes: geography from jsDelivr world-atlas TopoJSON (**CDN single point of failure offline**);
bundled `assets/port_coordinates.json`; unknown ports pseudo-placed deterministically in regional bounding boxes;
corridors from state else derived top-5 from services.

## 4. Backend contract surface (what the dashboard actually consumes)

Live server: `backend/server.py` (FastAPI :8000):
REST `/api/health`, `/api/pipeline/status`, `/api/metrics/summary`, `/api/regions/`,
`/api/pipeline/iterations`; WS `/ws/pipeline` with event set frozen as T0-10.
Payload fields consumed flow through runtimeAdapter normalization from the keys frozen in
PIPELINE_OUTPUT_CONTRACT.json. Superseded servers (`main.py`, `unified_main.py`) and orphaned
`routes/*` are NOT part of this contract.

## 5. State management & UX characteristics (current truth)

Single hook state source (no redux/zustand); load-time snapshot + WS merges;
**no stale-data detection, no polling, no timestamps freshness check**;
"vs Previous Run" panel hardcodes single-run mode; PulseDot indicates WS connection.

## 6. Future maritime console requirements (DESIGN ONLY — not implemented in Phase 0)

The future dashboard SHOULD provide (per program direction):

- smooth state transitions; progressive disclosure; graceful loading and degraded states; no layout jumps; no unnecessary reloads
- operational telemetry: live system status, event timeline, per-source health (HEALTHY/DEGRADED/STALE/RATE_LIMITED/AUTH_FAILURE/UNAVAILABLE)
- map-centric intelligence: congestion halos per port marker, density heat toggle, weather overlays — layers default OFF so current views render identically
- vessel intelligence, port intelligence panels; route comparison; explainability surfaces (extend existing DecisionTrace/DecisionExplanation pattern)
- unified maritime operations console feel

Sanctioned extension mechanics when that phase is approved:
1. ONE new nav entry (`navItems.js`, e.g. id `maritime`) → one new view component reading new endpoints/state fields.
2. Status strip beside existing runtime-health widgets on Overview.
3. Optional overlay props on existing `WorldMap.jsx` (default-off layers).
4. Additive reads of `maritime_intelligence` payload block (IP-5) — adapter untouched.
5. Attribution footer component for licensed data sources.
6. New backend read-only endpoints under `/api/maritime/*` beside the existing REST block; optional NEW channel `/ws/maritime` — never touching `/ws/pipeline`.

Forbidden without explicit approval: replacing react-simple-maps, introducing a routing library or global state library, changing theme/design system, restructuring `useOptimizationState`, renaming WS events or payload fields.

## 7. Regression guard for the dashboard boundary

`tests/architecture/test_network_isolation.py` + `test_output_contract.py` protect the
data side (schema + no network in optimizer). Frontend has no test runner today; until one
exists, dashboard protection = contract tests + the frozen key/event lists in this document
and PROTECTED_COMPONENTS.md (T0-9/T0-10).
