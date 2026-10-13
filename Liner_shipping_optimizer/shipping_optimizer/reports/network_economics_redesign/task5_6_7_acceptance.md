# Tasks 5, 6, 7 — acceptance

Every row names the test that fails if the property is lost. "Hand" = expected value computed by hand in the test, not by the
code under test. Synthetic fixture: vessel V, 1,000 TEU, design 12 kn, TC 8,000 USD/day, 20 t/day sea, 2 t/day idle, 600 USD/t,
24 h port stay; ports A–B 1,000 nm, B–A 1,200 nm → sailing 2,200/288 = 7.639 d, cycle 10 d, 2 vessels at f = 1.

## Task 5 — MILP accounting and fleet feasibility
| Property | Test |
|---|---|
| objective = revenue − vessel hire − fuel − port calls − per-TEU port/handling/transshipment; **no** coverage reward, no penalty folded into profit | `TestPlanner::test_profit_equals_revenue_minus_each_cost_line`, `::test_optimiser_penalty_is_reported_separately_never_as_profit`, `test_shared_contracts::test_reported_profit_is_revenue_minus_total_cost` (hand: revenue 1,000,000; vessels 112,000; fuel 94,066.67; ports 2,000; handling 30,000) |
| capacity is `cap · f` on **every** leg, not a per-service total | `TestPlanner::test_leg_capacity_is_per_leg_not_per_service`, `test_shared_contracts::test_capacity_per_leg_scales_with_departures` |
| vessels = ⌈cycle·f/7⌉ and are variables; class inventory is a hard constraint; total cap optional | `TestPlanner::test_class_inventory_limits_frequency`, `test_shared_contracts::test_class_inventory_is_enforced` |
| a plan that cannot be sustained is an explicit status with causes | `test_milp::test_milp_over_subscribed_chromosome_is_explicit_infeasible` (cause: `fleet_exceeded: class X needs N vessels, inventory M`) |
| transit-time limits shape paths; transfer dwell is part of transit | `TestPaths::test_transfer_transit_time_includes_port_stays_and_connection_dwell`, `::test_time_limit_is_enforced_when_paths_are_built`, `TestPlanner::test_transit_time_limit_makes_demand_unserved` |
| transshipment priced at the hub's own rate, cargo counted once | `test_shared_contracts::test_transshipment_is_priced_at_the_port_specific_rate`, `TestPlanner::test_transfer_cargo_is_counted_once_in_revenue` |
| an unprofitable corridor is left unserved, never forced | `TestPlanner::test_unprofitable_demand_is_left_unserved_not_forced` |
| the independent ledger rejects invalid plans | `TestLedgerCatchesInvalidPlans` (leg capacity, fleet, over-service, transit, inactive service, invalid path/frequency/class) |

## Task 6 — aggregation and failure propagation
| Property | Evidence |
|---|---|
| regional numbers are an **additive partition** of one verified network (cargo → origin region, service costs → proposing region) | orchestrator section N.6: Σ regional (profit, cost, revenue) == network (U6: exact), `summary_metrics.weekly_profit == network operating profit` |
| satisfied + unserved == true demand; coverage = satisfied / demand; no clamp | `test_economic_metric_documentation::test_regional_coverage_is_not_clamped`, `::test_satisfied_plus_unserved_equals_true_demand`, `::test_summary_coverage_denominator_is_true_demand` (F-16 repaired) |
| record count == headline count | `::test_service_record_count_matches_headline` (F-25 repaired) |
| `status == "complete"` iff `network_ledger.verified`; otherwise `incomplete_accounting` with message/violations; regional results marked `Unverified (<status>)` | orchestrator section N.1; `tests/test_network_failure_propagation.py::test_orchestrator_marks_regions_unverified_when_the_global_stage_fails`, `::test_orchestrator_survives_a_global_stage_exception` |
| a stage that cannot model its input is a reasoned failure, never a zero or an empty "complete" network | `tests/test_network_failure_propagation.py` — `Invalid Input` with reasons (`missing_fleet`, `missing_frequency`, `invalid_frequency`, `missing_directed_distance`); `::test_global_stage_where_every_candidate_is_rejected_fails_explicitly` (**found and fixed a real silent-success path in `reconcile`**) |
| a failed region is an explicit result ("Solver Error" status + message), never silently zero | `RegionalAgent` MILP failure branch (`regional_agent.py`, `milp_region_failed`) — exercised only through the orchestrator; no direct unit test (stated gap) |
| output contract changed only additively and deliberately | `tests/architecture/test_output_contract.py` (+`network_ledger`, +3 service fields), `docs/architecture/PIPELINE_OUTPUT_CONTRACT.json` |

## Task 7 — frequency / GA alignment
| Property | Test |
|---|---|
| GAs price a candidate through the same service model the MILP and ledger use (one fuel, one time basis) | `tests/test_ga.py::test_genetic_algorithms` (ceilings, per-class vessels ≤ inventory, mask/frequency agreement) |
| frequency ceiling is `⌊7·inventory/cycle⌋`, one more is unsustainable; cycle = ⌈sailing + port⌉ | `tests/test_ga.py::test_frequency_follows_real_rotation_time` |
| a selected service with f = 0 is removed from the mask | `HierarchicalGA` post-processing; `test_ga` mask/frequency assertion |
| chromosome indexes the **filtered** `problem.services` (unmodellable or demand-less services leave the pool) | `test_ga` (`len(result["services"]) == len(problem.services)` after the run) |
| FrequencyGA fitness is net of the full service cost (F-07 repaired) | `test_economic_metric_documentation::test_frequency_ga_fitness_is_net_of_fuel` |

**Not delivered, stated plainly:** route-level GA operators (insert/delete/swap a port) do not exist — `ServiceGA` is a binary
subset GA over a fixed pool, exactly as before; candidate quality is therefore bounded by the generator (see `solver_findings.md`).
