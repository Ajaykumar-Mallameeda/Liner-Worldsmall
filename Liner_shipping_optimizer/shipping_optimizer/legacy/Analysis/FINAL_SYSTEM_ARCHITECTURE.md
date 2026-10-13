# FINAL SYSTEM ARCHITECTURE
## AI Vessel Routing System — Production Architecture v2

**Benchmark Target**: LINERLIB WorldLarge (435 ports · 9,622 OD pairs · 5 regions)  
**Scale Target**: 5,000+ ports · 100,000+ demand lanes (production)  
**Architecture Pattern**: Distributed Asynchronous Multi-Agent Optimization  

---

## Architecture Overview

The system is an 8-layer end-to-end pipeline from raw data ingestion through validated maritime network output. Each layer has strict input/output contracts, enforced via Pydantic schemas at every inter-agent boundary.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: DATA LAYER                                                              │
│ Port DB · Demand Matrix · Fleet DB · Dist Matrix · Cost Model · Hist Routes     │
│ External Maritime APIs · Market Demand Signals · AIS feeds                       │
└──────────────────┬───────────────────────────────────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: ETL / DATA PROCESSING                                                   │
│ ETL Pipeline · Schema Normalization · FFE→TEU Conversion · Pydantic Validation  │
│ K-means Geographic Clustering · Regional Partitioning · Candidate Route Gen      │
└──────────────────┬───────────────────────────────────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 3: CORE OPTIMIZATION (GLOBAL CONTROL + PARALLEL REGIONAL)                  │
│                                                                                  │
│  Global Orchestrator → Regional Splitter → ┌─────────────────────────────┐      │
│       (LLM, α/β/γ)      (origin-only OD)  │ ASIA     · SVC GEN → GA → MILP│     │
│                                            │ EUROPE   · SVC GEN → GA → MILP│     │
│                                            │ AMERICAS · SVC GEN → GA → MILP│     │
│                                            │ AFRICA   · SVC GEN → GA → MILP│     │
│                                            │ MID EAST · SVC GEN → GA → MILP│     │
│                                            └─────────────────────────────┘      │
└──────────────────┬───────────────────────────────────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 4: AGENT INTELLIGENCE (COORDINATION)                                       │
│ Global Aggregation (unique served_od_map) · LLM Coordinator · Conflict Resolver  │
│ Adaptive Weight Controller · Strategy Selection · Iterative Feedback Loop        │
└──────────────────┬───────────────────────────────────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 5: VALIDATION + BENCHMARK                                                  │
│ Route Validation Engine · Fleet Constraint Checker · Service Pattern Validator   │
│ Benchmark Comparator (LINERLIB) · KPI Scoring Engine · Historical Comparator     │
└──────────────────┬───────────────────────────────────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 6: INFRASTRUCTURE + OBSERVABILITY                                          │
│ Redis Streams (job queue) · PostgreSQL (solution store) · FastAPI + Nginx        │
│ Prometheus metrics · Grafana dashboards · OpenTelemetry tracing · Structured log │
└──────────────────┬───────────────────────────────────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 7: RESILIENCE / FAULT TOLERANCE                                            │
│ Circuit Breakers (LLM API) · Retry + Exponential Backoff · MILP Timeout Fallback│
│ Partial Recovery Engine · Graceful Degradation · Failure Detection Engine        │
└──────────────────┬───────────────────────────────────────────────────────────────┘
                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ LAYER 8: OUTPUT LAYER                                                            │
│ Final Route Recommendation · Vessel Deployment Plan · Service Frequency Plan     │
│ Profit Dashboard · Benchmark Comparison · Validation Report · Scenario Output    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Data Layer

### Components
| Component | Description | Source |
|-----------|-------------|--------|
| Port Database | 435 global ports with UNLOCODEs, draft, cost, coordinates | `ports.csv` |
| Demand Matrix | 9,622 OD pairs, FFEPerWeek, Revenue_1, TransitTime | `Demand_WorldLarge.csv` |
| Fleet Database | 6 vessel classes with capacity and quantity | `fleet_WorldLarge.csv` |
| Distance Matrix | 62,002 port-pair distances, Panama/Suez flags | `dist_dense.csv` |
| Cost Model Data | Port handling costs, fuel config, vessel specs | `vessel_specs_enriched.json`, `fuel_config.json`, `ports_cost_enriched.csv` |
| Historical Route Dataset | Past service patterns and LINERLIB baselines | LINERLIB benchmark files |
| External Maritime APIs | AIS feeds, market demand signals, weather, port congestion | API integrations |

