# Task 3 — blockers resolved (candidate feasibility → pipeline)

Problem first (see `FINAL_REPORT.md` §1): the Task 3 candidate model was correct; the pipeline downstream of it was not
ready for real cycle times. Each blocker below was understood, reproduced, fixed at its cause, and then pinned by a test.

| Blocker | Root cause | Resolution | Pinned by |
|---|---|---|---|
| fleet check `TypeError: A False object cannot be passed as a constraint` | GA frequencies are fixed numbers, so `prob += total_vessels_used <= fleet_size` (`hub_milp_legacy.py:392`) compared two Python numbers; when the fleet was exceeded PuLP received the `bool` `False` | fleet inventory is a **per-class linear constraint** `Σ n_s ≤ N_class` over real vessel variables; an unsustainable chromosome yields `status="Infeasible"`, `valid=False`, and a structured cause (`fleet_exceeded: class X needs 42 vessels, inventory 20`) | `test_shared_contracts::test_fleet_infeasible_chromosome_returns_an_explicit_status`, `::test_class_inventory_is_enforced`, `test_milp::test_milp_over_subscribed_chromosome_is_explicit_infeasible` |
| zero frequency counted as one departure | `max(1, round(f))` in the fleet check; GA prune ignored `f = 0` | `f = 0` ⇒ not operated, 0 vessels, 0 cost; removed from the mask (`HierarchicalGA`, `HubMILP`) | `::test_zero_frequency_is_not_operated_and_not_billed` |
| `TypeError` from the error handlers | stdlib `logging.Logger` called with structlog-style keyword arguments (45 calls) | AST-based conversion to `"event \| k=%s"` positional form (structlog modules untouched); dry-run listing then apply, each result recompiled | module import + full-suite runs |
| hard-coded frequency / time | `max_freq = 3`, constant 7/14/21-day cycles, capacity × `7/cycle_time`, 300-vessel defaults | commented out / retired with a note; frequency ceiling `⌊7·N/T⌋` from the service's own rotation time; capacity `cap·f` per leg; `fleet_size=None` ⇒ real inventory | `::test_weekly_capacity_is_capacity_times_departures_per_week`, `::test_capacity_per_leg_scales_with_departures`, `test_ga::test_frequency_follows_real_rotation_time`, `test_economic_metric_documentation::test_milp_has_no_phantom_default_fleet` |
| silent zeros | missing port record / distance / vessel class priced as 0 | `ServiceModelError` with reasons (`missing_port_record`, `unknown_vessel_class`, `missing_distance`, …); `HubMILP` returns `status="Invalid Input"` and `reasons`; regional failures are explicit results | `::test_unmodellable_service_is_invalid_input_not_zero_cost` |
| unverifiable result | "optimal" copied from the solver | status mirrors the **independent ledger**; a plan the ledger rejects carries its violations (`PlanResult.infeasibility`) | `test_network_economics::TestLedgerCatchesInvalidPlans` |

## Real-world time per selected service
Each service's rotation time is computed, not declared. Example from the verified run (U6):

| service | class | route nm | sailing d | port d | cycle d | vessels at f=1 | headway |
|---|---|---|---|---|---|---|---|
| asia_svc_710 | Post_panamax | 14,976 | 37.8 | 2.0 | **40** | 6 | 7 d |
| americas_svc_598 | Super_panamax | 7,062 | 17.3 | 2.0 | **20** | 3 | 7 d |
| asia_svc_151 | Feeder_800 | 10 | 0.0 | 2.0 | **3** | 1 | 7 d |

Cycle times in the operated plan: 3, 5, 7, 19, 20, 31, 33, 35, 39, 40 days. The legacy pool had 92 % of declared cycle times
below the physical minimum.

## Tests were modified only to follow the repaired behaviour
`tests/test_shared_contracts.py` — the documented-defect `xfail(strict)` tests became enforced tests on synthetic fleets with
hand-computed expectations; `tests/test_ga.py`, `tests/test_milp.py` — fabricated `capacity=5000 / weekly_cost=800000 / cycle=28`
services replaced by the real fleet and the production generator (the old versions failed at baseline for the defects above);
`tests/test_economic_metric_documentation.py` — characterisation tests of repaired defects now assert the repaired state
(F-04 readers, F-07, F-08, F-16, F-25). No assertion was weakened; originals are in
`reports/overnight_tasks_2_to_4/legacy_tests/*.before.txt`.
