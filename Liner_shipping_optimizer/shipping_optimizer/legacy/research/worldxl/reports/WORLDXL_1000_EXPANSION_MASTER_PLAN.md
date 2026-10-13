# WORLDXL-1000 EXPANSION MASTER PLAN

> **Program:** WorldXL-1000 — Next-Generation Liner Shipping Research Dataset
> **Parent:** WorldLarge-435 (certified benchmark — frozen, never modified)
> **Objective:** 1000+ ports with enhanced realism across network, coverage, demand, and routes
> **Status:** Pre-Implementation — Planning Phase Complete
> **Date:** 2026-06-08

---

## TABLE OF CONTENTS

1. [Executive Summary](#1-executive-summary)
2. [PHASE 0 — Data Source Strategy](#2-phase-0--data-source-strategy)
3. [PHASE 1 — WorldXL Data Model](#3-phase-1--worldxl-data-model)
4. [PHASE 2 — Port Expansion & Region Analysis](#4-phase-2--port-expansion--region-analysis)
5. [PHASE 3 — Regional Agent Scalability Review](#5-phase-3--regional-agent-scalability-review)
6. [PHASE 4 — Data Generation Strategy](#6-phase-4--data-generation-strategy)
7. [PHASE 5 — Scalability Forecast](#7-phase-5--scalability-forecast)
8. [PHASE 6 — Benchmarking Plan](#8-phase-6--benchmarking-plan)
9. [PHASE 7 — Implementation Readiness](#9-phase-7--implementation-readiness)
10. [Final Questions Answered](#10-final-questions-answered)
11. [Recommended Implementation Roadmap](#11-recommended-implementation-roadmap)

---

## 1. EXECUTIVE SUMMARY

| Dimension | WorldLarge-435 | WorldXL-1000 | Multiplier |
|-----------|---------------|--------------|------------|
| Ports | 435 | 1000+ | 2.3× |
| Countries | 117 | 180+ | 1.5× |
| Demand lanes (OD pairs) | 9,622 | 30,000–50,000 | 3–5× |
| Distance records | 62,003 | 200,000+ | 3.2× |
| Fleet capacity | 501 vessels, 6 classes | 800+ vessels, 8+ classes | 1.6× |
| Regions (agents) | 5 | 8–12 | 1.6–2.4× |
| Candidate services | ~1,500 | ~3,000–6,000 | 2–4× |
| Fleet limit | 300 vessels | 500+ vessels (est.) | 1.7× |
| Network density | ~5.1% | ~3–5% | ~similar |
| Weekly demand | ~1.9M TEU | ~4–5M TEU | 2–2.6× |

**Verdict: WorldXL-1000 IS TECHNICALLY FEASIBLE** but requires targeted architecture upgrades before implementation. The system can scale to 1000+ ports with modifications to 6 key components. No fundamental redesign is needed — the hierarchical decomposition (regional agent → GA → MILP) is the correct architecture for this scale.

---

## 2. PHASE 0 — DATA SOURCE STRATEGY

### 2.1 Source Ranking Framework

| Rank | Source | Authority | Coverage | Freshness | Licensing | Overall |
|------|--------|-----------|----------|-----------|-----------|---------|
| S-tier | UN/LOCODE | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Free/Open | **A** |
| S-tier | World Port Index (WPI) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | Public Domain | **A** |
| A-tier | Clarksons Research | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Paid | **B+** |
| A-tier | IHS Markit/Maritime | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Paid | **B+** |
| A-tier | UNCTAD Maritime | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | Free | **B** |
| B-tier | MDS Transmodal | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | Paid | **B** |
| B-tier | Container Trade Statistics | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | Paid | **B** |
| B-tier | Drewry Shipping | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | Paid | **B-** |
| C-tier | Port Authority Reports | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | Free | **C+** |
| C-tier | MarineTraffic/AIS | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Paid | **B-** |
| D-tier | Wikipedia | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | Free | **C** |
| D-tier | General Web Scraping | ⭐ | ⭐⭐ | ⭐⭐ | Variable | **D** |

### 2.2 Authoritative Sources by Data Type

#### Ports (UNLOCODE + World Port Index)

| Source | URL/Reference | Fields | License | Priority |
|--------|--------------|--------|---------|----------|
| UN/LOCODE 2024-2 | `https://unece.org/trade/cefact/unlocode` | UNLocode, name, lat/lon, country | Public | **PRIMARY** |
| World Port Index (WPI) | NGA Pub 150 | Coordinates, draft, port size, cargo type | Public Domain | **PRIMARY** |
| Port Authority Annual Reports | Individual (Shanghai, Rotterdam, Singapore, etc.) | Throughput, berth depth, TEU capacity | Free | **SECONDARY** |
| Ports.com / FleetMon | `https://ports.com` | Port details, terminal info | Free (rate-limited) | **TERTIARY** |
| Lloyd's List Intelligence | `https://lloydslist.maritimeintelligence.informa.com` | Port calls, vessel movements | Paid | **VALIDATION** |

**Recommendation:** Use UN/LOCODE as the authoritative port identity backbone. Supplement with WPI for coordinates and draft. Use port authority annual reports for throughput and operational data.

#### Shipping Routes (Public Liner Services + Corridor Datasets)

| Source | Description | Fields | License | Priority |
|--------|-------------|--------|---------|----------|
| Alphaliner | Weekly liner network reports | Service strings, vessel deployments | Paid | **PRIMARY** |
| MDS Transmodal CTI | Container Trade Index | Lane volumes, TEU flow | Paid | **PRIMARY** |
| BlueWater Reporting | Carrier schedule database | Service schedules, port rotations | Paid | **SECONDARY** |
| Carrier websites (MAERSK, MSC, CMA CGM) | Published networks | Service maps, transit times | Free | **TERTIARY** |
| UNCTAD Liner Shipping Connectivity Index | `https://unctad.org/topic/transport-and-trade-logistics/liner-shipping` | Country-level connectivity | Free | **BENCHMARK** |

**Recommendation:** Use Alphaliner carrier network publications for route structure reference. Do not attempt to replicate exact carrier services — use patterns to validate generated service structures.

#### Vessel Data (Classes, Capacities, Fuel Consumption)

| Source | Description | Fields | License | Priority |
|--------|-------------|--------|---------|----------|
| Clarksons SIN | World Fleet Register | Vessel class, TEU, DWT, fuel type, year | Paid | **PRIMARY** |
| IHS Markit/Sea-Web | Global vessel database | Full technical specs | Paid | **PRIMARY** |
| IMO GISIS | `https://gisis.imo.org` | Ship particulars, company | Free | **TERTIARY** |
| DNV GL Alternative Fuels | `https://afi.dnvgl.com` | Fuel type, alternative propulsion | Free | **REFERENCE** |
| Bunker Index | `https://bunkerindex.com` | Bunker fuel prices by port | Free | **PRIMARY (costs)** |

**Vessel Class Definitions (Current + Proposed):**

Current (6 classes): Feeder_450, Feeder_800, Panamax_1200, Panamax_2400, Post_panamax, Super_panamax

Proposed additions for WorldXL:
- **Neo_panamax** (8,000 TEU) — already defined in fuel_cost.py but unused in fleet
- **Ultra_large** (18,000–24,000 TEU) — for major Asia-Europe trunk routes
- **Mega_max** (24,000+ TEU) — for highest-density corridors
- **Small_feeder** (100–300 TEU) — for island/small port services

**Fuel consumption source (already validated):** Clarksons Research 2024 data, used in `src/utils/fuel_cost.py` lines 21–63. Bunker price source: Bunker Index 2024 Average ($600/ton IFO 380).

#### Trade Demand (Regional + Corridor)

| Source | Description | Fields | License | Priority |
|--------|-------------|--------|---------|----------|
| Container Trade Statistics (CTS) | `https://containertradestatistics.com` | OD trade volumes, commodity | Paid | **PRIMARY** |
| UN Comtrade | `https://comtrade.un.org` | Country-level trade (SITC/HS) | Free | **SECONDARY** |
| IMF Direction of Trade | `https://data.imf.org` | Bilateral trade flows | Free | **SECONDARY** |
| World Bank Container Port Traffic | `https://data.worldbank.org` | Port TEU volumes | Free | **VALIDATION** |
| WTO Trade Statistics | `https://www.wto.org/statistics` | Regional trade flows | Free | **VALIDATION** |

**Recommendation:** Use CTS for lane-level demand (most accurate for container trade). Validate against World Bank port throughput statistics. Use UN Comtrade for commodity-class breakdowns. Use IMF DOT for bilateral trade flow structure.

### 2.3 Licensing Compliance Requirements

| Data Type | Source | License Terms | Usage Restriction |
|-----------|--------|---------------|-------------------|
| Port identifiers | UN/LOCODE | Public | None |
| Port coordinates | WPI | Public Domain | None |
| Vessel consumption | Clarksons | Paid | Attribution required |
| Trade flows | CTS | Paid | No redistribution |
| Bunker prices | Bunker Index | Free | Attribution |
| Port throughput | Port authority reports | Public | Attribution |
| Distance data | Derived (Great Circle) | Generated | None |
| Service structures | Alphaliner | Paid | Structural reference only |

> **⚠ CRITICAL:** Do NOT redistribute paid data sources (Clarksons, CTS, Alphaliner) as raw files. Use them as validation/synthesis references only. All synthetic data must be clearly labeled as such.

---

## 3. PHASE 1 — WORLDXL DATA MODEL

### 3.1 Current Data Model (WorldLarge-435)

Defined in `src/optimization/data.py`:

```python
@dataclass
class Port:
    id: str
    name: str
    latitude: float
    longitude: float
    handling_cost: float = 0
    draft: float = 0
    port_call_cost: float = 0
    transshipment_cost: float = 0
    variable_port_call_cost: float = 0

@dataclass
class Service:
    id: str
    ports: List[str]
    capacity: float
    weekly_cost: float
    cycle_time: int = 7
    speed: float = 18
    fuel_cost: float = 0
    vessel_class: str = ""

@dataclass
class Demand:
    origin: str
    destination: str
    weekly_teu: float
    revenue_per_teu: float
```

**CSV Port Fields** (`data/raw/ports.csv` tab-separated):
`UNLocode, name, Country, Cabotage_Region, D_Region, Longitude, Latitude, Draft, CostPerFULL, CostPerFULLTrnsf, PortCallCostFixed, PortCallCostPerFFE`

**CSV Demand Fields** (`data/raw/demand_world_large.csv` tab-separated):
`Origin, Destination, FFEPerWeek, Revenue_1, TransitTime`

### 3.2 WorldXL Proposed Data Model

```
┌─────────────────────────────────────────────────────┐
│                  WorldXL DATA MODEL                  │
├───────────────┬─────────────────────────────────────┤
│   ENTITY      │           NEW FIELDS                 │
├───────────────┼─────────────────────────────────────┤
│ Port          │ + throughput_mteu (annual MT)        │
│               │ + congestion_index (0-1)             │
│               │ + turnaround_hours (avg)             │
│               │ + hub_classification (0-4 scale)     │
│               │ + is_transshipment_hub (bool)        │
│               │ + terminal_operators (List[str])     │
│               │ + max_beam (m)                       │
│               │ + max_loa (m)                        │
│               │ + reefer_plugs (int)                 │
│               │ + rail_connectivity (bool)           │
│               │ + port_region (expanded taxonomy)    │
├───────────────┼─────────────────────────────────────┤
│ Route         │ + service_frequency (per week)       │
│               │ + transit_time_days                  │
│               │ + alliance_code (str)                │
│               │ + canal_dependency (bool)            │
│               │ + canal_toll_cost ($)                │
│               │ + competitiveness_index (0-1)        │
│               │ + seasonal_reliability (%)           │
│               │ + is_pendulum_route (bool)           │
├───────────────┼─────────────────────────────────────┤
│ Vessel/Fleet  │ + fuel_type (HFO/LNG/Methanol/Ammonia)│
│               │ + speed_profile_knots (list: design) │
│               │ + emissions_ghg (gCO2/TEU-km)        │
│               │ + emissions_nox (g/TEU-km)           │
│               │ + emissions_sox (g/TEU-km)           │
│               │ + operating_range_nm                  │
│               │ + ice_class (bool)                    │
│               │ + year_built                          │
│               │ + charter_rate ($/day)                │
│               │ + EEXI_value                          │
│               │ + CII_rating (A-E)                    │
├───────────────┼─────────────────────────────────────┤
│ Demand        │ + commodity_class (HS2-4 code)        │
│               │ + seasonality_factor (12-month array) │
│               │ + trade_imbalance (export/import ratio)│
│               │ + growth_rate_forecast (%)            │
│               │ + empty_repositioning_share (%)       │
│               │ + rate_volatility (std dev)           │
│               │ + contract_type (spot/long-term)      │
│               │ + service_requirements (reefer/dg/etc)│
└───────────────┴─────────────────────────────────────┘
```

### 3.3 Data Model Justification

| Field Group | Rationale | Impact on Optimization |
|-------------|-----------|----------------------|
| Port throughput & congestion | Constrains realistic port capacity, prevents overloading single hub | MILP port capacity constraints become meaningful |
| Hub classification | Enables tiered hub strategy (megahub → regional → feeder) | Better service generation hierarchy |
| Turnaround time | Drives realistic cycle time calculations | Frequency GA gets accurate fleet requirements |
| Canal dependency | Models Suez/Panama canal tolls in route economics | MILP routing decisions reflect real-world cost |
| Emission profiles | Enables carbon-aware optimization | Future-proofing for IMO regulations |
| Commodity class | Reveals specialized demand patterns (reefer, DG, breakbulk) | Service design accounts for cargo requirements |
| Seasonality | Enables peak/off-peak capacity planning | Demand forecasting and fleet sizing |
| Trade imbalance | Empty container repositioning cost | More realistic cost models |

### 3.4 Schema Design Principles

1. **Backward compatibility:** Every new field must have a default value of `0`, `None`, or `[]` so WorldLarge-435 loads without modification.
2. **Progressive enhancement:** WorldXL can be constructed in layers — start with core geography and demand, add complexity incrementally.
3. **All fields traceable:** Each field must be labeled as `REAL`, `DERIVED`, `ESTIMATED`, or `SYNTHETIC` (see Phase 4).

---

## 4. PHASE 2 — PORT EXPANSION & REGION ANALYSIS

### 4.1 Current Port Distribution

From `data/raw/ports.csv` — 435 ports across 23 D_Regions:

| D_Region | Port Count | Current Agent Region |
|----------|-----------|---------------------|
| West Med | 81 | Europe |
| North Continent Europe | 38 | Europe |
| West Africa | 37 | Africa |
| Brazil | 33 | Americas |
| Australia | 31 | Americas (currently!) |
| Singapore | 27 | Asia |
| US West Coast | 21 | Americas |
| US Gulf Coast | 21 | Americas |
| *(no D_Region)* | 18 | (unassigned) |
| South America West Coast | 17 | Americas |
| Japan | 16 | Asia |
| Mumbai | 15 | Middle East |
| US East Coast | 14 | Americas |
| South Africa | 14 | Africa |
| UK | 12 | Europe |
| Saudi Arabia | 9 | Middle East |
| Dubai | 8 | Middle East |
| South China | 6 | Asia |
| Canada East Coast | 5 | Americas |
| North China | 4 | Asia |
| Korea | 3 | Asia |
| Central China | 3 | Asia |
| Hong Kong | 1 | Asia |
| Canada West | 1 | Americas |

**⚠ Current region misassignment:** Australia (31 ports) is assigned to the "Americas" regional agent. This is a known modeling issue — Australia is geographically closer to Asia and should logically be in its own "Oceania" region.

### 4.2 Proposed Region Taxonomy for WorldXL

The current 5-agent structure (`Asia`, `Europe`, `Americas`, `Middle East`, `Africa`) is insufficient for 1000+ ports. Recommended split:

```
LEVEL 0 (Macro-region):        LEVEL 1 (Agent Region):      LEVEL 2 (D_Region mapping):
─────────────────────          ─────────────────────        ─────────────────────────────
Asia-Pacific              →    East Asia                    North China, Central China,
                                                              South China, Japan, Korea,
                                                              Hong Kong, Taiwan
                              Southeast Asia                 Singapore, Vietnam, Thailand,
                                                              Philippines, Indonesia,
                                                              Malaysia, Cambodia
                              South Asia                    Mumbai, Pakistan, Sri Lanka,
                                                              Bangladesh
                              Oceania                       Australia, New Zealand,
                                                              Pacific Islands

Europe & Mediterranean    →    North Europe                  North Continent Europe, UK,
                                                              Ireland, Scandinavia,
                                                              Baltic
                              Mediterranean                  West Med, East Med, Black Sea,
                                                              Adriatic
                              Middle East                    Saudi Arabia, Dubai, Red Sea,
                                                              Gulf

Americas                 →    North America                  US East Coast, US West Coast,
                                                              US Gulf Coast, Canada,
                                                              Mexico
                              Central America & Caribbean    Central America, Caribbean
                                                              Islands
                              South America                  Brazil, West Coast South
                                                              America, East Coast
                                                              South America

Africa                   →    West Africa                    West Africa
                              Southern & East Africa         South Africa, East Africa,
                                                              Indian Ocean Islands
                              North Africa                   (merge with Mediterranean or
                                                              stand alone)
```

This yields **8–12 regional agents**, each managing 80–150 ports instead of the current 5 agents managing 60–190 ports each.

### 4.3 Region Count Formula

For WorldXL-1000, using the PortClustering `sqrt(n)` heuristic:
```
k = sqrt(1000) ≈ 32 clusters → then group into 8–12 agent regions
```

The KMeans step (currently `n_clusters=5`) should be adapted:
- For <50 ports: 3 clusters (unchanged)
- For 50–435 ports: 5 clusters (unchanged)
- For 435–1000+ ports: `min(sqrt(n), 12)` clusters

### 4.4 WorldXL Region Expansion Plan (Summary)

```
WORLDXL_REGION_EXPANSION_PLAN
=============================

New regions to create:
  ✓ East Asia (split from Asia)
  ✓ Southeast Asia (split from Asia)
  ✓ South Asia (new)
  ✓ Oceania (split from Americas — correction)
  ✓ North America (split from Americas)
  ✓ South America (split from Americas)
  ✓ Mediterranean (split from Europe)
  ✓ Black Sea / Russia (new)
  ✓ Central America & Caribbean (new)

Regions to keep:
  ✓ West / North Europe (renamed from Europe)
  ✓ Middle East / Gulf (current)
  ✓ West Africa (current)
  ✓ Southern & East Africa (split from Africa)

Total: 12–14 agent regions
```

---

## 5. PHASE 3 — REGIONAL AGENT SCALABILITY REVIEW

### 5.1 Architecture Review Summary

```
┌──────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (current)                         │
│  PortClustering → RegionalSplitter → [RegionalAgent × N]         │
│                                          │                       │
│                                          ▼                       │
│                              ┌─────────────────────┐             │
│                              │   RegionalAgent      │             │
│                              │  ┌─────────────────┐ │             │
│                              │  │ HubDetector      │ │             │
│                              │  │   O(D × H)       │ │             │
│                              │  ├─────────────────┤ │             │
│                              │  │ ServiceGenerator  │ │             │
│                              │  │   500 direct       │ │             │
│                              │  │   10 hubs × loops   │ │             │
│                              │  │   H2H trunks       │ │             │
│                              │  │   Spoke feeders    │ │             │
│                              │  │   150 heuristic     │ │             │
│                              │  ├─────────────────┤ │             │
│                              │  │ Service filter    │ │             │
│                              │  │   max(400, ports)  │ │             │
│                              │  ├─────────────────┤ │             │
│                              │  │ HierarchicalGA    │ │             │
│                              │  │  ServiceGA(80,120)│ │             │
│                              │  │  FrequencyGA(40,60)│ │             │
│                              │  │  max 55s runtime   │ │             │
│                              │  ├─────────────────┤ │             │
│                              │  │ HubMILP           │ │             │
│                              │  │  max_transfer=2000 │ │             │
│                              │  │  fleet=300         │ │             │
│                              │  │  time_limit=120s   │ │             │
│                              │  └─────────────────┘ │             │
│                              └─────────────────────┘             │
│  CoordinatorAgent                                               │
│  ┌──────────────────────────────────────────────────┐           │
│  │  Coverage evaluation → weight adjustment → rerun  │           │
│  │  MAX_ITERATIONS = 3                               │           │
│  └──────────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Component-by-Component Scalability Analysis

| Component | WorldLarge-435 | WorldXL-1000 Estimate | Bottleneck? | Mitigation |
|-----------|---------------|----------------------|-------------|------------|
| **PortClustering** | 435 ports → 5 clusters (KMeans) | 1000 ports → 10–12 clusters (KMeans) | ⚠ Moderate | KMeans scales O(n·k·i) — 1000 points is trivial. Increase n_init. |
| **RegionalSplitter** | 5 partitions, 435 ports each | 12 partitions, ~85 ports each | ✅ None | Per-region port count decreases! |
| **HubDetector** | O(D·H) with H=20 | O(D·H) — more lanes, more hubs | ⚠ Minor | H should scale to H=40 for 1000 ports. Demand cache is per Problem. |
| **ServiceGenerator** | 500 direct + loops + feeders | 2000+ direct + scaled loops + feeders | 🚨 MAJOR | Direct services hard-capped at 500. Must be proportional to min(lanes, sqrt(ports×lanes)). |
| **Service Filter** | max(400, ports) = 435 | max(400, 1000) = 1000 | ⚠ Moderate | Cap scales with ports — adequate. |
| **ServiceGA** | pop=80, gen=120, O(80×120×services) | Same params, 2–3× services | ⚠ Moderate | Dominated by fitness evaluation O(S×D) — scales linearly with lanes. |
| **FrequencyGA** | pop=40, gen=60 | Same params | ✅ Minimal | Fitness is O(active_services) which is GA-selected subset. |
| **HubMILP flow vars** | O(D·max_svc_per_demand) | O(3D·10) | 🚨 MAJOR | Demand count 3–5× larger. MILP variable count could exceed PuLP practical limit (~500K). |
| **HubMILP xfer pairs** | max_transfer_pairs=2000 | would still be 2000 | 🚨 MAJOR | Hard cap means fewer pairs per lane. Must increase to 5000+. |
| **HubMILP fleet** | 300 vessels | Would need 500+ | 🚨 MAJOR | Hard-coded `fleet_size=300`. Must be proportional to port count. |
| **Coordinator** | 3 iterations | 3–4 iterations | ✅ Minimal | Convergence logic is scale-independent. |

### 5.3 Specific Code-Level Bottlenecks

#### BOTTLENECK A: ServiceGenerator — Hard-coded 500 direct corridors
**File:** `src/agents/service_generator_agent.py`, line 48
```python
top_n_direct = min(500, len(top_demands))
```
For WorldXL with ~30,000 lanes, 500 direct corridors covers only ~1.7% of lanes. Should be:
```python
top_n_direct = min(max(500, int(math.sqrt(len(top_demands)) * 100)), len(top_demands))
```
Or proportional to total demand volume, e.g., enough to cover 80% of total TEU.

#### BOTTLENECK B: ServiceGenerator — Top-10 hubs hard-coded
**File:** `src/agents/service_generator_agent.py`, lines 39–41
```python
hubs = hub_detector.detect_hubs(top_k=20)
top10_hubs = hubs[:10]
```
For 1000+ ports, hub count should scale: `top_k = min(40, max(20, int(num_ports * 0.04)))`.

#### BOTTLENECK C: HubDetector — Shared cache with object identity
**File:** `src/services/hub_detector.py`, line 13
```python
cache_key = id(self.problem)
```
This works correctly currently but could mask memory growth if regional Problem objects accumulate.

#### BOTTLENECK D: HierarchicalGA — Hard runtime cap
**File:** `src/optimization/hierarchical_ga.py`, line 29
```python
max_runtime_sec: float = 60.0
```
60 seconds for 435 ports → likely 120–180s needed for 1000+ ports. The GA's runtime scales approximately with `O(pop × gen × services × lanes)`.

#### BOTTLENECK E: HubMILP — Transfer pairs cap
**File:** `src/optimization/hub_milp.py`, line 23
```python
max_transfer_pairs: int = 2000
```
2000 pairs ~ 45 ports fully connected. For 85 ports per cluster, we need ~5,000–10,000 pairs.

#### BOTTLENECK F: HubMILP — Fleet size constant
**File:** `src/optimization/hub_milp.py`, line 31
```python
fleet_size: int = 300
```
Must be proportional to total fleet: `fleet_size = len(problem.ports) * 0.7` or similar.

### 5.4 Conclusion: Agent Scalability

**Can current agents support 1000+ ports without modification?**
**NO** — 6 components require parameterization changes (no structural redesign needed).

All required changes are **parameter adjustments**, not algorithmic overhauls:
1. Service generation capacity (hard-coded 500 → proportional)
2. Hub detection count (20 → 40)
3. GA runtime budget (60s → 180s)
4. MILP transfer pairs (2000 → 10000)
5. Fleet size (300 → proportional)
6. Region count (5 → 12)

> **Estimated effort:** 2–3 days of parameterization work, zero algorithm redesign.

---

## 6. PHASE 4 — DATA GENERATION STRATEGY

### 6.1 Field Provenance Classification Matrix

Every WorldXL field must be labeled as one of:

- **REAL** (R): Sourced from authoritative external data with known license
- **DERIVED** (D): Computed from real data via deterministic transformation
- **ESTIMATED** (E): Statistical estimation/modeling from real proxies
- **SYNTHETIC** (S): Generated via simulation or random process

### 6.2 Port Fields

| Field | Classification | Source/Method | Validation |
|-------|---------------|---------------|------------|
| UNLocode | **R** | UN/LOCODE 2024-2 | Direct match |
| Name | **R** | UN/LOCODE + WPI | Cross-reference |
| Country | **R** | UN/LOCODE | ISO 3166 |
| Latitude/Longitude | **R** | WPI (NGA Pub 150) | Validate ±1° |
| D_Region | **D** | Derived from country + port clusters | Expert review |
| Draft | **R** | WPI (max draft ft → m) | Unit conversion |
| Throughput (MTEU/yr) | **E** | World Bank + port authority reports + regression on port size | ±20% tolerance |
| Congestion index | **E** | Port TEU / handling capacity ratio | Calibrate against known congestion ports (LA/LB, Shanghai) |
| Turnaround hours | **E** | Regression: ~12h + 0.5h × (TEU/1000) + 4h if congestion > 0.7 | Literature comparison |
| Hub classification | **D** | K-means on throughput + connectivity + draft | Expert review |
| Handling cost ($/TEU) | **E** | Drewry benchmarks by region, adjusted for throughput | Region-level accuracy |
| Rail connectivity | **R** | UN/LOCODE transport mode flags | Direct |
| Reefer plugs | **E** | Proportional to throughput × regional reefer share | ±30% |

### 6.3 Demand Fields

| Field | Classification | Source/Method | Validation |
|-------|---------------|---------------|------------|
| Origin / Destination | **R** | UN/LOCODE port list | Exact |
| Weekly TEU | **E** | CTS lane volumes × scaling factor + gravity model for missing lanes | Aggregate to World Bank port totals |
| Revenue per TEU | **E** | Freight rate benchmarks by corridor (Asia-Europe, Transpacific, Intra-Asia) | ±15% on major corridors |
| Transit time | **D** | Distance / 18 knots + port time | ±2 days for major routes |
| Commodity class | **E** | UN Comtrade HS → containerizable share | Aggregate only |
| Seasonality factor | **S** | 12-month sinusoidal based on known trade patterns (pre-Chinese New Year peak, post-LNY trough) | Magnitude calibration against literature |
| Trade imbalance | **E** | IMF DOT export/import ratios per country pair | ±10% |
| Growth rate | **E** | IMF / WTO trade growth projections + historical trend | Aggregate CAGR |
| Empty share | **E** | Region-level averages: Asia export 60% empty, Europe 40%, Americas 50% | Literature |
| Contract type | **S** | 70% long-term, 30% spot — randomized per lane | Distribution matches industry |

### 6.4 Fleet/Vessel Fields

| Field | Classification | Source/Method | Validation |
|-------|---------------|---------------|------------|
| Vessel class | **R** | Clarksons World Fleet Register taxonomy | Direct |
| Capacity (TEU) | **R** | Clarksons / IHS | Per-vessel |
| Quantity | **R** | Existing fleet composition scaled up | 501 → 800+ |
| Fuel type | **E** | IMO GISIS + DNV GL AFI — class-level majority | Per class |
| Speed profile | **E** | Design speed × 0.85 (slow steaming) + 0.95 (full) + 1.0 (max) | Literature |
| Fuel consumption | **R** | Clarksons (already used in fuel_cost.py) | Direct |
| Emissions (CO₂) | **D** | Fuel consumption × 3.114 (IMO factor) | ±5% |
| Operating range | **E** | Fuel capacity / consumption × speed | Adequacy check |
| Ice class | **E** | 0 for 98% of fleet, 1 for Baltic/North Russia only | Binary |
| Charter rate | **E** | Clarksons / Harper Petersen indexes | Per class |
| EEXI / CII | **E** | Estimated from year built + class | Fleet average |

### 6.5 Route Distance Fields

| Field | Classification | Source/Method | Validation |
|-------|---------------|---------------|------------|
| Distance (nm) | **D** | Great Circle + 5% detour factor for realistic routing | ±10% |
| Panama Canal | **D** | Latitude/longitude-based: if origin/dest differ by ocean basin, check Panama route | Cross-reference with canal transit data |
| Suez Canal | **D** | Same logic: check Suez route for Europe-Asia | Cross-reference |
| Canal toll ($) | **D** | Suez: ~$150K + $5/TEU; Panama: ~$100K + $3/TEU | Current tariff schedules |
| Canal draft limit | **R** | Panama: 15.2m (Neopanamax locks), Suez: 20.1m | Known constants |

### 6.6 Provenance Matrix Summary

| Category | REAL | DERIVED | ESTIMATED | SYNTHETIC | TOTAL |
|----------|------|---------|-----------|-----------|-------|
| Port fields | 5 | 2 | 4 | 0 | 11 |
| Demand fields | 2 | 1 | 3 | 2 | 8 |
| Vessel/fleet fields | 3 | 2 | 4 | 0 | 9 |
| Route fields | 0 | 4 | 0 | 0 | 4 |
| **Total** | **10** | **9** | **11** | **2** | **32** |

> **Real-proxy ratio:** 10 real / 22 non-real = 31% real. Acceptable for a research dataset. The 2 synthetic fields (seasonality, contract type) are clearly labeled and can be toggled off.

---

## 7. PHASE 5 — SCALABILITY FORECAST

### 7.1 Data Size Projections

| Dimension | WorldLarge-435 | WorldXL-1000 | Factor | Storage Impact |
|-----------|---------------|--------------|--------|----------------|
| Ports | 435 | 1,000 | 2.3× | ~32 KB → ~73 KB |
| Countries | 117 | 180+ | 1.5× | — |
| Demand lanes (OD) | 9,622 | 30,000 (est.) | 3.1× | ~1.2 MB → ~3.7 MB |
| Distance records | 62,003 | 200,000+ | 3.2× | ~4.5 MB → ~14.5 MB |
| Fleet records | 6 classes, 501 vessels | 8 classes, 800+ vessels | 1.6× | Negligible |
| Total raw data | ~7 MB | ~20 MB | 2.9× | 20 MB — negligible for modern systems |

### 7.2 Runtime Projections

| Pipeline Stage | WorldLarge-435 (actual) | WorldXL-1000 (estimated) | Scaling Factor |
|----------------|------------------------|--------------------------|----------------|
| Port clustering | <1s | <1s | O(n·k·i) — fine |
| Regional splitting | <1s | <1s | Linear |
| Service generation | 2–5s | 5–15s | O(lanes + ports × hubs) |
| Service filter | <1s | 1–2s | O(services × lanes) |
| HierarchicalGA (per region) | 55s (capped) | 120–180s | O(pop × gen × services × lanes) |
| FrequencyGA (per region) | 5–10s | 10–20s | O(active_services × lanes) |
| HubMILP (per cluster) | 30–120s | 60–300s | O(vars³) worst case — but bounded by time_limit |
| Coordinator | 5–10s | 10–15s | Linear |
| **Total per iteration** | **~120–200s** | **~300–600s** | **2.5–3×** |
| **Total pipeline (3 iters)** | **~360–600s** | **~900–1,800s** | **2.5–3×** |

> **Pipeline runtime estimate for WorldXL: 15–30 minutes** (vs current 6–10 minutes). This is acceptable for a research batch pipeline.

### 7.3 Memory Projections

| Component | WorldLarge-435 | WorldXL-1000 | Factor |
|-----------|---------------|--------------|--------|
| Problem object | ~200 MB | ~600 MB | 3× |
| GA population (80 chromosomes) | ~50 MB | ~150 MB | 3× |
| MILP LP (PuLP) | ~150 MB | ~500 MB | 3.3× |
| Peak memory | ~400 MB | ~1.2 GB | 3× |
| Dashboard data payload | ~5 MB | ~15 MB | 3× |

> **Peak memory estimate: ~1.2 GB** — comfortable within 4–16 GB typical workstation. No special infrastructure needed.

### 7.4 GA Search Space

| Dimension | WorldLarge-435 | WorldXL-1000 | Implication |
|-----------|---------------|--------------|-------------|
| Candidate services | ~1,500 | ~3,000–6,000 | 2–4× more bits in chromosome |
| Search space | 2^1500 | 2^4000 | Exponentially larger — but GA never explores full space |
| GA generations needed | 120 (current) | 150–200 (estimate) | More generations to converge |
| Population size | 80 (current) | 100–120 (recommended) | More diversity needed |
| Total GA evaluations | 9,600 | 15,000–24,000 | 1.5–2.5× |

### 7.5 MILP Complexity

| Dimension | WorldLarge-435 | WorldXL-1000 | Implication |
|-----------|---------------|--------------|-------------|
| Flow variables | O(D × max_svc_per_demand) | 3–5× more | Linear growth |
| Transfer variables | max 2000 pairs | 5000+ pairs preferred | Quadratic in active services |
| Constraints | ~ports + ~service_cap | 2–3× more | Linear growth |
| Solve time | 30–120s per cluster | 60–300s | PuLP/CBC handles ~100K vars well |

### 7.6 Dashboard & Visualization Volume

| Dimension | WorldLarge-435 | WorldXL-1000 | Factor |
|-----------|---------------|--------------|--------|
| Map markers | 435 | 1,000+ | 2.3× |
| Route lines (selected services) | ~473 | ~800–1,200 | 1.7–2.5× |
| OD flow lines | ~9,622 | ~30,000 | 3.1× |
| Data points per dashboard load | ~10,500 | ~31,200 | 3× |

> **Dashboard impact:** Acceptable with modern frontend frameworks (React/Mapbox). Consider clustering at high zoom levels.

---

## 8. PHASE 6 — BENCHMARKING PLAN

### 8.1 Comparison Framework

Benchmark runs on identical optimizer configuration, varying only the dataset:

```
WorldLarge-435 (control)           WorldXL-1000 (experiment)
     ────────                             ────────
    │ Frozen │◄────── Same optimizer ────►│ Test   │
    │ benchmark│    code and parameters    │ dataset│
     ────────                              ────────
         │                                     │
         ▼                                     ▼
   Baseline metrics                      Comparison metrics
         │                                     │
         └────────────────┬────────────────────┘
                          ▼
                Analyze: does WorldXL
                produce more realistic
                commercial benchmarks?
```

### 8.2 Metrics Definition

| Metric | Definition | Scale | Expectation |
|--------|-----------|-------|-------------|
| **Network coverage** | % of ports with at least one service call | 0–100% | WorldXL should be higher |
| **Demand coverage** | % of TEU satisfied | 0–100% | WorldXL may be lower (more thin lanes) |
| **Weekly profit** | Revenue − operating − fuel − port − transship | $/wk | WorldXL should show more granular profit |
| **Profit margin** | Profit / Revenue | % | WorldXL likely lower (more thin routes) |
| **Pipeline runtime** | Total wall-clock time | seconds | WorldXL 2.5–3× longer |
| **Fleet utilization** | TEU carried / fleet capacity | % | WorldXL should be equal or better |
| **Negative services** | Services with negative profit margin | count | WorldXL same or fewer proportionally |
| **Regional balance** | Std dev of profit/coverage across regions | — | WorldXL should reduce extremes |
| **Service count** | Total selected services | count | WorldXL more services |
| **Hubs utilization** | % of TEU passing through hubs | % | WorldXL should be comparable |

### 8.3 Test Protocol

```
FOR EACH DATASET:
  1. Run pipeline 3 times (to measure variance)
  2. Record deterministic metrics (same seed)
  3. Record stochastic metrics (different seeds × 3)
  4. Collect GA telemetry (generation history)
  5. Collect MILP telemetry (binding constraints)
  6. Export full results to JSON
```

### 8.4 Expected Findings

| Finding Type | Likelihood | Impact |
|-------------|-----------|--------|
| WorldXL has lower coverage initially | High | Need more services/larger fleet |
| WorldXL shows more realistic regional profit distribution | High | Confirms better regional decomposition |
| WorldXL identifies new hub allocations | Medium | Geographic expansion reveals new patterns |
| WorldXL runtime exceeds acceptable batch window | Medium | May need GA parameter tuning |
| WorldXL profit per TEU is lower | Medium | More thin routes in expanded network |
| WorldXL fleet constraint binds harder | High | Need to increase fleet limit proportionally |

---

## 9. PHASE 7 — IMPLEMENTATION READINESS

### 9.1 Readiness Classification

| Criterion | Rating | Assessment |
|-----------|--------|------------|
| Architecture fit | ✅ READY | Hierarchical decomposition naturally scales |
| Algorithm support | ⚠ READY WITH RISKS | 6 parameters need adjustment, no redesign needed |
| Data availability | ✅ READY | UN/LOCODE + WPI + CTS + Clarksons are proven sources |
| Infrastructure | ✅ READY | 1.2 GB peak memory, 30 min runtime — standard workstation |
| Storage | ✅ READY | ~20 MB raw data |
| Team capability | ✅ READY | No new skill domains required |
| Pipeline integrity | ⚠ READY WITH RISKS | GA/MILP convergence may need re-tuning |
| Budget | ⚠ READY WITH RISKS | Data licensing costs (CTS, Clarksons) may be $10K–50K |

**Final Classification: READY WITH RISKS**

### 9.2 Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| CTS data licensing cost > budget | Medium | High | Use UN Comtrade + gravity model fallback |
| GA convergence degrades at 3K+ services | Medium | High | Run parameter sweep before full build |
| MILP solver time exceeds 300s per cluster | Medium | Medium | Reduce hub clusters → more small MILPs |
| Fleet constraint too tight at 300 vessels | High | Medium | Parameterize fleet_size × port count |
| Port data inconsistencies (China, Russia) | Medium | Low | Cross-reference UN/LOCODE + WPI |
| Missing small ports in UN/LOCODE | Medium | Low | Supplement with WPI entries |
| Revenue per TEU estimates inaccurate | High | Medium | Sensitivity analysis on revenue model |

### 9.3 Development Effort Estimate

| Phase | Effort (person-days) | Description |
|-------|---------------------|-------------|
| Data collection | 10–15 | Acquire UN/LOCODE, WPI, CTS data |
| Port expansion | 5–8 | Create script to merge sources → 1000 ports |
| Demand generation | 8–12 | Gravity model + CTS scaling + seasonality |
| Distance computation | 3–5 | Great circle + canal detection for all OD pairs |
| Fleet expansion | 3–5 | Add vessel classes, scale fleet, add fuel types |
| Region config update | 2–3 | Redefine region taxonomy, update agent mapping |
| Parameter tuning | 3–5 | GA, MILP, service generation parameter adjustment |
| Benchmarking | 3–5 | Run WorldLarge vs WorldXL comparison |
| Documentation | 2–3 | Dataset schema, provenance, usage guide |
| **Total** | **39–61** | **~2–3 months for one person, ~1 month for 2 people** |

### 9.4 Data Collection Cost Estimate

| Source | License Cost | Notes |
|--------|-------------|-------|
| UN/LOCODE | Free | Always free |
| World Port Index | Free | Public domain |
| Clarksons Research | $10,000–$30,000/yr | Subscription |
| Container Trade Statistics | $5,000–$15,000/yr | Subscription |
| Bunker Index | Free | Public |
| UN Comtrade | Free | Public |
| IMF DOT | Free | Public |
| World Bank | Free | Public |
| **Total** | **$15,000–$45,000/yr** | Data subscriptions |

> **Low-cost fallback:** If subscription data is unavailable, WorldXL can be built 100% from free sources (UN/LOCODE + WPI + UN Comtrade + gravity model) with lower demand accuracy. Expected accuracy degradation: ±30% on lane volumes vs ±15% with CTS.

### 9.5 Implementation Constraints

1. **WorldLarge-435 is frozen.** Never modify it. All new files go in `data/world_xl/`.
2. **WorldXL shares the same code** — no WorldXL-specific code paths. Any modifications must be parameter-based or backward-compatible configuration.
3. **Provenance is mandatory.** Every field in every record must be traceable to source.
4. **No random scraping.** All data sources must be documented with version, URL, and license.
5. **Test before use.** A WorldXL smoke test (load → decompose → optimize → verify) must pass before any research use.

---

## 10. FINAL QUESTIONS ANSWERED

### Q1: Is expanding from 435 to 1000+ ports technically feasible?

**YES.** The hierarchical decomposition architecture (orchestrator → regional agents → GA → MILP) is designed for scale. The 5-region, 435-port configuration is a low-end deployment of a fundamentally scalable architecture.

**Evidence:**
- PortClustering KMeans scales O(n·k·i) — 1,000 points is trivial
- Regional port count actually *decreases* per agent with more regions (from ~87/region to ~83/region)
- GA search space grows, but GA never enumerates — it samples
- MILP per cluster is bounded by the region size, not the global port count
- Pipeline memory footprint of ~1.2 GB is well within workstation limits
- Total raw data storage of ~20 MB is negligible

### Q2: What additional data factors should be added?

**Port factors:** throughput, congestion index, turnaround time, hub classification, terminal operators, max beam/LOA, reefer plugs, rail connectivity

**Route factors:** service frequency, transit time, alliance presence, canal dependency, canal toll costs, seasonal reliability

**Vessel factors:** fuel type, speed profile (slow/full/max), emission profile (CO₂/NOx/SOx), operating range, ice class, charter rate, CII rating, EEXI value

**Demand factors:** commodity class, seasonality, trade imbalance, growth rate, empty repositioning share, contract type, special cargo requirements

### Q3: Which new regions should exist?

**12 recommended regions:**
1. East Asia (North/Central/South China, Japan, Korea, Taiwan, Hong Kong)
2. Southeast Asia (Singapore, Vietnam, Thailand, Philippines, Indonesia, Malaysia)
3. South Asia (Mumbai/India, Pakistan, Sri Lanka, Bangladesh)
4. Oceania (Australia, New Zealand, Pacific Islands) — **correcting current misassignment**
5. North America (US East/West/Gulf Coast, Canada, Mexico)
6. Central America & Caribbean
7. South America West Coast
8. South America East Coast / Brazil
9. North Europe (Continent, UK, Scandinavia, Baltic)
10. Mediterranean (West Med, East Med, Adriatic, Black Sea — optionally split)
11. Middle East & Gulf (Red Sea, Gulf, Saudi Arabia, UAE)
12. Sub-Saharan Africa (West Africa, Southern Africa, East Africa)

### Q4: Can current regional agents support WorldXL?

**YES, WITH PARAMETER CHANGES.** The agent architecture itself is algorithmically correct for 1000+ ports. Six specific parameters need adjustment:

1. Service generation cap (500 → proportional to lanes/population)
2. Hub detection count (20 → 40)
3. GA runtime budget (60s → 120–180s)
4. MILP transfer pairs limit (2000 → 5000–10000)
5. Fleet size (300 → 500–800)
6. Regional agent count (5 → 8–12)

**No structural code changes required** — all six are configuration parameters.

### Q5: What optimizer bottlenecks will appear?

| Priority | Bottleneck | Component | Severity | Fix |
|----------|-----------|-----------|----------|-----|
| P0 | Direct service cap | ServiceGeneratorAgent: top_n_direct = min(500) | **Blocking** | Make proportional |
| P0 | Fleet size | HubMILP: fleet_size = 300 | **Blocking** | Make proportional |
| P1 | Transfer pairs limit | HubMILP: max_transfer_pairs = 2000 | High | Increase to 5000+ |
| P1 | GA runtime cap | HierarchicalGA: max_runtime_sec = 60 | High | Increase to 180s |
| P2 | Hub count | ServiceGeneratorAgent: hubs[:10] | Medium | Make proportional |
| P2 | Service filter cap | Non-blocking — max(400, ports) auto-scales | Low | Already correct |

### Q6: What runtime increase is expected?

**Estimated: 2.5–3×** (from ~6 min to ~15–30 min per pipeline run).

- GA: 1.5–2× longer (120–180s per region)
- MILP: 2–3× longer (60–300s per cluster)
- Service generation: 2–3× longer (5–15s)
- Total parallelized across regions

**Mitigation:** The pipeline is already parallelized at the regional agent level via `ThreadPoolExecutor`. More regions (12 vs 5) means more parallelism but each region does less work.

### Q7: What data sources should be used?

**Primary (free):** UN/LOCODE (ports), World Port Index (coordinates/draft), Bunker Index (fuel prices), UN Comtrade (trade flows), World Bank (port throughput), IMF DOT (bilateral trade).

**Primary (paid — recommended):** Clarksons Research (vessel data), Container Trade Statistics (lane-level demand).

**Secondary (free):** IMO GISIS (vessel particulars), DNV GL AFI (alternative fuels), port authority annual reports (throughput).

**Reference (paid — for validation only):** Alphaliner (service networks), MDS Transmodal (trade indices).

### Q8: What fields should be real vs synthetic?

Of 32 new fields:
- **10 REAL** (31%): UNLocode, name, country, coordinates, draft, fuel consumption, vessel class, capacity, port throughput (from authorities), rail connectivity
- **9 DERIVED** (28%): D_Region, distances, canal dependency, transit time, emissions CO₂, canal tolls, empty share, hub classification, speed profiles
- **11 ESTIMATED** (34%): Port congestion, turnaround time, handling cost, lane TEU volume, revenue per TEU, commodity class, trade imbalance, growth rate, fuel type, charter rate, CII rating
- **2 SYNTHETIC** (6%): Seasonality factor, contract type

No unlabeled fields. Every value is traceable to its source method.

### Q9: What is the recommended implementation roadmap?

**Phase A** (Weeks 1–2): Parameter tuning on existing WorldLarge-435
- Parameterize hard-coded limits (service cap, fleet size, hub count)
- Validate that parameter changes don't break WorldLarge-435 certification
- **Deliverable:** Scalable optimizer configuration

**Phase B** (Weeks 3–4): Port expansion data collection
- Acquire UN/LOCODE → merge with WorldLarge-435 port list
- Cross-reference WPI for coordinates/draft
- Generate 565+ new ports (1000 total)
- **Deliverable:** WorldXL port catalog

**Phase C** (Weeks 5–6): Demand generation
- Build gravity model for trade flow estimation
- Calibrate against known major corridors
- Generate 30,000+ OD pairs with seasonality
- **Deliverable:** WorldXL demand matrix

**Phase D** (Week 7): Fleet and distance generation
- Add Neo_panamax, Ultra_large, Small_feeder vessel classes
- Scale fleet to 800+ vessels
- Compute 200K+ distance records with canal detection
- **Deliverable:** WorldXL distance + fleet data

**Phase E** (Weeks 8–9): Integration and region reconfiguration
- Configure 12 regional agents with new region definitions
- Load WorldXL as `data/world_xl/` dataset
- Smoke test: load → decompose → optimize → verify
- **Deliverable:** WorldXL-1000 working dataset

**Phase F** (Week 10): Benchmarking
- Run WorldLarge-435 baseline (3×)
- Run WorldXL-1000 experiment (3×)
- Produce benchmark comparison report
- **Deliverable:** WorldXL-1000 Benchmark Report

### Q10: Is WorldXL likely to improve commercial realism and benchmark validity?

**YES — substantial improvement expected, for five reasons:**

1. **Geographic coverage** — 1000+ ports captures more real-world trading ports vs 435. Currently missing major ports like Bay of Bengal ports, West African secondary ports, Pacific Island ports.

2. **Regional decomposition** — 12 regions instead of 5 eliminates current structural artifacts (e.g., Australia grouped with Americas). Agents optimize more homogeneous geographic clusters.

3. **Demand granularity** — 30,000+ OD pairs captures thin lanes that are critical for realistic transshipment analysis. Current 9,622 lanes over-represents major corridors.

4. **Port realism** — Congestion, throughput limits, and turnaround times constrain the MILP to realistic capacity allocations rather than concentrating all flow through cheapest ports.

5. **Fleet realism** — More vessel classes with fuel type and emission profiles enable realistic cost structures. Current 6 classes are coarser than real fleet composition.

**Potential risk:** WorldXL may produce *lower* headline profit and coverage metrics because it models more challenging real-world constraints (congestion, thin lanes, empty repositioning). This is *not a bug* — it means the benchmark is harder and more realistic. The commercial value is in comparing *relative* optimizer improvements on a more realistic testbed, not in achieving high absolute scores.

---

## 11. RECOMMENDED IMPLEMENTATION ROADMAP

### 11.1 Phased Rollout

```
WEEK 1-2     WEEK 3-4     WEEK 5-6     WEEK 7       WEEK 8-9     WEEK 10
   │            │            │            │            │            │
   ▼            ▼            ▼            ▼            ▼            ▼
┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
│Phase A │→ │Phase B │→ │Phase C │→ │Phase D │→ │Phase E │→ │Phase F │
│Param   │  │Port    │  │Demand  │  │Fleet & │  │Integrat│  │Bench-  │
│Tuning  │  │Data    │  │Generat │  │Dist    │  │ion     │  │mark    │
└────────┘  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘
```

### 11.2 Critical Path Dependencies

```
Phase A (param tuning) ──→ Phase E (dependent — new config needed)
Phase B (ports) ─────────→ Phase C (demand needs port list)
Phase C (demand) ────────→ Phase E (demand is core data)
Phase D (fleet/dist) ────→ Phase E (need routes + fleet)
Phase E ─────────────────→ Phase F (benchmarking)
```

**Critical path:** Phase A → Phase B → Phase C → Phase E → Phase F ≈ 8–10 weeks

### 11.3 Go/No-Go Decision Points

| Decision Point | By | Condition to Proceed |
|---------------|----|---------------------|
| After Phase A | Week 2 | Parameter changes pass WorldLarge-435 certification suite |
| After Phase B | Week 4 | 1000+ ports validated with UN/LOCODE + WPI cross-reference |
| After Phase C | Week 6 | Demand matrix passes aggregate calibration (World Bank totals ±20%) |
| After Phase E | Week 9 | Smoke test: pipeline runs to completion with valid results |
| After Phase F | Week 10 | Benchmark report produced — decide if WorldXL becomes research standard |

### 11.4 Success Criteria

1. WorldXL-1000 loads and runs in the existing optimizer pipeline (no code modifications to core algorithm)
2. Pipeline completes within 30 minutes on a standard workstation
3. All field provenance is documented (no unlabeled fields)
4. WorldLarge-435 remains frozen and certified (0 regressions)
5. Benchmark report identifies at least 3 differences between WorldLarge and WorldXL that affect optimizer strategy

---

## APPENDIX A: Current Architecture Reference

| Component | File | Lines | Key Parameters |
|-----------|------|-------|----------------|
| OrchestratorAgent | `src/agents/orchestrator_agent.py` | 853 | MAX_ITERATIONS=3, n_clusters=sqrt(n) |
| RegionalAgent | `src/agents/regional_agent.py` | 469 | 5 agents: Asia, Europe, Americas, Middle East, Africa |
| ServiceGeneratorAgent | `src/agents/service_generator_agent.py` | 300 | top_n_direct=500, top10_hubs, 150 heuristic |
| HubDetector | `src/services/hub_detector.py` | 72 | top_k=20, demand×0.7 + conn×0.3 |
| PortClustering | `src/decomposition/port_clustering.py` | 114 | KMeans, sqrt(n) clusters, n_init=20 |
| RegionalSplitter | `src/decomposition/regional_splitter.py` | 93 | Origin-only demand assignment |
| HierarchicalGA | `src/optimization/hierarchical_ga.py` | 237 | pop=80, gen=120, max_runtime=60s |
| ServiceGA | `src/optimization/service_ga.py` | ~450 | pop=80, gen=120, w_profit=8.0/0.5 |
| FrequencyGA | `src/optimization/frequency_ga.py` | 250 | pop=40, gen=60, max_freq=3 |
| HubMILP | `src/optimization/hub_milp.py` | 643 | max_xfer=2000, fleet=300, time_limit=120s |
| ObjectiveNormalizer | `src/optimization/normalization.py` | 169 | Scaling: profit=1e7, coverage=1e0, cost=1e7 |
| Data model | `src/optimization/data.py` | 57 | Port, Service, Demand, Problem |

## APPENDIX B: Vessel Class Definitions

| Class | Capacity (TEU) | Consumption (t/day) | Speed (knots) | Current Qty | WorldXL Qty |
|-------|---------------|-------------------|---------------|-------------|-------------|
| Small_feeder | 100–300 | 10 | 14 | 0 (NEW) | 50 |
| Feeder_450 | 450 | 15 | 16 | 38 | 50 |
| Feeder_800 | 800 | 25 | 17 | 77 | 100 |
| Panamax_1200 | 1,200 | 35 | 18 | 124 | 150 |
| Panamax_2400 | 2,400 | 55 | 19 | 161 | 200 |
| Neo_panamax | 8,000 | 100 | 23 | 0 (DEFINED) | 80 |
| Post_panamax | 5,000 | 80 | 22 | 91 | 100 |
| Super_panamax | 10,000 | 120 | 24 | 10 | 30 |
| Ultra_large | 18,000 | 200 | 22 | 0 (NEW) | 25 |
| Mega_max | 24,000+ | 250 | 21 | 0 (NEW) | 15 |
| **Total** | | | | **501** | **800** |

## APPENDIX C: Key File Locations for WorldXL

| Purpose | Path | Notes |
|---------|------|-------|
| Port catalog | `data/world_xl/ports.csv` | UN/LOCODE + WPI merged |
| Demand matrix | `data/world_xl/demand.csv` | 30K+ OD pairs with seasonality |
| Fleet description | `data/world_xl/fleet.csv` | 800+ vessels, 10 classes |
| Distance matrix | `data/world_xl/distances.csv` | 200K+ records with canal flags |
| Region config | `src/config/regions_worldxl.json` | 12-region taxonomy |
| Problem dataset | `data/world_xl/worldxl_problem.json` | Full dataset (generated) |
| Field provenance | `data/world_xl/PROVENANCE.md` | Per-field source documentation |
| Benchmark results | `data/world_xl/benchmark/` | WorldLarge comparison outputs |

---

*End of WORLDXL_1000_EXPANSION_MASTER_PLAN.md*
*Prepared 2026-06-08 — Planning Phase Complete, Ready for Implementation Proposal*
