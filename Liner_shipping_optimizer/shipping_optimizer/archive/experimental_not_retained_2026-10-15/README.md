# Experimental optimiser code that did NOT produce a repeatable improvement (archived 2026-10-16)

Moved out of `src/` and `tests/` at the owner's request ("keep only the things that worked"). Nothing was deleted;
the files are byte-identical to the versions committed in `2e26572`. `conftest.py` here stops pytest from collecting them.

| Archived file | Experiment (campaign workstream) | Why it was not retained |
|---|---|---|
| `src_network/trunk_lanes.py`, `tests/test_trunk_lanes.py` | Trans-Pacific / Atlantic trunk-lane family (WS4, flag `LINER_TRUNK_LANES`) | ~3 candidates per seed, 1 of 30 used; paired -0.69 M vs control, 2 of 6 pairs lose > 3 M |
| `src_network/targeted_paths.py`, `tests/test_targeted_paths.py` | Targeted path additions (WS5, flag `LINER_PATH_TARGETED`) | 0/10, 3/10 solved (second LP eats the CBC budget); no-resolve variant -2.19 M, one seed -17.7 M |
| `src_network/dual_screen.py`, `tests/test_dual_screen.py` | Dual-priced candidate screening (WS6, study tool) | rank correlation with the real LP gain 0.03 (stand-alone rule: 0.51) |
| `patches/hooks_for_lanes_targeted_dual.patch` | The hook edits that were reverted in `src/network/{network_milp,plan,reconcile,trunk_candidates}.py` | -- |

Evidence (per-seed CSVs, predeclarations, comparison tables) stays in `reports/continuation_20261015/` and
`reports/final_campaign_audit/CONTINUATION_2026_10_15_REPORT.md`. The study drivers under
`reports/continuation_20261015/tools/` (`study_hooks.py`, `global_stage_experiment_v3.py`) import the archived modules and
will not run on the cleaned tree unless the experiment is restored.

## Restore (only if the experiment is to be re-run)

From `shipping_optimizer/`:

    git mv archive/experimental_not_retained_2026-10-15/src_network/*.py src/network/
    git mv archive/experimental_not_retained_2026-10-15/tests/*.py tests/
    git apply archive/experimental_not_retained_2026-10-15/patches/hooks_for_lanes_targeted_dual.patch

(or `git revert` the commit that archived them). All three features are default OFF, so the C3 configuration is the
same with or without them.
