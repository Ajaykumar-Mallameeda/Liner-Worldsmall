# Tasks 14 · 15 · 16 — final acceptance summary

**Date:** 2026-10-11 · **Scope:** WorldSmall only (no WorldLarge file read) · **Not done, by instruction:** Task 11
(two-transfer paths), Task 12 (route-level GA operators). Detailed records: `task14_tier0_recertification.md`,
`task15_milp_strategy_comparison.md`, `task16_regional_filter_economics.md`; manifest `experiment_manifest.json`;
evidence under `evidence/` (every run has a `.log` and `.meta.txt`; every figure below comes from a recorded file).

Legend: **[prev]** previously reported (Tasks 8–10 reports), **[repro]** newly reproduced in this run, **[new]** newly
observed, **[proven]** proven optimum, **[feasible]** time-limited incumbent.

## 1. Executive verdict

| | Result |
|---|---|
| **Task 14** — advisory 15 % margin verdict | **PASS, adopted.** The 15 % is a reported band; no path rejects, re-runs or de-selects a feasible, verified, positive-profit network below it (a real pipeline run at 14.67 % finished `complete`, ledger verified, 0 violations). Three misclassifications fixed (undefined margin shown as 0.0 %; `>` vs `>=` at exactly 15 %; a region without revenue called "Poor"). Full Tier-0 recertification **not claimed**: frontend/backend consumers were read, not executed |
| **Task 15** — global MILP | Production strategy realises **90.9 %** of the **proven optimum** (8.49 vs 9.33 M/wk, 5 paired seeds). **Two defects fixed and adopted** (slack vessels made a feasible incumbent "unverified" — in 2 of 3 end-to-end runs with the new pool; solver noise reported as a flow). **HiGHS backend implemented, opt-in**: +0.82 M/wk (+9.7 %, 5/5 seeds; end-to-end 9.7 – 10.5 M vs 8.5 – 9.2 M). Making it the default needs the owner's approval. No CBC-only strategy beat production |
| **Task 16** — regional filter | The margin guess **removes nothing** in the current defaults; the cap ranked by a class constant and cut ≈ 120 small Feeder_800 feeders per seed. **Economic replacement adopted as the default** (`LINER_REGIONAL_FILTER=auto`): end to end **9.98 – 11.82 M (n = 5, mean 10.88) vs 8.48 – 9.19 M (7 legacy runs, mean 8.94)**, coverage ≈ 24 % vs ≈ 20 %; controlled +0.51 M (4/5 seeds); HiGHS 600 s +2.15 M (5/5). Reversible by `LINER_REGIONAL_FILTER=legacy`; interacts with the opt-in HiGHS at 120 s (−0.64 M). Found: the per-OD **10-fastest-paths cap discards 77–84 % of valid paths** and interacts with the pool |
| Failed gates | **One, understood and fixed:** `T15_orch_highs_run3` 341/342 (solver-noise flow; patch C, then 3 × 342/342). No other gate failed |
| Pending owner decisions | HiGHS as default **and** the global-stage budget (decide together with the filter); upper verdict bands (20 vs 25); Tier-0 consumer sign-off |

## 2. Task 14 (details: `task14_tier0_recertification.md`)

* **Owner decision recorded** verbatim, dated 2026-10-11; implemented as exactly that: number unchanged, no gate added.
* **Audit:** `canonical_network_economics`, coordinator metrics/evaluation/feedback, `IterationSelector`, payload
  assembly, report writers, API/frontend consumers (§8 of that record).
* **Evidence [repro]:** baseline orchestrator 342/342 (`B0_orch1`, 8.71 M/wk); patched tree 342/342 (`T14_orch1`,
  9.19 M/wk, margin **14.67 % < 15 %**, status `complete`); focused 79 passed / 5 skipped (artifact-dependent); 29 new
  tests, all failing on the baseline; whole suite 51 failed / 1,143 passed → 51 / 1,172, **0 newly failing** (and
  51 / 1,198 on the final tree, §7).
* **Patch:** `evidence/patches/task14_advisory_margin_verdict.patch` (6 files).

## 3. Task 15 — baseline versus candidate, every seed (details: `task15_milp_strategy_comparison.md`)

