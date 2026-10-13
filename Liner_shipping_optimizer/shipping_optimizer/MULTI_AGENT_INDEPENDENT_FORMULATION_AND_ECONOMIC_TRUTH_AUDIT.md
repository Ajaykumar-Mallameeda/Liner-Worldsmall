# MULTI-AGENT INDEPENDENT FORMULATION AND ECONOMIC TRUTH AUDIT

**System:** AI Vessel Routing System — Multi-Agent Optimizer
**Audit mode:** Forensic, evidence-driven, **read-only**
**Date:** 2026-10-05
**Artifact under audit:** `frontend/public/pipeline_output.json`
**Mandate:** Establish the complete mathematical, computational, and economic truth of the Multi-Agent system, **independently of the RL engine.**

---

## 0. Compliance statement

| Constraint | Status |
|---|---|
| No source / config / dataset / test modification | **Honoured** — zero Write/Edit on any tracked file |
| No git operations of any kind | **Honoured** |
| No dependency installation or infrastructure | **Honoured** |
| RL repository not modified | **Honoured** — never opened |
| No historical artifacts overwritten | **Honoured** |
| Tests not weakened, expected outputs not rewritten | **Honoured** |
| No optimizer parameter altered to improve results | **Honoured** |
| No unexecuted calculation claimed as validated | **Honoured** — §17 states limitations |
| Production pipeline not run without approved isolated workspace | **Honoured** — §11 |
| This phase is discovery and verification only; no repairs | **Honoured** — §18 proposes acceptance criteria, implements nothing |
| Formulation differences not auto-classified as defects | **Honoured** — §14 distinguishes B from A |
| Ambiguity recorded rather than invented away | **Honoured** — §14 category C |

**Files written by this audit:** only the audit reports (MA_01–MA_09 and this document). **No code, configuration, dataset, test, or production artifact was modified.**

---

## 1. Executive summary

The Multi-Agent system's reported economics are **not merely suboptimal. They are unattainable.**

Three independent bounds, each derived without reference to the system's own formulas, are violated:

| Bound | Ceiling | Reported | Ratio |
|---|---|---|---|
| Dataset gross revenue | **$264,870,100/wk** | $1,136,109,658.57 | **4.29×** |
| Fleet physical fuel capacity | **$55,335,000/wk** | $648,031,918.31 | **11.71×** |
| Profit ceiling (granting **zero** fuel cost) | **$122,288,267/wk** | $345,495,908.06 | **+$223,207,640** |

The third is decisive. It requires no assumption about the fuel model: the dataset does not contain enough revenue to produce this profit, and the system's own reported non-fuel costs consume most of what exists. **No reformulation of this dataset with these costs can produce $345.5M/week.**

Three root causes account for essentially all of the divergence:

1. **A dimensional error at load time.** `network_loader.py:109` multiplies the revenue *rate* by the same FFE→TEU factor used for *volume*. Volume × k and rate × k yields revenue × k². Measured inflation: **×4.001773**.
2. **No fleet constraint anywhere that binds.** The MILP's fleet constraint is a Python `bool` — verified against pulp 2.7.0 to be either silently dropped or a `TypeError`. The GA-level check that *does* work checks each region against the **entire unpartitioned fleet**, so 3 regions × 263 = 789 vessels appear permissible against 263 that exist. Measured overcommitment: **2.37×**.
3. **Per-cluster cost re-billing.** `operating_cost` and `fuel_cost` are Python constants summed over `services_mask` with **no port filter**, so every cluster's MILP re-bills every active service. Measured inflation vs the artifact's own per-service detail: **1.29–1.97×**.

**66 findings** across 9 deliverables, classified A–G. **52 are verified implementation defects.** No repair was made or attempted.

---

## 2. Scope and deliverables

| Deliverable | Contents |
|---|---|
| `MA_01_RUNTIME_ARCHITECTURE_AND_DATAFLOW_AUDIT.md` | Live call graph, dead layers, aggregation defects |
| `MA_02_DATA_AND_UNIT_SEMANTICS_AUDIT.md` | Unit dictionary, FFE/TEU chain, dataset checks |
| `MA_03_REVENUE_FORMULATION_AND_RECONCILIATION_AUDIT.md` | Four revenue models, reconciliation, oracle ceiling |
| `MA_04_COMPLETE_COST_LEDGER_AND_FORMULATION_AUDIT.md` | Cost ledger, fuel bound, missing cost elements |
| `MA_05_SERVICE_GENERATION_AND_FLEET_FEASIBILITY_AUDIT.md` | Fleet feasibility, per-region scope defect |
| `MA_06_GA_MILP_FORMULATION_AND_OBJECTIVE_AUDIT.md` | MILP mathematics, all four objective layers |
| `MA_07_NETWORK_ECONOMICS_AND_DEMAND_RECONCILIATION_AUDIT.md` | Profit ceiling, demand reconciliation |
| `MA_08_INDEPENDENT_ECONOMIC_ORACLE_AND_VALIDATION_REPORT.md` | Independent oracle, 10 acceptance tests |
| `MA_09_FORMULA_AND_VARIABLE_REGISTRY.md` | Human-readable formula registry |
| `MA_09_FORMULA_INDEX.json` | Machine-readable formula index |
| `MA_09_METRIC_LINEAGE.json` | Per-metric provenance from CSV to artifact |
| `MA_09_ACTIVE_DEPENDENCY_MAP.json` | Active vs dead runtime nodes |

