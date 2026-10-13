# Task 2 report — shared data, unit and economic contracts

Date: 2026-10-10 · scope: audit + contract-level corrections only; **no GA, MILP, frequency, aggregation or objective logic was changed.**
Companion: `TASK1_CLOSURE_REPORT.md` (loader), `changes.patch` (full diff vs the pristine copy), `evidence/` (raw outputs and re-runnable scripts).

Reading guide: *measured* = a number I computed from the data or from a run; *read* = established by reading code only; *unresolved* = I could
not establish it. Tests named `D-…` in `tests/test_shared_contracts.py` are strict-xfail acceptance criteria for defects I document but do not fix.

---------------------------------------------------------------------------------------------------

## 0. Summary

* The loader/data contract is now explicit and tested; the economic contract downstream of it is **not internally consistent**. The
  integration test cannot establish business correctness: its profit is a solver objective, its revenue is derived from that profit, and its
  coverage and costs are double counted.
* Measured on one run (baseline run 1): regional `satisfied + unserved` is **120.8 %** of the regional demand; reported "revenue" (108.3 M) is
  `profit + cost`, whereas the per-service revenues sum to 160.1 M; fuel is **81 %** of total cost (214.7 M of 264.3 M); `load / capacity` is 109 %.
* 86 % of the 1,046 generated candidate services (901) cannot physically complete their rotation in their hard-coded `cycle_time` at the
  vessel's **maximum** speed; 85 carry a capacity no vessel in the fleet has; none has the capacity of its own `vessel_class`.
* Corrections made (small, contract-level, each tested): fuel-cost guards, typed candidate pool, units documented in the data model,
  `Optional` canal fees (Task 1). Eight further defects have strict-xfail tests that will flip when fixed.
* Final state: `tests/test_orchestrator.py` still fails on the same six profit-sign assertions (as at baseline). Rest of suite: 57 → 53
  failing, 0 new failures, 785 → 830 passing, 8 documented-defect xfails.

## 1. Active pipeline and call graph (Step 3.5)

```
tests/test_orchestrator.py::test_orchestrator
 └ load_worldsmall_problem()        NetworkLoader.load_ports/demands/distance_matrix/fleet   (explicit canonical CSV; no JSON)
 └ OrchestratorAgent.process({"problem"})
    ├ CONFIG → problem.objective_mode, problem.profit/coverage/cost_weight           (src/config/optimizer_config.py)
    ├ optional maritime attach (importlib "maritime.optimizer_bridge"; off by default)
    ├ n_clusters = 3 if ports < 50 else 5 → PortClustering.cluster_ports            (47 ports → 3 regions)
    └ for iteration in 0..2:                                                        (MIN_ITERATIONS = MAX_ITERATIONS = 3)
        ├ RegionalSplitter.split          demands assigned by ORIGIN; deepcopy(problem) ⇒ full distance matrix AND full fleet per region
        ├ ThreadPool: RegionalAgent.process(region problem)
        │    ├ LLM strategy text (rule-based fallback)
        │    ├ ServiceGeneratorAgent.generate_services   direct / hub loops / trunks / feeders + CandidateServiceGenerator heuristics
        │    ├ normalise + rename ids ("asia_svc_000")
        │    ├ _filter_services          (capacity*0.5*150 > weekly_cost; cap from AdaptiveBudget)
        │    ├ HierarchicalGA            _filter_services → ServiceGA → FrequencyGA → prune to fleet.total_vessels
        │    ├ split_by_hubs(5)          each cluster: HubMILP(sub, SAME chromosome).solve()  (all active services in every cluster)
        │    ├ aggregate: Σ over clusters of profit, cost, fuel, port, transship, total, satisfied, unserved; per-service rows merged by id
        │    └ LLM explanation (rule-based fallback)
        ├ CoordinatorAgent.process       conflicts (service ids), global_metrics (coverage), feedback
        ├ ConsensusEngine / SharedContext / snapshot
    ├ IterationSelector.select           ranks on weekly_profit, global coverage, operating_cost (vessel fixed cost only)
    └ aggregate_results                  Σ regional values; revenue := profit + total_cost; coverage := coordinator value; status := "complete"
 └ test asserts; writes pipeline_output.json / SYSTEM_TRUTH_REPORT.md (→ backend/server.py, unified_main.py, routes/metrics.py, routes/pipeline.py)
```

