# Tasks 19 · 20 · 21 — implementation plan and change log

**Date:** 2026-10-11 / 12 · Companion of `architecture_audit.md`.  The plan below is what was decided from the audit and then
executed; where an experiment changed the plan the change is stated in §5 (nothing is rewritten after the fact).

## 1. Principles applied

* One integrated experiment: every change sits behind a switch; the baseline `B0` (frozen Tasks 14–16 tree) is the control
  of every comparison; with all switches off the candidate pool and the path set equal the baseline's, element by element.
* No hard constraint is relaxed: capacity of every leg, demand once, vessel inventory, transit limits, port-call /
  fuel / handling / transshipment accounting, the independent ledger, the corrected revenue convention, the Tasks 9/10
  rollback, the existing solver and its budget.
* Evidence before default: a switch becomes a default only if the paired experiments and the end-to-end gate runs support
  it; otherwise it stays opt-in and the result is reported as a recommendation.

## 2. Changes per task (narrow, testable)

| Task | Change | Files | Switch (default state is in `acceptance_report.md`) | Tests |
|---|---|---|---|---|
| 19 | Network signals of the candidate network (OD alternatives, demand share without a path / with a direct path / on a single path, demand concentration, port connectivity, transfer concentration, path budgets) recorded in `path_model.signals` | `src/network/paths.py` | — (reporting) | `test_multi_hop_paths.py::TestSignals` |
| 19 | Value-adaptive per-OD path budget: the baseline's number of retained paths is redistributed by `demand × (revenue − cheapest per-TEU charges)^0.5`, bounds 3 … 20 | `src/network/paths.py` (`_allocate_budget`) | `LINER_PATH_BUDGET=fixed|adaptive` | `TestSelection` |
| 19 | Strategy / utilisation / unserved-demand report of the verified plan; reconciled against the ledger inside the report and against the test's independent recomputation | `src/network/strategy_report.py`, `reconcile.py` | always on (output only) | `TestStrategyReport`, orchestrator §N.9 |
| 19 | Objective hierarchy: opt-in epsilon constraint on coverage for the global MILP (existing `min_served_fraction`); lexicographic staging as an experimental harness strategy | `src/network/reconcile.py`; `evidence/tools/global_stage_experiment.py` | `LINER_GLOBAL_MIN_COVERAGE=<0..1>` (unset = profit-first) | `TestGlobalStage`, frontier runs |
| 20 | Bounded two-transfer journeys (hard bound 2): enumeration where the shorter journeys are too few, ledger / planner / partition support for ≤ 3 segments | `paths.py`, `ledger.py`, `plan.py`, `reconcile.py`, `network_milp.py`, `hub_milp.py` | `LINER_MAX_TRANSFERS=0|1|2` (**default 2**), `LINER_PATH_MULTI_HOP_MIN_ALT` | `TestTwoTransfers`, `TestLedger`, `TestPlanner` |
| 20 | Cost-aware and hybrid path selection (full-load slot cost of the canonical service model + per-TEU charges + reuse penalty) | `paths.py` | `LINER_PATH_SELECTION=fastest|cost_aware|hybrid` | `TestSelection` |
| 20 | **Flow re-optimisation**: LP re-routing of the fixed network over all valid paths through operated services; never serves less than the incumbent, never lowers profit; status downgraded from `optimal` when it improves | `src/network/flow_reopt.py`, `plan.py` | `LINER_FLOW_REOPT=0|1` (**default 1**) | `TestFlowReoptimisation` |
| 20 | **Profit-floor repair**: when the plan's profit is below the approved floor (0), switch off the worst-attributed services and re-route until the floor is met | `src/network/flow_reopt.py`, `plan.py` | `LINER_PROFIT_FLOOR_REPAIR=0|1` (**default 1**) | `TestProfitFloorRepair` |
| 21 | Time-feasible class correction in the class screening (a class that cannot carry any cargo of the rotation inside its transit limits is not kept as "legacy" when another class can) | `src/services/class_screening.py` | `LINER_CLASS_TIME_FEASIBLE=0|1` (**default 1**, acts only while the Task 10 screening is on) | `test_route_operators.py::TestTimeFeasibleClass` |
| 21 | Route-level operators (insert / remove / swap / reclass on elite rotations), elitism across iterations | `src/services/route_operators.py`, `service_generator_agent.py`, `regional_agent.py`, `regional_filter.py`, `orchestrator_agent.py` | `LINER_ROUTE_OPERATORS=<n>`, `LINER_ELITISM=0|1` | `test_route_operators.py` |
| all | Orchestrator test: independent recomputation understands ≤ 2 transfers; §N.9 strategy report vs recomputation; §N.10 flow re-optimisation checks | `tests/test_orchestrator.py` | — | the test itself |