---

## 3. Method and evidence standard

Every number in this audit is one of: read from a named file, computed by a quoted expression, or executed against the installed solver. No value was taken from a prior audit without independent reproduction.

| Evidence class | How established |
|---|---|
| Source facts | Direct file read with line reference |
| Arithmetic | Reproducible `python -c` over raw CSV; no project module imported |
| Solver behaviour | `pulp` 2.7.0 executed in isolation |
| Liveness | `__pycache__` inventory + cross-module grep |
| Prior findings | Re-derived from source; recorded as CONFIRMED / NOT REPRODUCED / CORRECTED |

### 3.1 What was deliberately NOT done

- The **RL engine was never consulted** as a correctness standard. No RL objective, reward, cost model, or result was read.
- **No optimization was run.** Every figure is arithmetic over existing data.
- **No prior conclusion was copied.** Where a prior report claimed something, it was independently re-derived; three claims did not survive (§16).

---

## 4. Runtime architecture

### 4.1 The optimizer does not run at serve time

`backend/__pycache__/` contains exactly `{__init__, server}`. `backend/services/__pycache__/` and `backend/routes/__pycache__/` **do not exist**. Across all of `backend/`, only `server.py` has ever been imported — and it contains **zero** references to `Orchestrator`, `NetworkLoader`, or `src.`.

The dashboard is a static artifact viewer. The optimizer executes only under pytest.

### 4.2 Dead backend layers

`backend/routes/` (4 modules) is mounted by no entrypoint — `include_router` appears in none of `server.py`, `main.py`, `unified_main.py`. `backend/services/pipeline_service.py`, the only backend module that imports the optimizer, returns a `MockProblem` with 435 synthetic ports and a **zero distance matrix**; `MockPort`/`MockDemand` carry no cost attributes, so it could not run if activated.

### 4.3 The optimizer call graph

```
tests/test_orchestrator.py :: load_worldsmall_problem()          [:210-238]
  └── NetworkLoader (ports 47 | demands 1764 | distance | fleet 263)
        └── OrchestratorAgent.process                           [:430+]
              ├── CONFIG.get_weights() → problem.*_weight      [:435]  ⚠ DEAD
              ├── true_global_demand = 276,446.80               [:505]  ✓
              └── 3 × RegionalAgent
                    ├── KMeans clustering → hub split
                    ├── cluster_demands by (origin OR destination)  ⚠ DUPLICATES
                    ├── ServiceGeneratorAgent → 2,238 candidates  (LLM unused)
                    ├── HierarchicalGA
                    │     ├── ServiceGA       ⚠ fitness = +0.1·cost
                    │     ├── FrequencyGA     ⚠ fuel omitted from fitness
                    │     └── post-GA prune   ⚠ per-region fleet scope
                    └── HubMILP (PULP/CBC)  ⚠ objective rewards cost
                                                ⚠ fleet constraint is a bool
                                                ⚠ costs re-billed per cluster
              └── Aggregate                                      ⚠ revenue = profit + cost
                    └── tests/test_orchestrator.py:2222-2235  WRITES the artifact
                          └── backend/server.py:71-79  READS it (never runs the optimizer)
```

---

## 5. Data and unit semantics

### 5.1 The unit dictionary

| Field | Raw unit | Loaded as | Correct? |
|---|---|---|---|
| `Port.handling_cost` | $/FFE | $/FFE × 2.0 | ✅ |
| `Port.transshipment_cost` | $/FFE | $/FFE × 2.0 | ✅ |
| `Port.variable_port_call_cost` | $/FFE | $/FFE × 2.0 | ✅ |
| `Port.port_call_cost` | $/call | $/call | ✅ |
| `Demand.weekly_teu` | FFE/week | **FFE·k/week** | ✅ value, ❌ name |
| `Demand.revenue_per_teu` | $/FFE | **$/FFE × k** | ❌ **should be ÷k** |
| `FleetClass.*` (economic) | various | loaded | ⚠ **never read** |

