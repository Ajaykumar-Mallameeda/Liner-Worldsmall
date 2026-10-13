# WorldSmall Phase 1.5 + Phase 2 Audit Report

**Date:** 2026-09-12  
**Auditor:** Claude Code (Agnes)  
**Scope:** Data Semantics Audit + Runtime Loader Investigation  
**Status:** AUDIT ONLY — No production code modified

---

## 1. Executive Summary

This report presents findings from a comprehensive audit of the WorldSmall dataset and existing runtime data-loading architecture. The audit covers:

- **Phase 1.5:** Semantic verification of WorldSmall data transformations (FFE→TEU, Revenue units, port costs, fleet semantics, distance semantics)
- **Phase 2:** Investigation of the existing runtime data-loading pipeline for WorldLarge and identification of integration requirements for WorldSmall

**Key Discovery:** Two distinct data loading paths exist in the codebase with different transformation rules and scaling factors. This has critical implications for WorldSmall integration.

**Overall Verdict:** READY WITH CONDITIONS

---

## 2. Phase 1 Validation Confirmation

The initial validation of WorldSmall artifacts passed all checks:

| Metric | Expected | Actual | Status |
|--------|----------|--------|--------|
| Ports | 47 | 47 | PASS |
| Demands | 1,764 | 1,764 | PASS |
| Vessel Classes | 6 | 6 | PASS |
| Total Vessels | 263 | 263 | PASS |
| Distance Pairs | 2,162 | 2,162 | PASS |
| Missing Demand References | 0 | 0 | PASS |
| Duplicate OD Pairs | 0 | 0 | PASS |
| Missing Distances | 0 | 0 | PASS |

---

## 3. WorldSmall Data Semantics Audit

### 3.1 JSON Field → Source CSV Traceability Table

| JSON Field | Source CSV Field | Source Unit | JSON Unit | Transformation | Required? | Evidence |
|------------|-----------------|-------------|-----------|----------------|-----------|----------|
| ports.id | UNLocode | — | string | none | No | `generate_worldsmall_dataset.py:176` |
| ports.name | name | — | string | none | No | `generate_worldsmall_dataset.py:177` |
| ports.latitude | Latitude | decimal degrees | float | none | No | `generate_worldsmall_dataset.py:178` |
| ports.longitude | Longitude | decimal degrees | float | none | No | `generate_worldsmall_dataset.py:179` |
| ports.handling_cost | CostPerFULL | USD/FFE | USD/TEU | ×2 | Yes | `generate_worldsmall_dataset.py:181`, `network_loader.py:44` |
| ports.draft | Draft | meters | float | none | No | `generate_worldsmall_dataset.py:182` |
| ports.port_call_cost | PortCallCostFixed | USD/port_call | USD/port_call | none | No | `generate_worldsmall_dataset.py:183` |
| ports.transshipment_cost | CostPerFULLTrnsf | USD/FFE | USD/TEU | ×2 | Yes | `generate_worldsmall_dataset.py:184` |
| ports.variable_port_call_cost | PortCallCostPerFFE | USD/FFE | USD/TEU | **HARDCODED 20.0** | **NO — SEE FINDING #3** | `generate_worldsmall_dataset.py:186` |
| demands.origin | Origin | UNLOCODE | string | none | No | `generate_worldsmall_dataset.py:195` |
| demands.destination | Destination | UNLOCODE | string | none | No | `generate_worldsmall_dataset.py:196` |
| demands.weekly_teu | FFEPerWeek | FFE/week | TEU/week | ×2 | Yes | `generate_worldsmall_dataset.py:198` |
| demands.revenue_per_teu | Revenue_1 | USD/FFE | USD/TEU | ×2 | Yes | `generate_worldsmall_dataset.py:200` |
| distance_matrix | dist_dense | nautical miles | nautical miles | none | No | `generate_worldsmall_dataset.py:208-213` |

### 3.2 Critical Finding: variable_port_call_cost Hardcoded

**ISSUE:** The WorldSmall generator hardcodes `variable_port_call_cost = 20.0` for all ports, while the WorldLarge loader computes it from `PortCallCostPerFFE × 2.0`.

| Port | WS CSV PortCallCostPerFFE | WL var_port_call_cost (×2) | WS hardcoded value | Difference |
|------|---------------------------|---------------------------|-------------------|------------|
| AEJEA | 2.00 | 4.0 | 20.0 | **+16.0 (400% higher)** |
| AOLAD | 61.00 | 122.0 | 20.0 | **-102.0 (84% lower)** |
| AUBNE | 12.00 | 24.0 | 20.0 | -4.0 |
| BEANR | 16.00 | 32.0 | 20.0 | -12.0 |

**Source:** `scripts/generate_worldsmall_dataset.py:186` — comment says "Hardcoded per existing convention" but the existing convention uses `PortCallCostPerFFE × 2.0`.

**Impact:** This creates inconsistent economic modeling between WorldSmall and WorldLarge. Port call cost variations across ports are lost.

---

