# Master audit summary — Phase A + D + B (WorldSmall, read-only, 2026-10-13)

Companion files: `phase_A_baseline.md`, `phase_D_architecture_blockers.md`, `phase_B_units_and_assumptions.md`, `unresolved_decisions.md`, `evidence_manifest.json`.
No source, test, configuration, dataset or default was modified; no optimisation, test or patch was run.

## A. Executive status

| Question | Answer |
|---|---|
| What is verified? | The live tree equals campaign snapshot `snap_T11_final` (188/188 `.py` files, EOL-normalised); effective defaults of every `LINER_*` flag (read from source); WorldSmall file hashes; 160-row per-seed table recomputed (all CBC / 120 s, 160/160 `feasible`, 160/160 ledger-valid, default gap to bound 70 %, with C1 4–9 %); paper unit definitions (FFE for demand, capacity, rates; no TEU anywhere) |
| What remains uncertain? | The unit of `Capacity FFE` at the primary source; the semantics of `TransitTime`; value lost to the per-OD path cap; behaviour beyond 47 ports; Table 2 World Small values of the paper |
| Baseline reproducible? | **REPORTED yes** (10/10 seeds to the dollar on the flags-off tree; bit-identical pairs under equal load); **not independently re-run** here.  Single-run plan equality is *not* guaranteed: CBC's wall-clock incumbent moves the same configuration by up to 2.6 M |
| FFE/TEU unit gate | **FAIL** — capacity is read as TEU while demand is converted ×2; the paper defines capacity in FFE; owner decision D-01 |
| Architecture audit complete? | **PASS WITH LIMITS** — stage map and defaults source-read; regional GA/LLM stages and sizes REPORTED |
| Blocker to safe implementation? | Yes, two: **D-01** (unit) and **D-13** (no version-control baseline; rollback relies on copies on `D:\liner_scratch`) |

## B. Implementation inventory (live tree)

* **Accepted, default ON:** corrected loader (units provisional), independent ledger, LP-guided MILP, class screening k = 1, time-feasible class correction, demand loops (60),
  economic regional filter (auto), flow re-optimisation, ≤ 2 transfers, profit-floor repair, advisory margin verdict, trim / noise fixes.
* **Accepted for owner approval, default OFF:** `LINER_LOCAL_SEARCH`, `LINER_MILP_VUB`, expanded profile (+ `LINER_CLASS_VARIANTS=0.10`), `LINER_SEED`.
* **Inconclusive:** class-variant increment (7/10 hold-out, 16/20 pooled).
* **Experimental only:** search-only variants, 5 %/20 % variants, HiGHS backend, coverage floor, regional bunker pricing, route operators / elitism (no gain).
* **Rejected:** `LINER_PATH_INCLUDE` (no plan on 60–80 % of seeds), multi-hop local-search evaluator (−0.24 M), cost-aware/hybrid path selection, adaptive path budget.
* **Blocked:** 29 documentation tests, 9 xfail regional tests, seven maritime assumptions (A3, A5, A7, A10–A12, A14).

## C. Top blockers (full register: Phase D §9)

| Rank | ID | Priority | Blocker | Evidence | Effect |
|---|---|---|---|---|---|
| 1 | B-01 | P0 | `Capacity FFE` used as TEU while demand ×2; paper defines capacity as FFE | `network_loader.py:675`; RL paper p.15, p.9 | levels ×1.6–2.5 (REPORTED, n = 3) |
| 2 | B-02 | P0 | Objective / constraints differ from the paper (no penalty, no unused-vessel credit, integer `f`/`n`, transit limits, cargo-based port-variable cost) | Eq. 28–35, §3 | no fair comparison without a paper mode |
| 3 | B-03 | P0 | Ledger and test recomputation share the loader's units: a unit error is invisible; unsourced lane factors | `ledger.py`, `FFE_TO_TEU_LANE_FACTORS` | correctness gates cannot catch B-01 |
| 4 | B-04 | P1 | CBC 120 s never reaches optimality; 70 % gap, ≤ 2.6 M run-to-run | CSV | profit and benchmark validity; +1.9 M C1, +2.28 M LS available |
| 5 | B-08 / B-05 | P1 | No VCS baseline; no 20-seed paired batch on T11 / 60.7 % of unserved demand "not economic" with integer weekly frequency | git; D-8; architecture_audit §4 | reproducibility; coverage ceiling |