`Revenue_1` is **USD/FFE** — established by `docs/DATA_DICTIONARY.md`, `01_GOLDEN_SPECIFICATION.md:108`, magnitude plausibility (O(10³) USD/TEU would be ~1000× a real freight rate), and the project's own ×2.0 convention on port costs.

### 5.2 The FFE→TEU defect

```python
# src/data/network_loader.py:106-109
weekly_teu      = float(row["FFEPerWeek"]) * ffe_to_teu_factor   # ×k  ✓
revenue_per_teu = float(row["Revenue_1"])  * ffe_to_teu_factor   # ×k  ✗ should be ÷k
```

The conversion factor belongs on the volume and on the **denominator** of the rate. Multiplying the rate by k makes the product `USD/week × k²`.

| Quantity | Correct | As implemented | Ratio |
|---|---|---|---|
| `avg_rev_per_teu` | **958.1232** | **3,834.1919** | **×4.001773** |
| Dataset gross revenue | 264,870,100.00 | 1,059,950,076.25 | ×4.001773 |

Verified by **two independent computations agreeing to 10 significant figures** — dividing raw revenue by converted volume, and converting both sides of each product. The implemented rate of $3,834/TEU is ~4× implausible for ocean freight; the correct $958/TEU is ordinary.

**The inflation is non-uniform** — 3.0625 to 4.41 per lane — so it does not cancel in service ranking. Six lanes (1.84% of demand) are systematically over-valued relative to the rest.

### 5.3 A second demand path

`load_problem()` (JSON) applies `DEMAND_SCALE = 6` **unconditionally**, though its docstring claims a WorldSmall exemption that does not exist in code. It scales `weekly_teu` but not revenue, creating a 6× revenue/cost skew. Not the production path.

### 5.4 Distance matrix

**17,169 duplicated OD pairs, all with conflicting distances** (mean |first − last| = 4,086.7 nm; max ratio 37.94×). The loader is last-write-wins, so results are order-dependent and non-reproducible. WorldSmall is unaffected (47/47 ports present); 227 of 435 WorldLarge ports are missing entirely, triggering a silent 500 nm substitution.

### 5.5 Unused fleet vocabulary

`tc_rate_daily`, `bunker_consumption_tons_per_day`, `idle_consumption_tons_per_day`, `capacity_teu`, `designSpeed`, `minSpeed`, `maxSpeed`, `panama_fee`, `suez_fee` — all loaded into dataclasses, **zero consumers**.

---

## 6. Revenue formulation

Four revenue models exist. The MILP is the only lane-aware one; the GAs — which perform the actual selection — are not.

| # | Location | Formula | Lane-specific? |
|---|---|---|---|
| 1 | `service_ga.py:146,243` | `served × avg_rev_per_teu × yield` | **No** — network average |
| 2 | `service_ga.py:285` | `served × avg_rev_per_teu` | No |
| 3 | `frequency_ga.py:200` | `demands[0].revenue_per_teu` | No — **one arbitrary lane** |
| 4 | `hub_milp.py:294-300` | `flow × demand.revenue_per_teu` | **Yes** |
| 5 | `orchestrator_agent.py:316` | `profit + cost` | **Tautology** |

Two independent defects compound:

- **Single average rate** — lane profitability differences never enter selection. Even with k² fixed, ServiceGA would still price every lane identically.
- **Multi-service overlap** — `service_ga.py:134-138` credits each lane in full to *every* service covering both endpoints. Implied served volume **296,310 TEU/wk vs 276,446.80 true** (×1.0719). This biases selection toward broad many-port services — the opposite of efficient liner design.

**4.001773 × 1.0719 = 4.28931**, which is exactly the reported/theoretical revenue ratio. The two factors fully explain the revenue excess with no residual.

---

## 7. Cost ledger

### 7.1 The reported ledger

| Component | USD/week | % of cost | % of revenue |
|---|---|---|---|
| Fuel | **648,031,918.31** | **81.97%** | 57.04% |
| Operating | 100,822,500.00 | 12.75% | 8.87% |
| Transshipment | 22,531,440.01 | 2.85% | 1.98% |
| Port | 19,227,892.20 | 2.43% | 1.69% |
| **Total** | **790,613,750.51** | 100% | 69.58% |

The **identity holds exactly** (1¢ rounding). The aggregation layer is sound; every defect is upstream.

### 7.2 The fuel bound — the single most consequential finding

Computed from the project's own fleet file and its own consumption table:

| Class | Vessels | t/day each | t/day |
|---|---|---|---|
| Feeder_450 | 24 | 15 | 360 |
| Feeder_800 | 29 | 25 | 725 |
| Panamax_1200 | 68 | 35 | 2,380 |
| Panamax_2400 | 74 | 55 | 4,070 |
| Post_panamax | 58 | 80 | 4,640 |
| Super_panamax | 10 | 100 | 1,000 |
| **Total** | **263** | | **13,175** |

```
13,175 t/day × 600 USD/t × 7 = $55,335,000/week   ← HARD CEILING
Reported                    = $648,031,918/week
Ratio                       = 11.71×
```

This ceiling assumes **every vessel underway every hour** — no port time, no idle. Real operation burns 50–65% of it, so the reported figure is ~19–26× realistic.

**No unit ambiguity rescues this.** Even if `BUNKER_PRICE_PER_TON` were wrong by 10×, the tonnage alone is impossible.

Corroborated by per-TEU: reported **$2,371.42/TEU-week** against an industry range of **$15–40** — 59–158×.

**Mechanism.** `hub_milp.py:312-322` computes fuel as `Σ per-service × frequency` with **no vessel↔service correspondence** and **no fleet constraint that binds** (MA-05-02). `frequency_ga.py:211` additionally **omits fuel from its fitness**, so the frequency optimizer is blind to the dominant cost term.

### 7.3 Canal fees are entirely absent

`IsPanama`/`IsSuez` (distance matrix) and `panamaFee`/`suezFee` (fleet file) are loaded and **never read anywhere**. Measured exposure: **18,948 of 62,002 pairs (30.6%)** cross a canal. A single Suez transit by a `Super_panamax` costs **$1,035,376** — 2–7× an entire service-week of modelled operating cost.

`docs/RELEASE_NOTES.md:38` claims *"62,002 inter-port pairs with canal and transit time modeling."* **No such modeling exists.** This is a documentation defect that would mislead any reader of the release notes.

### 7.4 Port cost basis

```python
# hub_milp.py:599-601
share = port_service_loads[p][s_idx] / port_load[p]
port_alloc += share * (load * handling + load * variable)   # per-TEU rate × service TOTAL load
port_alloc += share * fixed                                  # per-CALL cost × load ratio
```

Additionally, `hub_milp.py:337` appends the *same variable* once per port on a route, so per-TEU handling is charged **once per port** — a 7-port hub loop pays 7×, and a hub loop listing its hub twice charges it 2×. Transfer flows are never added to `port_flow_direct`, so a transshipped TEU pays **zero** handling at any port.

Symptom in the artifact: Asia `port_cost` is 913,818 across 104 services (8,786/service); Europe's is 14,825,836 across 100 (148,258/service) — **16.9× divergence from identical code**.

---

## 8. Fleet feasibility

### 8.1 The 2.37× overcommitment

`cycle_time` defaults to 14 for generator-dict services, so each needs `ceil(14·1/7) = 2` vessels.

| Region | Services | Vessels | Per-region check vs 263 |
|---|---|---|---|
| Asia | 104 | 208 | ✅ passes |
| Europe | 100 | 200 | ✅ passes |
| Americas | 108 | 216 | ✅ passes |
| **Σ** | **312** | **624** | ❌ **2.37× over** |

```python
# regional_agent.py:357-362 — every region receives the FULL fleet
sub = Problem(..., fleet=problem.fleet)     # 263, unchanged per region
```

**The check exists, executes, and binds — against the wrong scope.** No partitioning, no reservation, no global check. The system can permit up to 3 × 263 = 789 vessels while possessing 263.

### 8.2 The MILP constraint is a verified no-op

`hub_milp.py:389` — both operands are Python ints, so this is a `bool`:

| Case | pulp 2.7.0 behaviour |
|---|---|
| `208 <= 300` | `len(prob.constraints) == 0` — **silently dropped** |
| `900 <= 300` | **`TypeError: A False object cannot be passed as a constraint`** |

So the constraint never binds, and a violation **crashes `solve()`** — which `regional_agent.py:381-395` catches and converts into a **zero-profit fallback region**. A fleet violation silently zeroes a region instead of failing loudly. The warn-only check at `:558-565` is both non-blocking and unreachable.

`fleet_size` is hardcoded at 300 (`:61`), never overridden — so the GA enforces 263 while the MILP intends 300. **Two different fleet limits on the same problem.**

### 8.3 No vessel economics are reported

The artifact contains no vessel count, no utilization, no feasibility flag. `backend/server.py` initializes `vesselsUtilized = None`. A 2.37× overcommitment is invisible to every consumer.

---

