# Tasks 19 – 21: patches, defaults and rollback

## 1. Patches (checksums in `patches.sha256`)

Applied in this order on the frozen Tasks 14–16 tree (`D:\liner_scratch\snap_T19B0_orch_run1`), `git -c core.autocrlf=false apply`
(this machine has `core.autocrlf=true`, which rewrites LF files otherwise), they reproduce the final `src/` and `tests/`
**byte for byte** (162 files, 0 differences — `evidence/comparisons/patch_series_verification.txt`).

| # | Patch | Files | What |
|---|---|---:|---|
| 1 | `p1_network_paths_reopt_reports_candidates.patch` | 17 | paths v2 (≤ 2 transfers, cost-aware / hybrid / adaptive, signals), ledger / planner / partition for ≤ 3 segments, flow re-optimisation, strategy report, route operators + elitism, time-feasible class correction, opt-in coverage floor (as first built) |
| 2 | `p2_flow_reopt_no_coverage_regression.patch` | 5 | the re-routing never serves less than the incumbent; `only_services` restriction; coverage floor honoured by the LP; `max_transfers = 0` is direct-only |
| 3 | `p3_profit_floor_repair.patch` | 4 | `repair_profit_floor` (acts only below the approved floor of 0) and its switch |
| 4 | `p4_defaults_and_tests.patch` | 4 | defaults of the accepted configuration, tests for them |
| — | `tasks_19_20_21_cumulative.patch` | 17 | all of the above in one step (applies on the baseline) |

## 2. Defaults of the accepted configuration (and the switch that undoes each)

| Behaviour | Default | Switch to restore the baseline |
|---|---|---|
| Flow re-optimisation over all valid paths of the operated services | **ON** | `LINER_FLOW_REOPT=0` |
| Profit-floor repair (acts only below a weekly profit of 0) | **ON** | `LINER_PROFIT_FLOOR_REPAIR=0` |
| Journeys with up to two transfers (where the shorter journeys are too few; + operated capacity in the re-routing) | **ON** (2) | `LINER_MAX_TRANSFERS=1` |
| Time-feasible class correction in the class screening | **ON** (acts only while the Task 10 screening is on) | `LINER_CLASS_TIME_FEASIBLE=0` |
| Path ranking | fastest (unchanged) | `LINER_PATH_SELECTION=fastest` (`cost_aware`, `hybrid` are opt-in; measured worse under CBC) |
| Per-OD path budget | fixed 10 (unchanged) | `LINER_PATH_BUDGET=fixed` (`adaptive` is opt-in; measured unstable) |
| Route-level operators / elitism | OFF | `LINER_ROUTE_OPERATORS=0`, `LINER_ELITISM=0` |
| Coverage floor of the global MILP | unset (profit-first) | unset `LINER_GLOBAL_MIN_COVERAGE` |
| Solver, budget | CBC, 120 s (**frozen**; HiGHS opt-in `NETWORK_MILP_BACKEND=highs`, not the default) | do not set |

## 3. Rollback

* **Behavioural, no file touched** — the Tasks 14–16 behaviour exactly:

  ```
  LINER_FLOW_REOPT=0 LINER_PROFIT_FLOOR_REPAIR=0 LINER_MAX_TRANSFERS=1 LINER_PATH_SELECTION=fastest \
  LINER_PATH_BUDGET=fixed LINER_CLASS_TIME_FEASIBLE=0 LINER_ROUTE_OPERATORS=0 LINER_ELITISM=0
  ```

  Add `LINER_DEMAND_LOOP_BUDGET=0 LINER_CLASS_SCREEN=0` to restore the pre-Task-9/10 pool as before, and
  `LINER_REGIONAL_FILTER=legacy` for the pre-Task-16 filter.  Verified by (a) candidate-pool and path-set hashes equal to
  the frozen baseline's (`evidence/outputs/pool_identity_*`), (b) controlled batch `M7` variant `RB` reproducing the
  frozen `B0` profits seed by seed, (c) the orchestrator run `T19O_rollback_run1`.
* **File rollback** — `git -c core.autocrlf=false apply -R` the patches in reverse order (p4, p3, p2, p1), or the cumulative
  patch, or restore the 17 files from `D:\liner_scratch\snap_T19B0_orch_run1` (manifest
  `snap_T19B0_orch_run1.manifest.json`).  No command above deletes a file.
