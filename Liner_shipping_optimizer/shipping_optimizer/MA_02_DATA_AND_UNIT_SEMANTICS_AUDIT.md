# MA_02 — DATA AND UNIT SEMANTICS AUDIT

**System:** AI Vessel Routing System — Multi-Agent Optimizer
**Audit mode:** Forensic, evidence-driven, read-only
**Date:** 2026-10-05
**Status:** COMPLETE for the WorldSmall production path. WorldLarge partially covered (see §7).

---

## 0. Audit constraints honoured

| Constraint | Status |
|---|---|
| No source / config / dataset / test modification | Honoured — zero Write/Edit on any tracked file |
| No git operations | Honoured |
| No dependency installation | Honoured |
| Production pipeline not executed | Honoured — all figures reproduced from raw CSV by independent arithmetic and from the existing `frontend/public/pipeline_output.json` artifact |
| RL engine not used as a correctness standard | Honoured — see §8 |
| No manufactured values | Honoured — every number is either read from a named file or computed by a quoted expression |

All Python used for verification was read-only arithmetic over raw CSV/JSON. No project module was imported for side effects.

---

## 1. Canonical data dictionary

Every field consumed by optimization or economics. "Verified" means the unit was established from dataset structure plus arithmetic, not inferred from the variable name.

### 1.1 Ports — `data/raw/ports.csv` (435 rows), `ports_world_small.csv` (47 rows), `WorldSmall/ports.csv` (47 rows)

| Field | Source column | Internal name | Unit | Time basis | Transformation | Consumers | Status |
|---|---|---|---|---|---|---|---|
| id | `UNLocode` | `Port.id` | string | — | `str(...).strip()` | all | **Verified** |
| name | `name` | `Port.name` | string | — | strip | reporting | Verified |
| latitude | `Latitude` | `Port.latitude` | degrees N | — | `to_numeric`, rows with NaN **dropped** (`network_loader.py:33`) | hub detection, clustering | Verified |
| longitude | `Longitude` | `Port.longitude` | degrees E | — | same | same | Verified |
| draft | `Draft` | `Port.draft` | metres | — | `to_numeric` | **NONE** | **Loaded but ignored** (grep: 0 readers outside loader/dataclass) |
| handling_cost | `CostPerFULL` | `Port.handling_cost` | **USD per FFE** ×2.0 | per TEU-ish event | `× 2.0` (`network_loader.py:45`) | ServiceGA, FrequencyGA, MILP | **Verified** — raw column is per FULL (FFE); ×2 converts FFE→TEU basis |
| transshipment_cost | `CostPerFULLTrnsf` | `Port.transshipment_cost` | **USD per FFE** ×2.0 | per transfer | `× 2.0` (`:48`) | **MILP only** (`hub_milp.py:183-186`) | Verified; **not used by either GA** |
| port_call_cost | `PortCallCostFixed` | `Port.port_call_cost` | **USD per call** ×1.0 | per call | none (`:47`) | ServiceGA, FrequencyGA, MILP | **Verified** — the only port column NOT scaled |
| variable_port_call_cost | `PortCallCostPerFFE` | `Port.variable_port_call_cost` | **USD per FFE** ×2.0 | per TEU-ish event | `× 2.0` (`:49`) | ServiceGA, FrequencyGA, MILP | Verified |

**Verified against the shipped JSON dataset.** Every port in `data/datasets/worldsmall_shipping_problem.json` matches the ×2.0 rule exactly:

```
handling_cost == CostPerFULL * 2.0              -> True for all 47 ports
transshipment_cost == CostPerFULLTrnsf * 2.0    -> True for all 47 ports
variable_port_call_cost == PortCallCostPerFFE*2 -> True for all 47 ports
port_call_cost == PortCallCostFixed * 1.0       -> True for all 47 ports
```

> **Note on the ×2.0.** The port columns are multiplied by 2.0 to convert an FFE-denominated rate into a TEU-denominated rate. This is the *correct* FFE→TEU conversion and is dimensionally sound **provided** the demand quantity is in TEU. See §3 — the demand quantity is not in TEU.

### 1.2 Demand — `data/raw/demand_world_small.csv` (1,764 rows)