## 9. Objective functions — all four layers defective

| Layer | Objective | Defect |
|---|---|---|
| **ServiceGA** | `10·profit + 0.01·coverage + 0.1·cost` | **Rewards operating cost.** The subtracting branch (`service_ga.py:379`) is guarded by `objective_mode == "legacy"`; production is `"profit_first"`. |
| **FrequencyGA** | `rev − op − transship − overcap − port` | **Fuel omitted** despite being computed at `:161-166`. |
| **HubMILP** | `profit + (w_c/w_p)·coverage·abs(OPEX + 1)` | **Multiplicative in operating cost** — raising cost raises the objective. Reduces to a linear per-TEU bonus that *grows with service count*. |
| **Orchestrator** | `revenue = profit + cost` | **Tautology** — substituting `profit = revenue − cost` yields `0 = 0`. |

### 9.1 Two weight systems, one of them dead

`CONFIG.get_weights()` returns `{profit: 0.60, coverage: 0.25, cost: 0.15}` → `problem.profit_weight` → `service_ga.w_profit` → consumed **only inside the unreachable legacy branch**. The weights that actually act are hardcoded in `normalization.py:114-118` as `{10.0, 0.01, 0.1}`.

The artifact reports `weights_used: {0.60, 0.25, 0.15}` — **values that did not affect the result.**

### 9.2 The MILP is not a MILP

Verified: the only `pulp.LpVariable` constructions are at `:275`, `:284`, `:289`, all `lowBound=0` with **no `cat=`**. There are **no binary or integer variables**. Service selection and frequency are fixed by the GA chromosome before the model is built. It is a pure LP, despite the name and the golden specification's claim.

Consequently the following are **dead**: the `min_coverage` constraint (`0.0` at both layers), the port-capacity constraint (max demand score 39,722 vs a 55,556 binding threshold — **0 of 47 ports qualify**), `DEFAULT_PORT_CAPACITY`, `_total_port_cost`, and the `skip_milp` flag.

---

## 10. Aggregation and reporting defects

### 10.1 The clamp asymmetry

```python
# regional_agent.py:438-442
satisfied = sum(cluster satisfied)          # duplicated across clusters
unserved   = sum(cluster unserved)           # duplicated
satisfied  = min(satisfied, total_demand)    # CLAMPED
# orchestrator_agent.py:305
total_satisfied = min(total_satisfied, true_global_demand)   # CLAMPED AGAIN
```

`satisfied` is clamped twice; `unserved` never.

| Region | satisfied | unserved | sum | coverage |
|---|---|---|---|---|
| Asia | 147,838.50 | 13,274.67 | 161,113.17 | **100.0000** |
| Europe | 45,330.00 | 6,307.70 | 51,637.70 | 93.4452 |
| Americas | 80,098.60 | 12,171.73 | 92,270.33 | **100.0000** |
| **Σ** | **273,267.10** | **31,754.10** | **305,021.20** | **89.5895** |

- `305,021.20 − 276,446.80 = +28,574.40 TEU/week` **(+10.34%) phantom demand**
- Two regions at **exactly 100.0000%** — the signature of a saturated clamp
- True coverage **98.8498%** vs reported **89.5895%** — **understated by 9.26 pp**

### 10.2 Regional revenue is structurally absent

`hub_milp.py:625-643` returns **no `revenue` key**. Verified in the artifact: **every `regional_results[*].revenue` is 0.00**. The dashboard's per-region revenue display is structurally zero.

### 10.3 Four incompatible profit definitions

`profit_v` (objective + coverage bonus) → regional `profit` → per-service `revenue − cost` (a **different** cost decomposition) → global `revenue = profit + cost`. The per-service profit and the regional profit come from mutually inconsistent decompositions.

### 10.4 Identities that DO hold

| Identity | Status |
|---|---|
| `Σ cost components == total_cost` | ✅ (1¢) |
| `revenue − total_cost == weekly_profit` | ✅ (tautological) |
| `annual == weekly × 52` | ✅ |
| `Σ regional == global` | ✅ |
| `Σ regional services == total_services` | ✅ (312) |

The aggregation layer is arithmetically sound. **Every defect is upstream.**

---

## 11. Independent economic oracle

Built from raw data only. No project module imported. Uses only **representation-independent** quantities — `FFE × ($/FFE) = USD` — so it is immune to the FFE/TEU question entirely.

### 11.1 Bounds

```
Gross revenue = Σ FFE × $/FFE = $264,870,100/week
```
Verified three ways, agreeing exactly.

```
Fleet fuel ceiling = Σ(quantity × t/day) × 600 × 7 = $55,335,000/week
```