## D. Data and units

* **Paper (RL, arXiv:2411.09068):** demand quantity FFE/week; flow = same; vessel capacity "maximum number of FFEs"; revenue USD/FFE; port and transshipment USD/FFE;
  penalty 1,000 USD per rejected unit (per FFE by Eq. 30); fractional vessels; unused vessels credited at TC rate; soft fleet limit; no transit constraint; time horizon
  and Table 2 horizon ambiguous.
* **Ours:** demand FFE→TEU (×k, k = 2.0 except six ODs at 1.75–2.1); revenue ÷k; port rates ÷2; **capacity unchanged**; integer weekly frequencies; no penalty; hard
  transit limits.
* **Cannot yet be determined:** the unit at the primary source (blocks D-01); penalty per FFE vs per demand; profit horizon; paper Table 2 rows.

## E. Owner decisions

See `unresolved_decisions.md` (D-01 … D-14).  Blocking now: **D-01, D-13**.

## F. Proposed next implementation phase (recommendation; ≤ Oct 20)

| # | Change | Blocker / evidence | Benefit | Risk | Dependencies | Targeted tests | Regression | Acceptance | Rollback |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Version-control baseline: commit live tree, copy `snap_*` manifests + patches into the project | B-08 | rollback, diffs | none (no code change) | D-13 | hash match vs manifests | – | tree hash = T11 manifest | n/a |
| 2 | Unit contract at the loader boundary (`capacity_teu = 2 × Capacity FFE` if D-01 = a) + invariance tests T1–T11 first; remove/source lane factors | B-01, B-03 | correct capacity-to-demand ratio; ledger-visible unit check | absolute figures change; classes' economics shift | D-01, D-03 | T1–T11, `test_capacity_units.py`, `test_worldsmall_loader.py` | `test_orchestrator.py` ×3; full suite vs 29-failure baseline | all T1–T11 pass; 0 new failures; ledger violations 0 | revert one loader line; `LINER_*` unset |
| 3 | Re-freeze baseline on corrected units: 10-seed paired batch, default vs LS vs final candidate on the live tree, same budget | D-8, B-04 | new defensible numbers | CBC noise | 1, 2 | per-seed CSV | – | ≥ 8/10 and mean > 0 per the existing rule | none (reports only) |
| 4 | Promote local search (opt-in → owner-approved default) | B-04; +2.28 M 20/20 | +~2 M/wk, coverage +2.9 pp, shorter stage | one post-solve heuristic; CBC lottery | D-05, 3 | `test_local_search.py` | orchestrator ×3 | ≥ 8/10 seeds, 0 violations, stage ≤ budget | `LINER_LOCAL_SEARCH` unset |
| 5 | Read-only diagnostics: pre-filter class mix (A14) and path-rank value | B-06, B-07 | decide cap / variants on data | logging only | – | unit test of the new fields | – | fields present in output JSON | remove logging |

Paper mode (D-02) and any model change to frequency granularity (D-07) are **not** recommended before October 20.

## G. Formal exit gates

| Gate | Status |
|---|---|
| A1 repository identified (root, branch, HEAD, untracked, nesting) | **PASS** |
| A2 prior evidence indexed, conflicts reconciled or marked unresolved | **PASS** |
| A3 baseline configuration frozen as an exact configuration | **PASS** (accepted default + final candidate stated; hashes; flags) |
| A4 baseline independently reproduced | **NOT VERIFIED** |
| A5 test baseline independently reproduced | **NOT VERIFIED** (not run by policy) |
| D1 pipeline mapped with source references | **PASS WITH LIMITS** |
| D2 coverage / unserved diagnostics documented, missing ones listed | **PASS** |
| D3 path-cap / pool evidence documented; value lost | **NOT VERIFIED** (not measured) |
| D4 blocker register ranked | **PASS** |
| D5 scalability | **NOT VERIFIED** (no evidence beyond 47 ports; gap list produced) |
| B1 paper unit evidence extracted with citations | **PASS** (Table 2 values NOT VERIFIED) |
| B2 our unit trace complete | **PASS** |
| B3 FFE/TEU gate | **FAIL** (D-01) |
| B4 dimensional test plan | **PASS** (specification only) |
| Safe to implement | **NO** until D-01 and D-13 are decided |