Ledger operating profit, USD M/week, 120 s unless stated; pools of generator seeds 0–4, production defaults.

| seed | **[proven]** optimum (HiGHS, gap ≤ 0.009 %) | production CBC [repro] | % of optimum | `reconciled` (baseline code) | HiGHS backend 120 s | economic filter + CBC 120 s | economic filter + HiGHS 600 s [feasible] |
|---:|---:|---:|---:|---|---:|---:|---:|
| 0 | 9.98 | 9.66 | 96.8 | true | 9.85 | 8.57 | 12.45 |
| 1 | 9.37 | 8.32 | 88.8 | **false** (4 slack vessels, 1.064 M) | 9.37 | 10.62 | 12.19 |
| 2 | 8.83 | 8.28 | 93.7 | true | 8.83 | 8.43 | 11.63 |
| 3 | 9.42 | 8.41 | 89.3 | true | 9.42 | 8.62 | 10.27 |
| 4 | 9.07 | 7.77 | 85.7 | true | 9.07 | 9.52 | 10.87 |
| **mean (sd)** | **9.33 (0.43)** | **8.49 (0.70)** | 90.9 | 4/5 | **9.31 (0.39)** | 9.15 (0.93) | 11.48 (0.91) |

(production CBC on the same pools measured a second time in the Task 16 batch: 9.66 / 8.32 / 8.28 / 8.42 / 8.54, mean
8.64; the two measurements differ by CPU load — see the CPU caveat in the Task 15 record.)

Solver status: production always `feasible`; unrestricted CBC `not_solved` on 2/5 and loss-making on 3/5; HiGHS
`optimal` (gap ≤ 1e-4) on 3/5 pools inside 120 s and on 5/5 pools in 78 – 160 s when run alone (200 – 296 s with five
solver processes competing).

| Strategy (paired vs production, 5 seeds) | mean M | Δ | seeds better | adopted |
|---|---:|---:|---:|---|
| unrestricted CBC | −5.00 (3/5 usable) | −13.57 | 0/3 | no |
| two-stage CBC (T1 = 40 / 60 s) | 7.97 (1/5) / 5.75 | −1.69 / −2.74 | 0/1 / 0/5 | no |
| LP support ∪ stand-alone-profitable | 7.87 | −0.62 | 1/5 | no |
| union of 3 LP supports | 8.12 | −0.37 | 1/5 | no |
| top-120 / top-60 LP-revenue services | 8.17 / 7.33 | −0.32 / −1.16 | 2/5 / 0/5 | no |
| progressive restricted CBC (120→200→support) | 8.67 | +0.19 | 2/5 | no (inside noise) |
| **HiGHS unrestricted (opt-in backend)** | **9.31** | **+0.82** | **5/5** | **opt-in; default needs approval** |

End to end (orchestrator, regional hints, 120 s, unseeded, n runs):

| configuration | runs (M/wk) | mean | coverage % |
|---|---|---:|---:|
| CBC + legacy filter | 8.71, 9.19, 8.48, 9.06, 9.02, 9.11, 9.03 (n = 7) | 8.94 | ≈ 20.0 |
| HiGHS (opt-in) + legacy filter | 10.47, 9.73, 10.31 | 10.17 | 19.7 – 20.8 |
| **CBC + economic filter (new default)**: three gate runs, then two runs of the final tree with no environment variables set | 10.85, 9.98, 11.82; 10.33, 11.42 (n = 5) | **10.88** | 23.7 – 24.6 |
| HiGHS + economic filter, 120 s | 9.82 (n = 1; third iteration gap 45 %) | 9.82 | 17.6 |

## 4. Task 16 — old versus new filter (details: `task16_regional_filter_economics.md`)