### Key Invariants
- All demand stored in **TEU** (FFE × 2 conversion applied at loader, never later)
- Port IDs: consistent string UNLOCODEs throughout (no integer/string mixing)

---

## Layer 2: ETL / Data Processing

### Components

**ETL Pipeline**: Sequential ingestion, transformation, and routing of raw data.

**Data Validation** (Pydantic strict mode):
- All required fields typed and present
- Fleet capacity ≤ 300 vessels
- Positive demand values (no zero/negative TEU)
- Geographic consistency (all ports have valid coordinates)

**Schema Normalization**:
- `weekly_teu = float(row["FFEPerWeek"]) * 2.0` — enforced at loader, not downstream
- Port IDs normalized to string UNLOCODEs

**Geographic Clustering**:
- K-means on all 435 port (longitude, latitude) coordinates
- 5 clusters: Asia, Europe, Americas, Africa, Middle East

**Regional Partitioning**:
- **Origin-only OD ownership**: each demand pair assigned to the region of the demand's origin port
- No OR-logic (origin-OR-destination was the root cause of 3× demand inflation bug)
- Conservation assert: `Σ regional_teu == global_teu`, relative delta < 1e-6

**Candidate Route Generator**:
- Direct routes: top-500 demand corridors
- Hub-loop routes: high-degree hub ports (degree ≥ 30) prioritized in Phase 1
- Trunk routes: major ocean lanes
- Feeder routes: regional distribution

---

## Layer 3: Core Optimization

### 3a. Global Orchestrator Agent

**Role**: Entry point, problem analysis, iterative control.

**LLM Integration**:
- Model: GPT-OSS-120B via OpenRouter API
- Temperature: 0.1 (deterministic, number-grounded outputs)
- Structured JSON output enforced
- Circuit breaker: fallback to rule-based logic after ≥5 API failures

**Weight Vector**:
```
Initial: α=0.50 (profit), β=0.40 (coverage), γ=0.10 (cost)
After Iter 1 (if coverage_gap > 5%): α=0.42, β=0.50, γ=0.08
After Iter 2: α=0.40, β=0.52, γ=0.08
```

**Convergence**: stops when `|coverage_iter_i - coverage_iter_{i-1}| < 0.5%` or `i == 3`.

### 3b. Regional Splitter

**Role**: Decomposes global problem into 5 independent regional subproblems.

**Critical correctness constraint**: origin-only OD assignment. Verified by:
```python
assert abs(sum(r.demand_teu for r in regions) - global_demand_teu) / global_demand_teu < 1e-6
```

### 3c. Regional Agents (×5, Parallel)

Each regional agent runs an independent pipeline:

**Stage 1 — Service Generator**:
- Direct (top-corridor), hub-loop, trunk, feeder service templates
- Hub-centric selection: ports with degree ≥ 30 forced into Phase 1 selection

**Stage 2 — Service Filter**:
- Margin threshold filter
- Fleet viability check (vessels required ≤ fleet_size)
- Capacity feasibility (service_capacity ≥ min demand threshold)

**Stage 3 — ServiceGA (Level 1)**:
- Population: 80, Generations: 120
- Fitness: `α × NormProfit + β × Coverage − γ × NormCost`
- `compatible_services()` fix: port-ordering uses explicit length check (not truthiness of 0)
- Early stopping: no improvement for N generations
- Runtime budget: 60s hard cap

**Stage 4 — FrequencyGA (Level 2)**:
- Frequency range: 1–3 sailings/week
- Fleet usage: `ceil(cycle_time × freq / 7)` — frequencies rounded to integer before this
- Post-GA pruning: removes inefficient services to satisfy fleet cap
- Runtime budget: 30s hard cap

**Stage 5 — HubMILP (PuLP/CBC)**:
- Fleet constraint: `prob += total_vessels_used <= self.fleet_size` — **active, not commented out**
- MILP status validated before extracting variables: if `status != "Optimal"` → return `{"status": status, "error": ...}`
- Capacity: `service_capacity × round(freq)` — integer freq enforced
- Transfer pairs: up to 2,000 per region
- Timeout: 120s hard cap → fallback to best GA solution
- Objective: maximize `Σ Revenue − Σ Cost` with bounded coverage reward (no unbounded multipliers)

