# Phase 0 Baseline

**Date:** 2026-08-26 · **Phase:** 0 (Architecture Lock & Regression Baseline)
**Baseline commit:** `a44b987` · **Branch:** `main` (synced with `origin/main`)

This is the verified runtime state of the system at the end of Phase 0.
Future phases measure against the numbers and expectations recorded here.

---

## 1. Repository state at the start of Phase 0

```
git status --short (Phase 0 entry):
 D REPOSITORY_DECISION_QUEUE.md              (deleted; archive twin preserved under legacy/)
 D REPOSITORY_RUNTIME_MAP.md                 (deleted; archive twin preserved under legacy/)
 M pipeline_output.json                      (user pre-existing uncommitted changes — PRESERVED)
 M src/pipeline/iteration_selection.py       (user pre-existing — PRESERVED untouched;
                                               strengthens deterministic-authority contract)
 M tests/test_iteration_selection.py         (user pre-existing — PRESERVED untouched)
 M tests/test_provider_system/test_router_failover.py  (user pre-existing — PRESERVED untouched)
?? Crucix/                                  (vendored foreign project; untracked; left alone)
?? FULL_PROJECT_ARCHITECTURE_AUDIT.json/.md (audit deliverables; untracked; gitignored pattern)
?? MARITIME_INTELLIGENCE_INTEGRATION_BLUEPRINT.json/.md (blueprint deliverables; untracked)
?? RUNTIME_PERFORMANCE_FALLBACK_FORENSIC_AUDIT.json (untracked)
?? legacy/REPOSITORY_DECISION_QUEUE.md / REPOSITORY_RUNTIME_MAP.md (archive twins)
?? docs/architecture/   (Phase 0 output)
?? tests/architecture/  (Phase 0 output)
```

**Pre-existing uncommitted modifications in the user's working tree are
preserved verbatim. Phase 0 added documentation under `docs/architecture/` and
regression tests under `tests/architecture/` only. No optimizer, frontend, or
backend source file was modified.**

## 2. Pipeline golden run

Executed via `venv/Scripts/python.exe tests/test_orchestrator.py` (the
de-facto production runner).

| Metric | Value (Phase 0 fresh run) | Value (pre-existing user artifact) |
|---|---|---|
| Wall-clock total | **495 s (8m 15s)** | 390.6 s reported in artifact |
| Iteration count | 3 (MIN=MAX enforced) | 3 |
| Selected iteration (deterministic) | **0** | 2 |
| Selection method | `deterministic_multi_objective` [LLM-OK] | `deterministic_multi_objective` [LLM-OK] |
| Weekly profit (selected) | $921,351,707.12 | $856,700,254.41 |
| Annual profit | $47,910,288,770 | $44,548,413,229 |
| Operating cost / week | $2,077,218,379 | $212,576,250 |
| Fuel cost / week | $1,673,581,106 (artifact) | same |
| Profit margin | 30.7% | (artifact) |
| Demand coverage (canonical gdwc) | 47.0% | 45.8% |
| Unserved demand / week | 883,458 TEU | 1,027,850 TEU |
| Services deployed | 540 | 524 / 528 |
| Iterations run | 3 | 3 |
| Test scorecard | **322/326 (99%)** | 322/326 |
| Pre-existing failing assertions | 4 (reproduced against HEAD in throwaway worktree) | 4 |

**Fresh golden artifact preserved** at `logs/pipeline_output.phase0_golden_run.json`
(the runner overwrote `<repo_root>/pipeline_output.json` during the run, but that
file was immediately restored from `logs/pipeline_output.pre_phase0_backup.json`
so the user's uncommitted content is preserved).

The 4 pre-existing certification failures are reproduced identically at HEAD
`a44b987` in a clean worktree (`tests/test_ga.py`, `tests/test_milp.py`,
`tests/test_multi_agent_coordination.py` ×5, `tests/test_regional_agent_activation.py`
×9, `tests/test_service_generator_activation.py` ×3, `tests/test_setup.py`,
`tests/test_provider_system/test_provider_config.py`); they are unrelated to the
user's working-tree modifications and are explicitly NOT to be silently fixed by
Phase 0 (CHANGE_CONTROL §2 — does not loosen certification assertions).

## 3. Structural expectations (must hold in every successful run)

These are the Phase 0 invariants encoded in
`tests/architecture/test_output_contract.py`. Future phases MUST keep them true:

- 20 top-level keys (21 with optional `test_scorecard`).
- `iterations_run == 3`, `len(iteration_audit) == len(iteration_results) == 3`.
- `len(regional_results) == 5`.
- `best_iteration == final_selected_iteration == iteration_selection.selected_iteration`.
- `iteration_selection.selection_method.startswith("deterministic")`.
- `summary_metrics.coverage == decision_output.global_metrics.global_demand_weighted_coverage`.
- Frozen key sets in `regional_results`, `selected_services`, `summary_metrics`,
  `iteration_selection` (see PIPELINE_OUTPUT_CONTRACT.json for full lists).

## 4. Runtime-variable values (legitimately change between runs)

Weekly profit, coverage %, unserved demand, selected iteration index, services
count, monetary breakdowns, LLM telemetry counters, scorecard values, reasoning
text. These are recorded for traceability only and must NEVER be hard-coded as
golden equality expectations.

## 5. Offline regression test suite

Run with `venv/Scripts/python.exe -m pytest tests/ --ignore=tests/test_orchestrator.py -v`:

- **213 tests collected** (matches audit expectation).
- **191 passed** / **21 failed** / **0 skipped** in 437.39 s (~7m17s).
- 21 failures are all pre-existing — verified by re-running the failing files in
  a throwaway worktree pinned to HEAD `a44b987` (identical results: 21 failed,
  96 passed). Provenance: they predate Phase 0 and the user's working-tree
  modifications are not the cause.

## 6. Architecture guard tests (Phase 0 additions)

`venv/Scripts/python.exe -m pytest tests/architecture/ -v`:

- **17 tests, 17 passed** in 0.34 s.
- Network isolation: 9 tests across `optimization / pipeline / validation /
  services / decomposition / data` plus a project-wide guard and the maritime
  source-presence guard.
- Output contract: 8 structural invariant tests covering top-level keys, frozen
  region/service/summary/selection key sets, iteration budget, region count,
  selection authority, canonical coverage.

## 7. Dependencies

- Python 3.11.9 (venv) — system Python 3.14 lacks project deps; all test/run
  commands must use the venv interpreter.
- `requirements.txt` and `backend/requirements.txt` unchanged from the start of
  Phase 0. **No new packages installed.** Full inventory + change procedure in
  PHASE_0_DEPENDENCY_BASELINE.md.

## 8. Rollback baseline (per INTEGRATION_BOUNDARIES.md)

- Level 1: flags off (no flags defined yet → trivial).
- Level 2: delete the `docs/architecture/` and `tests/architecture/` Phase 0
  artifacts → returns to pre-Phase 0.
- Level 3: revert Phase 0 PR (one focused PR per IP).
- Level 4: restore commit `a44b987` + the recorded uncommitted working-tree
  state from `logs/pipeline_output.pre_phase0_backup.json` (for `pipeline_output.json`).