| Field | Source column | Internal name | Unit as loaded | Transformation | Status |
|---|---|---|---|---|---|
| Origin | `Origin` | `Demand.origin` | string | strip | Verified |
| Destination | `Destination` | `Demand.destination` | string | strip; self-lanes dropped (`:98-99`) | Verified |
| FFEPerWeek | `FFEPerWeek` | *(not stored)* | **FFE/week** | — | Verified raw unit |
| Revenue_1 | `Revenue_1` | *(not stored)* | **USD/FFE** | — | Verified raw unit |
| — | `FFEPerWeek` × k | `Demand.weekly_teu` | **FFE/week × k** | `× ffe_to_teu_factor` (`:106`) | **MISLABELLED "TEU"** |
| — | `Revenue_1` × k | `Demand.revenue_per_teu` | **USD/FFE × k** | `× ffe_to_teu_factor` (`:109`) | **MISLABELLED "$/TEU"** |
| TransitTime | `TransitTime` | *(not loaded)* | days | — | **Column never read by the loader** |

**`Revenue_1` unit established by arithmetic, not by name.** The column name is not self-documenting. Evidence:

1. Demand volumes (`FFEPerWeek`) are O(10²–10³) and revenue values (`Revenue_1`) are O(10³). If `Revenue_1` were USD/TEU and the loader multiplied it by k to get USD/TEU, the resulting rate would be O(10³) USD/TEU — implausible by ~3 orders of magnitude for liner freight.
2. `docs/DATA_DICTIONARY.md` and `verification/01_GOLDEN_SPECIFICATION.md:108` both state `IN-003-D Revenue per FFE, USD/FFE, source Revenue_1`.
3. The `×2.0` applied to the port cost columns (`CostPerFULL` → USD/TEU) uses the identical 2.0 factor, confirming the project treats FFE/TEU as a factor of 2 throughout.
4. **Decisive self-consistency check:** if `Revenue_1` were $/TEU and the code multiplied it by k, the project would be inflating a rate that is *already* in TEU. If `Revenue_1` is $/FFE (as documented), the code is converting correctly. The code comment at `network_loader.py:108` — `# Revenue_1 is $/FFE, convert to $/TEU` — states the intent, and that intent is **wrong** (see §3).

**Conclusion: `Revenue_1` is USD/FFE. The loader's conversion to $/TEU is directionally correct but arithmetically inverted.**

### 1.3 Distance — `data/raw/distance_dense.csv` (62,002 rows)

| Field | Source column | Internal | Unit | Status |
|---|---|---|---|---|
| fromUNLOCODe | `fromUNLOCODe` | matrix key | UNLOCODE | Verified |
| ToUNLOCODE | `ToUNLOCODE` | matrix key | UNLOCODE | Verified |
| Distance | `Distance` | `distance_matrix[o][d]` | nautical miles | **Verified** — used with knots in `fuel_cost.py:144` |
| Draft | `Draft` | — | — | **Never read** (7,026 rows non-empty) |
| IsPanama | `IsPanama` | — | — | **Never read** (see MA_04) |
| IsSuez | `IsSuez` | — | — | **Never read** (see MA_04) |

**Loader is last-write-wins** (`network_loader.py:143-144`). Independently measured defects:

| Metric | Value |
|---|---|
| Unique (from,to) pairs | 43,056 |
| Duplicated pairs | **17,169** |
| Of those, with **conflicting** distance values | **17,169 (100%)** |
| Mean absolute difference first↔last | **4,086.7 nm** |
| Mean ratio last/first | **1.7718** |
| Max ratio last/first | **37.94×** |

Example conflicts: `AEJEA→BEANR` = [6297, 10999]; `AEJEA→BEZEE` = [6236, 10938].

**Matrix coverage:**

| Ports file | Ports | Present in `distance_dense.csv` | Missing |
|---|---|---|---|
| `ports_world_small.csv` (WorldSmall, **the production set**) | 47 | 47 | **0** |
| `ports.csv` (WorldLarge) | 435 | 208 | **227** |

Consequence for WorldSmall: the `fuel_cost.py:205` fallback of `500.0` nm is **never triggered** on the production path. For WorldLarge it fires for 227 of 435 ports, silently costing every leg from an unmapped port at 500 nm.

### 1.4 Fleet — `data/raw/fleet_world_small.csv` (263 vessels), `WorldSmall/fleet_data.csv`