Findings on the path (read unless marked measured):
* **Failure laundering.** `status` is the literal `"complete"`; an aggregation failure falls back to a zero metrics dict (and then dies on a
  missing `annual_profit` key); a regional failure becomes a zero-filled row; a cluster MILP failure becomes `{"status": "Failed", ... 0.0}` and
  the region reports only `cluster_results[0]["status"]`. Nothing downstream can tell a failed region from a valid zero-profit one.
* **Dead failure branches (measured).** `logging.getLogger` loggers are called with keyword fields (`logger.error("ga_failed", region=…, error=…)`).
  On a stdlib logger that raises `TypeError: Logger._log() got an unexpected keyword argument 'region'` *inside the exception handler*; I observed it
  when the new fuel guard fired in `test_regional_agent`. The designed fallbacks in `RegionalAgent`/`OrchestratorAgent` therefore never run — a real
  failure currently surfaces loudly but with a masking `TypeError`. **A naive logging fix would turn that into silent zero results**, so the fix
  must be paired with explicit failure status propagation (next-stage item 4).
* **No global fleet constraint.** Every region receives a deep copy of the whole fleet (263 vessels) and prunes only against it; per-class
  inventory (24/29/68/74/58/10) is not enforced anywhere. (read)
* **Iteration selection ranks on augmented profit, double-counted coverage and vessel cost only.** (read)
* **Unseeded randomness** in candidate generation (`random.random()` hub insertion, `random.choice`) and in both GAs; MILP/GA are wall-clock capped.

## 2. Shared contract specification (Step 3.7)

`D` = decision recorded in §6 (needs your confirmation). Producer/consumer abbreviations: LD = `NetworkLoader`, SG = `ServiceGeneratorAgent`,
CG = `CandidateServiceGenerator`, SGA = `ServiceGA`, FGA = `FrequencyGA`, HG = `HierarchicalGA`, MILP = `HubMILP`, RA = `RegionalAgent`,
OA = `OrchestratorAgent`, CO = `CoordinatorAgent`.

