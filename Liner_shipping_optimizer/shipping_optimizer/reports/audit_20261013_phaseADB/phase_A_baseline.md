# Phase A — Freeze and baseline (read-only audit, 2026-10-13)

Labels: **VERIFIED** (established in this audit from the live tree / data / recorded output), **REPORTED** (stated in a prior report, not reproduced here),
**INFERRED**, **HYPOTHESIS**, **UNKNOWN**, **CONTRADICTED**.  Nothing in this audit modified source, tests, configuration, data or defaults; no
optimisation or test was executed.

## 1. Repository identity

| Item | Finding | Label |
|---|---|---|
| Project directory (working tree) | `C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer` | VERIFIED |
| Git root | `C:\Users\WINDOWS\Liner-Worldsmall` (the project is a **nested, entirely untracked** sub-directory: `git status` shows `?? ../`) | VERIFIED |
| Branch / HEAD | `main` / `74bf7701b560959a4ec0aeb5e322051802fa9a95` — `Revert "Add liner shipping optimizer worldsmall"` (2026-10-09 14:04 +05:30); parent `3d6125aa…` "Add liner shipping optimizer worldsmall" | VERIFIED |
| Tracked files under the project | **0** (`git ls-files .` = 0; HEAD's tree is empty after the revert) | VERIFIED |
| Untracked | `../../Liner_shipping_optimizer.zip` (288,898,250 B, 2026-10-09) and the whole project tree | VERIFIED |
| Consequence | git cannot restore, diff or bisect anything in this project.  The only baselines are the zip, the `D:\liner_scratch\snap_*` copies, and the patch files below | VERIFIED |
| Python / solver | Python 3.11.9; PuLP 2.7.0 (bundled CBC; the campaign reports CBC 2.10.3); SciPy 1.12.0 (HiGHS via `scipy.optimize.milp`); NumPy 1.26.3; pandas 3.0.5 (venv `site-packages`) | VERIFIED (versions), CBC build REPORTED |
| Production entry / orchestration | `src/agents/orchestrator_agent.py` (`OrchestratorAgent.process`, 3 iterations; `GLOBAL_STAGE_TIME_LIMIT_SEC` default 120, line 355) → `src/network/reconcile.py::reconcile` → `NetworkPlanner.plan` (`src/network/plan.py`) → `solve_network` (`network_milp.py`) → `compute_ledger` (`ledger.py`); end-to-end command of record: `tests/test_orchestrator.py` | VERIFIED (source) |
| Environment variables currently set | none of `LINER_*`, `NETWORK_MILP_*`, `GLOBAL_STAGE_*`, `PYTHONHASHSEED` are set in this shell (names only checked; no API-key variable values were printed) | VERIFIED for this shell only |
| Other copies | `D:\liner_scratch\snap_C0_base` (accepted Tasks 19–21 tree, REPORTED sha256 of manifest `34a8d390…`), `snap_T11_final` (campaign final tree), `Downloads\copies\…` (older). **The live tree equals `snap_T11_final`**: 188 `.py` files under `src/`, `tests/`, `backend/` compared with line endings normalised — 188 identical, 0 different, 0 live-only | VERIFIED |

Note on WorldLarge: `data/raw/WorldLarge` exists in the tree.  Only its directory listing was displayed (three file names); no file in it was opened or loaded.

## 2. Input data (WorldSmall only; SHA-256 of the files on disk)

| File | Bytes | SHA-256 | Shape / format |
|---|---:|---|---|
| `Demand_WorldSmall_Fixed_Sep.csv` | 40,000 | `fd46294e5b71bcc6f7e49e6803a971a884be2b520c9a3bbd3bfe8f56b4703016` | tab-separated, 1,764 rows: `Origin, Destination, FFEPerWeek, Revenue_1, TransitTime`; no missing values |
| `demand_world_small.csv` | 40,000 | identical hash to the above | duplicate |
| `dist_dense.csv` | 50,654 | `8edf8cdf7a119c341b1bd3bab60a11529dec992335926a49914894c0b0080555` | tab-separated, 2,162 directed pairs: `fromUNLOCODe, ToUNLOCODE, Distance, Draft, IsPanama, IsSuez` |
| `fleet_WorldSmall.csv` / `fleet_world_small.csv` | 115 | `a8986ee2bfeda133fdc069292319bfa5f038d329359f519ec22872133a68e216` | 6 classes, 263 vessels (24/29/68/74/58/10) |
| `fleet_data.csv` | 503 | `5054eb5178cedbe28e33a3c6dde05e6d226025918f80250b7c148b8d846f458c` | 6 classes: `Capacity FFE`, TC rate, draft, speeds, bunker t/day, idle t/day, `panamaFee`, `suezFee` (blank for Post/Super-panamax Panama) |
| `ports.csv` | 4,521 | `b6c8c3b6c209222a33c68e1fe074092530082581ed4c5d5e4e6f9937677696ea` | tab-separated, 47 ports, 12 columns |

All `.csv` files are tab-separated (VERIFIED by reading them with `sep='\t'`; the loader docstring says the same).

## 3. Change inventory — accepted vs experimental (traced to source)

"Default" below is read from the live source (`config_from_environment` functions / dataclass defaults), not from a report.  "Reported" evidence is in
`reports/tasks_19_20_21`, `reports/campaign_20261012_1815`.

| Feature | Source (function / constant) | Introduced | Present | Default | Flag | Classification | Evidence (REPORTED unless stated) | Rollback |
|---|---|---|---|---|---|---|---|---|
| Corrected loader, FFE→TEU, revenue ÷ lane factor | `src/data/network_loader.py::load_demands`, `TEU_PER_FFE`, `ffe_to_teu_factor` | Task 1/2 | yes | always on | – | Accepted (units provisional — see Phase B) | `reports/task1_reproducibility`, `task2_shared_contracts` | NOT VERIFIED (zip only) |
| Independent ledger + reconciliation | `src/network/ledger.py::compute_ledger`; `reconcile.py` | Task 3–7 | yes | always on | – | Accepted | VERIFIED present; MILP objective = ledger profit < 1e-6 REPORTED | – |
| Global network MILP, LP-guided restriction | `network_milp.py::solve_network` (`lp_guided=True`) | Task 3–7 | yes | on | – | Accepted | `network_economics_redesign` | – |
| Integer weekly frequency / `ceil(T·f/7)` vessels | `economics.py` docstring; `service_feasibility.required_vessels` | Task 3 | yes | on | – | Accepted; assumption A10 unverified | VERIFIED (source) | – |
| Frequency-zero semantics (`f=0` ⇒ not operated) | `network_milp.py` module docstring | Task 3 | yes | on | – | Accepted | VERIFIED (source) | – |
| Class screening k=1 | `class_screening.py::ClassScreeningConfig.k = 1` | Task 10 | yes | on | `LINER_CLASS_SCREEN` | Accepted | `task10_vessel_class_screening.md`: +2.5 M (5/5) | `LINER_CLASS_SCREEN=0` |
| Time-feasible class correction | `class_screening.py::config_from_environment` (default ON) | Task 21 | yes | **ON** | `LINER_CLASS_TIME_FEASIBLE` | Accepted | +2.9 pp coverage (9/10) | `=0` |
| Demand-coherent loops (budget 60) | `demand_coherent.py::DemandCoherentConfig.budget=60` | Task 9 | yes | **ON** | `LINER_DEMAND_LOOP_BUDGET` | Accepted | `task9_candidate_generation.md` | `=0` |
| Regional economic filter (`auto` → economic when generators on) | `regional_filter.py::filter_mode` | Task 16 | yes | **ON (auto)** | `LINER_REGIONAL_FILTER` | Accepted; interacts with HiGHS @120 s | `task16_regional_filter_economics.md` | `=legacy` |
| Regional bunker pricing (snapshot) | `bunker_prices.py` | Task 8 | yes | **OFF** — uniform 600 USD/t | pricing config | Experimental / deferred (licence) | `task8_regional_bunker_pricing.md` | n/a |
| Flow re-optimisation | `paths.py::PathConfig.reoptimize_flows=True`; `flow_reopt.py` | Task 20 | yes | **ON** | `LINER_FLOW_REOPT` | Accepted | +2.34 M 10/10 (M7) | `=0` |
| ≤ 2 transfers | `PathConfig.max_transfers=2`, `HARD_MAX_TRANSFERS=2` | Task 20 | yes | **2** | `LINER_MAX_TRANSFERS` | Accepted | 1.5–2.4 % of served TEU | `=1` |
| Profit-floor repair | `PathConfig.repair_profit_floor=True`; `flow_reopt.repair_profit_floor` | Task 20 | yes | **ON** | `LINER_PROFIT_FLOOR_REPAIR` | Accepted (never triggered in clean runs) | M7 | `=0` |
| Per-OD path cap, fastest-first | `paths.py::DEFAULT_MAX_PATHS_PER_OD=10`, `SELECT_FASTEST` | legacy | yes | 10, fastest | `LINER_PATH_SELECTION`, `LINER_PATH_BUDGET` | Accepted as default; alternatives **rejected** (cost-aware −6.5 M, adaptive −7.4 M under CBC) | `task20_path_selection.md` | – |
| Advisory margin verdict, trim, solver-noise flows | Tasks 14–16 patches | Task 14–15 | yes | ON | – | Accepted | `tasks_14_15_16/final_acceptance_summary.md` | patches in `evidence/patches` |
| HiGHS backend | `network_milp.py` `NETWORK_MILP_BACKEND` (default `cbc`) | Task 15 | yes | **OFF (CBC)** | `NETWORK_MILP_BACKEND` | Experimental, owner decision (HiGHS 300 s recommended) | `task15_milp_strategy_comparison.md` | unset |
| Stage budget | `orchestrator_agent.py:355`, `GLOBAL_STAGE_TIME_LIMIT_SEC` | – | yes | **120 s**, CBC single thread | env | Frozen | – | – |
| Coverage floor | `reconcile.py::ENV_GLOBAL_MIN_COVERAGE` | Task 19–21 | yes | OFF | `LINER_GLOBAL_MIN_COVERAGE` | Experimental; loss-making end-to-end run (repair skipped) | `remaining_tasks.md` | unset |
| Route operators / elitism | `route_operators.py` (budget 0, elitism False) | Task 21 | yes | OFF | `LINER_ROUTE_OPERATORS`, `LINER_ELITISM` | Rejected (no gain) | `task21_candidate_diversity.md` | unset |
| C1 variable-upper-bound inequality | `network_milp.py::ENV_VUB` | Campaign 10-12 | yes | **OFF** | `LINER_MILP_VUB` | Accept for owner approval | +1.9 M 9/10; bound ÷ 2.5 | unset |
| Local search + idle prune | `local_search.py` (`LINER_LOCAL_SEARCH`, `_SEC` 15 s, `_MOVES`) | Campaign | yes | **OFF** | `LINER_LOCAL_SEARCH` | Accept for owner approval (strongest single change) | +2.28 M 20/20 | unset |
| Class variants (pool) | `class_variants.py` (`LINER_CLASS_VARIANTS`, `_FLOOR`) | Campaign | yes | **OFF** | `LINER_CLASS_VARIANTS` | Inconclusive increment; part of expanded profile | +0.56 M 7/10 hold-out | unset |
| Search-only variants / multi-hop evaluator / path inclusion | `local_search.py`, `paths.py::ENV_PATH_INCLUDE` | Campaign | yes | **OFF** | `LINER_LOCAL_SEARCH_VARIANTS`, `…_MULTIHOP`, `LINER_PATH_INCLUDE` | Experimental / **rejected** / **rejected** | P4b: not solved on 60–80 % of seeds | unset |
| Central seeding | `src/utils/rng.py`, `LINER_SEED` | Task 17 | yes | **OFF** (unset = unseeded) | `LINER_SEED` | Accept for owner approval; does not determinise CBC | R1/R2 | unset |
| Documentation drift tests, 9 xfail regional tests | `tests/test_economic_metric_documentation.py`, `tests/test_regional_agent_activation.py` | Campaign | yes | – | – | Blocked (owner) | `test_failure_remediation_report.md` | restore from `snap_C0_base` |

Documentation drift noticed in the source (VERIFIED): the module docstring of `paths.py` (lines 40–41) still says `max_transfers` is "1 by default"; the dataclass default
is 2.  Code, not docstring, was used above.

Unexplored flags: `LINER_PATH_HYBRID_SLOTS`, `LINER_PATH_MULTI_HOP_MIN_ALT`, `LINER_LOCAL_SEARCH_VARIANTS_FLOOR`, `LINER_CLASS_VARIANTS_FLOOR` — all read, all default as above.

## 4. Authoritative baseline

Two configurations, kept separate:

1. **Last accepted (production default) = the tree with no `LINER_*` flag set**: CBC single thread, 120 s global stage; flow re-opt ON, ≤ 2 transfers, time-feasible
   class ON, profit-floor repair ON, class screening k=1, demand loops 60, economic regional filter (auto), path cap 10 fastest, uniform 600 USD/t, `Capacity FFE`
   read as TEU, 24 h port stay, 48 h + 3.5 d transfer dwell, integer weekly frequency, no rejection penalty.
   Experiment identity: Tasks 19–21 batch M7 (arm `D`, seeds 0–9) = campaign D5 `base`; REPORTED reproduced to the dollar on 10/10 seeds (`phase5` §1).
2. **Most recent experimental = "final candidate"**: the above plus `LINER_MILP_VUB=1`, `LINER_LOCAL_SEARCH=1`, `LINER_CLASS_VARIANTS=0.10` (arm `e` in D5/H5, `fin` in C9/C9b). Opt-in; not a production setting.

Dataset hashes: §2.  Seeds: generator seeds 0–9 (development) and 10–19 (hold-out); `PYTHONHASHSEED=0`; `LINER_SEED` unset in the controlled batches (REPORTED).
Solver: CBC single thread, 120 s, `solver_backend = "CBC (PuLP PULP_CBC_CMD, single thread)"` — VERIFIED in all 160 rows of
`evidence/comparisons/per_seed_acceptance.csv`; `time_budget_sec = 120` in all 160 rows.

What is **not** reconstructable: the exact machine load per run (CBC is wall-clock limited); the `snap_*` trees live only on `D:\liner_scratch`; the original
Task 1 baseline in the zip differs from the loader-corrected tree (memory note, REPORTED).

## 5. Report discrepancy register

All figures were recomputed by this audit from `per_seed_acceptance.csv` (160 rows; read-only) where marked **R**.

| # | Discrepancy | Evidence | Reconciliation | Status |
|---|---|---|---|---|
| D-1 | **`fin` means different things.**  In D5/H5 `fin` = final candidate + search-only variants (15.29 / 15.45 M) and the final candidate is `e` (15.12 / 15.26 M); in C9/C9b `fin` = final candidate (14.89 / 15.23 M) and `lv` = + search-only variants (15.19 M). **R** | `phase5` §0, CSV | Arm labels are batch-local; never pool by label | Reconciled (naming) |
| D-2 | **Same configuration, same seeds 10–19, three means**: H5 `e` 15.26 M (tree T8), C9 `fin` 14.89 M (T9), C9b `fin` 15.23 M (T9). **R** | CSV; `phase5` §4 (“seeds 10–12 differ: 16.42→15.49, 15.50→15.32, 13.95→11.36”) | CBC wall-clock incumbent / load history; T8→T9 changed two defect fixes that do not act in these plans (REPORTED) | Explained by noise; **not removable** — a single batch mean is ± ~0.4 M |
| D-3 | Default on the same seeds 10–19: H5 12.36, C9 12.27, C9b 12.36 M (H5 and C9b equal to the dollar although on different trees). **R** | CSV | Bit-identical outcomes occur under equal load (R1: 10/10 pairs); C9's base ran under a different group load | Explained |
| D-4 | Default profit levels: controlled dev 11.52 M, hold-out 12.36 M, pooled 11.94 M; orchestrator 13.12 M (T9, 362/362), 13.43 M (T11 `G11_base`, 364/364); Tasks 19–21 end-to-end 12.59 / 12.17 / 13.88 M; unauthorised live run 12.17 M | `phase5` §2, §5, §7; `acceptance_report` §1; `ROLLBACK.md` §4 | Different quantity: controlled arm = one GA-pool + one global solve; orchestrator = best of 3 iterations incl. regional stage.  **Unpaired; do not compare across rows.**  The 12.17 M live run is outside the campaign and excluded | Reconciled by definition |
| D-5 | “Pooled summary” vs per-batch tables: pooled `e − base` = +3.25 M (20/20, mixes trees T8 for D5/H5); final-code hold-out gives +2.62 M (C9) and +2.87 M (C9b). **R** | `phase5` §2 vs §4 | Pooled figure uses the T8 tree; final-code batches are lower by 0.3–0.6 M but rule (10/10) still met | **The defensible final-code estimate is +2.6 … +2.9 M (hold-out, 10/10), not +3.25 M** |
| D-6 | Combination vs search alone: +0.97 M pooled 14/20 (rule fails), +0.98 M 8/10 hold-out (H5), +0.61 M 7/10 (C9), +0.95 M 8/10 (C9b); orchestrator +1.20 M n = 3 | `phase5` | Increment inconclusive by the report's own 8/10 rule | Unresolved by design |
| D-7 | Assertion counts: headline row says 362/362 × 3 (T9 default) while §2 of the final report says 364/364 (default) and 368/368 (final candidate) | `final_acceptance_report.md` §0 vs §2; `phase5` §5/§7 | Different trees: T9 vs T11 (+2 always-on state assertions; +N.11 flag-contract assertions) | Reconciled |
| D-8 | Controlled batches ran on T8/T9; the live tree is T11 (= T9 + per-region candidate stream + test changes, REPORTED).  **No controlled paired batch exists on T11**; only `G11` orchestrator groups (n = 3) | `INDEX.md` §6 | Candidate-stream change is not covered by a 20-seed paired batch | **Evidence gap** |
| D-9 | Test counts: frozen baseline 51 failed / 1,257 passed; final 29 failed / 1,341 passed / 46 skipped / 9 xfailed (51 − 13 fixed − 9 xfail = 29 ✓.) | `test_failure_remediation_report.md` | Arithmetic consistent; **not re-run here** | REPORTED |
| D-10 | Absolute profit depends on provisional units: S2 (`Capacity FFE` ×2) default 19.7 M, final 38.1 M vs 12.3 / 15.3 M reference (n = 3 each) | `maritime_assumption_validation.md` §2 | Levels not comparable across assumption sets | Open (Phase B) |

## 6. Test baseline inventory (no test was run in this audit)

| Suite | Last result | Failures | Nature | Evidence | Reproduced here |
|---|---|---|---|---|---|
| Full suite, frozen baseline | 51 failed / 1,257 passed / 46 skipped | 51 | pre-existing (baseline) | `test_failure_remediation_report.md` | No |
| Full suite, final tree | 29 failed / 1,341 passed / 46 skipped / 9 xfailed | 29 = `test_economic_metric_documentation.py` (documentation drift; 6 genuine after regeneration) | baseline / drift; 0 outside baseline | `FINAL_suite.log` | No |
| Regional policy tests | 9 strict xfail | 9 | re-specified, owner to retire | same | No |
| `tests/test_orchestrator.py` | 364/364 ×3 default; 368/368 ×3 final candidate | 0 | – | `phase5` §7 | No |
| Capacity-unit contract | `tests/test_capacity_units.py` enforces `CAPACITY_UNIT_STATUS = provisional` | – | documentation test of the open unit | source | No |

Side effects to know before any future run (REPORTED, `patches/ROLLBACK.md` §4): `tests/maritime/test_phase5_weather.py` writes stubs into `data/maritime/snapshots/…`;
`tests/test_orchestrator.py` overwrites `pipeline_output.json`, `frontend/public/pipeline_output.json`, `SYSTEM_TRUTH_REPORT.md`, `P2_DIAGNOSTIC_RUNTIME_VALIDATION_REPORT.md`.
A broad baseline re-run was therefore **not** attempted (policy §1.3).

## 7. Patch / rollback inventory

| Patch | SHA-256 (matches `patches.sha256`) | Target |
|---|---|---|
| `campaign_20261012_1815/patches/final_vs_accepted.patch` | `0dd4256a0aca6f7c88bc072727dc066cafa21b310713cb67deea513f0ed9e406` | `snap_C0_base` → T11 (20 modified, 8 added) |
| `…/final_vs_accepted_T9_superseded.patch`, `interim_code_changes.patch`, `phase2_T1_flags.patch` | hashes recorded in `patches.sha256` (first 20 hex re-verified) | superseded / interim |
| `tasks_19_20_21/patches/*` (+ `ROLLBACK.md`) | recorded in `experiment_manifest.json` | zip-derived → accepted |
| `tasks_14_15_16/evidence/patches/*`, `overnight_tasks_*/patches/*`, `network_economics_redesign/patches/*` | per-report manifests | earlier tasks |

Rollback is **behavioural** (leave the flags unset) or **file-based** from `D:\liner_scratch\snap_C0_base` (single copy, outside the repository).  No patch was applied
or reversed by this audit.

## 8. Unknowns / missing artefacts

* The RL paper is not named `RL_paper.pdf` anywhere; the matching document is `C:\Users\WINDOWS\Downloads\copies\linershipping\source.pdf`
  (arXiv:2411.09068v1, "Liner Shipping Network Design with Reinforcement Learning", SHA-256 `689a408ab3e4e4b4ab240a1c38eb4584c45a5053dcd1d0f1d8b2c56e6b75898b`) — identity INFERRED from content.
* All named prior reports were located (see manifest); `phaseD_validation_and_reconciliation.md` is nested at `reports/network_economics_redesign/`. Its content was not re-read in depth in this audit (listed, not reviewed).
* The LINERLIB technical report (Brouer, Pisinger, Sigurd) is not in the project; unit definitions of the benchmark cannot be taken from the primary source.
* Per-run machine load; the original Task 1 zip baseline numbers (superseded by the loader correction).

## 9. Phase A verdict

| Gate | Result |
|---|---|
| Repository state and configuration identified | **PASS** |
| Prior evidence indexed | **PASS** (10 campaign reports, 5 earlier mission directories, 160-row per-seed CSV) |
| Conflicts reconciled or marked unresolved | **PASS** (D-1…D-10; D-2/D-6/D-8 are explicitly unresolved) |
| Baseline independently reproduced in this audit | **NOT VERIFIED** (no run authorised; REPORTED 10/10 to the dollar) |
