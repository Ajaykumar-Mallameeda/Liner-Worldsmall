# Tasks 19 · 20 · 21 — acceptance report

**Date:** 2026-10-12 · **Scope:** WorldSmall only (no WorldLarge file was read) · Tasks 17 and 18 **not started**.
Every figure below is read from a recorded file (`results_matrix.md` lists every run and seed; manifest:
`experiment_manifest.json`; patches: `patches/`).  Controlled batches differ in tree and in machine state and are
compared **only within a batch**.

## 1. Verdict

| | |
|---|---|
| **Tasks 19 – 21, combined phase** | **ACCEPTED on gates 1 – 7 (all PASS)** for the configuration of §2 |
| **Whole project** | **NOT complete.** Owner decision 1 (promotion of HiGHS / a larger budget) and 2 (upper verdict bands) are `OWNER_APPROVAL_REQUIRED`; decision 3 (Tier-0 consumers) is `NOT_VERIFIED`; Tasks 17 and 18 are separate and open |
| Production defaults changed | flow re-optimisation, the ≤ 2-transfer bound, the time-feasible class correction, the profit-floor repair — each reversible by one variable (`patches/ROLLBACK.md`). **Solver CBC and the 120 s budget are frozen and unchanged; HiGHS is not the default** |
| Headline (controlled, 10 paired seeds, CBC 120 s, same batch) | profit **9.18 → 11.52 M USD/wk (+2.34 M, 10/10 seeds, smallest +0.75 M)**, demand coverage **21.2 → 25.3 % (+4.0 pp, 9/10 seeds)**, served TEU +19 %, network load factor 0.603 → 0.632, 0 ledger violations |
| Headline (end to end, orchestrator, unseeded) | profit **10.64 / 10.80 → 12.59 / 12.17 / 13.88 M** (362/362 assertions each); coverage 23.0 / 23.9 → 23.0 / 23.6 / 25.5 % (**not distinguishable** end to end at n = 2 vs 3) |

## 2. The accepted configuration

| Component | State | Evidence |
|---|---|---|
| Flow re-optimisation (`LINER_FLOW_REOPT`) | **default ON** | +3.10 M (10/10) vs B0 in batch M5; +2.34 M (10/10) vs rollback in M7 (final tree); +2.41 M (5/5) under HiGHS |
| ≤ 2 transfers (`LINER_MAX_TRANSFERS`, hard bound 2) | **default 2** (enumerated where the shorter journeys are too few; through operated capacity in the re-routing) | 1.5 – 2.4 % of served TEU, 0 transit violations; no coverage effect on WorldSmall (0 of 90 unreachable ODs rescued) |
| Time-feasible class correction (`LINER_CLASS_TIME_FEASIBLE`) | **default ON** (only while the Task 10 screening is on) | coverage +2.9 pp (9/10 seeds) at equal profit (M5); pool size unchanged |
| Profit-floor repair (`LINER_PROFIT_FLOOR_REPAIR`) | **default ON** (acts only below a weekly profit of 0) | never triggered in the 10 clean final controlled runs (M7) nor in the 3 default orchestrator runs; behaviour proven by unit tests, the offline drop-one analysis and, as an illustration only, the degraded-machine batch M6 |
| Cost-aware / hybrid path selection | opt-in, **rejected** | −6.5 M / −3.0 M under CBC |
| Adaptive per-OD budget | opt-in, **rejected** | −7.4 M (CBC, 10 seeds), −1.45 M (HiGHS) despite +3 … +8 pp coverage |
| Route operators, elitism | opt-in, no gain | −0.08 M; best-of-3 +0.14 M (3/5) |
| Coverage floor `LINER_GLOBAL_MIN_COVERAGE` | opt-in, experimental, **not proposed** | controlled: −1.55 M for +2.1 pp (floor 25 %, 10 seeds, all `feasible`); end to end (n = 2): +11.65 M / 26.1 % in one run and a loss-making incumbent (−8.69 M, 6 profit assertions failed) in the other, because the profit-floor repair is not run while a floor is active (§3.3, `evidence/comparisons/O4_coverage_floor_orchestrator.md`) |

## 3. Baseline versus integrated results

### 3.1 Controlled, final tree, same pools / budget / seeds (batch M7; `RB` = documented rollback = frozen B0)

