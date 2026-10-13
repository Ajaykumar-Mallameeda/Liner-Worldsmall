# Rollback of the 2026-10-12 campaign

Nothing below was executed by the campaign (it never deletes or overwrites a file; evidence and snapshots live on `D:\liner_scratch`).

## 1. Behavioural rollback (no file change) — the default

Every new behaviour is behind an environment variable that is **unset by default**.  With none of them set the tree reproduces the accepted
Tasks 19–21 behaviour — verified on ten seeds to the dollar (`phase5_combined_acceptance_report.md` §1).

| variable | meaning | default |
|---|---|---|
| `LINER_MILP_VUB` | C1: variable-upper-bound inequality `q ≤ demand·f` in the network MILP | unset (off) |
| `LINER_LOCAL_SEARCH` (+ `_SEC`, `_MOVES`) | C2: exact-LP local search after the solve, inside the 120 s stage | unset (off) |
| `LINER_CLASS_VARIANTS` (+ `_FLOOR`) | targeted alternative-class candidates | unset (off) |
| `LINER_LOCAL_SEARCH_VARIANTS` (+ `_FLOOR`) | experimental: search-only variants | unset (off) |
| `LINER_LOCAL_SEARCH_MULTIHOP` | experimental: multi-hop evaluator (rejected) | unset (off) |
| `LINER_PATH_INCLUDE` | experimental: restriction-aware path inclusion (rejected) | unset (off) |
| `LINER_SEED` | Task 17: per-component seeded generators | unset (global generators, as before) |

## 2. File rollback to the accepted tree

The accepted tree is `D:\liner_scratch\snap_C0_base` (1,511 files; manifest `D:\liner_scratch\snap_C0_base.manifest.json`,
sha256 `34a8d39052c49d287f824418191cf8de9647176c5288398799f4ea24b3f4ae9d`).

Option A — reverse-apply the patch (from the project directory; GNU `patch`, text mode):

    patch -R -p1 < reports/campaign_20261012_1815/patches/final_vs_accepted.patch

(20 files modified, 8 added; the three added source files `src/network/class_variants.py`, `src/network/local_search.py`,
`src/utils/rng.py` and the five added test files are emptied by the reverse patch and can then be removed by the owner).

Option B — restore the changed files from the snapshot (PowerShell, from the project directory):

    $snap = 'D:\liner_scratch\snap_C0_base'
    $files = 'src\agents\regional_agent.py','src\agents\service_generator_agent.py','src\network\flow_reopt.py','src\network\network_milp.py',
             'src\network\paths.py','src\network\plan.py','src\network\reconcile.py','src\optimization\frequency_ga.py',
             'src\optimization\hierarchical_ga.py','src\optimization\service_ga.py','src\services\candidate_service_generator.py',
             'tests\maritime\test_phase5_weather.py','tests\maritime\test_phase8_command_center.py','tests\maritime\test_port_pipeline.py',
             'tests\test_economic_metric_documentation.py','tests\test_multi_agent_coordination.py','tests\test_regional_agent_activation.py',
             'tests\test_service_generator_activation.py','tests\test_setup.py','tests\test_orchestrator.py'
    foreach ($f in $files) { Copy-Item (Join-Path $snap $f) $f -Force }

The files added by the campaign (`src/network/class_variants.py`, `src/network/local_search.py`, `src/utils/rng.py`, `tests/test_expansion_flags.py`,
`tests/test_local_search.py`, `tests/test_milp_vub.py`, `tests/test_regional_policy_architecture.py`, `tests/test_rng_control.py`) are not
imported by the accepted code; leaving them in place is harmless (the restored `plan.py` / `reconcile.py` do not reference them).

## 3. Partial rollback

* Keep C2 (local search), drop C1: leave `LINER_MILP_VUB` unset — no file change.
* Drop only the test-side changes (documentation of the 9 retired regional tests, fixtures): restore the eight modified test files from the snapshot.
* Task 17: unset `LINER_SEED`; `src/utils/rng.py` is inert without it.  `tests/test_economic_metric_documentation.py` then needs its
  `_SEEDING_ALLOWED` exemption removed (restore the file from the snapshot).

## 4. Not undone by any rollback (test-run artifacts, listed for the owner)

Running `tests/maritime/test_phase5_weather.py` on the live tree writes snapshots into `data/maritime/snapshots/maritime_weather_observations/`
(the test uses the live store, a defect of that test; provider `STUB`).  This campaign's runs added **63 files in 21 directories**
(`maritime_20261012T135724Z_*` … `maritime_20261012T140111Z_*`).  They are not inputs of the optimiser (`MARITIME_INTELLIGENCE_ENABLED` is off
by default) and were left in place under the no-deletion rule; they are excluded from the patch.

A second class of artifact, found by the final tree-diff of the live project against snapshot `snap_T11_final`: **a default-configuration
orchestrator run was executed in the live project directory from 23:37:57 to 23:44:35 on 2026-10-12** (`logs/app_20261012_233757.log`;
364/364 assertions, selected plan 12.17 M USD/week).  It was **not started by any script or command of this campaign** (checked against
the session's command log and the four chains it ran; every campaign orchestrator run executes in an isolated `D:\liner_scratch` copy) —
most likely a manual run of `tests/test_orchestrator.py` from the owner's IDE.  Its side effects, which the campaign left untouched:

| file (project root) | state |
|---|---|
| `pipeline_output.json` | created (28 KB) |
| `frontend/public/pipeline_output.json` | overwritten (the original, 682 KB of 2026-10-05, is in the zip and in every snapshot) |
| `SYSTEM_TRUTH_REPORT.md`, `P2_DIAGNOSTIC_RUNTIME_VALIDATION_REPORT.md` | overwritten (originals in the zip / `snap_C0_base`) |
| `logs/app_20261012_*.log` | new log files |

No source or test file was touched by that run; the final snapshot `snap_T11_final` (taken 23:37:32) and the patch are unaffected.  The run
overlapped the three `G11_fin` orchestrator runs (a fourth concurrent pipeline on the same machine).  To restore the originals:
`Copy-Item D:\liner_scratch\snap_C0_base\<file> .\<file> -Force` for the three overwritten files; `pipeline_output.json` at the root
did not exist in the accepted tree.