| Field / metric | Authoritative source | Unit | Time basis | Definition | Validation rule | Producer | Consumers | Evidence / status |
|---|---|---|---|---|---|---|---|---|
| `Demand.weekly_teu` | `Demand_WorldSmall_Fixed_Sep.csv` `FFEPerWeek` × lane factor k (default 2.0) | TEU | per week | OD demand | finite ≥ 0; OD unique; no self loop; Σ = 276,446.8 | LD | SGA, FGA, MILP, SG, CO, OA | measured; loader tests |
| `Demand.revenue_per_teu` | `Revenue_1` ÷ k | USD/TEU | per TEU shipped | revenue rate | `weekly_teu × revenue_per_teu == FFEPerWeek × Revenue_1` per row | LD | SGA, FGA, MILP | measured; Σ = 264,870,100 USD/wk |
| Gross revenue available | derived | USD | per week | Σ weekly_teu × revenue_per_teu | = 264,870,100 | LD | accounting | measured |
| `Port.handling_cost` | `CostPerFULL` ÷ 2 | USD/TEU | per TEU moved (load **or** discharge) | handling | ≥ 0 | LD | SGA, FGA, MILP | S3, **review** |
| `Port.transshipment_cost` | `CostPerFULLTrnsf` ÷ 2 | USD/TEU | per TEU transshipped | | ≥ 0 | LD | MILP only | MILP prices origin/dest port rate, not the hub's (read) |
| `Port.variable_port_call_cost` | `PortCallCostPerFFE` ÷ 2 | USD/TEU | per TEU handled in a call | | ≥ 0 | LD | SGA, FGA, MILP | |
| `Port.port_call_cost` | `PortCallCostFixed` | USD | per vessel call | | ≥ 0 | LD | SGA, FGA, MILP | |
| `FleetClass.capacity_teu` | `fleet_data.csv` `Capacity FFE` (numerically) | TEU | per vessel, per sailing | | > 0 | LD | **nobody** (`AdaptiveBudget` reads only the vessel total) | U-2 |
| `FleetClass.quantity` | `fleet_WorldSmall.csv` | vessels | static | inventory | int ≥ 0; Σ = 263 | LD | HG, FGA (total only) | per-class never enforced |
| `FleetClass.tc_rate_daily` | `fleet_data.csv` | USD/day/vessel | per day | charter cost | ≥ 0 | LD | **nobody** | D-SVC-COST |
| `FleetClass.bunker_consumption…`, `design_speed`, `idle…` | `fleet_data.csv` | t/day, kn, t/day | | fuel parameters | > 0 | LD | **nobody** (fuel table is hard-coded) | D-FUEL-TABLE |
| `FleetClass.panama_fee/suez_fee` | `fleet_data.csv` | USD / transit | per transit | canal fee | `None` = no value given | LD | nobody | S2, U-3 |
| `Service.capacity` | *should be* the fleet capacity of `vessel_class` | TEU | per vessel, per sailing | | ≤ max fleet capacity | SG | all optimisers | **violated** D-SVC-CAP |
| `Service.cycle_time` | *should be* derived from rotation distance, speed, port time | days | per rotation | | ≥ sailing time of the closed rotation | SG | SGA, FGA, MILP, fuel | **violated** D-SVC-CYCLE |
| `Service.weekly_cost` | *should be* `tc_rate_daily × 7` of the vessel class | USD | per vessel per week | | > 0 | SG | all | **not derived from data** D-SVC-COST |
| frequency (chromosome `frequencies[i]`) | decision variable | sailings | per week | integer in [0, MAX_FREQ = 3] | | FGA | MILP, HG | `D` C-FREQ |
| vessels required | `ceil(cycle_time × f / 7)` | vessels | steady state | | Σ ≤ fleet (and per class) | FGA/HG/MILP | fleet checks | same formula at 5 sites (FGA 1, HG 2, MILP 2); `FlowOptimizer` uses `max(1, int(cycle/7)) × f` (read) |
| weekly capacity | `capacity × f` | TEU | per week | | | — | MILP, FGA | **MILP and FGA use `× 7 / cycle_time`** D-CAP-FREQ |
| weekly vessel cost | `weekly_cost × vessels required` | USD | per week | | | — | MILP, FGA | code uses `weekly_cost × f` (read) |
| weekly fuel cost | `fuel_per_vessel_week × vessels required` | USD | per week | see §3 | | — | MILP, FGA, SGA | `× f` in code; FGA computes it but omits it from fitness (read) |
| port cost | Σ calls × `port_call_cost` + Σ TEU × (`handling` + `variable`) | USD | per week | | | MILP | OA | handling charged at every route call of each flow (read) |
| transshipment cost | TEU transshipped × rate at the hub | USD | per week | | | MILP | OA | **reported ≠ objective** D-ACCT-TRANSSHIP |
| total operating cost | vessel + fuel + port + transshipment (no penalties) | USD | per week | | each term once | MILP/RA/OA | OA, CO, selector | summed per cluster ⇒ duplicated D-ACCT-DEDUP |
| gross revenue | Σ served TEU × `revenue_per_teu` | USD | per week | **measured**, not derived | ≤ 264,870,100 | MILP | — | **absent**; derived as `profit + cost` D-ACCT-PROFIT |
| net profit | gross revenue − total operating cost | USD | per week | | identity holds exactly | — | OA, test | **absent**; "profit" is the augmented objective |
| coverage | served TEU ÷ **true** demand | % | per week | | 0–100 | CO | OA, test | divides by `satisfied + unserved` (double counted) D-ACCT-COV |
| vessel usage / fleet feasibility | Σ vessels used, per class | vessels | steady state | | ≤ inventory | — | — | **not reported** |
| validation status / provenance | per cluster solver status | | | all `Optimal` | | — | — | **not reported** D-ACCT-STATUS |

## 3. Fuel-cost contract (Step 3.2)

