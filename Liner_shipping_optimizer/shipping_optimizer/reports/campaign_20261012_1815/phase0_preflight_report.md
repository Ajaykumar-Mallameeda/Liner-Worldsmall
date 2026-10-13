# Phase 0 — repository, input and baseline preflight

**Run:** 2026-10-12 17:15 – 17:30 · **Campaign directory:** `reports/campaign_20261012_1815/` (new; nothing earlier overwritten)
**Gate result:** PASSED — the working tree equals the accepted Tasks 19–21 final tree, every canonical input is hashed, the model/ledger relationship was verified (reconciled to < 1e-6 relative on every run), and the baseline is recorded (Phase 1).

## 0.1 Environment

| Item | Value |
|---|---|
| Git root / branch / HEAD | `C:\Users\WINDOWS\Liner-Worldsmall` · `main` · `74bf7701b560959a4ec0aeb5e322051802fa9a95` (`Revert "Add liner shipping optimizer worldsmall"`) |
| Working-tree status | project directory **untracked** (`?? ../`), `Liner_shipping_optimizer.zip` untracked: git cannot reconstruct the accepted state; **provenance = SHA-256 snapshot manifests** |
| Project directory | `C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer` (the path in the prompt is wrong: the correct one has `Liner-Worldsmall` as the first component, as verified) |
| Python / packages | 3.11.9 · PuLP 2.7.0 (CBC 2.10.3, single thread) · SciPy 1.12.0 · NumPy 1.26.3 · pandas 3.0.5 · pytest 7.4.4 · `highspy` not installed |
| CBC settings | `PULP_CBC_CMD(msg=False, timeLimit=ceil(budget), threads=None→1, warmStart only with initial frequencies)` (`network_milp.py::_solver`) |
| Hardware | Intel i7-1360P (16 logical cores), 15.7 GB RAM (≈ 2.7–3.5 GB free during runs), C: 1.2 GB free (!), D: 206 GB free |
| Active optimisation env vars | none (`LINER_*`, `NETWORK_MILP_*`, `GLOBAL_STAGE_*`, `T15_*` all unset; only the IDE's `PYTHONSTARTUP`) |
| Verified defaults (source) | `PathConfig`: fastest, fixed cap 10/OD, `max_transfers=2`, `reoptimize_flows=True`, `repair_profit_floor=True`; class screening k=1 with time-feasible correction ON; economic regional filter; `GLOBAL_STAGE_TIME_LIMIT_SEC=120`; backend `cbc`; demand-coherent loop budget 60 |

## 0.2 Canonical inputs (`data/raw/WorldSmall`, SHA-256)

| File | SHA-256 |
|---|---|
| `Demand_WorldSmall_Fixed_Sep.csv` (= `demand_world_small.csv`) | `fd46294e5b71bcc6f7e49e6803a971a884be2b520c9a3bbd3bfe8f56b4703016` |
| `dist_dense.csv` | `8edf8cdf7a119c341b1bd3bab60a11529dec992335926a49914894c0b0080555` |
| `fleet_data.csv` | `5054eb5178cedbe28e33a3c6dde05e6d226025918f80250b7c148b8d846f458c` |
| `fleet_WorldSmall.csv` (= `fleet_world_small.csv`) | `a8986ee2bfeda133fdc069292319bfa5f038d329359f519ec22872133a68e216` |
| `ports.csv` | `b6c8c3b6c209222a33c68e1fe074092530082581ed4c5d5e4e6f9937677696ea` |

No file of `data/raw/WorldLarge` was read by any step of this campaign.

## 0.3 Provenance of the accepted tree

* Snapshot `D:\liner_scratch\snap_C0_base` made from the live tree at the start of this campaign: **1511 files, manifest sha256 `34a8d39052c49d287f824418191cf8de9647176c5288398799f4ea24b3f4ae9d`** = the recorded `T19_final` manifest of Tasks 19–21 (`experiment_manifest.json` → `trees.T19_final`).
* All baseline runs used this snapshot. Later phases use new snapshots (`snap_T1_flags` = baseline + default-off flags, 1515 files, sha `555970f3…b7de3`); every result file records the tree path it ran from.

## 0.4 Historical artifacts (checksums)

| File (`reports/tasks_19_20_21/`) | SHA-256 |
|---|---|
| `acceptance_report.md` | `88443c97bb83fee9d2674d78849e55df154cb4d78624e88cccdf0d46c6369f33` |
| `architecture_audit.md` | `54038d4f9e1d46e6ef061e8ad389e0e67f25b5b0ffc89bd4b09b83f8deeb1047` |
| `task19_network_adaptation.md` | `da7811e0ada376c2b2da369e1ff8e8f1f12c96492d5f7ffb73459fd0d55bf200` |
| `task20_path_selection.md` | `58b4b7b1227f1ec49ab225dcf16b60dfe939e3c7b67cf55ab137c8e76d84dfbb` |
| `task21_candidate_diversity.md` | `def48734543bb70aebedb420f71917d77c0c1e02e18b6b8831782420fcbfab2a` |
| `remaining_tasks.md` | `3fa5e144f243227ab3a9488076f3678c2bab1f6d9fd5d636e80ba6a2375e8fc8` |
| `results_matrix.md` | `587a171ddd00c653ef5589aabdadb79663db7a694c1689970a22a42aba52118e` |
| `experiment_manifest.json` | `a9a1f4520d0f4a17bc9e9e89942a79ace81f7655e7cd8142b169b31757d35b6d` (its `inputs` is `{}`: input hashes were never recorded there) |
| `owner_decisions.json` | `c077901c2b0f7c2878056ac63e2fa4bc4fcab3c6420b65f33d071aab1a170f32` |
| `patches/ROLLBACK.md` | `c7eb4cdc9bf603dda2d205a07b696ecb6c918fbc7379a0e95f0213dd36740b0e` |
| `patches/patches.sha256` | `9bc446f9138588955ac5979ed05081de1ba2f4571bd64c639ebe2252dba04dfb` |

## 0.5 Existing test-failure inventory (before any change)

Full suite, orchestrator test excluded, on snapshot `T22_suite_baseline` (identical tree): **51 failed / 1,257 passed / 46 skipped** (107 s).
The 51 failing test ids are identical to the recorded artifact-free baseline (`tasks_19_20_21/evidence/runs/T19S_final_free.log`).
Failure groups (traceback read, not inferred from names): see `test_failure_remediation_report.md`.
`tests/test_orchestrator.py`: 362/362 assertions on the accepted tree (`reports/expansion_2026_10_12/evidence/runs/E0_baseline_orch_run1.log`).

## 0.6 Rollback

* Behavioural rollback of Tasks 19–21: `reports/tasks_19_20_21/patches/ROLLBACK.md` (unchanged).
* This campaign: every new behaviour is behind a default-off environment variable (`LINER_MILP_VUB`, `LINER_LOCAL_SEARCH`, `LINER_CLASS_VARIANTS`, `LINER_PATH_INCLUDE`); unset = the accepted behaviour (checked: the baseline arm on the modified tree reproduces the frozen tree's results). File rollback: `patches/` of this directory + the frozen snapshot `snap_C0_base`.

## 0.7 Baseline run manifest

`evidence/runs/P1_base.driver.txt`, outputs `evidence/outputs/P1_base_seed{0..9}.json`, harness `evidence/tools/global_stage_experiment.py` (verbatim copy of the Tasks 19–21 harness), runner `run_batch.sh` (2 concurrent processes, `PYTHONHASHSEED=0`), tree `snap_C0_base`.