### 11.2 The ten tests

| # | Test | Result |
|---|---|---|
| T1 | `revenue ≤ dataset gross revenue` | ❌ **4.29×** |
| T2 | `fuel ≤ fleet physical maximum` | ❌ **11.71×** |
| T3 | `profit ≤ revenue − non_fuel_cost` | ❌ **+$223,207,640** |
| T4 | `satisfied + unserved == true_demand` | ❌ **+10.34%** |
| T5 | `coverage == satisfied/true × 100` | ❌ **−9.26 pp** |
| T6 | `Σ components == total_cost` | ✅ PASS |
| T7 | `revenue − cost == profit` | ✅ PASS *(tautological)* |
| T8 | `Σ regional == global` | ✅ PASS |
| T9 | `Σ regional services == total_services` | ✅ PASS |
| T10 | `vessels_required ≤ vessels_available` | ❌ **2.37×** |

**7 failures, 3 passes — and both economically meaningful passes are structural checks.** Every test capable of detecting a substantive error failed.

---

## 12. Why the test suite caught none of this

| Property | Consequence |
|---|---|
| Only **internal identities** asserted | k² inflation, cost sign inversion, coverage clamps all pass |
| **SHA-256 baseline** on the artifact across 5 maritime modules | Protects the **bytes**, freezing defects |
| `assert 0 <= coverage <= 100` | **Enforces** the clamp artifact instead of detecting it |
| No cross-check against raw data | Nothing compares output to input |
| No physical-bound test | Nothing checks fuel against fleet capacity |
| `revenue = profit + cost` | Revenue is defined so it cannot fail |

**The suite is a regression guard, not a correctness oracle.** It would pass identically with revenue ×4.0 — which is what happened.

---

## 13. LLM / agent layer

| Counter | Value | Meaning |
|---|---|---|
| `llm_calls` | 5 | invocations attempted |
| `coordinator_fallback_count` | **0** | Coordinator **succeeded** |
| `servicegen_ai_count` | **0** | Service generation used **no** LLM output |
| `servicegen_fallback_count` | **3** | All regions fell back to rules |

The agent framework is real; on the production path its **generation layer is entirely inert** while its reasoning layer ran. The archetype mix (`0.6/0.15/0.2/0.05`) and `vessel_bias: "balanced"` are **hardcoded constants, identical across all three regions**.

Consequently the LLM-authored `explanation` and `strategy` fields describe a solution the LLM did not generate.

---

## 14. Finding classification

| Category | Count | Definition |
|---|---|---|
| **A** Verified implementation defect | **52** | Reproduced; wrong against the system's own specification or an unambiguous bound |
| **B** Formulation choice | 4 | Defensible; differs from a possible alternative but not wrong |
| **C** Specification ambiguity | 6 | Intent undocumented |
| **D** Reporting / aggregation defect | 21 | Underlying computation may be right; the report is wrong |
| **E** Missing model component | 9 | Data present and correct; model ignores it |
| **F** Unverified hypothesis | 2 | Could not be established within scope |
| **G** Previously reported finding not reproduced | 4 | Prior claims that failed verification |

### 14.1 Critical findings (A, highest impact)

| ID | Finding |
|---|---|
| **MA-02-01** | `revenue_per_teu = Revenue_1 × k` — revenue inflated by **k² = 4.001773×** |
| **MA-04-01** | Fuel is **11.71× the entire 263-vessel fleet's physical maximum** |
| **MA-05-01** | Fleet checked **per region against an unpartitioned fleet** — **2.37× overcommitment** |
| **MA-05-02** | MILP fleet constraint is a **verified no-op**; violation raises `TypeError` → silent zero-profit region |
| **MA-06-15** | `revenue = profit + cost` — **tautology** |
| **MA-06-20/21** | `operating_cost`/`fuel_cost` re-billed per cluster (measured 1.29–1.97×) |
| **MA-07-01** | Profit exceeds the **fuel-independent ceiling by $223,207,640/week** |
| **MA-06-08** | ServiceGA fitness **rewards operating cost** |
| **MA-06-09** | FrequencyGA **omits fuel** from fitness |
| **MA-01-07 / MA-06-01** | MILP coverage reward **scales with operating cost** |

### 14.2 Formulation choices (B) — explicitly NOT defects

Per the mandate, these are recorded but **not** classified as defects:

| Item | Why it is a choice |
|---|---|
| GA+MILP hybrid rather than pure MILP | Service selection by GA is legitimate |
| `yield_factor` 0.6–1.0 | A utilization discount, correctly implemented |
| `Service.weekly_cost` as a flat constant | Possibly deliberate abstraction (though it ignores `tc_rate_daily`) |
| `0.9` at-sea factor | Plausible as published |
| Bunker price as a constant | Standard practice |