| | legacy | economic (default under `auto`) |
|---|---|---|
| margin test | class constant `capacity × 75 > one vessel's hire`; **rejects 0 of 8,491** candidates | none; no class named |
| cap order | class ratio (a constant) → generation order inside a class; cuts ≈ 120 Feeder_800 per seed | canonical stand-alone profit, ties in generation order; unknown → last, counted |
| Feeder_450 | 24.8 per seed, all exempt demand loops, **all loss-making** (−0.24 … −0.99 M), operated in **0 of 119 plans** | same treatment as every class |
| pool swap (seeds 1–3) | — | 16 – 69 per region: Feeder_800 in, Post/Super-panamax out; pool size unchanged |
| production CBC 120 s, controlled | 8.64 | 9.15 (4/5 seeds) |
| end to end, 120 s | 8.94 (n = 7) | 10.88 (n = 5, all above all legacy runs) |
| HiGHS 600 s | 9.33 [proven] | 11.48 [feasible, gaps 7 – 20 %] |
| HiGHS 120 s | 9.31 | 8.67 (2/5 seeds) |
| path cap 10 → 30, HiGHS 600 s | 9.33 → 5.29 (seed 3: 12.40) | 11.48 → 7.49 |

## 5. Cost analysis (USD M/week, means of 5 seeds; a lower cost from serving less is **not** claimed as an improvement)

| comparison | revenue | hire | fuel | port calls | handling | transshipment | profit | served TEU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| production CBC → HiGHS 120 s (same pools) | 63.78 → 61.67 | 17.31 → 16.65 | 26.30 → 24.35 | 0.58 → 0.54 | 10.43 → 10.27 | 0.19 → 0.09 | 8.49 → 9.31 | 55.1 k → 53.2 k |
| HiGHS 600 s legacy → economic | 63.1 → 80.7 | 17.1 → 21.8 | 25.0 → 32.1 | 0.55 → 0.75 | 10.5 → 13.3 | 0.11 → 0.59 | 9.33 → 11.48 | 54.5 k → 70.4 k |
| CBC 120 s legacy → economic | 63.4 → 64.2 | 17.3 → 17.0 | 25.8 → 26.2 | 0.55 → 0.60 | 10.5 → 10.3 | 0.15 → 0.37 | 8.64 → 9.15 | 55.0 k → 54.8 k |

Reading: the HiGHS plans are the **cost-efficient** ones (hire −0.66, fuel −1.95, total −2.9 M, with 3.5 % less cargo
carried because the dropped cargo was marginal: margin 13.4 → 15.1 %); the economic-pool plans at 600 s are **volume**
plans (+29 % cargo, every cost line up, margin unchanged ≈ 14.2 %, profit +2.15 M). Transshipment cost rising is the
signature of the feeder → hub connections the legacy cap had been removing. Controlled CBC at 120 s moves cost and cargo
by less than the run-to-run spread; the end-to-end runs show the volume effect (coverage ≈ 20 % → ≈ 24 %).

## 6. Acceptance gates (explicit status)

| Gate | Task | Status |
|---|---|---|
| Feasible, positive-profit network not rejected for margin < 15 % | 14 | **PASS** |
| Ledger valid; Tier-0 regression tests; orchestrator | 14 | **PASS** (342/342) |
| Full Tier-0 recertification | 14 | **NOT CLAIMED** (consumers not executed; label-band decision open) |
| Hard constraints not weakened (all patches) | 15/16 | **PASS** |
| Independent ledger zero violations | 15/16 | **PASS** — 0 in 119 recorded controlled runs and every orchestrator run |
| Regional = global | 15/16 | **PASS** |
| No unexplained orchestrator regression | 15/16 | **PASS after one understood failure** (341/342 → patch C → 3 × 342/342 HiGHS; 342/342 CBC with the economic filter ×3 and on the final default configuration ×2) |
| Paired-seed evidence & runtime trade-off documented | 15/16 | **PASS** (5 seeds, every seed reported) |
| Time limit respected | 15 | **PASS** (120 s; HiGHS deadline includes model build) |
| Status/optimality claims accurate | 15 | **PASS** (`optimal` only on HiGHS optimality with gap ≤ 1e-4, reported; tests) |
| New solver without approval | 15 | **RESPECTED** — HiGHS is opt-in; default solver unchanged |
| Pool restored with Task 9/10 switches off | 16 | **PASS** (element by element, seeds 1–3, final code) |
| No blanket Feeder_450 exemption / no hard-coded revenue / no zero fallback | 16 | **PASS** |
| Defensible improvement under the production configuration | 16 | **PASS** — end to end 5/5 above all 7 legacy runs (+1.9 M mean), controlled +0.51 M 4/5, HiGHS 600 s +2.15 M 5/5; **not** an improvement with opt-in HiGHS at 120 s (−0.64 M) — documented |
| Stop conditions (checkout mismatch, input unresolved, constraint relaxed, invented value, ledger violation, non-reconciling totals, uncomparable experiment, unexplained failure) | all | **none triggered** (one test failure explained and fixed; one contaminated experiment identified, labelled and not used) |
| Task 11 / Task 12 | — | **NOT STARTED** (instruction) |

