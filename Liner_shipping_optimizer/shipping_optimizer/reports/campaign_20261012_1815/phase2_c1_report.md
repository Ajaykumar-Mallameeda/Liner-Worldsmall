# Phase 2 — C1: valid-inequality strengthening of the network MILP (`LINER_MILP_VUB`)

**Status: ACCEPT FOR OWNER APPROVAL** (production default stays OFF until the owner decides).
Tree: `snap_T1_flags` (accepted tree + four default-off flags; manifest `555970f3…b7de3`; patch `patches/phase2_T1_flags.patch`, sha256 `1047222a…ac0b2`).
Solver/budget unchanged: CBC 2.10.3, single thread, `GLOBAL_STAGE_TIME_LIMIT_SEC` = 120.

## 1. The change

`src/network/network_milp.py` — for every path `p` of an OD `d` and every service `s` the path rides, one row

    q[d,p]  <=  weekly_teu[d] * f[s]                (`vub_<od>_<path>_<service>`)

added to the LP relaxation (bound + LP-guided restriction) and to the integer problem. Applied only to free-frequency solves
(`fixed_frequencies is None`); with imposed frequencies it is redundant and skipped (reported in `NetworkSolution.formulation`
and in `network_ledger.optimality.formulation`). Default OFF; `LINER_MILP_VUB=1` enables; any other value raises `ValueError`.
No other file's behaviour changes with the flag off (verified: the flag-off arm on the modified tree reproduces the frozen tree).

### Validity (why no legitimate integer solution is excluded)
Variables: `f_s` ∈ Z≥0 weekly departures; `q_{d,p}` ≥ 0 TEU/week of OD `d` on path `p`; the model has `Σ_p q_{d,p} + u_d = weekly_teu_d`
(`u_d` ≥ 0) and, for every leg of every service, `Σ_{p∋(s,leg)} q_{d,p} ≤ cap_s · f_s`.

1. If `f_s ≥ 1` (integer): `q_{d,p} ≤ Σ_p' q_{d,p'} ≤ weekly_teu_d ≤ weekly_teu_d · f_s`.
2. If `f_s = 0`: the leg-capacity row of any leg of `s` gives `q_{d,p} ≤ cap_s · 0 = 0 = weekly_teu_d · f_s`.
3. Hence every point that satisfies the original constraints with integer `f` satisfies the new row; nothing is removed from the
   integer-feasible set, the objective and the accounting are untouched (the row has no cost coefficient and no new variable).
4. A path with several services (a transfer) contributes one row per service; a service appearing twice on a path is counted once
   (`set(path.services)`), because capacity is consumed per leg, not per visit.
5. Fractional LP points `0 < f_s < 1` are exactly what the rows remove: they let a service run at a fraction of one weekly
   sailing. `f_s` may be fractional only in the relaxation, never in an accepted plan.

### Tests (`tests/test_milp_vub.py`, 17 tests, all pass; plus 177 existing network / ledger / reconcile / screening tests unchanged)
* parsing, default-off, skip with imposed frequencies, one row per service of every path, row coefficients;
* **unrestricted integer optimum identical with and without the rows** on three instances (heavy demand, light demand, transfer path);
* **point-by-point equivalence**: every integer frequency vector `f ∈ {0,1,2}^services` is fixed in both models and the optimum
  (or the infeasibility) is compared — equal at every checked point (`heavy`, `transfer`);
* LP bound never weaker, strictly stronger when demand ≪ capacity; the bound stays ≥ the integer plan it produces;
* plans built with the flag pass the independent ledger and reconcile to the MILP objective.

| unit instance | LP bound, baseline | LP bound, VUB | integer optimum (both) | rows baseline → VUB |
|---|---:|---:|---:|---:|
| heavy (demand ≥ capacity) | 4,825,926.7 | 4,825,926.7 | 4,299,066.7 / 4,299,066.7 | 14 → 26 |
| light (demand ≪ capacity) | 336,249.3 | **201,866.7** | 76,066.7 / 76,066.7 | 15 → 34 |
| transfer path | 919,061.1 | 919,061.1 | 742,066.7 / 742,066.7 | 13 → 28 |

## 2. Paired experiment — 10 seeds, CBC 120 s, both arms run concurrently (equal machine load)

`run_pairs.sh`, 17:28 – 17:50; harness = the Tasks 19–21 controlled global-stage harness; same pool, path set and cost model per seed.
Raw: `evidence/outputs/P2_{base,c1}_seed*.json`; table `evidence/comparisons/P2_base_vs_c1.md`.

