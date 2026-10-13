# Remaining work after Tasks 19 – 21 (genuine items only)

**Date:** 2026-10-12 · The combined phase is not the whole project: nothing below is claimed complete.

## A. Final-hardening tasks that this mission was told not to start

| # | Item | Why it is still open |
|---|---|---|
| 17 | Full-pipeline random-number control and wider reproducibility | Controlled generator seeds were used for paired pools only. The production pipeline is still unseeded (legacy generator sections, GA global `random`), CBC at 120 s is CPU-load sensitive (two batches of this mission differ for identical inputs: B0 seed 8, 5.05 vs 9.40 M; a degraded-machine batch returned `not_solved` on 18 of 40 runs) |
| 18 | Maritime source-data validation, unresolved units / assumptions | `TransitTime` is read as days (unverified): **41 ODs, 3.4 % of demand**, have a limit below the pure sailing time at the fastest class speed and are unservable by any network — a unit / data question. `Capacity FFE` is read as TEU (provisional). Port stay 24 h, transshipment 48 h + 3.5 d wait are assumptions, not source values |

## B. Owner decisions (statuses in `owner_decisions.json`)

| # | Decision | State |
|---|---|---|
| 1 | HiGHS as the global-MILP default and the global-stage budget (decide together with the economic regional filter) | `OWNER_APPROVAL_REQUIRED`; the recommended configuration and its evidence are in `acceptance_report.md` §6; production CBC / 120 s unchanged |
| 2 | Upper verdict bands: 20 % (executive summary) vs 25 % (regional explanations) (+ the unreferenced 20 % `BenchmarkBadge`) | `OWNER_APPROVAL_REQUIRED`; labels and thresholds preserved exactly; discrepancy recorded, not corrected |
| 3 | Tier-0 consumers: dispositions of defects T0-1 … T0-8 and execution of the not-executed consumers | `NOT_VERIFIED`; see `tier0_consumer_recertification.md` |
| 4 | An explicit coverage policy (`LINER_GLOBAL_MIN_COVERAGE`) — the frontier shows what a floor costs | not an approved bound; the opt-in knob exists, no default is set |
| 5 | Classification labels of the strategy report (`feeder` = capacity-tier difference of the two services, `hub_and_spoke` = same tier) | descriptive convention; owner may prefer another definition |

## C. Technical work the evidence points to

| Priority | Item | Evidence |
|---|---|---|
| P1 | Global MILP incumbent quality under CBC: negative-profit and `not_solved` incumbents occur on loaded pools (B0: −5.6 M on one of ten seeds); the repair and re-routing contain the damage but do not remove the cause | M4 / M5 / M6 |
| P1 | Capacity that is not economic to open: ≈ 59 % of demand is unserved because no service is worth its weekly cost at the incumbent, 7 % because a class inventory is exhausted. The model's integer weekly frequency (f ≥ 1, `ceil(T f / 7)` vessels) makes long thin routes expensive — whether fortnightly service or another frequency granularity exists in the source is an input question, not tested | strategy tables |
| P1 | Coverage floor (`LINER_GLOBAL_MIN_COVERAGE`) end to end: with a floor active the profit-floor repair is skipped (`plan.py:212`), and in 1 of 2 orchestrator runs the time-limited incumbent was loss-making (−8.69 M, 6 profit assertions failed) after two `not_solved` iterations. Fix to test: pass `floor_teu` into `repair_profit_floor` and reject trials that fall below it, then ≥ 10 end-to-end seeds. Not implemented (accepted patch series unchanged); the option stays opt-in | O4 (`evidence/comparisons/O4_coverage_floor_orchestrator.md`), M10 |
| P2 | Adaptive per-OD path budget is unstable under CBC and HiGHS; a solver-aware variant (or a smaller adaptive range) was not explored | M3 / M4 / M5 / M2 |
| P2 | Route-level operators found no measurable gain over their elite pool; elitism result in `task21_candidate_diversity.md`; a feedback loop driven by LP duals (column generation) is the untested alternative | M3 `ROP`, M9 |
| P3 | Two-transfer journeys: kept as a bounded, verified capability (1.5 – 2.4 % of served TEU); no coverage effect on WorldSmall; a dataset with sparser feeder networks would be the test | M5 |
| P3 | Frontend: null-safe margin handling and a single verdict source (T0-1 … T0-5) once the owner has decided the semantics | Tier-0 tables |
| P3 | Larger path reference (cap 30) was not repeated; historical result (Tasks 14–16): intractable for a 600 s MILP | task20 |