**Stage 6 — Profit Computation**:
```
Profit = Revenue − (C_fixed + C_dynamic + C_handling + C_transship + C_port)

Revenue     = Σ min(service_capacity, corridor_demand) × Rate_od   [no over-utilization]
C_dynamic   = FuelPrice × k × v³ × distance                        [Ronen 1982 cubic law]
Profit Margin = (Revenue − OpCost) / Revenue                        [EBIT standard]
```

---

## Layer 4: Agent Intelligence (Coordination)

### Global Aggregation

**Coverage computation**:
```python
served_od_map = {}  # unique dict, not per-region averages
for region_result in regional_results:
    for od_pair, teu in region_result.served_demands.items():
        if od_pair not in served_od_map:  # first-in (highest profit region wins)
            served_od_map[od_pair] = teu
global_coverage = sum(served_od_map.values()) / global_demand_teu * 100
# hard guard: min(global_coverage, 100.0)
```

**Key invariants**:
- No regional averages for global coverage
- Revenue = `min(capacity, demand)` — not assumed full utilization
- `unserved_demand` key exposed (not `uncovered_teu` — aliasing corrected)
- `operating_cost` key exposed (not `cost` — aliasing corrected)

### LLM Coordinator Agent

**Feedback signals generated**:
```json
{
  "coverage_gap": 12.3,
  "profit_gap": 150000,
  "conflict_severity": 0.08,
  "weight_adjustments": {"alpha": 0.42, "beta": 0.50, "gamma": 0.08},
  "needs_rerun": true,
  "convergence_score": 0.41
}
```

**Early stop gate**: `needs_rerun = bool(reasons) and not at_cap and improvement >= 0.5%`

---

## Layer 5: Validation + Benchmark

### Route Validation Engine

| Check | Constraint | Action on Failure |
|-------|-----------|-------------------|
| Fleet cap | total_vessels ≤ 300 | Hard error, no deployment |
| MILP status | == "Optimal" | Return structured error |
| FFE/TEU units | weekly_teu = FFE × 2 | Block at ETL |
| Flow conservation | flow_in == flow_out at hubs | Infeasibility signal |
| Profit margin | EBIT = (Rev − OpCost) / Rev | Flag for review |
| Demand conservation | rel_diff < 1e-6 | Pipeline crash (intended) |

### Benchmark Comparator

**LINERLIB benchmark instances**:
- `WorldLarge`: 435 ports, 9,622 OD pairs — primary target
- `WorldSmall`: reduced instance for rapid validation cycles  
- `Baltic`: North European regional validation
- `WestAfrica`: MEA regional validation

**KPI Scoring Metrics**:
- Coverage % delta vs benchmark baseline
- Weekly profit delta (USD)
- Fleet utilization ratio (vessels used / 300)
- Port rotation similarity score (Jaccard on port sets)
- Route overlap % with benchmark routes
- Sailing frequency alignment
- Service pattern entropy (network diversity)

---

## Layer 6: Infrastructure + Observability

### Message Queue (Redis Streams)
```json
{
  "job_id": "uuid4",
  "problem_id": "WorldLarge-v1",
  "priority": "normal|high",
  "config": {"max_iterations": 3, "fleet_size": 300},
  "timestamp": "ISO8601"
}
```
- Consumer groups with ACK for reliability
- Backlog limit: 1,000 jobs; retention: 24 hours

### API Layer (FastAPI + Nginx)
- Rate limit: 100 requests/minute per client
- Versioned endpoint: `POST /v1/optimize` → returns `{job_id, status: "queued"}`
- Health: `/health`, `/health/ready`, `/health/live`, `/metrics`

### Persistence (PostgreSQL)
- Solution history with iteration trace
- Scenario comparison storage
- Benchmark result archival

### Observability Stack
- **Prometheus**: optimization duration, solver status, coverage per iteration, fleet usage
- **Grafana**: profit trend, coverage convergence, fleet utilization dashboards
- **OpenTelemetry**: distributed traces with `region_id`, `operation`, `duration_sec` spans
- **Structlog**: structured logs with correlation IDs