| seed | baseline profit M | C1 profit M | Δ M | Δ coverage pp | Δ served TEU | Δ services | Δ vessels | C1 LP bound M | C1 gap % |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 13.20 | 13.46 | +0.27 | −2.4 | −6,634 | −6 | −14 | 16.3 | 17.5 |
| 1 | 11.57 | 15.50 | **+3.93** | +3.7 | +10,362 | 0 | +8 | 16.6 | 6.5 |
| 2 | 12.10 | 12.63 | +0.53 | −1.0 | −2,874 | +1 | +9 | 16.7 | 24.5 |
| 3 | 9.37 | 12.40 | +3.03 | +2.6 | +7,093 | +1 | +17 | 15.9 | 22.1 |
| 4 | 11.68 | 12.62 | +0.94 | +1.7 | +4,600 | −2 | 0 | 15.9 | 20.6 |
| 5 | 11.33 | 13.56 | +2.22 | +0.9 | +2,428 | +7 | +2 | 16.4 | 17.2 |
| 6 | 10.58 | 14.33 | +3.74 | −3.8 | −10,429 | −7 | −24 | 16.0 | 10.3 |
| 7 | 13.70 | 13.33 | **−0.37** | −2.4 | −6,724 | 0 | −11 | 15.9 | 16.4 |
| 8 | 11.19 | 14.37 | +3.18 | −2.8 | −7,618 | −5 | −18 | 17.2 | 16.6 |
| 9 | 11.58 | 12.62 | +1.05 | −2.4 | −6,610 | −4 | −29 | 15.6 | 18.8 |

| metric (n = 10) | baseline (concurrent arm) | C1 | paired Δ |
|---|---:|---:|---:|
| weekly profit M — mean (sd) | 11.63 (1.16) | **13.48 (0.95)** | **+1.85** (sd 1.48, se 0.49, t = 3.76) |
| profit — min / median / max | 9.37 / 11.58 / 13.70 | 12.40 / 13.40 / 15.50 | min −0.37, median +1.63, max +3.93 |
| seeds with higher profit | | | **9 / 10** (1 lower: seed 7, −0.37 M) |
| margin % mean | 14.5 | 17.2 | +2.7 pp |
| coverage % mean (sd) | 25.5 (2.5) | 24.9 (1.5) | **−0.59 pp** (improved 4/10, regressed 6/10; range −3.8 … +3.7) |
| served TEU mean | 70,398 | 68,757 | −1,641 |
| services / vessels (mean) | 27.9 / 148.6 | 26.4 / 142.6 | −1.5 / −6.0 |
| load factor mean | 0.635 | 0.675 | +0.040 |
| LP bound M, mean | 41.0 | 16.2 | −24.8 |
| gap to the bound %, mean | 71.6 | 17.0 | −54.6 |
| restricted integer problem: services / variables (mean) | 288 / 7,053 | 116 / 3,492 | |
| ledger valid / violations / reconciled | 10/10, 0, 10/10 | 10/10, 0, 10/10 | |
| negative-profit plans | 0 | 0 | |
| solver runtime s (mean) | 119.9 | 121.1 | +1.2 (LP phase of the larger relaxation) |

Against the stand-alone Phase 1 baseline (the first replicate; `P1_base`) the result is the same: Δ +1.61 M, 9/10 seeds higher,
t = 3.19, coverage −0.66 pp. The two baseline replicates differ from each other on 4 of 10 seeds (−0.25, +0.13, −1.87, −0.47 M):
that is the CBC timing noise the paired design is meant to absorb. Replicates under the same load pattern agree: the Phase 3 C1 arm
(`P3_c1`, 4 concurrent processes) equals this C1 arm on 9/10 seeds to the dollar, and its baseline arm equals this baseline on 9/10.

**What changed in the plans** — cargo structure: direct share 74.5 % → 74.4 % of served TEU (unchanged), two-transfer cargo 1,641 → 1,350 TEU (mean);
vessel mix: Panamax_1200 44.1 → 45.6, Panamax_2400 38.2 → 33.0, Post_panamax 33.0 → 27.0, Feeder_800 24.7 → 28.3 (the class
that is the binding inventory). Production unserved-demand labels (means): fleet-inventory-exhausted 14.3 → 20.4 %,
not-economic-to-open 50.5 → 44.9 %: with a better incumbent the same residual label moves towards the *physical* constraint.

