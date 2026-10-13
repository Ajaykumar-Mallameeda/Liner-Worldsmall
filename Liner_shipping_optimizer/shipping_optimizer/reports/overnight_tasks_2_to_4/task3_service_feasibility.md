# Task 3 — Physically feasible candidate services

> **STATUS UPDATE 2026-10-11:** superseded. The Task 3 blockers were resolved, Task 4 implemented and Tasks 5-7 / Phase D completed and verified - see `../network_economics_redesign/FINAL_REPORT.md`. The text below is the historical record of the overnight run and is left unchanged.

**Gate: BLOCKED at the integration gate.**
The candidate pool is now physically consistent and independently verified. `tests/test_orchestrator.py`, however, **crashes**
(4 of 4 runs) because correct cycle times expose a pre-existing downstream defect (MILP fleet check + zero-frequency
rounding). Fixing it is explicitly outside this plan (MILP failure propagation, GA/frequency semantics), so I stopped
instead of improvising. Task 4 has **not** been started.

## 1. What was built
| File | Role |
|---|---|
| `src/services/service_feasibility.py` (new) | pure, unit-testable model: `rotation_legs`, `evaluate_rotation`, `required_vessels`, `choose/rank_vessel_classes`, `reassign_vessel_class`, `CandidateReport`, 12 stable rejection reasons |
| `src/agents/service_generator_agent.py` | every candidate (direct / hub loop / trunk / feeder / heuristic) goes through one `_emit()` that selects a fleet class, evaluates, and appends only if feasible; raises `ServiceFeasibilityError` without a fleet |
| `src/services/candidate_service_generator.py` | source fix: the random "hub" can no longer equal the origin/destination (this produced `[A, A, B]` routes) |
| `src/agents/regional_agent.py` | a non-`Service` record now raises instead of receiving invented `capacity=5000 / cost=150000 / cycle=14` |
| `src/optimization/data.py` | `Service` gains optional `distance_nm`, `required_vessels` (1 departure/week), `capacity_unit_status` |
| tests | `tests/test_service_feasibility.py` (new, 67 tests); 3 strict-xfail markers retired in `test_shared_contracts.py` (D-SVC-CAP ×2, D-SVC-CYCLE); `test_fleet_cost_fields_are_unread_outside_the_loader` sanctions the feasibility module as the reader of `tc_rate_daily` (the other 4 fields still asserted unread); synthetic generator fixtures now carry the real loaded fleet |

## 2. Model and provenance of every input
| Quantity | Value used | Provenance |
|---|---|---|
| Route | unique port sequence; closing leg derived and counted once; `Service.ports` kept exactly as generated (open `[a,b]` or explicit loop `[h,…,h]`) so no accounting loop changes | contract; `HubMILP` uses `ports.index()` and loops over `svc.ports` |
| Distance | directed `dist_dense.csv`, nm; missing/invalid → rejection, never substituted | source |
| Speed | class `designSpeed`, checked `min ≤ design ≤ max` | `fleet_data.csv` |
| Capacity | class `Capacity FFE` as TEU | source column; **unit provisional (Task 2)** |
| Vessel cost | `TC rate daily × 7` per vessel-week | `fleet_data.csv` |
| Inventory | class `Quantity` | `fleet_WorldSmall.csv` |
| Port time | **24 h per call — ASSUMED**, configurable (`PortTimeAssumptions`) | not in the canonical files; LINERLIB documentation states a 24 h minimum port stay. Cargo-handling time not modelled |
| Cycle time | `sailing + port`, declared = `ceil` to whole days | derived |
| Vessels | `ceil(cycle_days × weekly_frequency / 7)`; frequency 0 → 0 | brief §3.4 |

Class choice is a **sizing heuristic, not source data**: nearest class capacity to the legacy sizing target (ties → smaller);
if the rotation is not locally feasible with it (needs more vessels than the class owns) the next-nearest is tried
(`class_fallbacks`). Only the local necessary condition (one weekly departure ≤ class inventory) is enforced; competition
for the shared inventory between services is left to the later MILP task.

## 3. Candidate statistics (WorldSmall, 4 seeds, identical counts)
| | first measurement | final |
|---|---|---|
| generated | 1,046 | 1,046 |
| accepted | 1,009 | **1,046** |
| rejected | 37 (34 exceed class inventory, 3 repeated port / self-leg) | **0** |
| class fallbacks | — | 34 (hub loops re-assigned from Super_panamax, 10 vessels) |
| by section (accepted) | direct 698, loop 6, trunk 45, feeder 54, heuristic 206 | direct 698, loop 40, trunk 45, feeder 54, heuristic 209 |
| by class | Feeder_800 702, Post_panamax 209, Super_panamax 51, Panamax_2400 28, Feeder_450 19 | Feeder_800 702, Post_panamax 246, Super_panamax 51, Panamax_2400 28, Feeder_450 19 |
| cycle time (days) min / median / max | 3 / 39 / 79 | 3 / 40 / **136** |
| vessels for 1 departure/week, median / max | 6 / 12 | 6 / **20** |
| legacy 7/14/21-day cycle times too short | 955 of 1,043 (92 %) | 957–960 of 1,046 (92 %) |
| missing source inputs | none (47×46 directed pairs, 6 classes complete) | none |
| capacity feasibility | conditional on the Task 2 assumption | same |