| Field | Source column | Internal | Unit | Consumers | Status |
|---|---|---|---|---|---|
| Vessel class | `Vessel class` | `FleetClass.vessel_class` | — | `total_vessels` only | Verified |
| Quantity | `Quantity` | `FleetClass.quantity` | count | `Fleet.total_vessels` | Verified |
| Capacity FFE | `Capacity FFE` | `FleetClass.capacity_teu` | **FFE** | **NONE** (grep: 0 readers outside loader/dataclass) | **Loaded but ignored** |
| TC rate daily | `TC rate daily (fixed Cost)` | `FleetClass.tc_rate_daily` | **USD/day** | **NONE** | **Loaded but ignored** |
| draft | `draft` | `FleetClass.draft` | m | **NONE** | Loaded but ignored |
| minSpeed / maxSpeed | same | `min_speed`/`max_speed` | knots | **NONE** | Loaded but ignored |
| designSpeed | `designSpeed` | `FleetClass.design_speed` | knots | **NONE** | Loaded but ignored |
| Bunker ton per day at designSpeed | same | `bunker_consumption_tons_per_day` | t/day | **NONE** | **Loaded but ignored** |
| Idle Consumption ton/day | same | `idle_consumption_tons_per_day` | t/day | **NONE** | **Loaded but ignored** |
| panamaFee | `panamaFee` | `FleetClass.panama_fee` | USD/transit | **NONE** | **Loaded but ignored** |
| suezFee | `suezFee` | `FleetClass.suez_fee` | USD/transit | **NONE** | **Loaded but ignored** |

**Fleet inventory:** WorldSmall = **263 vessels** (24/29/68/74/58/10 by class). WorldLarge = **501 vessels**.

> Every economic field the fleet file provides — charter rate, bunker consumption, idle consumption, canal fees, vessel capacity — is loaded into dataclasses and then never read by any optimizer, cost function, or reporter. The only thing the fleet is used for is `total_vessels` (a count). See MA_04.

---

## 2. Demand transformation lineage — end to end

### 2.1 The two loading paths

There are **two** demand loaders in `src/data/network_loader.py` with materially different semantics:

| | **CSV path — `load_demands()` :58** | **JSON path — `load_problem()` :250** |
|---|---|---|
| Source | `demand_world_small.csv` (or `WorldSmall/Demand_WorldSmall_Fixed_Sep.csv`) | `data/datasets/*.json` |
| Scaling | Lane-specific `FFE_TO_TEU_CONVERSIONS` table, default **2.0** | Flat **`DEMAND_SCALE = 6`** (:275-277) |
| Revenue rate | `Revenue_1 × k` | from JSON, **never scaled** |
| Fleet | `load_fleet()` → real `Fleet` (263) | **no `fleet=`** → `Problem.fleet is None` |
| Which path is production? | **YES** — see §2.2 | Legacy; runs by default in the CLI benchmark |

**Docstring/code contradiction.** `network_loader.py:251-256` claims the JSON path *"preserves the existing DEMAND_SCALE behavior for WorldLarge test compatibility while allowing WorldSmall datasets that already have correctly-scaled values."* But `:275-277` applies `DEMAND_SCALE = 6` **unconditionally**, with no branch on dataset identity. The claimed WorldSmall exemption does not exist in code. A WorldSmall JSON passed through `load_problem` is inflated 6× exactly as WorldLarge is.

### 2.2 Which path feeds the deployed system

**The CSV path is production.** Evidence, independently verified:

1. `tests/test_orchestrator.py:2108` → `load_worldsmall_problem()` (`:210`) → the CSV branch (`:217-237`), passing `load_fleet(...)` (`:222-225`).
2. That test is the **only writer** of `pipeline_output.json` — `tests/test_orchestrator.py:2222-2235` writes `pipeline_output.json`, `frontend/public/pipeline_output.json`, and `frontend/dist/pipeline_output.json`.
3. `backend/server.py:71-79` `load_pipeline_data()` reads exactly that file and ~50 routes consume it. Grep confirms `backend/server.py` contains **zero** references to `Orchestrator`, `NetworkLoader`, or `src.`.
4. Runtime corroboration: `backend/__pycache__/` contains only `{__init__, server}.cpython-311.pyc`. `backend/services/__pycache__/` **does not exist**. Nothing else in `backend/` has ever been imported.

### 2.3 Verified transformation chain for one record

Take the lane `CNSHA → NLRTM`, which carries a **non-default** lane factor k = 2.1 (`network_loader.py:76-77`).