**Quality gates (C1, all 10 seeds):** 0 transit-limit violations, maximum per-strategy p90 transit 39.5 – 46.2 d (baseline 39.3 – 46.4),
minimum slack to the limit 0.001 – 0.074 d (baseline 0.001 – 0.070); transfers ≤ 2; no flow on an inactive service; regional
partition verified 10/10; profit-floor repair never triggered.

## 3. End to end — `tests/test_orchestrator.py`, three runs per arm, concurrent, isolated snapshot copies

| run | assertions | status | selected iteration | profit M/wk | margin % | coverage % | services / vessels | MILP status | bound M | ledger |
|---|---|---|---:|---:|---:|---:|---|---|---:|---|
| base run1 | 362/362 | complete | 0 | 14.11 | 15.8 | 28.3 | 31 / 163 | feasible | 40.0 | verified, 0 violations |
| base run2 | 362/362 | complete | 1 | 12.31 | 16.3 | 24.0 | 27 / 136 | feasible | 42.3 | verified, 0 |
| base run3 | 362/362 | complete | 0 | 13.91 | 17.3 | 24.9 | 29 / 139 | feasible | 41.3 | verified, 0 |
| **C1 run1** | 362/362 | complete | 1 | **14.39** | 16.2 | 28.1 | 28 / 161 | feasible | 16.8 | verified, 0 |
| **C1 run2** | 362/362 | complete | 1 | **14.71** | 16.7 | 27.8 | 28 / 160 | feasible | 17.0 | verified, 0 |
| **C1 run3** | 362/362 | complete | 2 | **14.43** | 16.0 | 29.0 | 31 / 163 | feasible | 16.0 | verified, 0 |

Mean (n = 3): baseline 13.44 M / 25.7 % → C1 14.51 M / 28.3 % (+1.07 M, +2.6 pp). Profit spread 12.3 – 14.1 vs 14.4 – 14.7.
Each run is the profit-weighted best of three iterations; n = 3 is too small for a rate. The orchestrator wall time of the C1
block (≈ 500 s vs 380 s) comes from the **regional stage** (20 – 58 s vs 3 s per region), which does not use the changed
solve (imposed frequencies ⇒ rows skipped); all providers answered HTTP 429 in both blocks, so the difference is the
LLM client's back-off timing, not C1. Global stage: 120.8 – 123.4 s in both (C1 +1 s).

## 4. Gates

| Gate | Result |
|---|---|
| A economic correctness | PASS — ledger = MILP objective (< 1e-6 rel.) in 10/10 + 3/3 runs; no input substituted |
| B profit | PASS — mean +1.85 M, 9/10 seeds higher, min −0.37 M, no negative plan |
| C coverage | **Not claimed.** Controlled batch: −0.59 pp mean (6/10 seeds lower, per-seed above); end to end +2.6 pp (n = 3) |
| D physical feasibility | PASS — 0 violations of every class |
| E quality | PASS — transit mean/p90/slack in the baseline's range |
| F tests | PASS — 17 new + 177 existing focused tests; 3 × 362/362; whole suite: see `test_failure_remediation_report.md` |
| G repeatability | PASS on the stated rule (≥ 8/10 positive, mean > 0); seed 7 regressed |

## 5. Known limitations and risks
* The strengthened LP is larger (22 k rows in the relaxation on the seed-0 pool) and its phase takes ≈ 1 s more; with much larger
  pools the LP phase's 48 s cap (`min(60, 0.4 · budget)`) could be reached and the code would fall back to the unrestricted
  integer solve (an existing path, reported as `lp_guided = False`). Phase 4 watches `solver_runtime` and `restricted_to`.
* The time-limited incumbent is still not proven: gap to the (capped-model) bound 6.5 – 24.5 %.
* A baseline replicate and C1 differ in coverage in either direction; the claim is a profit one.
* A row-order effect exists (an in-process probe that appended the rows last produced 15.0 M on seed 0 against 13.46 M here with
  the rows before the vessel / fleet rows): CBC's time-limited search is order-sensitive; the production ordering is the one measured here.

## 6. Rollback
Unset `LINER_MILP_VUB` (default). File rollback: `patches/phase2_T1_flags.patch` reverse-applied, or restore `src/network/network_milp.py`
from `D:\liner_scratch\snap_C0_base`. No data, ledger or accounting code is touched.
