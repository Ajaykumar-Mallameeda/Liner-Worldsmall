# WorldSmall Adaptive Budget Policy

**Version:** 1.0  
**Date:** 2026-09-13  
**Status:** IMPLEMENTED

---

## 1. Design Rationale

The existing optimizer used fixed, instance-agnostic budgets for service generation, GA search, filtering, and MILP solving. This meant that even small or simple regions received the same maximal search effort as complex ones, wasting compute without improving solution quality.

The adaptive budget policy derives search budgets from **measurable properties of the current Problem instance or region** — port count, lane count, demand volume, network density, and fleet size. It preserves all existing optimization logic, objective formulation, constraints, route-generation algorithms, GA operators, and MILP formulation. Only computational budgets change.

**Key principle:** The adaptive layer changes computational/search budgets and candidate volume only. It does not change the underlying GA operators, fitness formulation, MILP formulation, constraints, objective semantics, demand data, fleet data, or service route construction logic.

---

## 2. Complexity Signals

The policy uses five measurable signals derived from the Problem instance:

| Signal | Source | Role |
|--------|--------|------|
| `num_lanes` | `len(problem.demands)` | Primary driver of search-space size |
| `density_pct` | `lanes / (ports × (ports-1)) × 100` | Secondary driver; captures network connectivity |
| `avg_demand_per_lane` | `total_teu / lanes` | Demand intensity per corridor |
| `fleet_total_vessels` | `problem.fleet.total_vessels` | Resource constraint affecting feasible search space |
| `num_ports` | `len(problem.ports)` | Indirect signal used in tier classification |

These signals are deterministic for identical inputs and contain no randomness or LLM dependency.

---

## 3. Formulas

### 3.1 Complexity Factor (dimensionless, [0.5, 2.0])

```
lane_factor    = 0.4 + 0.8 × min(1.0, num_lanes / 2000)
dens_factor    = 0.0 + 0.5 × min(1.0, density_pct / 100.0)
demand_factor  = 0.0 + 0.3 × min(1.0, avg_demand_per_lane / 500.0)
fleet_factor   = 0.5 + 0.7 × min(1.0, fleet_vessels / 500.0)

complexity_factor = max(0.5, min(2.0, (lane_factor + dens_factor + demand_factor) × fleet_factor))
```

For WorldSmall (47 ports, 1764 lanes, density=81.6%, fleet=263):
- `lane_factor ≈ 0.8`
- `dens_factor ≈ 0.4`
- `demand_factor ≈ 0.1`
- `fleet_factor ≈ 0.8`
- **`cf ≈ 1.4` → tier "large"**

### 3.2 Service-Generation Targets

| Mechanism | Formula | WorldSmall Result |
|-----------|---------|-------------------|
| Direct services | `clamp(500 × cf, 250, 800)` | **698** |
| Hub-loop services | `clamp(10 × cf, 4, 20)` | **14** |
| Feeder services | `clamp(100 × cf, 20, 250)` | **140** |
| Heuristic candidates | `clamp(150 × cf, 30, 250)` | **209** |
| Trunk services | `clamp(45 × cf × 0.7, 10, 45)` | **44** |
| **Candidate cap** | sum of above | **1105** |

Pre-adaptive baseline: ~2098 raw services generated (direct×0.6 ratio + hub_loop×0.15 + feeder×0.2 + heuristic 150). The adaptive policy produces ~1105 targeted candidates before archetype mixing, which then combines with the LLM-influenced archetype ratios.

### 3.3 ServiceGA Budget

| Parameter | Formula | WorldSmall Result |
|-----------|---------|-------------------|
| Population size | `clamp(60 + 0.8 × (lanes×0.001 + density×0.01)×100, 60, 140)` | **140** |
| Max generations | `clamp(40 + 0.3 × lanes, 40, 120)` | **120** |
| Stagnation limit | `clamp(0.08 × generations + 2, 5, 12)` | **11** |