## 7. Regression comparison

Same command in a fresh snapshot of each tree: `pytest tests --ignore=tests/test_orchestrator.py` (the orchestrator is
gated separately, §3/§6). "Artifact-free" = no `pipeline_output.json` at the root; "artifact-present" = the artifact of a
pipeline run copied in (the two states the previous mission compared). Tool: `compare_suites.py`.

| state | tree | failed | passed | skipped | newly failing vs `B0` | fixed | new tests (all passing) |
|---|---|---:|---:|---:|---:|---:|---:|
| artifact-free | baseline `B0` [repro] | 51 | 1,143 | 46 | — | — | — |
| artifact-free | after Task 14 (`T14_suite_free`) | 51 | 1,172 | 46 | **0** | 0 | 29 |
| artifact-free | **final tree** (`FINAL2_suite_free`) | 51 | 1,198 | 46 | **0** | 0 | 55 |
| artifact-present | baseline `B0` [repro] | 53 | 1,167 | 20 | — | — | — |
| artifact-present | **final tree** (`FINAL2_suite_present`) | 53 | 1,222 | 20 | **0** | 0 | 55 |

The failing sets are identical to the baseline's (51 / 53): missing `MULTI_AGENT_*.json` audit artifacts
(`test_economic_metric_documentation`, 29), LLM mock/activation tests (`test_regional_agent_activation`, `test_llm`), phase-8
command centre, SHA pins, `test_setup`, the 5-region count of `test_output_contract`. They are the **documented baseline
failures** of the Tasks 8–10 report (51 and 53) and none was edited, skipped or relabelled. One existing test changed:
`tests/test_class_screening.py::test_the_regional_filter_is_not_bypassed_by_screening` now sets
`LINER_REGIONAL_FILTER=legacy` first — it asserts the behaviour of the *legacy* margin guess, and its assertion is
unchanged; the economic filter's behaviour has its own tests (`tests/test_regional_filter.py`).

Orchestrator (`tests/test_orchestrator.py`), every recorded run of this mission, all with LLM 429s ignored as instructed:

| run | configuration | assertions | profit M/wk |
|---|---|---|---:|
| `B0_orch1` | baseline | 342/342 | 8.71 |
| `T14_orch1` | + Task 14 | 342/342 | 9.19 |
| `T15_orch_default_run1`, `T15g2_orch_default_run1` | + 15 (CBC default) | 342/342 ×2 | 8.48, 9.06 |
| `T15_orch_highs_run1..3` | HiGHS, before patch C | 342/342, 342/342, **341/342** | 9.60, 10.57, 10.04 |
| `T15g2_orch_highs_run1..3` | HiGHS, with patch C | 342/342 ×3 | 10.47, 9.73, 10.31 |
| `T16g_orch_econ_run1..3` | economic filter, CBC | 342/342 ×3 | 10.85, 9.98, 11.82 |
| `T16g_orch_econ_highs_run1` | economic filter + HiGHS | 342/342 | 9.82 |
| `FINAL2_orch_default_run1..2` | **final tree, no environment variables** | 342/342 ×2 | 10.33, 11.42 |

Full register with commands, elapsed time and fallback counts: `evidence/comparisons/run_register.md`.

## 8. Patch inventory

All under `evidence/patches/` with `patches.sha256`. Applied in the order below on the baseline `B0`, the five patches
reproduce the final `src/` and `tests/` **byte for byte** (157 files, 0 differences — `git -c core.autocrlf=false apply`;
this machine has `core.autocrlf=true`, which rewrites LF files as CRLF otherwise). `tasks_14_15_16_cumulative.patch` applies on
`B0` in one step (`git apply --check` OK). `task16_economic_regional_filter_opt_in.patch` is the superseded first version
(`SUPERSEDED_NOTE.md`).

