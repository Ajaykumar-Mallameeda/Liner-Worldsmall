# Phase 1 — paired baseline (frozen accepted configuration)

**Tree:** `snap_C0_base` (manifest `34a8d390…f24c` = accepted Tasks 19–21 tree) · **Harness:** the Tasks 19–21 controlled global-stage harness, verbatim
(`evidence/tools/global_stage_experiment.py`, strategy `prod`) · **Solver:** CBC 2.10.3, 120 s, single thread · **Seeds:** generator seeds 0–9
(the historical seeds) · **Execution:** 2 concurrent processes, `PYTHONHASHSEED=0`, no `LINER_*` variable set
(`evidence/runs/P1_base.driver.txt`, 17:16 – 17:26) · **Production source:** untouched during this run.
Raw outputs: `evidence/outputs/P1_base_seed{0..9}.json`; table: `evidence/comparisons/P1_base_vs_M7.md` / `.csv`.

## 1. Per-seed result

| seed | solver status | profit M/wk | margin % | coverage % | served TEU | services | vessels | load factor | LP bound M | gap to bound % | solver s | ledger | violations | reconciled | re-routing gain M | historical `D` profit M (M7) | Δ vs history M |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|
| 0 | feasible | 13.45 | 17.4 | 25.2 | 69,602 | 26 | 129 | 0.647 | 41.3 | 67.4 | 120 | verified | 0 | yes | 2.56 | 13.20 | +0.25 |
| 1 | feasible | 11.44 | 17.0 | 21.4 | 59,284 | 20 | 116 | 0.639 | 41.9 | 72.7 | 119 | verified | 0 | yes | 1.71 | 11.57 | −0.13 |
| 2 | feasible | 12.10 | 17.0 | 22.8 | 62,960 | 21 | 112 | 0.601 | 41.4 | 70.8 | 120 | verified | 0 | yes | 1.46 | 12.10 | 0.00 |
| 3 | feasible | 11.24 | 12.5 | 27.7 | 76,702 | 33 | 168 | 0.605 | 39.5 | 71.5 | 120 | verified | 0 | yes | 3.51 | 9.37 | +1.87 |
| 4 | feasible | 11.68 | 15.5 | 23.9 | 65,998 | 28 | 143 | 0.679 | 41.9 | 72.1 | 120 | verified | 0 | yes | 2.94 | 10.57 | +1.11 |
| 5 | feasible | 11.33 | 14.5 | 23.7 | 65,608 | 24 | 145 | 0.651 | 41.3 | 72.5 | 120 | verified | 0 | yes | 1.81 | 11.33 | 0.00 |
| 6 | feasible | 10.58 | 11.8 | 28.4 | 78,614 | 32 | 173 | 0.609 | 41.6 | 74.6 | 120 | verified | 0 | yes | 6.10 | 10.58 | 0.00 |
| 7 | feasible | 13.70 | 14.8 | 28.6 | 78,984 | 28 | 167 | 0.654 | 40.5 | 66.1 | 120 | verified | 0 | yes | 4.25 | 13.70 | 0.00 |
| 8 | feasible | 11.19 | 12.2 | 29.3 | 80,946 | 31 | 167 | 0.620 | 40.4 | 72.3 | 120 | verified | 0 | yes | 5.52 | 11.19 | 0.00 |
| 9 | feasible | 12.05 | 16.1 | 24.3 | 67,220 | 29 | 141 | 0.702 | 40.3 | 70.1 | 120 | verified | 0 | yes | 2.36 | 11.58 | +0.47 |

| aggregate (n = 10) | this run | historical `D` (M7) |
|---|---:|---:|
| profit M/wk — mean (sd) | **11.88 (0.95)** | 11.52 (1.20) |
| profit — median / min / max | 11.56 / 10.58 / 13.70 | 11.45 / 9.37 / 13.70 |
| coverage % — mean (sd) | 25.5 (2.6) | 25.3 (2.7) |
| served TEU — mean | 70,592 | 69,879 |
| services / vessels — mean | 27.2 / 146.1 | 27.8 / 147.6 |
| margin % — mean | 14.9 | 14.4 |
| load factor — mean | 0.641 | 0.632 |
| statuses | 10 × `feasible` (time-limited incumbents; none `optimal`) | 10 × `feasible` |
| negative-profit plans | 0 | 0 |

## 2. Quality / feasibility gates (all 10 seeds)

* **Independent ledger:** valid in 10/10, **0 violations of any type** (fleet, class, capacity, flow, frequency, transit, transfer, continuity); MILP objective = ledger profit to < 1e-6 relative (reconciled 10/10); regional partition `verified` in 10/10.
* **Repair:** profit-floor repair never triggered (no plan below 0).
* **Transit:** 0 transit-limit violations; maximum per-strategy p90 transit 39 – 46 d (multi-hop); minimum slack to the limit 0.0006 – 0.07 d (flows are allowed to ride exactly at their limit; this is the existing rule).
* **Cargo structure (means):** direct 52,370 TEU, feeder 13,468, hub-and-spoke 3,088, two-transfer 1,666 TEU.
* **Unserved demand (production labels, mean % of total demand):** not-economic-to-open 52.3, fleet-inventory-exhausted 12.6 (0.0 – 24.7 across seeds), capacity-exhausted 3.4, limit below sailing time 3.4, no time-feasible service 2.5. These labels are properties of the incumbent (see the bottleneck report in `reports/expansion_2026_10_12/`).
* **Solver:** LP bound 39.5 – 41.9 M against incumbents of 10.6 – 13.7 M: the relaxation is not informative (gap 66 – 75 %).

## 3. Paired comparison with the historical reference and observed non-determinism

* Same seeds, same code, same inputs, same solver settings. **5 of 10 seeds reproduce the recorded profit to the dollar** (2, 5, 6, 7, 8); the other five differ: +0.25, −0.13, +1.87, +1.11, +0.47 M. Their pool hashes, model sizes, dual bounds and path-set hashes before the solve are identical, so the differences are the **time-limited CBC incumbent** (wall-clock dependent), not the model.
* Paired difference this run − historical: mean **+0.36 M** (4 seeds higher, 1 lower by 0.13 M, 5 identical); coverage +0.26 pp. The accepted baseline is therefore reproduced in distribution (and exactly on half the seeds); no discrepancy needs to be explained away.
* Earlier in the audit the *same* seed-0 model produced 3.35 M (heavy machine load), 13.20 M (2 jobs) and 13.45 M (1 job): the timing sensitivity of CBC at 120 s is real and sets the noise floor of every paired comparison below (roughly ±1 M per seed, rarely −6 … −10 M under heavy load). All later comparisons run both arms **concurrently** so that they see the same load.

## 4. Baseline acceptance

All ten final plans are ledger-verified, physically feasible and have positive profit; the baseline is accepted as the frozen comparator. The earlier acceptance report's headline (9.18 → 11.52 M, +2.34 M) concerned the rollback-vs-default comparison; the default arm is what is reproduced here.