---

## Layer 7: Resilience / Fault Tolerance

### Circuit Breaker (LLM API)
```python
CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,       # seconds
    expected_exception=LLMTimeout,
    fallback=rule_based_coordinator
)
```

### Timeout Hierarchy
| Component | Timeout | Fallback |
|-----------|---------|---------|
| ServiceGA | 60s | Best chromosome found |
| FrequencyGA | 30s | Last valid frequency set |
| HubMILP | 120s | Best GA-derived solution |
| LLM API | 15s | Rule-based logic |

### Partial Recovery
If a regional agent fails, the system:
1. Assembles results from successful regions
2. Logs the failed region with `circuit_open` status
3. Returns partial solution with explicit coverage reduction noted
4. Does not present partial as complete (no silent failure)

### Failure Detection
- MILP solver status checked before any variable extraction
- Demand conservation assert fires before pipeline continues
- Fleet overshoot = hard stop, not warning
- Zero-demand edge case handled at coverage division

---

## Layer 8: Output Layer

### Deliverables
| Output | Content |
|--------|---------|
| Final Route Recommendation | Service list with port rotations, vessel assignments |
| Vessel Deployment Plan | Vessel class → service mapping, fleet utilization |
| Service Frequency Plan | Sailings/week per service, capacity utilization |
| Profit Dashboard | Revenue, cost breakdown (fixed/dynamic/handling/transship/port), EBIT |
| Benchmark Comparison | Delta vs LINERLIB WorldLarge optimal, per-KPI breakdown |
| Validation Report | All constraint checks (pass/fail), coverage %, fleet count |
| Scenario Simulation | Sensitivity to α/β/γ weight changes, alternate coverage targets |

---

## Data Flow Summary

```
Raw CSV/JSON
    → ETL (validate, FFE×2, cluster)
    → Orchestrator (LLM, α/β/γ init)
    → Splitter (origin-only OD, 5 regions)
    → Regional Agents ×5 (parallel, async queue)
        → SVC GEN → FILTER → GA L1 → GA L2 → MILP → PROFIT
    → Global Aggregation (unique OD map, conservation assert)
    → Coordinator (feedback signals, weight update)
    → Route Validator + Benchmark Comparator
    → Final Optimizer (hard constraint pass)
    → Infrastructure (Redis store, Prometheus emit)
    → Resilience (circuit check, partial recovery if needed)
    → Output (dashboards, report, JSON solution)
    ↑___________________ adaptive feedback loop (up to 3 iterations) ___________↑
```

---

## Critical Correctness Constraints (Enforced)

| # | Constraint | Location | Why It Matters |
|---|-----------|----------|---------------|
| 1 | Origin-only OD ownership | `regional_splitter.py` | Eliminates 3× demand inflation from OR-logic |
| 2 | Global coverage via unique OD map | `orchestrator_agent.py` | No averaging regional figures |
| 3 | FFE×2 at loader | `network_loader.py:68` | All downstream calculations correct |
| 4 | Fleet constraint active in MILP | `hub_milp.py:249` | Fleet ≤300 enforced, not warned |
| 5 | MILP status check before extraction | `hub_milp.py:287` | No silent None→0.0 garbage |
| 6 | Integer frequency before capacity calc | `hub_milp.py:270` | No fractional vessel allocation |
| 7 | Relative FP tolerance (1e-6) | `orchestrator_agent.py:381` | No crash on large-scale rounding |
| 8 | Revenue = min(capacity, demand) | All profit calcs | No over-utilization assumption |
| 9 | EBIT profit margin standard | All reporting | Academic-grade metric consistency |
| 10 | Ronen (1982) cubic fuel law | `hub_milp.py` | Economically realistic dynamic cost |

---

## Academic Validation References

- **Álvarez (2009)**: Joint routing and fleet deployment — theoretical foundation
- **Ronen (1982)**: Cubic fuel law `FuelBurn = k × v³` — dynamic cost model
- **Dutta et al. (2024)**: RL for LSNDP — benchmarking reference
- **Brouer et al. (2023)**: Matheuristic framework — GA+MILP hybrid validation
- **LINERLIB**: WorldLarge, WorldSmall, Baltic, WestAfrica benchmark instances