CBC 120 s, regional hints absent, solver backend `cbc`, concurrency ≤ 4 on 16 threads, `PYTHONHASHSEED=0`, candidate-pool and
path-pool hashes recorded per run.  All 20 runs `feasible`, ledger-verified, 0 violations, reconciled.

| seed | RB profit M | D profit M | Δ profit M | RB coverage % | D coverage % | Δ coverage pp | D services / vessels | re-routing gain M | ledger viol. |
|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| 0 | 10.91 | 13.20 | +2.29 | 21.9 | 26.6 | +4.7 | 30 / 143 | 2.54 | 0 |
| 1 | 10.62 | 11.57 | +0.95 | 18.0 | 23.4 | +5.3 | 26 / 140 | 3.12 | 0 |
| 2 | 8.43 | 12.10 | +3.67 | 17.4 | 22.8 | +5.3 | 21 / 112 | 1.46 | 0 |
| 3 | 8.62 | 9.37 | +0.75 | 19.4 | 22.1 | +2.6 | 28 / 138 | 2.44 | 0 |
| 4 | 9.52 | 10.57 | +1.05 | 22.9 | 22.0 | -0.9 | 27 / 133 | 2.80 | 0 |
| 5 | 10.01 | 11.33 | +1.32 | 19.7 | 23.7 | +4.1 | 24 / 145 | 1.81 | 0 |
| 6 | 6.14 | 10.58 | +4.45 | 22.5 | 28.4 | +5.9 | 32 / 173 | 6.10 | 0 |
| 7 | 9.72 | 13.70 | +3.98 | 21.6 | 28.6 | +7.0 | 28 / 167 | 4.25 | 0 |
| 8 | 9.31 | 11.19 | +1.88 | 24.7 | 29.3 | +4.6 | 31 / 167 | 5.52 | 0 |
| 9 | 8.48 | 11.58 | +3.10 | 24.3 | 25.9 | +1.6 | 31 / 158 | 2.15 | 0 |
| **mean (sd)** | | | **+2.34** (1.37) | | | **+4.0** (2.3) | | | |

| | RB (B0) | D (default) |
|---|---:|---:|
| profit M/wk, mean (sd) | 9.18 (1.30) | **11.52 (1.20)** |
| revenue / all-in cost M/wk | 68.6 / 59.4 | 80.3 / 68.8 |
| margin on revenue | 13.6 % | 14.4 % |
| coverage / served TEU | 21.2 % / 58,715 | **25.3 % / 69,879** |
| services / vessels | 23.4 / 130 | 27.8 / 148 |
| network load factor | 0.603 | 0.632 |

*Cost is not claimed as an improvement:* cost rises with the cargo it serves (+9.4 M for +11.2 k TEU, +0.84 k USD/TEU);
the margin is unchanged-to-higher and profit is higher in every seed.

### 3.2 Rollback reproduces the frozen baseline

RB vs the frozen B0 results of batch M5 on the same ten pools: **identical to the dollar on 8 of 10 seeds**, with
identical path-pool hashes, dual bounds and model sizes on all 10; seeds 6 and 8 differ only in the time-limited CBC
incumbent (−5.62 vs +6.14 M; 9.40 vs 9.31 M) for the *same* model — the known CPU-timing sensitivity of CBC at 120 s
(`evidence/comparisons/` and `task20_path_selection.md` §7).

### 3.3 End to end (orchestrator, `tests/test_orchestrator.py`, regional hints, 3 iterations, LLM 429s ignored as instructed, unseeded)

| run | configuration | assertions | profit M/wk | margin % | coverage % | services / vessels | re-routing gain M | iteration |
|---|---|---|---:|---:|---:|---|---:|---:|
| `T19B0_orch_run1` | frozen B0 | 342/342 | 10.64 | 14.5 | 23.04 | 24 / 133 | — | 1 |
| `T19B0_orch_run2` | frozen B0 | 342/342 | 10.80 | 14.3 | 23.94 | 25 / 135 | — | 1 |
| `T19O_default_run1` | **accepted default** | 362/362 | 12.59 | 17.5 | 23.02 | 24 / 130 | 3.08 | 1 |
| `T19O_default_run2` | accepted default | 362/362 | 12.17 | 16.1 | 23.61 | 28 / 141 | 2.57 | 0 |
| `T19O_default_run3` | accepted default | 362/362 | 13.88 | 17.0 | 25.47 | 30 / 145 | 4.80 | 0 |
| `T19O_rollback_run1` | documented rollback switches | 360/360 | 10.66 | 16.5 | 19.69 | 22 / 111 | — | 2 |

