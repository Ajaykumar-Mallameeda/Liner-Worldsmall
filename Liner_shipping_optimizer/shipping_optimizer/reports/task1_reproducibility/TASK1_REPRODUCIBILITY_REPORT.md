# Task 1 — Reproducible patch and test evidence (2026-10-10)

**Decision: PASS** (patch reproducible; no WorldLarge reads in tests; old vs new failures separated) — with the caveats in §8.
All numbers below come from runs recorded in `evidence/` (logs, JUnit XML, tools). Nothing was inferred where a run could measure it.

## 1. Repository and base revision
| Item | Value |
|---|---|
| Working dir used | `C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer` |
| Path named in the brief | `E:\Downloads\...\shipping_optimizer` — **does not exist on this machine**; the working dir above is the only live copy (an older OneDrive copy exists and was not touched) |
| Git | repo root `C:/Users/WINDOWS/Liner-Worldsmall`, branch `main`, HEAD `74bf770` (a revert of a gitlink-only commit). **0 tracked files** under the project dir: there is no git base to diff against |
| Base used for the patch | `Liner_shipping_optimizer.zip`, SHA-256 `23ab83b3337c99144710e5ebd87b6a546e73f64fbcebc9117bc8c235910302d2` (source only: `venv`, `logs`, `node_modules`, caches excluded) |
| Interpreter | project `venv`, Python 3.11.9, pytest 7.4.4, numpy 1.26.3, pandas 3.0.5, PuLP 2.7.0, scikit-learn 1.4.2 (`evidence/environment.txt`) |
| Dataset identity | SHA-256 of the five canonical WorldSmall files in `evidence/dataset_hashes.txt` |

The zip is **not** what the earlier session's patch was built against (that "pristine copy" no longer exists), and the flat `data/raw/*.csv` → `data/raw/WorldLarge/` move happened after the zip was made.

## 2. Files changed
This session (4 files, test/helper only — no optimizer or loader code):
- `tests/test_worldsmall_integration.py` — all WorldLarge reads removed (§3)
- `tests/test_worldsmall_loader.py` — real-looking "WorldLarge-only" port codes replaced by synthetic `FOREIGN_IDS` + guard test
- `tests/test_economic_metric_documentation.py` — 2 tests read a flat path that no longer exists and were **silently skipping**; repointed to `data/raw/WorldSmall/Demand_WorldSmall_Fixed_Sep.csv` (byte-identical, same MD5 pin) and a missing canonical file is now a failure, not a skip
- `scripts/run_pipeline_benchmark.py` — default instance `"WorldLarge"` → `"WorldSmall"`

Cumulative delta zip → final tree: `changes_B0_to_M.patch` (20 entries: 9 content-free data moves, 9 modified, 2 new test files incl. `tests/test_shared_contracts.py`). Supersedes `reports/task2_shared_contracts/changes.patch`, which was not applicable (`a/a/…` paths and a literal placeholder instead of the `test_shared_contracts.py` diff).

## 3. WorldLarge read audit
Static: all tests, fixtures, helpers grepped (name, Path-composed, JSON, `read_csv`). Runtime: whole suite incl. orchestrator run under an audit hook that logs every `open()`.

| Where | Before | After |
|---|---|---|
| `test_worldsmall_integration.py` | 7 tests read `data/raw/WorldLarge/*` or `large_shipping_problem.json` (1 vacuous: asserted only `.exists()`) | 0 reads; replaced by WorldSmall raw-read identity checks + synthetic foreign-id fixtures + tripwire test that a foreign-location file is rejected before `_read_table` is called + legacy WorldSmall JSON rejection |
| Runtime positive control (pre-edit tests) | 5 real WorldLarge files opened | — |
| Runtime, final tree, full suite + orchestrator | — | files opened under `data/`: the 5 canonical `WorldSmall` files + legacy `worldsmall_shipping_problem.json`; **0 WorldLarge, 0 writes**. 10 name-pattern hits are all files the tests create under pytest temp dirs |

Removed/replaced assertions about WorldLarge itself (435 ports, 62,002 distance rows, 501 vessels, 9,622 demands, ×6 scale) are dropped by directive (§1.2/§4.3), not by weakening: the WorldSmall-side assertions they carried are kept (47/1,764/2,162/263, scale 1). Remaining "WorldLarge" strings are names/comments, a legacy-scale constant test, and tmp-dir fixture names. Non-test: `src/utils/sample.py` (unused generator) still names WorldLarge files; untouched.

## 4. Baselines (same interpreter and commands for every tree)
Orchestrator: `python -m pytest tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider`

| Tree | Result | Weekly profit | "revenue" (profit+cost) | Total cost | Fuel | Services | Coverage |
|---|---|---|---|---|---|---|---|
| **B0** pristine zip | **265/265 pass, exit 0** | **+277.3 M** | 1,125.6 M | 848.3 M | 701.8 M | 305 | 88.7 % |
| **V_loader** (B1 + zip `network_loader.py` only) | **265/265 pass** | +299.7 M | 1,134.0 M | 834.3 M | 688.9 M | 312 | 89.6 % |
| **B1** tree at session start | 258/264, 6 fail | −319.0 M | 300.7 M | 619.7 M | 516.2 M | 282 | 83.5 % |
| **R** zip + patch (final) | 258/264, 6 fail | −328.1 M | 307.8 M | 635.9 M | 528.6 M | 282 | 84.4 % |

