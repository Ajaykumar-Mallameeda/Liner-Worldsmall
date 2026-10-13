# Issue 1 - unit contract (2026-10-13)  -  gate: PASS

## Decision (owner-authorised in the campaign instruction)
* `Capacity FFE` is an FFE count; `capacity_teu = 2 * Capacity FFE`, converted once at the loader boundary
  (`src/data/network_loader.py`, `load_fleet`). Evidence is **secondary-source only**: RL paper arXiv:2411.09068
  (App. A.1 `vcap` "maximum number of FFEs", section 6.1 "capacity of 800 FFEs"; the string "TEU" never occurs).
  The primary LINERLIB report was not available; the status is therefore `secondary_source`, never `verified`.
* 1 FFE = 2 TEU exactly. The six lane-specific factors (1.75/1.85/1.9/2.1 on CNSHA->DEHAM/NLRTM/USLAX,
  AEJEA->DEHAM/NLRTM, BRSSZ->USLAX; comment "based on typical cargo mix") have no source in the repository, the
  LINERLIB README or the paper, and contradict the lane-independent cost conversion: removed (table kept, empty).
* Revenue and per-FFE port costs are divided by 2 (unchanged); gross revenue invariant (tested to 1e-12).

## Changed files
`src/data/network_loader.py`, `src/network/strategy_report.py` (unit string only);
tests: new `tests/test_unit_contract.py` (18 tests); updated contract-pinning tests
`test_capacity_units.py`, `test_worldsmall_loader.py`, `test_worldsmall_integration.py`,
`test_service_feasibility.py`, `test_class_screening.py`, `test_economic_metric_documentation.py`, `test_orchestrator.py`
(expected values x2 / status string / one fixture premise - each change states why in a comment; no assertion removed,
no tolerance widened). Audit of consumers: every capacity consumer reads `FleetClass.capacity_teu`; no second conversion exists
(grep of src/backend for `capacity_teu`, `* 2`, `TEU_PER_FFE`; frontend has no consumer of the unit status).

## Order of work
1. `tests/test_unit_contract.py` written first and run on the unchanged loader: **12 failed / 6 passed** (the failures are the contract).
2. Loader changed. Same file: **18 passed**.
3. Targeted: unit_contract + capacity_units + worldsmall_loader + worldsmall_integration + data_loader + shared_contracts = **213 passed**.

## Tests (actual output in this directory)
| command | result |
|---|---|
| `pytest tests --ignore=tests/maritime --ignore=tests/test_orchestrator.py --ignore=tests/test_provider_system` (before test adaptation) | 39 failed / 902 passed / 9 xfailed - `suite_non_orchestrator.log` |
| same, after the test adaptations | **30 failed / 911 passed / 9 xfailed** - `suite_non_orchestrator_rerun.log` |
| `PYTHONHASHSEED=0 python tests/test_orchestrator.py` | exit 0, **364/364 assertions, 0 failed** (`pipeline_output.json` test_scorecard; `orchestrator_after_unit_fix.log`) |

Failure classification of the 30 (vs the frozen list of `FINAL_suite.log`): 28 are the documented documentation-drift / baseline set;
2 differ from that log and are **independent of this change** - `test_regions_count_and_keys_frozen` (reads the root `pipeline_output.json`
produced by the out-of-campaign run: 3 regional results) and `test_metric_matrix_declares_non_reconciling_metrics`
(`MULTI_AGENT_ECONOMIC_METRIC_MATRIX.json` absent from the tree). Both fail identically on a clean extraction of the baseline tag
with the original artifact (checked in a scratch directory). No test was deleted, skipped or weakened.

## Observed consequences (single unpaired orchestrator run - NOT a baseline; Issue 2 measures it)
profit 37.5 M USD/wk, coverage 32.5 %, 31 services (old units, same pipeline: 12-13 M, 25 %). Ledger valid, 0 violations.
Predicted by the S2 sensitivity of the 2026-10-12 campaign (levels x1.6-2.5).

## Noted, not changed (outside Issue 1)
* `tests/test_orchestrator.py::section_vessel_utilization_summary` divides weekly load by capacity **per departure**
  (166.8 % "utilization"): a display defect, not a model quantity. Candidate for Issue 5/8.
* The legacy regional margin guess (`capacity x 0.5 x 150 > weekly cost`, `regional_agent._filter_services`) is calibrated to
  the old capacity numbers; it is only used with `LINER_REGIONAL_FILTER=legacy` (default is the economic filter).
* Generator standard sizes (500...14,000 TEU) now select different classes, which is the intended effect of consistent units.

## Artifacts overwritten by the orchestrator run
Backed up before the run in `artifact_backup/` (untracked); tracked ones (`SYSTEM_TRUTH_REPORT.md`, `P2_DIAGNOSTIC_...md`,
`frontend/public/pipeline_output.json`) restored with `git checkout`; the new versions are in `artifacts_after_run/`.
Root `pipeline_output.json` (ignored) holds the new run.

## Rollback
`git revert <Issue 1 commit>` or `git checkout baseline-t11-20261013 -- Liner_shipping_optimizer/shipping_optimizer/src/data/network_loader.py ...tests`.