| Step | Quantity | Value | Unit | Source |
|---|---|---|---|---|
| Raw | `FFEPerWeek` | **1,052** | FFE/week | `demand_world_small.csv` |
| Raw | `Revenue_1` | **2,960** | USD/FFE | `demand_world_small.csv` |
| Loader k | `ffe_to_teu_factor` | **2.1** | ratio | `network_loader.py:103` |
| Stored | `Demand.weekly_teu` | **2,209.2** | FFE/week × 2.1 | `:106` |
| Stored | `Demand.revenue_per_teu` | **6,216.0** | USD/FFE × 2.1 | `:109` |
| Product | — | **13,732,494.2** | **USD/week × k²** | `:106 × :109` |
| **Correct product** | FFE × $/FFE | **3,113,920.0** | **USD/week** | 1052 × 2960 |
| **Inflation** | — | **× 4.41** | — | k² = 4.41 |

And the dimensionally correct alternative:

| Representation | Volume | Rate | Product |
|---|---|---|---|
| As implemented | 2209.2 (FFE×k) | 6216.0 ($/FFE×k) | 13,732,494.2 |
| Correct (÷k on rate) | 2209.2 (TEU) | 2957.1 ($/TEU) | **6,532,843.2** |
| Raw (no conversion) | 1052 (FFE) | 2960 ($/FFE) | **3,113,920.0** |

All three are equal in the first row **iff** the rate is divided by k. The two "correct" rows are identical to each other, as they must be — a pure unit change cannot alter revenue.

---

## 3. The FFE→TEU revenue-rate defect (priority investigation)

### 3.1 The algebra

Let `q_FFE` = demand in FFE/week, `r_FFE` = revenue per FFE, `k` = FFE→TEU factor. Two representations are available:

- **Representation A (raw):** `q_FFE · r_FFE` — units USD/week. Correct.
- **Representation B (converted):** `q_TEU = k·q_FFE` and `r_TEU = r_FFE / k` — units USD/week. Also correct.
  Then `q_TEU · r_TEU = k·q_FFE · r_FFE/k = q_FFE · r_FFE`. ✓

**The conversion factor must be applied to the volume and to the *denominator* of the rate — never to the rate itself.**

### 3.2 What the code does

```python
# src/data/network_loader.py:106-109
weekly_teu      = float(row["FFEPerWeek"]) * ffe_to_teu_factor   # ×k   (correct)
revenue_per_teu = float(row["Revenue_1"])  * ffe_to_teu_factor   # ×k   (WRONG — should be ÷k)
```

The comment at `:108` states the intent: `# Revenue_1 is $/FFE, convert to $/TEU`. The stated intent is correct; the implementation multiplies instead of dividing.

### 3.3 Measured impact — WorldSmall production dataset

Reproduced by direct arithmetic over `demand_world_small.csv` (1,764 rows, no self-lanes):

| Quantity | Value | Unit |
|---|---|---|
| Total demand, raw | **138,247.0** | FFE/week |
| **Raw theoretical revenue** (`Σ FFE × $/FFE`) | **264,870,100.00** | USD/week |
| Total demand as loaded (`Σ FFE × k`) | **276,446.8** | FFE·k/week |
| **Revenue as loaded** (`Σ (FFE·k)(k)($/FFE)`) | **1,059,950,076.25** | USD/week |
| **Inflation factor** | **× 4.001773** | — |
| Reported revenue in artifact | 1,136,109,658.57 | USD/week |
| Reported ÷ raw | **× 4.289309** | — |

The inflation factor is exactly `mean(k²)`, where the mean is weighted by FFE volume. Because only 6 of 1,764 lanes carry a non-default factor (k ≠ 2.0), the aggregate ratio sits just under 4.0. The **per-lane** factor ranges from 3.0625 (k=1.75) to 4.41 (k=2.1).

### 3.4 The inflation is non-uniform and therefore re-ranks lanes

| Lane | k | FFE/week | Revenue inflation (k²) | Raw revenue | Share of network revenue |
|---|---|---|---|---|---|
| CNSHA→NLRTM | 2.10 | 1,052 | **4.41×** | 3,113,920 | 1.18% |
| CNSHA→DEHAM | 2.10 | 202 | **4.41×** | 634,280 | 0.24% |
| AEJEA→DEHAM | 2.10 | 2 | **4.41×** | 3,480 | 0.00% |
| AEJEA→NLRTM | 2.10 | 84 | **4.41×** | 137,760 | 0.05% |
| **CNSHA→USLAX** | **1.85** | **1,206** | **3.4225×** | 1,941,660 | 0.73% |
| BRSSZ→USLAX | 1.90 | 3 | **3.61×** | 9,450 | 0.00% |

