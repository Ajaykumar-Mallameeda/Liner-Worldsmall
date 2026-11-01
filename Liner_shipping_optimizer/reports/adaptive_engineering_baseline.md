# Adaptive Engineering — WorldSmall Baseline

**Date:** 2026-09-13  
**Branch:** main  
**Commit:** e647381 (Merge pull request #1 from Ajaykumar-Mallameeda/phase-0-9-freeze)

---

## Current Source State

All source files under `shipping_optimizer/src/` reflect the pre-adaptive state at the time of snapshot. No modifications were made before this baseline capture.

---

## Baseline Configuration

### Instance Specification
| Property | Value |
|----------|-------|
| Ports | 47 |
| Demand lanes | 1,764 |
| Fleet vessels | 263 (6 classes) |
| Directed distance pairs | 2,162 |
| Network density | 81.6% |
| Total weekly demand | 276,447 TEU |
| Avg demand/lane | 156.7 TEU |
| Median demand/lane | ~38 TEU |

### Service Generation (pre-adaptive)
| Mechanism | Fixed Count |
|-----------|-------------|
| Direct services | 500 base × archetype ratio |
| Hub-loop services | 10 base × archetype ratio |
| Feeder services | 100 base × archetype ratio |
| Heuristic candidates | 150 fixed |
| Trunk services | C(10,2) = 45 |

### Regional Filtering
```python
max_services = max(400, num_ports)  # = max(400, 47) = 400
```

### ServiceGA Configuration
```python
pop_size      = 100   # (threshold-based: <100→60, 100-500→100, >500→140)
generations   = 120
NO_IMPROVE_LIMIT = 8
MAX_RUNTIME     = 90s
```

### FrequencyGA Configuration
```python
pop_size       = 40
generations    = 60
NO_IMPROVE_LIMIT = 8
MAX_RUNTIME    = 90s
```

### MILP Configuration
```python
max_transfer_pairs = 2000
time_limit         = 120 seconds
max_services_per_demand = 10
alpha_unserved   = 300 USD/TEU
```

---

## Baseline Runtime Metrics

| Metric | Value |
|--------|-------|
| Total wall-clock runtime | 319.7 s |
| Iterations | 3 |
| LLM status | fallback-driven (0 successful calls, 306 attempts) |
| LLM error | `Client.__init__() unexpected keyword argument 'proxies'` |

---

## Baseline Pipeline Output

### Per-Region Results
| Region | Generated | Filtered | Selected | Profit/wk | Coverage | Neg-prof svcs |
|--------|-----------|----------|----------|-----------|----------|---------------|
| Asia | 812 | 508 | 102 | $275,735,289 | 100.0% | 6 |
| Europe | 623 | 405 | 99 | $7,227,294 | 94.1% | 10 |
| Americas | 803 | 499 | 102 | $-11,350,536 | 100.0% | 18 |

### Global Aggregated Metrics
| Metric | Value |
|--------|-------|
| Total services deployed | 303 |
| Weekly profit | $271,612,047 |
| Annual profit | $14,123,826,444 |
| Global demand-weighted coverage | 88.65% |
| Unserved demand | ~29,000 TEU/wk |

---

## Baseline Negative-Profit Analysis

| Statistic | Value |
|-----------|-------|
| Negative-profit service count | 34 |
| Total negative-profit loss | $-86,961,691 |
| Positive-profit service count | 265 |
| Zero-profit service count | 0 |
| Profit margin on positive services | ~15.5% avg |

---

## Baseline Duplicate Analysis

| Statistic | Value |
|-----------|-------|
| Exact duplicate routes | 7 |
| Reverse-route pairs | 37 |

Note: Deduplication not applied — both duplicates and reverse pairs retained as separate candidates per existing semantics.

---

## Pre-Change Statement

This document records the **pre-change baseline**. All subsequent engineering (Phases A, B, C) must preserve the optimization logic, objective formulation, constraint formulation, service route generation algorithms, GA operators, and MILP formulation documented here. Only search budgets and candidate volumes may change.
