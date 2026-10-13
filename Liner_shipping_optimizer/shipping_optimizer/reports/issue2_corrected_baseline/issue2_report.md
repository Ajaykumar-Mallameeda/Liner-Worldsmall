# Issue 2 - corrected operational baseline (2026-10-13)  -  gate: PASS (with stated instability)

Tree: commit `7460391` (Issue 1) on branch `campaign/20261013-issues-1-8`. Dataset hashes unchanged from Issue 0
(`Demand_WorldSmall_Fixed_Sep.csv` fd46294e...; `fleet_data.csv` 5054eb51...; `ports.csv` b6c8c3b6...; `dist_dense.csv` 8edf8cdf...;
`fleet_WorldSmall.csv` a8986ee2...). Configuration: CBC 2.10.x single thread, 120 s global stage, `PYTHONHASHSEED=0`, `LINER_SEED` unset,
every `LINER_*` variable removed from the environment except the arm's own; generator seeds 0-9; the four arms of a seed run
concurrently (equal load). Harness: `tools/global_stage_experiment.py` (copy of the campaign-2026-10-12 harness, production
candidate pool + production `reconcile`). Output hashes: `outputs_sha256.txt`.

## 1. Test gates (actual output in this directory)
| gate | result |
|---|---|
| unit / loader tests (Issue 1) | 213 passed |
| `tests/test_orchestrator.py` | 364/364 assertions, 0 failed (`../issue1_unit_contract/orch_clean.log`); also passed inside the full suite |
| full suite `pytest tests` on this tree (`full_suite.log`) | **41 failed / 1374 passed / 20 skipped / 9 xfailed** (658 s) |
| the same command on the baseline tag extracted to a scratch directory (`baseline_tag_full_suite.log`) | **41 failed / 1356 passed / 20 skipped / 9 xfailed** (472 s) |
| failing ids | **identical sets** (`fail_full.txt` = `fail_base_full.txt`; 0 only-here, 0 only-baseline); +18 passed = the 18 new unit-contract tests |

The 41 are: the documentation-drift set of the 2026-10-12 report plus 13 tests that only run when a root `pipeline_output.json` exists
(golden-SHA regression tests of maritime phases 5/6/7/9 and `tests/architecture/test_output_contract.py`). A side effect shared by baseline and
this tree: the full suite leaves a **truncated, invalid `pipeline_output.json`** (a test writes it while another test process state is mocked;
reproduced on the baseline tag) - hence 8 `test_output_contract` failures. Not caused by Issue 1. The invalid file was kept as
`pipeline_output_corrupt_after_full_suite.json`; the root file was restored from the Issue-1 run. Tracked artifacts were restored with `git checkout`.
Weather-test stub files in `data/maritime/snapshots`: 81 -> 84 (untracked, not an optimiser input).

## 2. Corrected-unit result, paired 10 seeds (`per_seed_issue2.csv`, `summary_issue2.txt`)
Arms: `base` = production default (no flag); `ls` = `LINER_LOCAL_SEARCH=1`; `vub` = `LINER_MILP_VUB=1`;
`e` = `LINER_MILP_VUB=1, LINER_LOCAL_SEARCH=1, LINER_CLASS_VARIANTS=0.10` (the previous "final candidate").

| arm | n solved | profit M USD/wk mean (min-max) | margin % | coverage % | services | departures/wk | vessels used / idle | leg load factor | cost / served TEU | gap to model bound % | stage s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| base | 10 | **24.64** (4.71-33.52) | 26.8 | 28.7 | 30.4 | 30.8 | 179 / 84 | 0.536 | 841 | 67.8 | 121.9 |
| ls | 9 (seed 8 `not_solved`) | 35.31 (28.96-39.53) | 34.3 | 32.5 | 32.7 | 30.7 | 178 / 76 | 0.594 | 752 | 58.8 | 115.6 |
| vub | 10 | 34.98 (31.58-38.83) | 35.4 | 31.2 | 30.1 | 30.2 | 171 / 92 | 0.606 | 741 | 3.1 | 123.5 |
| e | 10 | 35.64 (33.34-38.10) | 35.4 | 31.7 | 31.8 | 32.1 | 176 / 87 | 0.603 | 743 | -14.5 | 115.6 |

Per-seed profit (M USD/wk):
```
seed   base   ls     vub    e
0      17.08  39.53  32.43  37.48
1      33.52  36.31  36.14  37.92
2      30.87  35.26  36.54  38.10
3      25.71  28.96  35.38  34.97
4      31.92  37.59  32.74  35.66
5      26.00  33.62  35.04  33.96
6       4.71  32.33  38.83  33.34
7      30.45  35.41  35.32  36.19
8      26.98  not_solved 31.58 33.87
9      19.18  38.74  35.77  34.94
```
Paired vs base: ls +10.93 M (9/9 solved seeds higher; seed 8 no plan), vub +10.34 M (10/10), e +11.00 M (10/10).
Coverage +2.4 .. +3.7 pp (8/10 seeds higher in each arm). Transit: 0 violations in every plan; maximum p90 transit 50.4 d (base) / 37.6-48.7 d.

## 3. Gates
* Ledger: 39 solved plans, 39 valid, 0 violations, MILP objective = ledger profit (reconciled), regional partition verified, 0 negative-profit plans.
* The one `not_solved` plan (ls seed 8: no incumbent within 105 s) is reported, not hidden; no plan = no ledger result.
* **Do not compare absolute profits with any pre-Issue-1 number** (capacity was understated 2x). Old: base 11.9 M / 24.9 % coverage (20 seeds);
  new: 24.6 M / 28.7 %.

## 4. Findings that shape later issues (measured)
1. **The corrected default is unstable**: profit 4.7-33.5 M (sd ~8 M) against sd ~1.3 M in old units; gap to the model's LP bound 68 %
   (up to 94 % on seed 6). The 120 s CBC solve is the dominant uncertainty (ISSUE 3).
2. **The model bound is not a bound for the final plan**: with C1 (+ LS) the final profit exceeds the "relaxation bound" (gap -14.5 % mean in `e`)
   because flow re-optimisation uses the full valid path set while the bound belongs to the per-OD-capped model. Direct evidence that the
   per-OD path cap hides value (ISSUE 4); the gap column is a model-bound gap, not a gap to the true optimum.
3. **Unserved demand by principal reason (base, mean of 10)**: fleet inventory exhausted 30.8 %, not economic to open a service 29.1 %,
   no time-feasible service in pool 5.3 %, limit below fastest sailing 3.4 %, leg capacity 2.4 %. Under correct units the **class inventory is
   binding**: Feeder_450 22.8/24 and Feeder_800 26.3/29 used, Panamax_1200 66/68, while Post_panamax 11.5/58 and Super_panamax 0.2/10 are mostly idle
   (84 of 263 vessels idle). The pre-fix report's "60.7 % not economic" no longer describes the system.
4. Fuel is the largest cost (30.7 M of ~66 M/wk) - bunker price is provisional (A6).

## 5. Rollback
This issue changed no source file. Reports only: `git revert` of this commit, or ignore the directory.