The six failures (identical in B1 and R): `Global weekly profit > 0`, `Network is profitable`, `Weekly profit > 0` ×2, `Annual profit > 0`, `Profit margin > 0`. Not modified or redefined. Pipeline is unseeded (~7 % run-to-run noise).

Rest of suite: `python -m pytest tests --ignore=tests/test_orchestrator.py -q --tb=line -p no:cacheprovider --junitxml=…`

| Protocol | Tree | total | pass | FAIL | skip | xfail |
|---|---|---|---|---|---|---|
| B (no stale artifact) | B0 | 803 | 705 | 55 | 43 | 0 |
| B | B1 | 936 | 830 | 53 | 45 | 8 |
| B | R | 940 | 836 | 53 | 43 | 8 |
| A (orchestrator artifact present) | B0 / B1 / R | 803 / 936 / 940 | 725 / 849 / 856 | 58 / 57 / 56 | 20 / 22 / 20 | 0 / 8 / 8 |

## 5. Existing versus new failures
- **Suite, protocol B, B0 → R: 0 newly failing; 53 failing in both (identical set).** All 144 tests present only in R pass; the 7 removed tests are the WorldLarge-reading ones (2 of them were already failing in B0).
  The 53: 29 `test_economic_metric_documentation` (missing `MULTI_AGENT_*` deliverables, never in the zip), 24 agent-activation / ga / milp / setup / maritime tests.
- **Protocol A adds one artifact-dependent characterization failure** (`test_profit_margin_pct_is_two_distinct_values`, F-15) whose value moves with the corrected revenue units; a second (`…record_count_disagrees…`) flips with the stochastic artifact. Both skip when no artifact exists.
- **The six orchestrator profit assertions are not defects of the original code.** Relative to the zip they are *new*: they appear only because the loader now converts revenue as `Revenue_1 / lane_factor`.

## 6. Why the profit sign changed (measured, §4 + `evidence/comparisons/`)
- Loaded-data diff zip loader vs current loader (47 ports, 1,764 demands, 2,162 pairs, 6 classes): `revenue_per_teu` is **4× higher** in the zip (e.g. AEJEA→AOLAD 4,740 vs 1,185; Revenue_1 = 2,370 USD/FFE) because it multiplied the per-FFE rate by the lane factor while also multiplying quantity (k², 4.41/3.61/3.42 on the 6 non-2.0 lanes); port handling/transshipment/variable call costs are 4× higher; `weekly_teu`, distances, capacities identical.
- Swapping only the zip loader back into the current tree restores +$300 M. Revenue line moves −$833 M; port cost only −$13 M. The corrected conversion matches brief §1.3 and preserves `weekly_teu × revenue_per_teu = FFE × Revenue_1` (264,870,100 USD/week potential gross).
- Fuel alone ($516–529 M/week) exceeds that entire gross potential, and sat+unserved exceeds demand per cluster (previously documented D-SVC-CYCLE / D-MILP-FLEET / double counting). The corrected units expose the cost-model defect; they do not create it. Not re-measured here.

## 7. Reproduction (patch reproducible: yes)
```
python -I evidence/tools/extract_base.py Liner_shipping_optimizer.zip <dest>      # fresh base, 592 files
cd <dest>
git -c core.autocrlf=false apply --check <path>\changes_B0_to_M.patch              # exit 0
git -c core.autocrlf=false apply          <path>\changes_B0_to_M.patch              # exit 0
python -I evidence/tools/tree_diff.py <final_tree_without_reports> <dest>           # 0 modified/added/removed
```
Outcome: applied tree byte-identical to the final tree (595 files). **`-c core.autocrlf=false` is required**: Git for Windows has `core.autocrlf=true` at system level and otherwise rewrites LF→CRLF on apply (content-equivalent, not byte-identical). Tests in §4 (columns R) were run on the applied tree. `network_loader.py` shows +858/−286 partly because the zip used CRLF and the rewritten file uses LF. Reports are linked by hash, not carried in the patch (`changes_B0_to_M.patch.sha256`).

## 8. Caveats and open decisions
1. The zip is the only base; no git history exists. Suggest committing the tree (not done: not asked).
2. **Decision for you:** accept the unit-corrected loader as the authoritative baseline (the six failures then are the honest baseline), or not. Port costs ÷2 (not ×2) is still a judgment from field tables, not an authoritative source, but it is not what flips the sign.
3. Legacy artifacts still pin the ×2 convention: `test_no_demand_scale_on_worldsmall_json_path` asserts `revenue_per_teu == 4580.0` (brief convention gives 1,145); `test_revenue_is_four_times_the_raw_csv_product` characterizes the same. Left unchanged and flagged; the loader rejects that JSON.
4. `tests/test_orchestrator.py` is byte-identical to the zip; its legacy `load_problem(json)` helper still defaults to ×6 for non-"worldsmall" names (unused by the primary test).
5. Audit hook sees Python `open()` events only; subprocesses are not covered.
6. `data/raw/WorldLarge/` holds WorldSmall-named duplicates (`ports_world_small.csv` etc.); left in place.

## 9. Exact next action
Phase A step 3 / Task 2: verify or formally mark as provisional the `Capacity FFE` unit (kept as TEU capacity, 450…7,500), with a visible assumption flag propagated to outputs. Task 3 onward must not start until the unit-corrected baseline in §8.2 is confirmed.