All six: `complete`, ledger verified, 0 violations, regional partition reconciled.  362 = 342 + 20 new assertions
(§N.9 strategy report vs independent recomputation, §N.10 re-optimisation, journey bound); the rollback run has 360 because
two §N.10 value assertions apply only when the re-optimisation is applied.  Historical reference (Tasks 14–16, same code
as B0, 5 runs): 9.98 – 11.82 M, mean 10.88, coverage 23.7 – 24.6 %.
End to end the profit gain is **+2.2 M (+20 %)**; the coverage gain seen in the controlled batches is **not visible** here
(24.0 vs 23.5 %): the selected iteration is a profit-weighted best of three, and the end-to-end n is 2 vs 3.

**Opt-in coverage floor, end to end (`LINER_GLOBAL_MIN_COVERAGE=0.25`, experimental, not part of the accepted default):**

| run | assertions | profit M/wk | margin % | coverage % | services / vessels | global stage per iteration (0 / 1 / 2) |
|---|---|---:|---:|---:|---|---|
| `T19O_cov25_run1` | **355/361 — 6 failed** | **−8.69** | −9.8 | 28.43 | 35 / 215 | not_solved / not_solved / feasible |
| `T19O_cov25_run2` | 362/362 | 11.65 | 13.8 | 26.10 | 26 / 161 | not_solved / feasible / feasible |

Both: `complete`, ledger verified, 0 violations, reconciled, honest statuses.  The six failed assertions of run 1 are the
profit-positivity assertions on a plan that really is loss-making.  Cause (code and output files): with a floor active the
time-limited CBC returned no incumbent on the early pools (`not_solved`, regional fallback), and `plan.py:212` deliberately
skips the profit-floor repair while a floor is set, so the −8.69 M incumbent was not repaired.  n = 2, no rate estimated;
this is the reason the floor is **not** proposed for approval.  Follow-up (not implemented, to keep the accepted patch
series unchanged): run the repair under the floor and re-test ≥ 10 seeds (`remaining_tasks.md` C).

### 3.4 Opt-in HiGHS, same pools (experimental; **not** the default) — batch M8, HiGHS 300 s, seeds 0 – 4

| seed | RB profit M | D profit M | Δ profit M | RB coverage % | D coverage % | Δ coverage pp | D services / vessels | re-routing gain M | ledger viol. |
|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| 0 | 12.47 | 14.57 | +2.11 | 25.8 | 27.8 | +2.0 | 28 / 144 | 2.62 | 0 |
| 1 | 12.19 | 15.44 | +3.24 | 25.5 | 28.0 | +2.5 | 27 / 154 | 3.33 | 0 |
| 2 | 11.63 | 12.92 | +1.29 | 26.3 | 25.3 | -1.0 | 25 / 141 | 2.96 | 0 |
| 3 | 9.81 | 10.76 | +0.95 | 20.9 | 25.5 | +4.6 | 33 / 155 | 2.67 | 0 |
| 4 | 8.03 | 13.83 | +5.80 | 22.5 | 24.8 | +2.3 | 24 / 131 | 3.82 | 0 |
| **mean (sd)** | | | **+2.68** (1.96) | | | **+2.1** (2.0) | | | |

HiGHS rollback 10.83 M (cov 24.2 %) → HiGHS default 13.50 M (cov 26.3 %), **+2.68 M, 5/5**; versus the frozen CBC
configuration on the same five pools (9.62 M, cov 19.9 %) the HiGHS + default + 300 s configuration is **+3.9 M**.  On 3 of 5
seeds the delivered profit is **above the dual bound of the capped model** (14.57 > 13.7, 15.44 > 13.7, 13.83 > 12.7 M):
the 10-fastest-paths cap excluded plans worth more than the proven bound of the model it defines — the cost of the cap is
larger than the optimality gap.  End to end, HiGHS: 120 s **10.54 M, cov 19.8 %** (the Tasks 14–16 interaction: a harder
instance for the same budget), 300 s **15.54 M, margin 18.4 %, cov 27.5 %** (n = 1 each, 362/362).