## 3. Dependencies and risks

| Risk | Control |
|---|---|
| A larger / re-ranked path set changes the LP guidance of the production CBC solve and makes the time-limited incumbent worse (measured: cost-aware selection) | every selection variant measured under the production solver and, separately, the opt-in HiGHS; a variant that loses under CBC is not made a default |
| The re-routing LP could trade coverage for profit | the LP carries `served ≥ incumbent served` (and any coverage floor); regression tests |
| `optimal` reported for a plan improved outside the solved model | status downgraded to `feasible`, message stated; orchestrator §N.10 |
| New candidates bypass the regional cap | each source has its own budget; exempt only the `elite` / `route_operator` sections; counted in the report |
| Test's independent recomputation shares logic with the code | it is written separately (no `src` import for the economics); the dry-run on recorded baseline output reproduced every figure |
| CPU-load sensitivity of CBC at 120 s | concurrency capped at 4; deterministic repeat runs recorded (B0 seeds reproduce bit-for-bit) |

## 4. Acceptance gates (as in the mission) and where each is evidenced

Gate 1 integrity → orchestrator §N + `results_matrix.md` ledger columns · Gate 2 regression → `evidence/comparisons/suite_diff_*.md`
· Gate 3 coverage / utilisation → `results_matrix.md`, `task19_network_adaptation.md` · Gate 4 profit and cost →
`task19_network_adaptation.md` (frontier) · Gate 5 quality → strategy report (transit, transfers) · Gate 6 reproducibility →
`experiment_manifest.json` · Gate 7 rollback → `patches/ROLLBACK.md`, `evidence/comparisons/pool_identity_*`.

## 5. Plan changes forced by evidence

1. **Cost-aware selection was planned as the main Task 20 lever.** Under the production CBC solve it was worse
   (profit −6 M/wk on average, incumbents below zero on 2 of 5 seeds) and the hybrid rule was no better, so the main
   Task 20 gain moved to the flow re-optimisation, which was *not* in the first plan: it was found by measuring what the
   10-path cap costs with the network held fixed (+1.4 … +2.3 M/wk on the recorded B0 networks, `fixed_network_flow_lp.py`).
2. **Two-transfer paths were planned to extend coverage.** The audit showed they cannot reach the 90 unreachable ODs
   (their limit is below the sailing time); they were kept as bounded capability and measured for what they add
   (cheaper alternatives through operated capacity), not for coverage.
3. **Task 21 was planned as GA operators.** The unreachable-demand audit found a precise defect first (43 ODs, 4.7 % of
   demand, only a 14-knot feeder candidate); the time-feasible class correction was added ahead of the operators.
4. **Defaults.** The plan had left every default to the evidence.  Result (10 paired seeds, `acceptance_report.md`):
   flow re-optimisation, the ≤ 2-transfer bound, the time-feasible class correction and the profit-floor repair are the
   defaults; cost-aware / hybrid selection, the adaptive budget, route operators and elitism stay opt-in because they lost
   or did not gain under the production solver; HiGHS and the budget are untouched (owner decision 1).
5. **The first frontier batch ran with a re-routing LP that could trade coverage for profit** (tree ctl3); once seed 2
   showed +1.05 M bought with −1.7 pp of coverage the LP was constrained to serve at least the incumbent's cargo (tree ctl4)
   and the affected batches were re-measured on the new tree (`M5`, `M7`, `M8`, frontier `FR*`, `M10`).
6. **Batch `M6` (profit-floor repair variants) ran on a degraded machine** (18 of 40 runs `not_solved`, results far from
   the same models in `M5`) and is excluded from every claim; its in-pipeline repair triggers are quoted only as
   an illustration, the clean evidence being the unit tests and the offline drop-one analysis.  The final validation
   queue waits for an idle machine before every batch (`wait_idle.ps1`).