| Question | Answer |
|---|---|
| Units | distance nm; speed knots; consumption t/day; price USD/t (600); idle consumption **not modelled** |
| Voyage formula | `days = nm / (speed·24·0.9)`; `cost = days × t_per_day × price`. The 0.9 divides *distance* time (inflates days by 11 %) rather than adding port time; fuel is charged for all days at sea speed (read) |
| Weekly formula | `voyage(sum of listed legs) × 7 / cycle_time_days` — **one vessel**; multiplication by sailings/vessels is the caller's |
| Route | used exactly as listed; **no closing leg** is added. A 2-port service therefore burns one leg while its `cycle_time` (14 d) implies a round trip; hub loops are listed closed. (D-FUEL-ROUTE, needs a decision) |
| Double counting | fuel is not in port cost; canal fees are not modelled anywhere |
| Silent fallbacks (before) | missing leg → +500 nm; unknown class → Post_panamax; `cycle_time_days = 0` → `ZeroDivisionError`; negative → negative cost |
| After | missing distinct leg → `MissingDistanceError`; same-port leg → 0 nm; unknown class → `UnknownVesselClassError`; non-finite / ≤ 0 inputs → `FuelCostError`. All subclass `ValueError`. Numbers for valid inputs are unchanged (known-value tests). |
| Measured effect of the old fallback | 3 same-port legs in one deterministic 1,046-service pool; **38,481** fallback warnings during six GA runs (A/B). In the orchestrator run after the change: 0 guard exceptions on canonical data. |
| Source of parameters | hard-coded table "Clarksons Research 2024", **disagrees with `fleet_data.csv`** on every class (measured): capacity 5,000/8,000 vs 4,200/7,500; t/day 15/25/35/55/80/100 vs 18.8/23.7/52.5/57.4/82.2/126.9; speed 16–23 vs design 12–18; table speed exceeds the class `maxSpeed` for Feeder_450 and Super_panamax |

Known values verified by test (hand computed): 1,000 nm Feeder_450 = 1000/(16·24·0.9)·15·600 = **26,041.67 USD**; weekly with a 14-day cycle = 13,020.83.

## 4. Configuration trace (Step 3.3)

| Setting | Declared | Actual consumer | Finding |
|---|---|---|---|
| `CONFIG.objective_mode = "profit_first"` | `optimizer_config.py` | `OA.process` → `problem.objective_mode`; `RA` → `HierarchicalGA` → `ServiceGA` | live |
| `profit_first_weights` 0.60/0.25/0.15 | `optimizer_config.py` | `OA.process` → `problem.profit_weight…` | **not used by `ServiceGA` in profit-first mode**, which takes `ObjectiveWeights.PROFIT_FIRST_WEIGHTS` = 10.0 / 0.01 / 0.1 (`normalization.py`). Coordinator/consensus weight feedback reaches `ServiceGA` only in legacy mode (D-CFG-WEIGHTS) |
| `ObjectiveWeights.calculate_weighted_score` | `normalization.py` | `ServiceGA` (profit-first) | **adds** `+0.1 × cost`: a higher vessel cost *raises* fitness (legacy branch subtracts it) (D-CFG-COSTSIGN) |
| `min_coverage_percent`, `profitability_gate_enabled`, `min_margin_percent` | `optimizer_config.py` | **none** | dead |
| `Config.GA_POPULATION_SIZE/GA_GENERATIONS/MILP_TIME_LIMIT` | `utils/config.py` | **none** (budgets come from `AdaptiveBudget`) | dead; only echoed by the benchmark script |
| `COVERAGE_TARGET = 70` | `coordinator_agent.py` | CO | duplicates unlinked `min_coverage_percent = 70` |
| `ALPHA_UNSERVED = 300` | `regional_agent.py` | passed to GA and MILP | `ServiceGA`/`HierarchicalGA` defaults are 50 (overridden); the same 300 USD/TEU is a solver penalty, not a cost |
| `fleet_size = 300` | `HubMILP`, `FrequencyGA`, `HierarchicalGA` defaults | GA overrides from `problem.fleet`; **MILP never receives it** | MILP fleet constraint uses 300 while the loaded fleet is 263 (D-FLEET-300) |
| `TRANSSHIP_COST_PER_TEU = 80` | `regional_agent.py` / `hub_milp.py` | MILP fallback; GA estimate (`hub_ratio × satisfied × 80`); FGA uses `5 % × revenue` | three different transshipment estimates |
| `BUNKER_PRICE_PER_TON = 600` | `fuel_cost.py` | fuel functions | single source (the test re-hard-codes 600 for display) |
| `MAX_FREQ = 3`, `MIN_FREQ = 1`, `MAX_RUNTIME = 90`, `NO_IMPROVE_LIMIT = 8` | `frequency_ga.py`, `service_ga.py` | GA loops | live; unseeded |

