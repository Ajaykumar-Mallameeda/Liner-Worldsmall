# Tasks 19 · 20 · 21 — architecture audit (written before any behaviour was changed)

**Date:** 2026-10-11 · **Scope:** WorldSmall only (no WorldLarge file was read) · **Status of this document:** facts about
the frozen Tasks 14–16 tree `B0`, each with the command or file that produced it. Nothing here is a result of the new code.

## 1. Baseline identity

| Item | Result |
|---|---|
| Repository root | `C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer` (git root is `C:\Users\WINDOWS\Liner-Worldsmall`; the project directory is **untracked**, HEAD `74bf770`) |
| Live tree vs the recorded Tasks 14–16 final tree | `src/`, `backend/`, `data/`, `tests/`: **216 / 216 files byte-identical** to `D:\liner_scratch\snap_FINAL2_orch_default_run1.manifest.json` and to `snap_FINAL2_suite_free.manifest.json` (`evidence/tools/verify_tree.py`) |
| Cumulative Tasks 14–16 patch | `tasks_14_15_16_cumulative.patch` sha256 `0ec66996…9a4cb6` — equals the recorded checksum |
| Fresh baseline `B0` (this mission, no environment variable) | `T19B0_orch_run1`: 342/342, profit 10,642,434 USD/wk, margin 14.50 %, coverage 23.04 %, 24 services, 133 vessels; `T19B0_orch_run2`: 342/342, 10,798,150 USD/wk, 14.3 %, 23.94 %, 25 services, 135 vessels (both ledger-verified, `complete`, iteration 1 selected) |
| Dataset | 47 ports, 1,764 OD rows, 276,446.8 TEU/wk demand, 6 vessel classes (263 vessels): Feeder_450 ×24 (450 TEU, 12 kn), Feeder_800 ×29 (800, 14), Panamax_1200 ×68 (1,200, 18), Panamax_2400 ×74 (2,400, 16), Post_panamax ×58 (4,200, 16.5), Super_panamax ×10 (7,500, 17) |

## 2. Architecture as it actually runs

```
OrchestratorAgent.process  (3 iterations; best verified iteration reported)
 └ per iteration, per region (3 clusters):  RegionalAgent.process
     ServiceGeneratorAgent.generate_services     candidate pool (sections A-F, below)
     RegionalAgent._filter_services              Task 16 economic filter (cap = adaptive filter_max_services)
     HierarchicalGA (service GA + frequency GA)  switches candidates on/off, frequencies   <- no route edits
     HubMILP (NetworkPlanner, fixed frequencies) regional allocation, produces hints
 └ reconcile()  src/network/reconcile.py         ONE global stage over the union of the regional pools
     NetworkPlanner.plan -> build_models -> build_paths (paths.py) -> solve_network (network_milp.py)
                         -> compute_ledger (ledger.py, independent) -> reconciliation
     regional partition of the verified plan; network_ledger block
```

### 2.1 Where the "strategy mix" comes from