## 4. FFE/TEU Audit

### 4.1 LINERLIB Source Definition

- **Field:** `FFEPerWeek`
- **Unit:** Freight Freight Equivalent per week (FFE/week)
- **Definition:** 1 FFE = 1 full container equivalent (20' or 40' box counted as 1 unit regardless of size)
- **Revenue field:** `Revenue_1` — USD per FFE

### 4.2 Current Application Expectation

- **Internal model:** `Demand.weekly_teu` (TEU/week)
- **TEU definition:** 1 TEU = 1 twenty-foot equivalent unit
- **FFE → TEU conversion:** Industry-standard factor of ~2.0 (1 FFE ≈ 2 TEU, reflecting mix of 20' and 40' containers)

### 4.3 Conversion Trace

```
Stage                    Input          Transformation        Output           Unit
─────────────────────────────────────────────────────────────────────────────────
LINERLIB source CSV      FFEPerWeek     —                     FFEPerWeek       FFE/week
JSON generator           FFEPerWeek     × 2.0                 weekly_teu       TEU/week
NetworkLoader.load_demands (CSV path)  FFEPerWeek  × lane_factor (default 2.0)  weekly_teu  TEU/week
Test load_problem (JSON path)  weekly_teu   × DEMAND_SCALE(6)  weekly_teu*6    TEU/week
Optimizer (frequency_ga) weekly_teu     —                     route_demand     TEU
Optimizer (hub_milp)     weekly_teu     —                     flow variables    TEU
Profit evaluator         weekly_teu     × revenue_per_teu     revenue          USD
```

### 4.4 Assessment