## 5. Candidate-service semantics (Step 3.4, measured on one seeded pool of 1,046)

| Property | Where it comes from | Measured |
|---|---|---|
| Route / legs | direct `[o, d]`; hub loops `[hub, s1..s5, hub]`; trunks `[hubi, hubj]`; feeders `[spoke, hub]`; heuristic `[o, (hub), d]` | 3 same-port legs in the pool |
| `capacity` | size buckets; observed {500, 1,000, 2,000, 4,500, 5,000, 8,000, 10,000, 12,000, 14,000} (the generator also allows 16,000) | 85 > 7,500 (fleet max); **1,046/1,046** differ from their class's fleet capacity; trunks are always 12,000 |
| `vessel_class` | `map_capacity_to_vessel_class(size)` against the hard-coded table (max 8,000) | every size above 8,000 is labelled with the 8,000-capacity class (e.g. a 12,000-TEU trunk is "Super_panamax") |
| `cycle_time` | literal 7 / 14 / 21 days | 54 / 952 / 40; closed-rotation sailing time at class **max** speed exceeds it for **901 of 1,046**; median `cycle_time / min sailing days` = 0.46 |
| `weekly_cost` | `150,000 × size/8,000`, `{150k,180k,280k}`, `200k`, `70k × size/4,000` | not derived from `tc_rate_daily` (Super_panamax 55,000 USD/day = 385,000/wk) |
| Frequency, vessel count | not on `Service` | FGA/HG/MILP: `ceil(cycle × f / 7)` |
| Weekly capacity | per consumer | MILP, FGA: `capacity × f × 7/cycle`; SGA: `capacity × 7/cycle` (no f); FlowOptimizer: `capacity × f` |
| Recomputed elsewhere | cost: GA fitness, FGA, MILP objective, MILP reporting, RA aggregation | five independent recomputations, not one |
| Demand to fleet | Σ `ceil(cycle/7)` over all candidates = 2,078 vessels vs 263 | pool is ~8× the fleet before selection |

## 6. Accounting identity and decisions

Required identity (per week, USD):

```
net_profit = gross_revenue − (vessel_cost + fuel_cost + port_cost + transshipment_cost)
```
with `gross_revenue = Σ served_TEU × revenue_per_teu` measured from flows, no solver penalty, no coverage reward, each term counted once.

What the pipeline reports (read + measured):
* `profit` is `value(prob.objective)` = revenue − vessel − fuel − transship − port **− 300 × unserved TEU + coverage_reward** (`hub_milp.py`
  `profit_v`). Tiny instance (test `D-ACCT-PROFIT`): reported −11,641.35 vs accounting +3,158.33.
* `revenue` is `profit + total_cost` (`aggregate_results`) — a derived number carrying the penalty and reward. Run 1: 108.3 M vs Σ service revenue 160.1 M.
* `cost` (returned by the MILP) is **vessel cost only**; `total_cost` adds fuel, transshipment and port. The iteration selector and the profit-margin
  display use the vessel-only figure.
* Each cluster MILP charges vessel and fuel cost for **every active service in the chromosome**, and demand with origin in one cluster and
  destination in another appears in both. Region totals are sums over clusters, then `satisfied` is clipped to demand. Measured (all four runs):
  regional `satisfied + unserved` = 113–121 % of regional demand; regional operating cost 31.0 M vs per-service vessel cost 19.3 M (run 1).
* `coverage` = `Σsatisfied ÷ (Σsatisfied + Σunserved)` — run 1: 160,570 ÷ 333,978 = 48.08 %, which is the reported figure; against true demand it is 58.1 %.
* Selected-service rows carry per-vessel `capacity` next to weekly `load`, so "utilisation" is 109–111 % (baseline) / 76–77 % (after) and meaningless.