**Solver × budget on the same five pools** (profit M/wk, coverage %; CBC rows from batch M7 seeds 0–4, HiGHS rows from M8 and
M11 — M11 is a **long-budget reference**, separately labelled, experimental):

| configuration | CBC 120 s (frozen) | HiGHS 300 s | HiGHS 600 s (reference) |
|---|---:|---:|---:|
| documented rollback (= frozen B0 model) | 9.62 / 19.9 % | 10.83 / 24.2 % | 11.56 / 25.4 % |
| **accepted default** | 11.36 / 23.4 % | 13.50 / 26.3 % | 14.07 / 26.6 % |

Dual-bound gaps of the capped model (HiGHS): rollback 7.6 – 35 % at 300 s, 0.0 – 17.8 % at 600 s (seed 2 proven optimal);
default: the delivered profit exceeds the capped model's bound on 4 of 5 seeds at 600 s.  The budget curve is flattening
(+0.57 M from 300 to 600 s for the default) while the default's lead over the rollback (+2.5 M at 600 s) persists; the
HiGHS-vs-CBC difference at equal configuration is +1.2 M (rollback) … +2.1 M (default) at 300 s.  The per-seed rows of M11 are in
`evidence/comparisons/M11_paired_rows.md`.

## 4. Gates

| Gate | Status | Evidence |
|---|---|---|
| **1 Integrity and feasibility** | **PASS** | 0 independent-ledger violations in 247 controlled runs with a plan, 45 iteration runs and 10 orchestrator runs (counts: `evidence/comparisons/integrity_counts_final.txt`); reconciled in every one; regional partition equals the ledger (also for a two-transfer plan: `TestGlobalStage`); the independent recomputation (written without `src` code; dry-run first reproduced a recorded baseline output to the cent) checks revenue, every cost line, fleet, leg loads, transit and the new journey bound; no flow on an inactive service above 1e-6 TEU; a plan improved outside the solved model is reported `feasible`, never `optimal` (`TestFlowReoptimisation`, §N.10); 22 controlled runs ended `not_solved` (18 in the degraded batch M6) — an explicit non-result, never a number; no missing input was turned into zero economics |
| **2 Regression** | **PASS** | focused tests of every changed module (203 passed); orchestrator 362/362 × 3 default (+ rollback 360/360; the experimental opt-in floor: 362/362 and 355/361, §3.3 — not the default); whole suite artifact-free **51 failed / 1,198 passed → 51 / 1,257**, artifact-present **53 / 1,222 → 53 / 1,281**: the failing sets are **identical** (the documented Tasks 8–10 / 14–16 baseline), 0 newly failing, 59 new passing tests (`evidence/comparisons/suite_diff_B0_vs_final_*.md`) |
| **3 Coverage and utilisation** | **PASS** (controlled); end-to-end coverage inconclusive | coverage +4.0 pp (9/10 seeds), load factor 0.603 → 0.632 (10 seeds), legs ≥ 95 % full 22 → 28 of 72, idle capacity cost 19.4 → 16.6 M (M5); gain attributed separately to services already selected (re-routing: +1.5 pp, +4.2 k TEU on paid-for capacity) and to added services (class correction: +2.9 pp, +16 vessels). Bottleneck analysis: unserved demand is ≈ 49 – 59 % "not economic to open a service at the incumbent", 7 – 15 % class inventory exhausted, 3 – 4 % leg capacity, 3.4 % limit below sailing time (not servable), 2 – 5 % no time-feasible candidate (`strategy_tables_M5.md`) |
| **4 Profit and bounded cost** | **PASS** | approved safeguards derived from the project: ledger-verified profit ≥ 0 (coordinator profit floor 0.0), 15 % margin **advisory** (not a gate; the frozen baseline itself finished `complete` at 14.3 – 14.5 %), coverage target 70 % is a feedback signal; **no cost budget exists and none was invented**.  Every default run has profit > 0, ledger-verified; the coverage–profit–cost frontier is reported (§3.1, `task19_network_adaptation.md` §5): cost +9.4 M for +11.2 k TEU, margin 13.6 → 14.4 % |
| **5 Quality** | **PASS** | 0 transit-limit violations in every strategy of every run (minimum slack 0.1 d); multi-hop mean transit 35 – 37 d (p90 41 – 42 d); transfers per TEU by strategy, dwell 48 h + 3.5 d per transfer and port-stay assumptions are stated in the output |
| **6 Reproducibility and provenance** | **PASS** (with the limits of Tasks 17 / 18) | controlled generator seeds 0 – 9, `PYTHONHASHSEED=0`, per-run tree manifest hashes, configuration environment, solver backend, budget, pool and path hashes, exit codes, output paths (`experiment_manifest.json`); not claimed: full-pipeline RNG control (Task 17), source-data validation (Task 18) |
| **7 Rollback and maintainability** | **PASS** | all new behaviour behind switches; explicit rollback restores pool and path-set hashes (seeds 1–3), the frozen B0 profits (8/10 seeds to the dollar, same models on all) and 360/360 end to end; the Tasks 9/10 rollback still restores the pre-Task-9 pool element by element with the new defaults on; 17 files changed, no new package, HiGHS not the default; tests exist for enabled **and** disabled modes; the patch series reproduces the final tree byte for byte |