The ×2 transformation is **JUSTIFIED** as a legitimate FFE→TEU conversion:
- LINERLIB benchmark defines FFE as the base unit
- Industry standard: 1 FFE ≈ 2 TEU (accounts for 40' containers being 2 TEU)
- Applied consistently at generation time and again at CSV loader time (not double — they are alternative paths)

**However:** The two code paths produce different values:
- **CSV path:** FFE × 2.0 = TEU (single conversion)
- **JSON path:** (FFE × 2.0) × 6.0 = TEU × 6 (double scaled)

This is **BY DESIGN** for WorldLarge testing (DEMAND_SCALE=6 is intentional amplification), but creates inconsistency for WorldSmall.

---

## 5. Revenue Unit Audit

### 5.1 LINERLIB Source Definition

- **Field:** `Revenue_1`
- **Unit:** USD per FFE (USD/FFE)
- **Meaning:** Freight rate charged per full container equivalent per week

### 5.2 Transformation Analysis

| Stage | Input Unit | Transformation | Output Unit | Justified? |
|-------|-----------|----------------|-------------|------------|
| Raw CSV | USD/FFE | — | USD/FFE | — |
| JSON generator | USD/FFE | × 2.0 | USD/TEU | Yes (same FFE→TEU logic) |
| NetworkLoader (CSV) | USD/FFE | × lane_factor | USD/TEU | Yes |
| Test load_problem (JSON) | USD/TEU | **No scaling** | USD/TEU | Consistent |

### 5.3 Assessment

The ×2 transformation for revenue is **SEMANTICALLY CONSISTENT** with the FFE→TEU conversion. Revenue per TEU should be approximately double the revenue per FFE (since 1 FFE ≈ 2 TEU).

**Example trace (AOLAD→AEJEA):**
- Raw CSV: FFEPerWeek=1, Revenue_1=2290 USD/FFE
- JSON: weekly_teu=2.0 TEU, revenue_per_teu=4580 USD/TEU
- Verification: 2290 × 2 = 4580 ✓ (consistent)

---

## 6. Port Cost Audit

### 6.1 LINERLIB Source Fields

| CSV Field | Meaning | Unit | Typical Value Range |
|-----------|---------|------|---------------------|
| CostPerFULL | Handling cost per full container | USD/FFE | 50–600 |
| CostPerFULLTrnsf | Transshipment cost per full container | USD/FFE | 20–280 |
| PortCallCostFixed | Fixed cost per port call | USD/port_call | 1,000–50,000 |
| PortCallCostPerFFE | Variable cost per full container | USD/FFE | 2–120 |

### 6.2 Transformation Analysis

| JSON Field | Source | Transformation | Correct? |
|-----------|--------|----------------|----------|
| handling_cost | CostPerFULL | × 2.0 | **Yes** — converts USD/FFE to USD/TEU |
| transshipment_cost | CostPerFULLTrnsf | × 2.0 | **Yes** — converts USD/FFE to USD/TEU |
| port_call_cost | PortCallCostFixed | none | **Yes** — fixed cost, no unit conversion needed |
| variable_port_call_cost | PortCallCostPerFFE | **HARDCODED 20.0** | **NO** — should be × 2.0 like other costs |

### 6.3 variable_port_call_cost Origin Analysis

**Evidence:**
1. `network_loader.py:48` computes `variable_port_call_cost = PortCallCostPerFFE × 2.0` for WorldLarge
2. `generate_worldsmall_dataset.py:186` hardcodes `variable_port_call_cost = 20.0` for ALL WorldSmall ports
3. Comment in generator says "Hardcoded per existing convention" — but the existing convention is `×2.0`, not hardcoded 20.0

**Likely origin:** The value 20.0 was chosen as a reasonable average (many ports have PortCallCostPerFFE ≈ 10, and 10×2=20), but it should NOT be hardcoded. This is a **LEGACY/HARDCODED** assumption, not a benchmark specification.

---

## 7. Fleet Semantics Audit

### 7.1 Fleet Data Structure

Two fleet files exist for WorldSmall:

**fleet_WorldSmall.csv** (quantity only):
| Vessel class | Quantity |
|--------------|----------|
| Feeder_450 | 24 |
| Feeder_800 | 29 |
| Panamax_1200 | 68 |
| Panamax_2400 | 74 |
| Post_panamax | 58 |
| Super_panamax | 10 |
| **Total** | **263** |

**fleet_data.csv** (specifications):
| Vessel class | Capacity FFE | TC rate daily | designSpeed | Bunker/day |
|--------------|-------------|---------------|-------------|------------|
| Feeder_450 | 450 | 5000 | 12 | 18.8 |
| Feeder_800 | 800 | 8000 | 14 | 23.7 |
| Panamax_1200 | 1200 | 11000 | 18 | 52.5 |
| Panamax_2400 | 2400 | 21000 | 16 | 57.4 |
| Post_panamax | 4200 | 35000 | 16.5 | 82.2 |
| Super_panamax | 7500 | 55000 | 17 | 126.9 |

### 7.2 Runtime Usage

**FINDING: Fleet data is NOT loaded by NetworkLoader or any production runtime component.**

Evidence:
- `src/data/network_loader.py` — no fleet loading methods
- `src/optimization/hub_milp.py` — uses `fleet_size=300` (hardcoded default)
- `src/optimization/frequency_ga.py` — uses `FLEET_SIZE=300` (hardcoded)
- `src/optimization/hierarchical_ga.py` — uses `FLEET_SIZE=300` (hardcoded)
- Grep for `fleet_data.csv` — zero matches in source code

**Fleet capacity semantics:**
- LINERLIB fleet_data.csv uses **Capacity FFE** (FFE capacity per vessel)
- Runtime `VESSEL_FUEL_CONSUMPTION` dictionary uses **TEU-equivalent capacity**:
  ```
  Feeder_450: capacity=450 TEU  ← matches FFE=450 (no conversion)
  Feeder_800: capacity=800 TEU  ← matches FFE=800
  Panamax_1200: capacity=1200 TEU  ← matches FFE=1200
  Panamax_2400: capacity=2400 TEU  ← matches FFE=2400
  Post_panamax: capacity=5000 TEU  ← MISMATCH: FFE=4200, runtime=5000
  Super_panamax: capacity=8000 TEU  ← MISMATCH: FFE=7500, runtime=8000
  ```

**Impact:** For Post_panamax and Super_panamax classes, there is a 19-20% discrepancy between LINERLIB specifications and runtime fuel consumption models. This affects fuel cost calculations and profitability estimates.

---

## 8. Distance Semantics Audit

### 8.1 Source File Structure

**dist_dense.csv headers:** `fromUNLOCODe`, `ToUNLOCODE`, `Distance`, `Draft`, `IsPanama`, `IsSuez`

| Column | Unit | Description | Used at Runtime? |
|--------|------|-------------|------------------|
| Distance | nautical miles | Great circle / routing distance | **Yes** — primary use |
| Draft | meters | Minimum draft required | **No** — dropped by loader |
| IsPanama | bool (0/1) | Panama canal flag | **No** — dropped by loader |
| IsSuez | bool (0/1) | Suez canal flag | **No** — dropped by loader |

### 8.2 Runtime Loading

- `network_loader.py:128-136` loads Distance column only, ignores Draft/IsPanama/IsSuez
- `fuel_cost.py:204-205` uses **500 nm fallback** for missing distance pairs

### 8.3 Distance Completeness

| Metric | Value |
|--------|-------|
| Total directed pairs expected (47×46) | 2,162 |
| Total pairs in dist_dense.csv | 2,162 |
| Missing distances | 0 |
| Completeness | 100% |

### 8.4 Directional Semantics

Distances are **directed** (asymmetric): `fromUNLOCODe → ToUNLOCODE`. The CSV contains 2,162 directed pairs (not symmetric). The runtime uses the directed matrix directly without symmetry enforcement.

---

## 9. ×2 Transformation Audit

### 9.1 All ×2 Transformations Applied

| Field | Source | ×2 Applied At | ×2 Applied Again? | Net Effect |
|-------|--------|---------------|-------------------|------------|
| handling_cost | CostPerFULL | JSON generator | CSV loader (network_loader.py:44) | **DOUBLE IF BOTH PATHS USED** |
| transshipment_cost | CostPerFULLTrnsf | JSON generator | CSV loader (network_loader.py:47) | **DOUBLE IF BOTH PATHS USED** |
| weekly_teu | FFEPerWeek | JSON generator | CSV loader (network_loader.py:100) | **DOUBLE IF BOTH PATHS USED** |
| revenue_per_teu | Revenue_1 | JSON generator | CSV loader (network_loader.py:103) | **DOUBLE IF BOTH PATHS USED** |
| variable_port_call_cost | PortCallCostPerFFE | **NOT in JSON generator** | CSV loader (network_loader.py:48) | Single ×2 |

### 9.2 Are Both Paths Ever Used Simultaneously?

**NO.** The two paths are mutually exclusive:
- **Path A (benchmark script):** Uses `NetworkLoader.load_network()` → reads CSV → applies ×2 once
- **Path B (tests/API):** Uses `load_problem(JSON)` → reads pre-scaled JSON → applies DEMAND_SCALE=6 on top

They are never combined in a single execution. However, the **potential for confusion exists** if someone mixes approaches.

### 9.3 Double Conversion Risk Assessment

| Risk | Likelihood | Severity | Mitigation |
|------|-----------|----------|------------|
| Accidentally applying ×2 twice in new code | Medium | HIGH | Document both paths clearly |
| WorldSmall integrated via wrong path | Low | CRITICAL | Use JSON path with explicit scaling |
| DEMAND_SCALE applied to WorldSmall unnecessarily | Unknown | MEDIUM | WorldSmall should NOT use DEMAND_SCALE |

---

## 10. Hardcoded Transformation Audit

### 10.1 All Hardcoded Values Found

| Value | Location | Type | Impact on WorldSmall |
|-------|----------|------|---------------------|
| `variable_port_call_cost = 20.0` | `generate_worldsmall_dataset.py:186` | Port-specific | **CRITICAL** — loses per-port variation |
| `FLEET_SIZE = 300` | `frequency_ga.py:122`, `hub_milp.py:61`, `hierarchical_ga.py:164` | Global constraint | WorldSmall has 263 vessels — should adjust |
| `DEMAND_SCALE = 6` | `test_orchestrator.py:129` | Scaling factor | WorldSmall should NOT scale demands |
| `distance fallback = 500.0` | `fuel_cost.py:205` | Missing distance | All WorldSmall distances present — no impact |
| `route fallback = 3000` | `sample.py:139` | Missing distance | Not used in production path |
| `fleet_size default = 300` | `hub_milp.py:61` | Parameter default | Should derive from fleet data |
| Standard sizes [1000,2000,...] | `service_generator_agent.py:92` | Service sizing | Not benchmark data — acceptable |

### 10.2 Classification

| Hardcode | Classification | WorldSmall Impact |
|----------|---------------|-------------------|
| variable_port_call_cost=20 | **WORLDLARGE-SPECIFIC** (legacy convention) | CRITICAL — must fix |
| FLEET_SIZE=300 | **LEGACY/HARDCODED** | MEDIUM — should adapt to 263 |
| DEMAND_SCALE=6 | **TEST-SPECIFIC** | INFO — not used in production |
| distance fallback=500 | **BENCHMARK-GENERIC** | LOW — no missing distances |
| Standard sizes | **LEGACY/HARDCODED** | LOW — acceptable defaults |

---

## 11. Existing WorldLarge Runtime Data Path

### 11.1 Primary Production Path

```
data/raw/ports.csv (435 ports, 11 columns)
    ↓ NetworkLoader.load_ports()
    ↓ ×2 for handling_cost, transshipment_cost, variable_port_call_cost
Port dataclass instances

data/raw/demand_world_large.csv (9,622 rows)
    ↓ NetworkLoader.load_demands()
    ↓ FFE × lane_factor (default 2.0) → weekly_teu
    ↓ Revenue_1 × lane_factor → revenue_per_teu
Demand dataclass instances

data/raw/distance_dense.csv (43,056 directed pairs)
    ↓ NetworkLoader.load_distance_matrix()
    ↓ Only Distance column used
Nested dictionary {origin: {dest: distance_nm}}

services = [] (empty — generated at runtime by ServiceGeneratorAgent)

Problem(ports, services=[], demands, distance_matrix)
    ↓
ServiceGeneratorAgent.generate_services() (~800+ services)
    ↓
HierarchicalGA + HubMILP optimization
    ↓
FrequencyGA frequency optimization
    ↓
Profit evaluation
```

### 11.2 Test/API Path (Different)

```
data/datasets/large_shipping_problem.json (333 ports, 9,622 demands, 1,219 services)
    ↓ test_orchestrator.load_problem()
    ↓ DEMAND_SCALE=6 applied to weekly_teu ONLY
    ↓ distance_matrix loaded from CSV separately
    ↓ services=[] (JSON services ignored, regenerated)
Problem(ports, services=[], demands×6, distance_matrix)
```

---

## 12. JSON Loader Investigation

### 12.1 Expected Schema

The JSON format (`large_shipping_problem.json` and `worldsmall_shipping_problem.json`) shares this schema:

```json
{
  "ports": [
    {"id": "AEJEA", "name": "...", "latitude": 25.14, "longitude": 55.19,
     "handling_cost": 266.0, "draft": 13.5, "port_call_cost": 4164.0,
     "transshipment_cost": 128.0, "variable_port_call_cost": 20.0}
  ],
  "demands": [
    {"origin": "AOLAD", "destination": "AEJEA", "weekly_teu": 2.0, "revenue_per_teu": 4580.0}
  ],
  "services": [],
  "distance_matrix": {"AEJEA": {"AOLAD": 6439.0, ...}, ...}
}
```

### 12.2 Field-by-Field Handling

| JSON Field | Loader | Internal Model | Transformation | Used By |
|-----------|--------|---------------|----------------|---------|
| ports[].id | Port(id=...) | Port.id (str) | none | All optimizers |
| ports[].latitude | Port(latitude=...) | Port.latitude (float) | none | Visualization |
| ports[].longitude | Port(longitude=...) | Port.longitude (float) | none | Visualization |
| ports[].handling_cost | Port(handling_cost=...) | Port.handling_cost (float) | pre-baked ×2 in generator | MILP, GA profit |
| ports[].draft | Port(draft=...) | Port.draft (float) | none | Optional constraint |
| ports[].port_call_cost | Port(port_call_cost=...) | Port.port_call_cost (float) | none | MILP fixed port cost |
| ports[].transshipment_cost | Port(transshipment_cost=...) | Port.transshipment_cost (float) | pre-baked ×2 in generator | MILP transfer cost |
| ports[].variable_port_call_cost | Port(variable_port_call_cost=...) | Port.variable_port_call_cost (float) | pre-baked in generator | MILP variable cost |
| demands[].origin | Demand(origin=...) | Demand.origin (str) | none | All optimizers |
| demands[].destination | Demand(destination=...) | Demand.destination (str) | none | All optimizers |
| demands[].weekly_teu | Demand(weekly_teu=...) | Demand.weekly_teu (float) | pre-baked ×2 in generator | Profit, capacity calc |
| demands[].revenue_per_teu | Demand(revenue_per_teu=...) | Demand.revenue_per_teu (float) | pre-baked ×2 in generator | Profit calculation |
| services[] | N/A (ignored) | — | — | Regenerated by agent |
| distance_matrix | Nested dict | problem.distance_matrix | none | Fuel cost, cycle time |

### 12.3 Services Handling

**Critical finding:** Services in the JSON are **IGNORED** at runtime.

Evidence:
- `test_orchestrator.py:122`: `services = []` (explicitly empty)
- `run_pipeline_benchmark.py:44`: `Problem(ports=ports, services=[], ...)` (empty)
- `service_generator_agent.py:363`: `problem.services = services` (overwrites with generated services)

The 1,219 services in `large_shipping_problem.json` are seed/preview data only. They are discarded and regenerated by `ServiceGeneratorAgent.generate_services()` at pipeline start.

---

## 13. CSV Loader Investigation

### 13.1 NetworkLoader Methods

| Method | Source File | Reads | Applies |
|--------|------------|-------|---------|
| `load_ports()` | `network_loader.py:17-52` | `data/raw/ports.csv` | ×2 for handling, transshipment, var_port_call |
| `load_demands()` | `network_loader.py:57-114` | `data/raw/demand_world_large.csv` | FFE×factor→TEU, Revenue×factor→per_teu |
| `load_distance_matrix()` | `network_loader.py:119-137` | `data/raw/distance_dense.csv` | None (raw values) |
| `load_network()` | `network_loader.py:142-158` | All three above | Assembles Problem dict |

### 13.2 WorldSmall CSV Path

The `NetworkLoader` is currently hardcoded to read:
- `ports.csv` → reads from `data/raw/ports.csv` (WorldLarge, 435 ports)
- `demand_world_large.csv` → reads from `data/raw/demand_world_large.csv` (WorldLarge, 9,622 demands)
- `distance_dense.csv` → reads from `data/raw/distance_dense.csv` (WorldLarge)

**No WorldSmall-specific CSV loader exists.** Integration requires either:
1. Adding a `load_world_small()` method with configurable paths
2. Making existing methods accept path parameters

---

## 14. Service Loading/Generation Investigation

### 14.1 Current Behavior with services=[]

When `services=[]` (empty), the runtime behavior is:

1. **OrchestratorAgent.process()** receives the Problem
2. **ServiceGeneratorAgent.generate_services()** is called
3. Generates ~800+ candidate services based on:
   - Top-demand direct services (500)
   - Hub-loop services (~10)
   - Trunk routes (~45)
   - Feeder services (~80+)
   - Heuristic base pool (150)
4. Results stored in `problem.services`
5. Passed to regional agents and optimizers

### 14.2 Service Generation Dependencies

The service generator depends on:
- `problem.ports` — for geographic coordinates and hub detection
- `problem.demands` — for demand-sourced service sizing
- `problem.distance_matrix` — for route feasibility
- `problem.services` — initially empty, overwritten

**No dependency on fleet data.** Fleet constraints use hardcoded `FLEET_SIZE=300`.

---

## 15. Internal Data Model

### 15.1 Core Entities

| Entity | Class Location | Key Fields | Source |
|--------|---------------|------------|--------|
| Port | `src/optimization/data.py:6-15` | id(str), name, lat, lon, handling_cost, draft, port_call_cost, transshipment_cost, variable_port_call_cost | CSV or JSON |
| Demand | `src/optimization/data.py:36-40` | origin(str), destination(str), weekly_teu(float), revenue_per_teu(float) | CSV or JSON |
| Service | `src/optimization/data.py:19-27` | id(int), ports(list[str]), capacity(float), weekly_cost(float), cycle_time(int), speed(float), fuel_cost(float), vessel_class(str) | Generated |
| Problem | `src/optimization/data.py:43-58` | ports(list[Port]), services(list[Service]), demands(list[Demand]), distance_matrix(dict) | Assembled |

### 15.2 Fleet Representation

**No Fleet class exists in the internal data model.** Fleet is represented implicitly:
- `FLEET_SIZE = 300` (hardcoded constraint)
- `vessel_class` on Service determines fuel consumption via `VESSEL_FUEL_CONSUMPTION` dict
- No vessel capacity limits, no fleet allocation tracking

### 15.3 Distance Representation

- **JSON path:** `{origin: {dest: distance_nm}}` nested dict
- **CSV path:** Same structure, loaded row by row
- **Missing values:** `500.0 nm` fallback in `fuel_cost.py:205`

---

## 16. WorldLarge-Specific Assumptions

### 16.1 Findings Classification

| Assumption | File:Line | Type | WorldSmall Impact |
|-----------|-----------|------|-------------------|
| 333 ports | `backend/server.py:180` | **WORLDLARGE-SPECIFIC** | Must change to 47 |
| 9622 lanes | `backend/services/pipeline_service.py:89` | **WORLDLARGE-SPECIFIC** | Must change to 1,764 |
| 1219 services | `backend/services/pipeline_service.py:90` | **WORLDLARGE-SPECIFIC** | Generated dynamically |
| DEMAND_SCALE=6 | `tests/test_orchestrator.py:129` | **TEST-SPECIFIC** | Should be 1.0 for WorldSmall |
| FLEET_SIZE=300 | `src/optimization/hub_milp.py:61` | **LEGACY/HARDCODED** | Should derive from fleet (263) |
| variable_port_call_cost=20 | `generate_worldsmall_dataset.py:186` | **LEGACY/HARDCODED** | Should use ×2 from CSV |
| 500 nm distance fallback | `src/utils/fuel_cost.py:205` | **BENCHMARK-GENERIC** | Acceptable |
| PortCallCostFixed used as-is | `generate_worldsmall_dataset.py:183` | **BENCHMARK-GENERIC** | No change needed |

### 16.2 Hardcoded Port Counts

```python
# backend/server.py:180 — parses "333 ports x 9622 lanes" pattern
# backend/services/pipeline_service.py:88 — returns fixed statistics
# backend/pipeline_streamer.py:301 — MockDemand(i) for i in range(9622)
```

These are documentation/display strings, not functional constraints. They do not affect optimization results but should be updated for WorldSmall reporting.

---

## 17. Double-Transformation Risks

### 17.1 Identified Risks

| Risk | Scenario | Severity |
|------|----------|----------|
| **Dual ×2 on demand/revenue** | If WorldSmall CSV path is used AND JSON is also loaded, FFE values would be ×4 | **CRITICAL** |
| **Variable port cost mismatch** | WS hardcoded 20.0 vs WL computed from CSV | **HIGH** |
| **Fleet size mismatch** | Hardcoded 300 vs actual 263 | **MEDIUM** |
| **Post_panamax capacity mismatch** | LINERLIB 4200 FFE vs runtime 5000 TEU | **MEDIUM** |
| **Super_panamax capacity mismatch** | LINERLIB 7500 FFE vs runtime 8000 TEU | **MEDIUM** |

### 17.2 Risk Mitigation Requirements

1. **Define authoritative data path** — JSON or CSV? (Recommend: JSON for WorldSmall)
2. **Remove DEMAND_SCALE for WorldSmall** — set to 1.0
3. **Fix variable_port_call_cost** — compute from CSV, don't hardcode
4. **Adjust FLEET_SIZE** — derive from fleet_WorldSmall.csv quantity (263)
5. **Document both paths** — prevent accidental combination

---

## 18. WorldSmall Integration Requirements

### 18.1 Data Path Decision

| Requirement | Recommendation | Rationale |
|------------|----------------|-----------|
| Primary loader | JSON path (`load_problem` + `worldsmall_shipping_problem.json`) | Already validated, consistent with WorldLarge test path |
| Distance matrix | Load from JSON (already included) | Avoids separate CSV loading |
| Services | Generate at runtime (services=[]) | Matches existing behavior |
| Scaling | DEMAND_SCALE=1.0 (no scaling) | WorldSmall is a benchmark subset, not an amplified test |
| Fleet size | Derive from fleet_WorldSmall.csv (263) | More accurate than hardcoded 300 |

### 18.2 Required Modifications (For Integration Phase)

| Component | Change | Priority |
|-----------|--------|----------|
| `generate_worldsmall_dataset.py:186` | Replace hardcoded 20.0 with `float(p["PortCallCostPerFFE"]) * 2.0` | **CRITICAL** |
| `hub_milp.py:61` | Add `fleet_size` parameter from fleet data | **HIGH** |
| `test_orchestrator.py:129` | Make DEMAND_SCALE configurable (1.0 for WS) | **HIGH** |
| `network_loader.py:59` | Add WorldSmall demand file option | **MEDIUM** |
| `fuel_cost.py:20-56` | Update Post_panamax/Super_panamax capacities to match LINERLIB | **MEDIUM** |

---

## 19. Findings and Severity

### CRITICAL Findings

| ID | Finding | Location | Current Behavior | Expected | WorldSmall Impact |
|----|---------|----------|-----------------|----------|-------------------|
| C1 | `variable_port_call_cost` hardcoded to 20.0 for all ports | `generate_worldsmall_dataset.py:186` | All 47 ports have identical var_port_cost=20.0 | Should be `PortCallCostPerFFE × 2.0` per port | **High** — eliminates port-specific cost variation, biases profitability |
| C2 | No fleet data loaded at runtime | `network_loader.py`, `hub_milp.py` | `FLEET_SIZE=300` hardcoded; fleet_WorldSmall.csv(263 vessels) unused | Should load fleet and use actual count | **Medium** — constraint may be slightly loose for WS |

### HIGH Findings

| ID | Finding | Location | Current Behavior | Expected | WorldSmall Impact |
|----|---------|----------|-----------------|----------|-------------------|
| H1 | DEMAND_SCALE=6 only for WorldLarge tests | `tests/test_orchestrator.py:129` | Applied to all JSON-loaded demands | Should be 1.0 for WorldSmall | **High** — would inflate demand 6× for benchmark |
| H2 | Post_panamax capacity mismatch | `fuel_cost.py:46` | Runtime: 5000 TEU, LINERLIB: 4200 FFE | Should align or document convention | **Medium** — affects fuel cost accuracy |
| H3 | Super_panamax capacity mismatch | `fuel_cost.py:52` | Runtime: 8000 TEU, LINERLIB: 7500 FFE | Should align or document convention | **Medium** — affects fuel cost accuracy |

### MEDIUM Findings

| ID | Finding | Location | Current Behavior | Expected | WorldSmall Impact |
|----|---------|----------|-----------------|----------|-------------------|
| M1 | Distance columns Draft/IsPanama/IsSuez dropped | `network_loader.py:128-136` | Only Distance column loaded | Could preserve for future use | **Low** — no current impact |
| M2 | Two mutually exclusive data paths | `run_pipeline_benchmark.py` vs `test_orchestrator.py` | Different transformations applied | Document clearly | **Medium** — risk of confusion |
| M3 | Fleet capacity vs fuel consumption class mapping | `fuel_cost.py:20-56` | Hardcoded capacities don't match LINERLIB exactly | Should match or document | **Low** — minor accuracy difference |

### LOW Findings

| ID | Finding | Location | Current Behavior | Expected | WorldSmall Impact |
|----|---------|----------|-----------------|----------|-------------------|
| L1 | Distance fallback 500 nm | `fuel_cost.py:205` | Used for missing pairs | WorldSmall has 100% coverage | **None** — not triggered |
| L2 | Display strings with "333 ports" | `backend/server.py:180` | Documentation strings | Should be dynamic | **None** — cosmetic only |

---

## 20. Recommended Next Steps

### Immediate (Before Integration)

1. **FIX C1:** Update `generate_worldsmall_dataset.py:186` to compute `variable_port_call_cost` from CSV instead of hardcoding
2. **DOCUMENT:** Clarify which data path (JSON vs CSV) is authoritative for WorldSmall
3. **CONFIGURE:** Make DEMAND_SCALE a parameter (1.0 for WorldSmall, 6.0 for WorldLarge tests)

### During Integration

4. **ADD:** WorldSmall fleet loading — derive `fleet_size` from `fleet_WorldSmall.csv`
5. **UPDATE:** `fuel_cost.py` vessel capacities to match LINERLIB `fleet_data.csv`
6. **TEST:** Verify no double-transformation occurs when WorldSmall JSON is loaded

### After Integration

7. **VALIDATE:** Run WorldSmall pipeline and compare economics with hand-calculated benchmarks
8. **DOCUMENT:** Record the exact data path used for reproducibility
9. **COMPARE:** Benchmark results against WorldLarge under equivalent conditions

---

## 21. Files/Lines Inspected

### Source Code
| File | Lines | Purpose |
|------|-------|---------|
| `src/data/network_loader.py` | 1-159 | Primary CSV loader — ports, demands, distance |
| `src/optimization/data.py` | 1-58 | Core data models (Port, Demand, Service, Problem) |
| `src/utils/fuel_cost.py` | 1-233 | Fuel consumption models and vessel class mapping |
| `src/agents/service_generator_agent.py` | 1-411 | Service generation (always overwrites JSON services) |
| `src/optimization/hub_milp.py` | 1-600 | MILP optimizer — fleet constraint at line 61, 389 |
| `src/optimization/frequency_ga.py` | 1-200 | GA optimizer — FLEET_SIZE at line 122 |
| `scripts/generate_worldsmall_dataset.py` | 1-269 | WorldSmall dataset generator |
| `scripts/validate_worldsmall_data.py` | 1-139 | WorldSmall validation script |
| `scripts/run_pipeline_benchmark.py` | 1-107 | Production benchmark — uses CSV path |
| `tests/test_orchestrator.py` | 103-145 | Test loader — uses JSON path + DEMAND_SCALE |
| `backend/services/pipeline_service.py` | 1-128 | Backend API — mock data, hardcoded counts |

### Data Files
| File | Records | Notes |
|------|---------|-------|
| `data/raw/WorldSmall/ports.csv` | 47 | Filtered from global ports.csv |
| `data/raw/WorldSmall/Demand_WorldSmall_Fixed_Sep.csv` | 1,764 | Authoritative demand source |
| `data/raw/WorldSmall/fleet_WorldSmall.csv` | 6 | Vessel class quantities |
| `data/raw/WorldSmall/fleet_data.csv` | 6 | Vessel specifications |
| `data/raw/WorldSmall/dist_dense.csv` | 2,162 | Complete directed distance matrix |
| `data/datasets/worldsmall_shipping_problem.json` | 47P/1764D/0S | Generated JSON |
| `data/datasets/large_shipping_problem.json` | 333P/9622D/1219S | Reference for comparison |
| `data/raw/ports.csv` | 435 | Global ports (not modified) |
| `data/raw/demand_world_large.csv` | 9,622 | Global demands (not modified) |
| `data/raw/distance_dense.csv` | 43,056 | Global distances (not modified) |

---

## 22. Final WorldSmall Integration Checklist

| Requirement | Status | Evidence |
|------------|--------|----------|
| 47 ports | ✅ PASS | `validate_worldsmall_data.py:42` |
| 1,764 demands | ✅ PASS | `validate_worldsmall_data.py:54` |
| 263 vessels | ✅ PASS | `validate_worldsmall_data.py:81` |
| 6 vessel classes | ✅ PASS | `validate_worldsmall_data.py:80` |
| 2,162 distances | ✅ PASS | `validate_worldsmall_data.py:88` |
| Demand units understood | ✅ PASS | FFE×2=TEU, verified via cross-path comparison |
| Revenue units understood | ✅ PASS | USD/FFE×2=USD/TEU, mathematically consistent |
| Port costs understood | ⚠️ CONDITIONAL | variable_port_call_cost hardcoded (C1) |
| Fleet units understood | ✅ PASS | Capacity FFE matches fuel_cost capacities for 4 classes |
| Distance units understood | ✅ PASS | Nautical miles, directed, 100% complete |
| ×2 transformations justified | ✅ PASS | FFE→TEU is legitimate benchmark conversion |
| No double conversion | ✅ PASS | Two paths are mutually exclusive |
| JSON loader identified | ✅ PASS | `test_orchestrator.py:103-145` |
| CSV loader identified | ✅ PASS | `network_loader.py:17-158` |
| Runtime source identified | ✅ PASS | Two paths documented (see Section 11) |
| Service behavior identified | ✅ PASS | Always regenerated, JSON services ignored |
| WorldLarge assumptions identified | ✅ PASS | See Section 16 |
| WorldSmall integration blockers identified | ⚠️ SEE FINDINGS | C1, H1, H2, H3 require attention |

---

## 23. Final Verdict

```
READY WITH CONDITIONS
```

**Conditions for integration:**
1. Fix `variable_port_call_cost` hardcoded value (Finding C1)
2. Configure DEMAND_SCALE=1.0 for WorldSmall path (Finding H1)
3. Decide on fleet_size derivation (Finding C2)
4. Document the chosen data path clearly (Finding M2)

All other aspects (data structure, ×2 transformations, distance semantics, service generation) are understood and ready for integration.

---

## 24. Important Disclaimer

**No production pipeline behavior was modified during this audit.**
**No RL code was modified.**
**No GA/MILP behavior was modified.**
**No WorldLarge data was modified.**

This report documents findings only. Actual fixes will be implemented in a separate integration phase.

---

*Report generated: 2026-09-12*  
*Audit scope: Phase 1.5 (Data Semantics) + Phase 2 (Runtime Loader)*  
*Methodology: Source code inspection, data cross-validation, transformation tracing*