Reading this honestly: "0 rejected" is a property of this generator on this data, not a sign that the model is lax — the
rejection paths are exercised by 40+ synthetic tests. The tail is physically awkward: a 136-day six-port loop needing 20
vessels for a single weekly departure is *locally* feasible but is exactly what the network-level value test (later task)
must prune. Baseline pools had capacities of 1,000–12,000 TEU on vessels of 450–7,500 TEU; every accepted candidate now
carries its own class's capacity (≤ 7,500).

## 4. Tests
* Focused + related (`test_service_feasibility`, `test_shared_contracts`, `test_capacity_units`,
  `test_service_generator_activation`, loader, integration, data-loader): **291 passed, 5 xfailed, 3 failed** — the 3 are the
  baseline-failing `TestLoggingTags`.
* Full suite, artifact-free protocol, clean baseline → final tree: **53 failed / 836 passed / 43 skipped / 8 xfailed →
  54 / 928 / 43 / 5** (1,030 tests). 53 failing in both (identical set); exactly one newly failing:
  `tests/test_regional_agent.py::test_regional_agent` — the same MILP crash as below. 3 xfail → pass (retired markers).
* A flaky test introduced by screening (`test_pool_size_changes_with_budget`, 1 in ~2 runs) was traced to the random
  hub-equals-endpoint routes and fixed at the source (0 failures in 15 runs).

## 5. Integration gate — why it is blocked
`tests/test_orchestrator.py` on the Task 3 tree: **4 of 4 runs crash** (T3b, T3c-A, T3c-B, final T3d) with the same chain:

```
hub_milp.py:389   prob += total_vessels_used <= self.fleet_size
                  TypeError: A False object cannot be passed as a constraint        <- D-MILP-FLEET (known xfail)
regional_agent.py:380  logger.error("milp_solve_failed", hub=hub, ...)
                  TypeError: Logger._log() got an unexpected keyword argument 'hub'
orchestrator_agent.py:627  logger.error("regional_agent_failed", agent_name=...)
                  TypeError: Logger._log() got an unexpected keyword argument 'agent_name'
```
The baseline (Task 2) runs end normally with the six known profit failures.

**Mechanism (measured, `evidence/tools/probe_ga_fleet.py`):** in one GA result on the Task 3 pool, 57 services were selected,
**38 of them with frequency 0**. The MILP's fleet check counts each selected service as `max(1, round(f))` departures —
"rounding zero frequency up to one" — so it demands **260** vessels where **75** are actually needed, against a fleet of 263.
The GA's `post_ga_fleet_prune` only considers services with `f > 0`, so it cannot remove them. With the old constant
7/14/21-day cycle times each phantom departure cost 1–3 vessels and the check never bound; with derived cycle times
(median 40 d) it costs ~6. The defect is pre-existing and independent of this change: `test_fleet_infeasible_chromosome_returns_an_explicit_status`
reproduces the same `TypeError` on a 2-port hand-built problem.

**Why I did not fix it.** Every remedy is a change this plan forbids and each also has a trap:
* returning an explicit "infeasible" from `HubMILP` is failure propagation (Task 6/9), and the existing fallback in
  `regional_agent.py` turns a failed MILP into `status "Failed", profit 0.0` — fixing only the logger kwargs would convert a
  loud crash into silent zero results;
* counting zero frequency as zero vessels, or pruning zero-frequency services, changes GA/frequency semantics (Task 7);
* shrinking the pool to dodge the check would be "rejecting every candidate individually" to solve global competition, which
  §3.5 forbids.

## 6. State of the tree and how to undo
Task 3 **is applied** in the working tree (nothing was deleted, per your instruction). The primary integration test therefore
crashes there. If you prefer the last passing state (Task 2), run from the project root:

```
git -c core.autocrlf=false apply -R reports/overnight_tasks_2_to_4/patches/task3_service_feasibility.patch
```
(validated with `--check` on a copy; it removes the two new files `src/services/service_feasibility.py` and
`tests/test_service_feasibility.py` and reverts 7 edits — I have not run it.)

## 7. Findings for the next stage (not acted on)
1. **Brief vs code.** The 50/30/20 hybrid initialization and route-level OX / insert / remove / swap / vessel-class-change
   operators do not exist in this code base. `ServiceGA` is a binary subset-selection GA (single-point crossover, top-10
   elitism, no tournament); candidates come from rule-based pools (direct / hub loop / trunk / feeder / heuristic).
   I kept what exists and did not build a new GA. Because no operator changes a route, "screen after every operator" is
   satisfied at pool construction; `reassign_vessel_class` provides the recomputation a class-change operator would need.
2. D-CAP-FREQ is still live: weekly capacity is `capacity × f × 7/cycle_time`. With realistic cycles this divides capacity by
   ~3 compared with the old 14-day constant — expect coverage to fall once the fleet blocker is fixed, for that reason alone.
3. The margin filter in `RegionalAgent._filter_services` (`capacity × 75 > weekly_cost`) now removes Feeder_450 services
   (450 × 75 = 33,750 < 35,000).
4. `max(1, round(f))` also appears in the operating-cost and fuel sums (`hub_milp.py:305,311`), so zero-frequency selected
   services are still billed one departure.

## 8. What Task 7/8/9 must cover to unblock (derived from the above)
zero frequency ⇒ zero vessels and zero cost; selected-but-unscheduled services deselected before the fleet check; a fleet
infeasible chromosome returns an explicit status; the MILP/regional error handlers use supported logging calls **together
with** an explicit failure status so that failure cannot become a zero result.

Patch: `patches/task3_service_feasibility.patch` (9 files, 61 KB, sha256 in `patches/patches.sha256`; applies on the Task 2 tree).