| Quantity | Where | Effect on the feasible solution space |
|---|---|---|
| `archetype_mix` {direct 0.60, hub_loop 0.15, feeder 0.20, trunk 0.05} | `orchestrator_agent.py` (consensus input), `service_generator_agent.py` (`arch_mix`), `validation/archetype_validator.py` (LLM advice → validated, else this default) | **Only `direct_ratio` acts**: `n_direct = min(direct_target, max(200, direct_target × dr / 0.60))`. With the fallback ratio the factor is exactly 1, i.e. the count is the complexity-signal target (`direct_target` = 559 / 491 / 551 for the three regions, capped by the region's demand rows: 604 / 391 / 769). `hub_loop_count` and `feeder_count_target` are computed and **never read**; `trunk_ratio` is only logged. The ratios are generation hints, never constraints of any optimiser |
| `if median ≤ 10 and lanes > 500 → hybrid; elif top-3 share > 35 % → hub-and-spoke` | `regional_agent.py`, `service_generator_agent.py::process` | **Reporting only** (strategy text for the LLM prompt and the report) |
| Fixed generator constants (top-10 hubs, 20 spokes per hub, loops of 5, feeders to the 2 best hubs, standard sizes 500…14,000) | `service_generator_agent.py` sections B–D | Shape the pool; every candidate is then screened by the canonical service model |
| `max_paths_per_od = 10`, ranked **fastest first** | `paths.py::build_paths`, `NetworkPlanner`, `HubMILP` | **Binding**: keeps 12,326 of 53,086 valid paths on seed 0 (23 %); 997 of 1,764 ODs at the cap. The global MILP can only choose among kept paths |
| `filter_max_services` (508 / 405 / 499) and the economic ranking | `adaptive_budget.py`, `regional_filter.py` | Binding for non-loop candidates (Task 16) |
| Profit / coverage / cost weights of the regional GA | `HierarchicalGA` | Only the regional hints; the global MILP's objective is operating profit (`unserved_penalty_per_teu = 0`) |
| `MIN_ITERATIONS = 3`, coverage target 70 %, profit floor 0 | orchestrator / coordinator | Feedback signals and the verdict; **not** a constraint of the global MILP |

**Which are merely reporting conventions:** the strategy text, the archetype ratios other than `direct_ratio`, the
`direct / transfer` label of a flow. **Which constrain the model:** the per-OD path cap and its ranking, the regional
cap, the class-screening rule, and the demand-loop budget.

### 2.2 The final strategy mix is an outcome

The global MILP chooses frequencies, vessels and path flows jointly; nothing in it fixes a share of direct, feeder or hub
cargo. On the final B0 plans: 108 of 185 flows direct and 77 one-transfer (`T19B0_orch_run1`), 110 of 172 and 62 (`run2`) — an outcome of the model.

## 3. Existing multi-hop support

| Question | Answer |
|---|---|
| Transfers per journey | **At most one.** `build_paths` enumerates direct paths and `(s1, hub, s2)` pairs only; `compute_ledger` rejects `len(segments) > 2` (`invalid_path`); the orchestrator test's independent recomputation rejects it too; `assumptions.max_transfers_per_od` was the constant `1` |
| Transfer time / cost | one `transfer_dwell_days` (48 h + 3.5 d) per transfer; `transshipment_cost + 2 × variable_port_call_cost` per TEU at the hub |
| Path selection | per OD: all valid direct paths, then transfers, **sorted by transit time then port cost, first 10** — transit time is a *constraint* of the model (paths over the limit are never built), so the rank carries no economic information |

## 4. Candidate and path bottlenecks (measured on the seed-0 production pool, 1,166 candidates)

`evidence/tools/path_analysis.py`, `unreachable_ods.py`, `unreachable_cause.py`; outputs `evidence/outputs/*seed0*.json`.

| Fact | Value |
|---|---|
| Valid time-feasible paths / kept (cap 10) / dropped by the cap | 53,086 / 12,326 / 40,760 — **reproduces the recorded Tasks 14–16 value exactly** (path-set regression check of the rewritten `paths.py`) |
| ODs without any path | 90 of 1,764 (**8.05 % of demand**): a one-transfer connection exists for none of them inside the limit |
| …of which the limit is below the pure sailing time at the fastest class (physically unattainable by any pool) | 41 ODs, 3.37 % of demand — *not* servable whatever the network (a unit / data question: `TransitTime` is read as days, flagged unverified; Task 18) |
| …of which a two-port candidate exists but only with a class too slow for the limit | 43 ODs, **4.67 % of demand**: all have only a Feeder_800 (14 kn) two-port candidate while Panamax / Post / Super classes (16–18 kn) could meet the limit — the Task 10 screen keeps the legacy class when no class is profitable stand-alone, even if that class carries no cargo within the limit |
| …not attainable but no two-port candidate in the pool | 6 ODs, 0.01 % |
| ODs with at least one direct path / transfer-only | 1,606 / 71 |
| Unserved demand of the B0 plans by principal reason (strategy report, mean of 10 seeds, batch M5) | not economic to open a service **60.7 %**; class inventory exhausted 7.8 %; no time-feasible service in the pool 4.6 %; time limit physically unattainable 3.4 %; leg capacity exhausted 2.2 %; not profitable per TEU < 0.2 % |
| Fleet use of the B0 plan | 133–143 of 263 vessels; the three smaller classes are far from exhausted |

Conclusion of the audit: coverage is limited **by economics at the incumbent** (the plan opens ≈ 23 of 1,150 services)
and by the path set, not by physical path existence; two-transfer journeys cannot help the 90 unreachable ODs
(a second transfer adds 5.5 days to a journey that is already too slow) — which is checked by experiment, not assumed.

## 5. File / function map

| Concern | File · function |
|---|---|
| Path enumeration and selection | `src/network/paths.py` · `build_paths`, `_select_fastest`, `_select_cost_aware`, `_allocate_budget`, `_two_transfer_paths`, `PathConfig` |
| Global MILP | `src/network/network_milp.py` · `solve_network`, `_build_and_solve`, `_trim_slack_vessels` |
| Planner / ledger | `src/network/plan.py` · `NetworkPlanner.plan`; `src/network/ledger.py` · `compute_ledger` |
| Global stage and regional partition | `src/network/reconcile.py` · `reconcile`, `_candidate_generation_settings` |
| Candidate generation | `src/agents/service_generator_agent.py` · `generate_services` (sections A–F) |
| Demand-coherent loops (Task 9) | `src/services/demand_coherent.py` · `generate_demand_coherent_rotations` |
| Class screening (Task 10) | `src/services/class_screening.py` · `ClassScreener.screen` |
| Regional filter (Task 16) | `src/services/regional_filter.py`, `src/agents/regional_agent.py::_filter_services` |
| Iteration loop | `src/agents/orchestrator_agent.py` · `process`, `_reconcile_iteration` |
| Independent recomputation | `tests/test_orchestrator.py` · `_recompute_network`, `section_network_ledger_validation` |

## 6. Owner decisions that remain open (unchanged by this mission)

HiGHS as the default solver and the global-stage budget; the 20 % / 25 % upper verdict bands; full Tier-0
recertification (frontend / backend consumers). See `acceptance_report.md` for their status per run.