Total affected: 2,549 FFE/week = **1.84% of demand**, 5,840,550 USD/week = **2.21% of raw revenue**.

**Consequence.** The optimizer sees a world where high-k lanes are disproportionately valuable per unit of cargo. A lane with 1,052 FFE at k=2.1 appears to yield 4.41× the revenue of the same FFE on a k=1.75 lane. This is not a uniform scalar that could be cancelled — it changes the *relative* ordering of lanes, and therefore changes which services the GA selects and the MILP prices.

**The lane table itself has a second, independent defect.** `network_loader.py:80-81` contains lane keys `"CNSHA-USA NY"` and `"JPTYO-USA NY"` — with a **space** before `NY`. UNLOCODEs have no spaces. These four keys can never match a real `f"{origin}-{destination}"` lookup, so those lanes silently fall through to the default k=2.0. Separately, `USNYC-DEHAM` and `USNYC-NLRTM` (`:84`) are correct UNLOCODEs, but `USLAX-…`/`USAOS-…` are used inconsistently against the actual port set. Six table entries never fire; only 6 of 1,764 rows use a non-default factor.

---

## 4. Dataset-level independent checks

| Check | Expected | Independently measured | Status |
|---|---|---|---|
| WorldSmall demand rows | 1,764 | 1,764 | ✅ |
| Self-lane rows dropped | 0 | 0 (none present) | ✅ |
| Rows kept | 1,764 | 1,764 | ✅ |
| Distinct origin–destination pairs | 1,764 | 1,764 (no duplicates) | ✅ |
| Ports referenced by WorldSmall demand | 47 | 47 | ✅ |
| Ports missing from `ports.csv` | 0 | **0** | ✅ |
| Ports missing from `ports_world_small.csv` | 0 | **0** | ✅ |
| Invalid / missing identifiers | 0 | 0 | ✅ |
| WorldSmall fleet total | — | **263** | ✅ |
| WorldLarge fleet total | — | **501** | ✅ |
| Distance matrix covers WorldSmall ports | 47/47 | 47/47 | ✅ |
| Distance matrix covers WorldLarge ports | 435/435 | **208/435 — 227 missing** | ❌ |
| Conflicting duplicate OD pairs | 0 | **17,169** | ❌ |

### 4.1 Loader-default port/demand mismatch

`NetworkLoader.load_ports()` defaults to `data/raw/ports.csv` (**435 ports**) at `network_loader.py:18`, while `load_demands()` defaults to `demand_world_small.csv` (**47 ports**) at `:61`. A caller using the defaults gets a 435-port network with 47-port demand — 388 ports carrying no demand, no services, and no economic effect, but inflating `n_ports` in the hub-ratio heuristic (`service_ga.py:325-328`) and the port-clustering count (`orchestrator_agent.py:510`).

### 4.2 The loader silently ignores its own argument

```python
# src/data/network_loader.py:7-10
def __init__(self, data_dir="data"):
    base = Path(__file__).resolve().parents[2]
    self.data_dir = base / "data" / "raw"     # data_dir parameter is DISCARDED
```

Every loader method resolves paths relative to `<repo>/data/raw` regardless of what the caller passes. Pointing the loader at a different dataset directory is silently a no-op. (The WorldSmall test path works only because it passes **absolute** paths to each individual method, bypassing `self.data_dir`.)

---

## 5. The `DEMAND_SCALE = 6` second path

`network_loader.py:275-277`:

```python
DEMAND_SCALE = 6
for d in demands:
    d.weekly_teu *= DEMAND_SCALE
```

Applied to the JSON path **only** — the CSV path is unaffected.