**Decisions for you (recorded as the contract; tests encode them):**
* **C-FREQ** frequency = sailings per week; `capacity` = TEU per vessel per sailing; `vessels = ceil(cycle_time × f / 7)`. Evidence: `MAX_FREQ`
  comment ("sailings per week"), `_analytical_frequency`, the five fleet-check sites, `FlowOptimizer`. Against: MILP/FGA `× 7/cycle_time`.
* **C-ROUTE** a service `ports` list is one rotation and is closed (the vessel returns to the first port) unless it already ends there.
* **C-PORTCOST** raw per-FFE rates are divided by 2 (Task 1, S3).
* **C-CAPACITY** `Capacity FFE` is kept as TEU capacity (U-2).

## 7. Defect register

Fixed: **D-PORTCOST-BASIS**, **D-CANAL-BLANK**, **D-BOUNDARY** (Task 1); **D-FUEL-FALLBACK** (silent 500 nm / class substitution / zero cycle);
**D-SVC-DICT** (209 of 1,046 candidates were plain dicts although typed `List[Service]`).

Documented with an executable acceptance test (`tests/test_shared_contracts.py`, strict xfail):

| ID | Defect | Measured failure | Where (read) |
|---|---|---|---|
| D-FUEL-TABLE | fuel table ≠ `fleet_data.csv` | capacity/consumption/speed differ per class | `fuel_cost.py` table |
| D-SVC-CAP | capacities no vessel can provide; capacity ≠ class capacity | 85/1,046 > 7,500; 1,046/1,046 mismatch | `service_generator_agent.py` direct/loop/trunk/feeder sizing |
| D-SVC-CYCLE | cycle time not derived from distance/speed | 901/1,046 infeasible | same |
| D-CAP-FREQ | weekly capacity `× 7/cycle` vs fleet check `cycle × f/7` | 500 vs 1,000 TEU on the tiny instance | `hub_milp.py` (capacity constraint), `frequency_ga.py` |
| D-ACCT-PROFIT | profit is the augmented objective; revenue derived | −11,641.35 vs 3,158.33 | `hub_milp.py` `profit_v`; `orchestrator_agent.py` `aggregate_results` |
| D-ACCT-TRANSSHIP | reported transshipment uses 80/TEU; objective uses port rates | 8,000 vs 1,000 | `hub_milp.py` `transship_cost_v` |
| D-MILP-FLEET | fleet-infeasible chromosome crashes PuLP (`True/False` constraint) | `TypeError` | `hub_milp.py` `prob += total_vessels_used <= fleet_size` |

Documented only (read unless noted):

| ID | Defect |
|---|---|
| D-SVC-COST | `weekly_cost` hard-coded, `tc_rate_daily` unused (U-5) |
| D-FUEL-ROUTE | open vs closed rotation in fuel/cycle (decision C-ROUTE) |
| D-ACCT-DEDUP | fixed costs and cross-cluster demand counted in every cluster; coverage denominators (measured 113–121 %) |
| D-ACCT-COV | coverage is relative to `satisfied + unserved` |
| D-ACCT-PORT | objective prices a missing handling cost at 15 USD/TEU while reporting 0; transfer flows incur no handling; handling charged at every call of the route for each flow |
| D-ACCT-STATUS | `status = "complete"` always; failures become zero rows; only cluster 0's status is reported; no fleet usage reported |
| D-ERR-LOG | stdlib loggers called with keyword fields: TypeError inside error handlers (observed) |
| D-FLEET-GLOBAL | each region gets the full fleet; per-class inventory unenforced |
| D-FLEET-300 | MILP fleet constraint 300 vs fleet 263 |
| D-FREQ-FUEL | `FrequencyGA._evaluate` computes `fuel_cost` and leaves it out of the fitness |
| D-CFG-WEIGHTS / D-CFG-COSTSIGN / D-CFG-DEAD | see §4 |
| D-UTIL | per-vessel `capacity` reported beside weekly `load` |
| D-HUB-IDS | hard-coded hub lists contain ids that are not WorldSmall ports (`HKG`, `SIN`, `ROT`, `NYC`, `SHA`, `CNXHG`); `CNSHA` is absent |
| D-JSON-STALE | `data/datasets/worldsmall_shipping_problem.json`: `revenue_per_teu` = 2 × `Revenue_1` and `weekly_teu` × 2 (gross revenue 4×), legacy ×2 port costs; pinned by a legacy test; now rejected by the loader |
| D-LEGACY-HELPER | `tests/test_orchestrator.load_problem(json)` pairs a JSON dataset with default distances (unused by the primary flow; primary test file left unmodified) |
| D-TEST-FABRICATED | `generate_p2_diagnostic_report` writes hard-coded sample rows and "ESTIMATED" cost splits |
| D-RANDOM | unseeded randomness; wall-clock-capped solvers |
| D-HUBCACHE | `HubDetector._demand_cache` is a class-level dict keyed by `id(problem)`; **hazard by reading; 0 of 2,000 collisions reproduced**, no change made |