| # | Patch | Files | sha256 | Rationale | Default behaviour |
|---|---|---:|---|---|---|
| 1 | `task14_advisory_margin_verdict.patch` | 6 | `9270df83…ae331d835` | one definition of the advisory band; margin never fabricated; boundary `>=`; report fields | changed (reporting only) |
| 2 | `task15_A_incumbent_vessel_trim.patch` | 3 | `5f624812…500f47` | slack vessels in a time-limited incumbent made a feasible plan "unverified" | changed (defect fix; same plan) |
| 3 | `task15_B_opt_in_highs_backend.patch` | 3 | `e8971782…ff8551d5d` | HiGHS (scipy) backend for free-frequency solves; honest status; no silent fallback | **unchanged** (CBC) |
| 4 | `task15_C_solver_noise_flows.patch` | 2 | `50ba8b61…025740d` | flows ≤ 1e-6 TEU are solver noise (found by gate 341/342) | changed (defect fix) |
| 5 | `task16_economic_regional_filter_default.patch` | 5 | `86cd174e…06514d6` | canonical-economics cap ranking; default `auto`; Task 10 test pinned to legacy | **changed** (economic while Task 9/10 generators on) |
| — | `tasks_14_15_16_cumulative.patch` | 14 | `0ec66996…9a4cb6` | all of the above | — |

Rollback (no file is deleted by these instructions): `git apply -R` the patches in reverse order, or restore the files from
snapshot `D:\liner_scratch\snap_B0_orch1` (manifest `snap_B0_orch1.manifest.json`). Behavioural rollback without touching
files: `LINER_REGIONAL_FILTER=legacy` (filter alone), `LINER_DEMAND_LOOP_BUDGET=0 LINER_CLASS_SCREEN=0` (also restores
the Task 9/10 pool exactly), do not set `NETWORK_MILP_BACKEND`; patches 1, 2 and 4 are defect fixes with no switch.

## 9. Pending work (genuine only)

| # | Item | Priority | Depends on |
|---|---|---|---|
| 1 | Owner: approve HiGHS (`scipy.optimize.milp`, already pinned) as the global-MILP default — with `LINER_REGIONAL_FILTER=legacy` at 120 s, or with a larger budget | P0 | — |
| 2 | Owner: global-stage budget (120 s → 300 s?) together with the filter; measured: economic + HiGHS 120 s is *worse* than legacy + HiGHS (8.67 vs 9.31), 300 s (10.4) and 600 s (11.5) better | P0 | 1 |
| 3 | Cost-aware OD path selection (best 10, not fastest 10; the cap drops 77–84 % of valid paths; raising it to 30 is intractable for a 600 s MILP) | P1 | — |
| 4 | Decide the upper verdict bands (20 % executive summary vs 25 % regional) | P2 | — |
| 5 | Execute and sign off the frontend/backend margin consumers (Tier-0 full recertification) | P2 | — |
| 6 | Hints for the HiGHS path (no warm start in `scipy.optimize.milp`) / newer HiGHS via `highspy` if a dependency is ever approved | P3 | 1 |
| 7 | Unseeded legacy generator sections / GA global `random` (pipeline not bit-reproducible); CBC at 120 s is CPU-load sensitive | P3 | — |
| 8 | Tasks 11 and 12 (instructed out of scope) | — | 3 |

## 10. Recommended next action

**Approve HiGHS as the global-stage solver and, in the same decision, set the global-stage budget** (the data, controlled:
legacy filter + HiGHS 120 s = 9.31 M; economic filter + HiGHS 300 s = 10.4 M, 600 s = 11.5 M; economic + HiGHS 120 s = 8.67 M;
today's default CBC + economic = 9.15 M controlled / 10.9 M end to end). It is the single remaining change with a large
measured effect, it is already implemented and gated, and it makes the optimality gap observable. If the budget cannot grow,
enable HiGHS only together with `LINER_REGIONAL_FILTER=legacy`.