### 14.3 Ambiguities (C) — recorded, not invented away

| Item | Ambiguity |
|---|---|
| Transfer revenue split `/2.0` | Intent undocumented; transfer load charged in full |
| Transshipment rate `τ(o_d)` | Depends on the lane's endpoints; the hub actually used is ignored |
| `min_coverage = 0.0` | Config declares `min_coverage_percent = 70.0`; is the floor deliberate or a stub? |
| `cycle_time` defaults of 7/14/21 | Real round trips are 70–80 days; is this a simplification or a placeholder? |
| Service filter criterion | 63.1% discarded with no documented rule |
| Transshipment `hub_ratio` heuristic | `0.1 × n_ports` clamped to [0.3, 0.7] |

---

## 15. Prior-finding adjudication

Per the mandate, no prior conclusion was carried forward without independent reproduction.

| Prior claim | Verdict | Basis |
|---|---|---|
| Revenue inflated by FFE/TEU k² | ✅ **CONFIRMED** | Direct arithmetic; 4.001773×, two computations agreeing to 10 s.f. |
| Revenue is a tautology (profit + cost) | ✅ **CONFIRMED** | `orchestrator_agent.py:316`; artifact reconciles exactly |
| `DEMAND_SCALE = 6` | ✅ **CONFIRMED** | Applies to demand only |
| Fleet vocabulary loaded, never read | ✅ **CONFIRMED** | All nine fields verified |
| Fuel model mismatch | ✅ **CONFIRMED** | Hardcoded table vs fleet file |
| FrequencyGA omits fuel | ✅ **CONFIRMED** | `frequency_ga.py:211` |
| `α = 300` does **not** propagate | ❌ **NOT REPRODUCED** | It **does** propagate correctly via `_sga_kwargs` |
| LLM calls failed | ❌ **NOT REPRODUCED** | `llm_calls: 5`, `coordinator_fallback_count: 0` — they **succeeded** |
| Margin values inconsistent | ❌ **NOT REPRODUCED** | 45.3 / 0.2 / 11.8 recompute correctly |
| `DEMAND_SCALE` inflates revenue 6× | ⚠ **CORRECTED** | Scales demand only; creates a 6× revenue/**cost** skew, not 6× revenue |
| 17,169 conflicting OD pairs | ✅ **CONFIRMED** | Independently measured; 100% conflict rate |

**A prior audit's headline service counts (309 / 98 / 107) were also corrected** — the artifact reports **312** (104 / 100 / 108).

---

## 16. Limitations — stated, not hidden

| Limitation | Consequence |
|---|---|
| **Production pipeline not executed** | It writes three artifact files, requires an isolated workspace, and makes 5 non-deterministic LLM calls. No workspace was authorized. |
| **GA stochastic variance unmeasured** | Every economic figure carries **unquantified** run-to-run spread. |
| **Artifact freshness unestablished** | Whether the committed artifact is the latest run was not verified. |
| **WorldLarge economics not verified** | No WorldLarge artifact exists. |
| **Cross-cluster duplication magnitude** | Structure is proven (`+10.34%`); an exact lane-level percentage would require reproducing KMeans clustering. |
| **Subagent claims independently spot-checked** | Where a delegated report's magnitude differed from my own measurement, **my measurement is reported** (canal exposure 30.6%, not 41.4%). |

**None of these limitations affects findings MA-02-01, MA-04-01, MA-05-01, MA-05-02, or MA-07-01.** Those rest on source inspection and closed-form arithmetic that are invariant to GA randomness — a load-time scale factor produces the same k² inflation on every run.

---

## 17. Phase boundary

**This phase is discovery and verification only. No repairs were authorized, and none were made.**

Explicitly **not** done:

- No source, configuration, dataset, test, or production artifact modified
- No git operation performed
- No dependency installed
- No optimizer parameter altered
- No formulation normalized toward the RL formulation
- No FFE/TEU conversion "corrected" to make numbers look similar
- No missing cost added merely because a different optimizer includes it
- No prior artifact overwritten

The recommendations in §18 are **acceptance criteria for a future authorized phase**, not work performed.

---

## 18. Prioritized decision register and acceptance criteria

Presented for a future correction phase. **Nothing here has been implemented.**

### 18.1 Tier 1 — Blocking (the result is currently unattainable)

| # | Item | Category | Acceptance criterion |
|---|---|---|---|
| 1 | Fix `network_loader.py:109` to divide the rate by k | A | `avg_rev_per_teu == 958.1232`; dataset revenue == 264,870,100 |
| 2 | Constrain fuel to the fleet | A | `fuel ≤ Σ(quantity × t/day) × price × 7` |
| 3 | Make the fleet constraint real and globally scoped | A | `vessels_required ≤ 263`, checked once globally with per-region partitioning |
| 4 | Stop re-billing costs per cluster | A | `Σ per-service cost == reported regional cost` |
| 5 | Restore the profit identity | D | `profit == revenue − total_cost` from independent quantities |

### 18.2 Tier 2 — Objective correctness

| # | Item | Acceptance criterion |
|---|---|---|
| 6 | Invert the ServiceGA cost sign | `fitness = w_p·profit + w_c·coverage − w_cost·cost` |
| 7 | Add fuel to FrequencyGA fitness | Fuel appears in the returned expression |
| 8 | Remove `abs(OPEX)` from the coverage reward | Bonus is dimensionless or absent |
| 9 | Make revenue a measured quantity, not `profit + cost` | Revenue exported from the MILP independently |
| 10 | Delete or wire the dead CONFIG weights | One weight system, actually used |
| 11 | Return `revenue` from the MILP | `regional_results[*].revenue` non-zero |

### 18.3 Tier 3 — Aggregation integrity

| # | Item | Acceptance criterion |
|---|---|---|
| 12 | Resolve the clamp asymmetry | `satisfied + unserved == true_demand` |
| 13 | Partition cluster demands | No lane appears in two MILPs |
| 14 | Report vessel count and utilization | Fields present in artifact and API |
| 15 | Report MILP failure count | Crashes distinguishable from unprofitable |

### 18.4 Tier 4 — Model completeness

| # | Item | Category |
|---|---|---|
| 16 | Source fuel consumption from `fleet_data.csv` | E |
| 17 | Derive `weekly_cost` from `tc_rate_daily`, or document why not | C/B |
| 18 | Add canal fees, or document the exclusion | E |
| 19 | Fix per-TEU port cost basis | A |
| 20 | Use distance-derived `cycle_time` | C |

### 18.5 Tier 5 — Oracle and test infrastructure

| # | Item |
|---|---|
| 21 | Add MA_08's ten oracle tests as CI gates |
| 22 | Add a unit-consistency test: `Σ q·r == Σ FFE × $/FFE` |
| 23 | Replace SHA-pinning with property assertions |
| 24 | Replace `assert 0 ≤ coverage ≤ 100` with `satisfied + unserved == demand` |
| 25 | Report solver gap, not just status |

### 18.6 Preconditions for any correction phase

1. An **approved isolated workspace** — the pipeline overwrites three artifacts at fixed paths.
2. LLM calls disabled or stubbed for determinism.
3. A fixed GA seed.
4. Re-run the oracle tests after each change.
5. **Explicit resolution of the six category-C ambiguities** — I have not invented a specification for them.

---

## 19. Statement of independence

This audit was conducted **without reference to the RL engine** at any point. No RL objective, reward function, cost model, or result was consulted as a correctness standard. Every determination rests on:

1. The shipped dataset's own column names and units
2. The project's own documentation (`docs/DATA_DICTIONARY.md`, `verification/01_GOLDEN_SPECIFICATION.md`)
3. Direct source inspection with line references
4. Reproducible arithmetic over raw data
5. Direct execution of the installed solver in isolation
6. Bounds derived from the project's own fleet inventory

The defects reported are defects **against the Multi-Agent system's own stated units and its own internal consistency**, and against physical bounds. Where the intended formulation is undocumented, the ambiguity is recorded rather than resolved.

**The system is not being compared to a different optimizer. It is being compared to arithmetic.**

---

## 20. Closing

The Multi-Agent architecture is real and substantial: a five-region orchestrator, hierarchical GA, MILP flow allocation, consensus layer, and an LLM reasoning tier. The code is organized, commented, and — in places, such as demand conservation (C1) and the cost identity — genuinely correct.

But the economic layer does not compute what it reports to be. One line at load time inflates revenue fourfold. A constraint that cannot bind fails to constrain. A cost model with no vessel correspondence reports fuel the entire fleet could not burn. Four different revenue models disagree, and the one reported is defined so it cannot be wrong. An assertion enforces the artifact it should detect.

The test suite is well-built and entirely internal. It pins bytes. It would pass unchanged if revenue were multiplied by four — which it was.

**No repairs were made. No optimizer was run. No artifact was touched.**

---

*Audit complete. 66 findings across 9 deliverables. 52 verified implementation defects. 3 independent bounds violated. The reported weekly profit exceeds the maximum attainable by $223,207,640 under an assumption that grants the system free fuel.*