## 8. Corrections made in Task 2 and their impact

| File | Change | Why | Callers / consumers | Covered by | Risk |
|---|---|---|---|---|---|
| `src/utils/fuel_cost.py` | typed errors instead of invented 500 nm / class substitution / zero cycle; same-port leg = 0 nm; unit contract docstring; table annotated | silent invalid calculation (measured 38,481 fallback hits) | `service_ga`, `frequency_ga`, `hub_milp`, `maritime` fuel kwargs | `TestFuelCostContract` (17 items) + existing `tests/maritime/test_phase7_integration.py` fuel tests | a caller that relied on the 500 nm fallback now fails loudly — `test_regional_agent` did (WorldLarge JSON + WorldSmall distances) and was retargeted |
| `src/agents/service_generator_agent.py` | heuristic dict records converted to `Service` with the same defaults `RegionalAgent` applied | declared `List[Service]`, 209/1,046 were dicts | `RegionalAgent` (isinstance branch now always true), `ServiceGeneratorAgent.process` direct users | `test_candidate_pool_contains_only_service_objects`, contract audit M3 | none expected: identical values; ids unique |
| `src/optimization/data.py` | units documented; fee fields `Optional` | ambiguous semantics | all | loader tests | `FleetClass()` fee default `None` |

Run 4 (final tree) vs run 3 (Task 1 tree): 285 vs 279 services, fuel 526.2 M vs 532.7 M, total cost 633.8 M vs 641.4 M — within run-to-run noise; no guard exception fired.

## 9. Tests and baseline comparison

| Suite | Baseline | Final | Notes |
|---|---|---|---|
| `tests/test_orchestrator.py` | FAILED — 258/264, same 6 profit-sign assertions (run 1: −156.0 M, run 2: −145.9 M) | FAILED — 258/264, same 6 (run 3: −326.5 M, run 4: −329.3 M) | not comparable across the port-cost correction (§Task 1, A) |
| everything else | 57 failed / 785 passed / 45 skipped | **53 failed / 830 passed / 45 skipped / 8 xfailed** | fixed: `test_data_loader`, three `test_worldsmall_integration` WorldLarge-era tests; **new failures: none** (one weather test failed once and passes in isolation and in the final run — flaky, unrelated) |
| new | — | `test_worldsmall_loader` +24 (108 total), `test_shared_contracts` 17 passing + 8 strict xfail | |

The 53 remaining failures are pre-existing and were not touched: 29 in `test_economic_metric_documentation.py` (the audit artifacts it reads are
not in the tree under those names), 9 in `test_regional_agent_activation`, 5 in `test_multi_agent_coordination`, 3 in
`test_service_generator_activation` (AI-tag / mock expectations), 3 in `tests/maritime/test_phase8_command_center.py` and 1 in
`test_port_pipeline` (generated-output / data-file dependencies), 1 in `test_setup` (missing `OPENROUTER_API_KEY`), `test_ga`
(`active_freq > 0` is 0; cause not investigated) and `test_milp` (fleet-infeasible chromosome = D-MILP-FLEET; it also asserts a key,
`num_variables`, that the MILP does not return).

## 10. Unresolved assumptions