## 5. Owner-decision gate (statuses; `owner_decisions.json`)

| Decision | Status | Evidence |
|---|---|---|
| 1a Production solver and global-stage budget | **FROZEN** | CBC (LP-guided restriction), 120 s; every default-configuration run used them |
| 1b HiGHS / budget comparison | **EXPERIMENTAL** | §3.4 (batches M2, M8, M11): solver, budget, concurrency, seeds, pools, objective, dual bound, gap recorded |
| 1c Promoting HiGHS or changing the budget | **OWNER_APPROVAL_REQUIRED** | a better experimental result is evidence, not authorisation; the recommended configuration is reported in §6 |
| 2a Upper verdict labels and thresholds | **FROZEN** | executive summary 20 %, regional 25 %, advisory 15 % — unchanged by the patch |
| 2b 20 % vs 25 % discrepancy | **OWNER_APPROVAL_REQUIRED** | recorded, not corrected, not represented as resolved |
| 3 Full Tier-0 recertification | **NOT_VERIFIED** | Python decision layer verified; consumers partly executed, defects T0-1 … T0-8, WebSocket live path / replay / several components / real browser not executed (`tier0_consumer_recertification.md`) |

## 6. Recommended configuration (separate from the accepted default; needs owner approval)

**HiGHS backend (`NETWORK_MILP_BACKEND=highs`) with the global-stage budget raised to 300 s, together with the accepted
defaults.**  Evidence (same pools): controlled 13.50 M, coverage 26.3 %, margin 16.4 % vs the frozen configuration's
9.62 M, 19.9 % (5 seeds, +3.9 M); end to end 15.54 M, 27.5 % (n = 1).  Costs: the global stage takes 300 s instead of 120 s
per iteration (the orchestrator run ≈ 17 min instead of ≈ 8); at 120 s HiGHS is **worse** (10.54 M, 19.8 %, end to end) —
the solver and the budget must be approved together (Tasks 14–16, owner decision 1).  Not adopted here; no default changed.

## 7. Confidence limitations

* Ten seeds of one generator on one dataset; controlled runs bypass the regional GA / MILP hints; end-to-end n = 2 – 3.
* CBC at 120 s is CPU-load sensitive; comparisons are within-batch, and one batch (M6) is excluded.
* The coverage gain is demonstrated in the controlled batches, not end to end.
* The opt-in coverage floor can return a loss-making time-limited incumbent end to end (1 of 2 runs) because the
  profit-floor repair is not run while a floor is active; it stays experimental.
* A `not_solved` global stage on an early iteration is an explicit non-result (regional fallback, labelled
  `Unverified (not_solved)`); in all 10 recorded orchestrator runs the selected iteration is ledger-verified.
* Time-limited incumbents: the global stage reports `feasible` with a stated bound, never a proof; after re-routing the bound
  belongs to the capped model (`bound_applies_to`).
* Strategy labels (`feeder` / `hub_and_spoke`) are descriptive conventions.
* 41 ODs (3.4 % of demand) are unservable under the current `TransitTime` reading (unit unverified, Task 18).

## 8. Remaining defects and owner decisions

See `remaining_tasks.md` (A: Tasks 17 / 18; B: owner decisions; C: technical items) and `tier0_consumer_recertification.md`.

## 9. Statement

The combined phase of Tasks 19, 20 and 21 is **accepted** on gates 1 – 7 on the evidence above.  The project is **not**
declared complete: three owner decisions are unresolved or unverified and Tasks 17 and 18 have not been started.