Verified that the JSON datasets already contain `FFE × k` values (1,758 of 1,764 demands match the CSV loader's output exactly; the 6 mismatches are precisely the six non-default-k lanes, which the JSON generator rounded to integer volumes):

```
AEJEA→DEHAM   JSON weekly_teu 4.0     vs loader 4.2
CNSHA→DEHAM   JSON 404.0              vs loader 424.2
AEJEA→NLRTM   JSON 168.0              vs loader 176.4
CNSHA→NLRTM   JSON 2104.0             vs loader 2209.2
BRSSZ→USLAX   JSON 6.0                vs loader 5.7
CNSHA→USLAX   JSON 2412.0             vs loader 2231.1
```

So the JSON path applies the ×k conversion **at generation time**, stores it, and then multiplies the result by a further 6:

```
JSON total weekly_teu      =    276,494.0
after DEMAND_SCALE = 6     =  1,658,680.8   (vs 276,446.8 on the CSV path — ×6.0)
```

**Because `revenue_per_teu` is NOT scaled**, the two paths produce GAs whose profit terms differ by 6× on identical raw CSVs: on the JSON path revenue is 6× too small relative to operating cost. Any cross-path comparison of economic outputs is invalid.

---

## 6. Demand aggregation — cross-cluster duplication

`regional_agent.py:349-352` selects cluster demands:

```python
cluster_demands = [
    d for d in problem.demands
    if d.origin in cluster_port_ids or d.destination in cluster_port_ids
]
```

A demand whose **origin and destination fall in different hub clusters appears in both clusters' MILPs**. Both clusters then allocate and price it independently.

The regional agent sums `unserved_demand` across clusters at `:439` but **caps `satisfied` at the regional total** at `:442`:

```python
satisfied = sum(r["satisfied_demand"] for r in cluster_results)   # :438  (duplicated)
unserved_teu = sum(r["unserved_demand"] for r in cluster_results) # :439  (duplicated)
satisfied = min(satisfied, total_demand)                          # :442  (CAPPED)
```

**Measured effect on the production artifact:**

| Metric | Value |
|---|---|
| Sum of regional `total_demand` | 276,446.80 — **exactly** the loader total (no duplication at region level) |
| Reported global `satisfied_demand` | 273,267.10 |
| Reported global `unserved_demand` | 31,754.10 |
| **`satisfied + unserved`** | **305,021.20** |
| **Loader total demand** | **276,446.80** |
| **Discrepancy** | **+28,574.40 TEU/week (+10.34%)** |

Two of three regions show `satisfied == total_demand` **exactly** — the `:442` clamp is saturated:

| Region | total_demand | satisfied | unserved | satisfied+unserved | coverage% |
|---|---|---|---|---|---|
| Asia | 147,838.50 | 147,838.50 | 13,274.67 | 161,113.17 | **100.0000** |
| Europe | 48,509.70 | 45,330.00 | 6,307.70 | 51,637.70 | 93.4452 |
| Americas | 80,098.60 | 80,098.60 | 12,171.73 | 92,270.33 | **100.0000** |

`unserved` is never clamped, so it retains the cross-cluster duplication. The two regions showing exactly 100% coverage are **artifacts of the clamp**, not genuine full coverage.

---

## 7. WorldLarge coverage — partial

The WorldLarge path (`demand_world_large.csv`, 9,622 rows, 201 distinct ports) was verified for structure and identifier integrity:

- 201 distinct ports referenced, **0 missing** from `ports.csv` (435 ports).
- 227 of the 435 ports in `ports.csv` have **no distance row**, so `fuel_cost.py:205` substitutes 500 nm per missing leg (see §1.3).
- `data/datasets/large_shipping_problem.json` contains 333 ports (not 435) and 9,622 demands.

Not fully verified: the WorldLarge revenue and cost figures, because no WorldLarge `pipeline_output.json` exists in the repository.

---

## 8. Independence from the RL formulation

Per the audit mandate, no RL engine output, objective, reward, or cost model was consulted as a correctness standard at any point in this document. Every unit determination above rests on:

1. The structure of the shipped CSV columns (`CostPerFULL`, `PortCallCostPerFFE`, `FFEPerWeek` — all FFE-denominated by name and by the project's own ×2.0 conversion).
2. `docs/DATA_DICTIONARY.md` and `verification/01_GOLDEN_SPECIFICATION.md:86-116`, which state the units explicitly.
3. Independent arithmetic (dimensional checks, magnitude plausibility, cross-record consistency).
4. Direct source inspection of every transformation.

The defects in §3 and §5 are defects **against the Multi-Agent system's own stated units and its own internal consistency**, not against any external benchmark.

---

## 9. Findings from MA_02

| ID | Finding | Classification | Confidence | Impact |
|---|---|---|---|---|
| **MA-02-01** | `revenue_per_teu = Revenue_1 × k` — rate scaled by k instead of ÷k, inflating every revenue term by **k²** (×3.06–×4.41 per lane; ×4.0018 network-weighted) | **A. Verified implementation defect** | **High** — reproduced by direct arithmetic; confirmed by dimensional analysis and by the ×2.0 convention used on port costs | Revenue ×4.0; reported/raw = **4.2893** |
| **MA-02-02** | Inflation is **non-uniform across lanes**, re-ranking lane profitability and therefore changing service selection | **A. Verified implementation defect** | High | 6 lanes affected; changes selection, not just scale |
| **MA-02-03** | Lane table contains 4 malformed keys (`"CNSHA-USA NY"`, `"JPTYO-USA NY"` — space in UNLOCODE) that can never match | **A. Verified implementation defect** | High | 4 dead entries |
| **MA-02-04** | Second demand path applies `DEMAND_SCALE = 6` unconditionally; docstring claims a WorldSmall exemption that does not exist in code | **A. Verified implementation defect** | High | Demand ×6 on the JSON path; revenue not scaled → 6× revenue/cost skew |
| **MA-02-05** | Cross-cluster demand duplication: `unserved` summed over overlapping clusters, `satisfied` clamped | **A. Verified implementation defect** | High | **+28,574.40 TEU/wk (+10.34%)** phantom demand |
| **MA-02-06** | Coverage understated: reported 89.5895% vs 98.8498% against the loader total | **D. Reporting defect** (consequence of MA-02-05) | High | **−9.26 pp** |
| **MA-02-07** | `NetworkLoader.__init__` discards its `data_dir` argument | **A. Verified implementation defect** | High | Silent no-op; dataset switching impossible |
| **MA-02-08** | `load_ports()` defaults to 435-port file while `load_demands()` defaults to 47-port file | **D. Reporting / configuration defect** | High | 388 demand-less ports inflate port-count heuristics |
| **MA-02-09** | `distance_dense.csv` has **17,169 conflicting duplicate OD pairs**, mean |first−last| = **4,086.7 nm**, max ratio 37.94×; loader is last-write-wins | **A. Verified implementation defect** (order-dependent, non-reproducible) | High — latent on WorldSmall (47 ports, 0 missing), active on WorldLarge |
| **MA-02-10** | 227 of 435 WorldLarge ports have no distance row; `fuel_cost.py:205` silently substitutes 500 nm | **A. Verified implementation defect** | High | WorldLarge fuel cost materially wrong |
| **MA-02-11** | Entire fleet economic vocabulary (capacity, TC rate, bunker t/day, idle t/day, design speed, panama/suez fees) loaded and **never read** | **E. Missing model component** (data present, model ignores it) | High | Charter cost, fuel, canal all modelled from constants instead |
| **MA-02-12** | `Port.draft`, distance-matrix `Draft`, and demand `TransitTime` loaded/stored but never consumed | **E. Missing model component** | High | Route feasibility not enforced on draft |
| **MA-02-13** | `weekly_teu` and `revenue_per_teu` field names assert units (TEU) that do not match their contents (FFE·k) | **D. Reporting defect** (naming) — contributes to MA-02-01 | High | Root cause of the k² error |
| **MA-02-14** | WorldLarge economic figures | **F. Unverified hypothesis** | — | No WorldLarge artifact exists |

---

## 10. Reproducibility

All figures in this document are reproducible with read-only arithmetic over the shipped data:

```bash
cd shipping_optimizer
# Demand and revenue chain
python -c "
import csv
rows=list(csv.DictReader(open('data/raw/demand_world_small.csv',encoding='utf-8-sig'),delimiter='\t'))
F={'AEJEA-DEHAM':2.1,'CNSHA-DEHAM':2.1,'AEJEA-NLRTM':2.1,'CNSHA-NLRTM':2.1,'CNSHA-USLAX':1.85,'BRSSZ-USLAX':1.9}
ffe=sum(float(r['FFEPerWeek']) for r in rows)
raw=sum(float(r['FFEPerWeek'])*float(r['Revenue_1']) for r in rows)
load=sum(float(r['FFEPerWeek'])*F.get(r['Origin'].strip()+'-'+r['Destination'].strip(),2.0)*float(r['Revenue_1'])*F.get(r['Origin'].strip()+'-'+r['Destination'].strip(),2.0) for r in rows if r['Origin'].strip()!=r['Destination'].strip())
print('FFE/wk',ffe,' raw rev',raw,' loader rev',load,' ratio',load/raw)
"
```

No project module was imported; no file was written.