| ID | Item |
|---|---|
| U-1 | lane-specific FFE→TEU factors (6 WorldSmall lanes) have no source in the repository |
| U-2 | `Capacity FFE` used as TEU capacity; if it is truly FFE the TEU capacity is 2× |
| U-3 | canal fees and Panama/Suez/draft feasibility (340 / 586 flagged pairs) are neither modelled nor inferable; blank fee ≠ 0 and ≠ infeasible |
| U-4 | idle/port-time fuel and port time in cycle time are not modelled; the 0.9 factor's intent is undocumented |
| U-5 | whether service `weekly_cost` is intended to be charter cost (then 55,000 USD/day for the largest class) or something else |
| U-6 | bunker price 600 USD/t labelled "Bunker Index 2024 Average" — not verifiable from the repo |
| U-7 | the per-region labels (Asia / Europe / Americas) are cluster indices; geography is not guaranteed (the "Europe" region's hubs were US/Brazilian ports) |

## 11. Change inventory (Part 6.3)

| File | Kind | Reason |
|---|---|---|
| `src/data/network_loader.py` | production | boundary, port-cost basis, canal fees, JSON route (Task 1) |
| `src/optimization/data.py` | production | units documented; `Optional` fees |
| `src/utils/fuel_cost.py` | production | contract guards |
| `src/agents/service_generator_agent.py` | production | typed candidate pool |
| `tests/test_worldsmall_loader.py` | test (+24, 2 retargeted) | Task 1 contracts |
| `tests/test_shared_contracts.py` | test (new) | Task 2 contracts + acceptance tests |
| `tests/test_data_loader.py`, `tests/test_worldsmall_integration.py`, `tests/test_regional_agent.py` | test (retargeted) | WorldLarge-era expectations |
| `reports/task2_shared_contracts/**` | documentation | reports, patch, evidence |

Not changed: `hub_milp.py`, `service_ga.py`, `frequency_ga.py`, `hierarchical_ga.py`, `flow_optimizer.py`, `regional_agent.py`,
`orchestrator_agent.py`, `coordinator_agent.py`, `optimizer_config.py`, `normalization.py`, `tests/test_orchestrator.py`, the dashboard/backend.
Generated files the test overwrites were restored byte-for-byte after every run.

## 12. Next-stage plan (not implemented; ordered by dependency)

1. **Confirm the four decisions in §6** (C-FREQ, C-ROUTE, C-PORTCOST, C-CAPACITY). Everything else depends on them.
2. **Service data from the fleet** (`service_generator_agent.py`): capacity, weekly cost and speed from `FleetClass`; `cycle_time` from the closed
   rotation distance, class speed and port time; drop sizes above the fleet maximum. Flips `D-SVC-CAP`, `D-SVC-CYCLE`; resolves D-SVC-COST.
   Then source fuel parameters from `FleetClass` (flips `D-FUEL-TABLE`). *Reason first:* every GA/MILP number is a function of these fields.
3. **MILP result contract, additive**: return measured `revenue`, accounting `net_profit`, per-cluster fixed costs attributed once, per-flow
   transshipment at the hub, explicit infeasible status instead of a crash. Flips `D-ACCT-PROFIT`, `D-ACCT-TRANSSHIP`, `D-MILP-FLEET`.
4. **Aggregation and failure semantics** (`regional_agent.py`, `orchestrator_agent.py`, `coordinator_agent.py`): de-duplicate cross-cluster demand,
   true-demand coverage, global fleet constraint across regions, status/validation propagation (never `"complete"` over a failed region), and fix the
   logger-kwargs defect *together with* explicit failure rows.
5. **Capacity/frequency semantics in the optimisers** (`hub_milp.py`, `frequency_ga.py`, `service_ga.py`): apply C-FREQ consistently; include fuel in
   FrequencyGA fitness; fix the profit-first weight sign and make problem weights reach `ServiceGA`. Flips `D-CAP-FREQ`.
6. **Configuration and determinism**: remove dead settings, one source for constants, seed RNGs in tests, retire the stale JSON datasets.

Stage 2 must precede 3–5 because the optimisers consume the service fields; stage 3 precedes 4 because aggregation needs per-cluster measured
values; stage 5 is last because changing GA/MILP semantics before the inputs and the accounting are right would be unverifiable.

## 13. Stop condition
Task 1 closure and Task 2 shared-contract work are complete. I stopped before any GA/MILP/aggregation change. Review items for you, in order:
(1) the port-cost basis (÷2) and its consequence for every previously reported profit; (2) the four decisions in §6; (3) whether D-FUEL-ROUTE should
be treated as a defect; (4) the ordering in §12.