Pre-adaptive: pop_size was threshold-based (100 for 100≤n<500 services), generations=120, stagnation=8 (hardcoded NO_IMPROVE_LIMIT).

### 3.4 FrequencyGA Budget

| Parameter | Formula | WorldSmall Result |
|-----------|---------|-------------------|
| Population size | `clamp(20 + 0.5 × (lanes×0.0005 + density×0.005)×100, 20, 60)` | **60** |
| Max generations | `clamp(30 + 0.2 × lanes, 30, 80)` | **80** |
| Stagnation limit | `clamp(0.10 × generations + 2, 5, 10)` | **10** |

Pre-adaptive: pop_size=40, generations=60, stagnation=8 (hardcoded).

### 3.5 Regional Filter Cap

```
filter_cap = clamp(100 + 0.4 × lanes + 0.5 × density_pct, 100, 600)
```

WorldSmall: `clamp(100 + 0.4×1764 + 0.5×81.6, 100, 600)` = **600**

Pre-adaptive: `max(400, num_ports)` = `max(400, 47)` = **400**.

### 3.6 MILP Workload Limits

| Parameter | Formula | WorldSmall Result |
|-----------|---------|-------------------|
| Transfer pairs | `clamp(1500 + 1.0 × lanes, 400, 4000)` | **3264** |
| Time limit (s) | `clamp(max(30, min(90, 30 + 0.02×lanes + 0.1×density)), 30, 90)` | **73** |

Pre-adaptive: max_transfer_pairs=2000, time_limit=120s.

---

## 4. What Remains Fixed

The following values are intentionally NOT adapted in this batch:

| Value | Reason |
|-------|--------|
| `alpha_unserved = 300 USD/TEU` | Part of objective semantics; changing it would conflate budget adaptation with objective calibration |
| GA crossover mechanism | Single-point crossover preserved |
| GA mutation mechanism | Random bit-flip preserved |
| GA selection mechanism | Tournament via elite ranking preserved |
| MILP decision variables | Same flow variables, same formulation |
| MILP constraints | Fleet, capacity, flow-balance unchanged |
| Negative-profit service policy | No hard floor added; negative-profit services still allowed |
| Route generation algorithms | All archetypes (direct, hub-loop, feeder, trunk, heuristic) preserved |

---

## 5. Minimum / Maximum Safety Bounds

Every adaptive parameter is clamped to prevent degenerate values:

| Parameter | Min | Max |
|-----------|-----|-----|
| SGA population | 60 | 140 |
| SGA generations | 40 | 120 |
| SGA stagnation | 5 | 12 |
| FreqGA population | 20 | 60 |
| FreqGA generations | 30 | 80 |
| FreqGA stagnation | 5 | 10 |
| Filter cap | 100 | 600 |
| MILP transfer pairs | 400 | 4000 |
| MILP time limit | 30s | 90s |

No parameter can produce zero, negative, or unreasonably large values.

---

## 6. Logging & Observability

Every budget computation logs:
- Input complexity signals (ports, lanes, density, fleet)
- Calculated raw value
- Clamped result
- Min/max bounds applied

This enables debugging and audit of any anomalous budget decisions.

---

## 7. LLM Independence

The adaptive budget policy is completely independent of LLM availability. The same budgets are produced whether the LLM succeeds or fails (the current environment has 0 successful LLM calls out of 306 attempts). This is verified by property tests.

---

## 8. Component Location

New file: `src/optimization/adaptive_budget.py`

Exports:
- `ComplexitySignals` — frozen dataclass of raw signals
- `compute_complexity_signals()` — factory from Problem-like view
- `AdaptiveBudget` — main budget object with `.from_signals()` classmethod
- Accessor functions: `get_service_generation_params()`, `get_filter_params()`, `get_service_ga_params()`, `get_frequency_ga_params()`, `get_milp_params()`
