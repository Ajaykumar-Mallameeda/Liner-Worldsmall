# Task 20 — bounded multi-hop routing and cost-aware path selection

**Date:** 2026-10-11/12 · WorldSmall only · every number is read from `evidence/outputs/*.json`
(controlled, one global stage per seed, regional hints absent, same pool and budget per seed) or from
`evidence/runs/*.pipeline_output.json` (end to end). Batch tables: `evidence/comparisons/M*_*.md`; all rows:
`results_matrix.md`. Production solver (CBC, 120 s) unless stated; HiGHS rows are the opt-in, experimental backend.

## 1. Verdict

| Question | Answer |
|---|---|
| Was a two-transfer journey supported? | **No** (one transfer: `paths.py`, `ledger.py`, test recomputation, `max_transfers_per_od = 1`). Implemented with the hard bound 2 and verified end to end (§2) |
| Does it extend coverage? | **No on WorldSmall.** It rescues **0 of the 90** ODs without a path (8.05 % of demand): their limit is below the sailing time (a second transfer only adds 5.5 days). Its measured value is routing cargo over *operated* capacity: 1.5 – 2.4 % of served TEU, +0.06 … +0.6 M USD/week |
| Does cost-aware path selection beat the ten fastest paths? | **No, under the production solver.** Cost-aware: −6.5 M/wk (1/5 seeds better; one incumbent below zero); hybrid (7 fastest + 3 cheapest): −3.0 M, or +0.3 M with sd 3.6 once the cargo is re-routed; adaptive per-OD budget: coverage +3 … +8 pp but profit −1.9 … −7.4 M under CBC (hold-out and 10 seeds) and −1.45 M (0/5) under HiGHS. **Not adopted** (opt-in switches) |
| What *did* the path cap cost, and what recovers it? | With the network held fixed, re-routing cargo over **all** valid paths through the operated services is worth **+1.4 … +2.3 M/wk** on the recorded B0 plans, in a 1.5 s LP. Implemented as `flow_reopt.py` (**default ON**): paired CBC 120 s, 10 seeds: **+3.10 M/wk (10/10 seeds)**, coverage +1.5 pp, load factor 0.59 → 0.67 |
| Profit-floor repair (`repair_profit_floor`, default ON) | Acts only when the plan's profit is below the approved floor of 0 and never touches a plan at or above it. Evidence: unit tests (`TestProfitFloorRepair`), the offline drop-one analysis of the recorded poor incumbents (one switch-off worth +2.0 … +6.2 M each), and the in-pipeline triggers of the degraded-machine batch M6 (−1.3 / −1.1 / −0.35 / −4.5 M → +3.5 / +3.4 / +2.4 / +0.5 M, coverage −1 pp; **not** used as a performance claim, see §7). Clean-batch triggers: `results_matrix.md` (M7) |

## 2. Multi-hop feasibility (what is enforced, where, and how it is checked)

| Rule | Enforced in | Checked independently |
|---|---|---|
| ≤ 2 transfers, never longer (`PathConfig` refuses 3; unrestricted length is not configurable) | `paths.py` (`HARD_MAX_TRANSFERS`), `ledger.py` (`max_transfers`) | orchestrator §N.9: every flow has ≤ `max_transfers + 1` segments; recomputation raises outside [0, 2] |
| Connected origin → hub 1 → hub 2 → destination; no repeated port, no service ridden twice | `_two_transfer_paths`, ledger (`invalid_transfer`, `invalid_path`) | `_recompute_network` (shares no `src` code) |
| End-to-end transit limit = rides + intermediate port stays + one dwell (48 h + 3.5 d) **per transfer**; an OD without a limit is unconstrained | built into the path, never selected-then-checked; ledger `transit_time_exceeded` | recomputed per flow; 0 violations in every recorded run |
| Capacity on every leg, vessel inventory, demand once | MILP / LP unchanged; ledger | recomputed leg loads; strategy report per service |
| Per-TEU charges: handling + port call at origin and destination, transshipment + 2 × port call **at every hub** | `paths.py`, `ledger.py`, `reconcile.py` (regional partition sums both hubs) | `tests/test_multi_hop_paths.py::TestLedger`, `::TestGlobalStage` (partition of a 2-transfer plan equals the ledger), orchestrator §N.2 |
| Enumeration bounded: only ODs with fewer than `multi_hop_min_alternatives` (1) direct / one-transfer paths; the 4 fastest first / last legs per hub; at most 24 cheapest journeys per OD; time-pruned | `paths.py` | build time 0.2 s per global stage (all ODs: 11 s, not default) |

## 3. Path selection benchmark (CBC 120 s, paired seeds; profit = independent ledger, M USD/week)

| configuration | seeds | mean (sd) | Δ vs same-batch B0 | seeds better | coverage % | model vars | batch |
|---|---:|---:|---:|---:|---:|---:|---|
| **B0** frozen: 10 fastest | 0–4 | 9.62 (1.01) | — | — | 19.9 | 6,988 | M3 |
| cost-aware (`C`) | 0–4 | 3.17 (5.55) | −6.46 | 1/5 | 22.1 | 7,426 | M1 |
| cost-aware + adaptive budget (`CA`) | 0–1 (stopped) | −3.05 (4.18) | −13.81 | 0/2 | 26.7 | 7,874 | M1 |
| adaptive budget, fastest ranking (`FA`) | 0–4 | 7.69 (2.59) | −1.94 | 1/5 | 26.7 | 7,218 | M1b |
| hybrid 7 fastest + 3 cheapest (`H3`) | 0–4 | 6.61 (4.31) | −3.01 | 1/5 | 21.4 | 7,454 | M1b |
| + flow re-optimisation: B0 + re-routing (`R`) | 0–4 | 11.29 (0.85) | +1.67 | 5/5 | 20.8 | 6,988 | M3 |
| `R` + adaptive budget (`RFA`) | 0–4 | 10.53 (2.34) | +0.91 | 2/5 | 28.3 | 7,218 | M3 |
| `R` + hybrid (`RH3`) | 0–4 | 9.90 (3.60) | +0.28 | 3/5 | 22.9 | 7,454 | M3 |
| `R` + multi-hop for all ODs (`RMH`) | 0–4 | 11.57 (0.76) | +1.95 | 5/5 | 22.0 | 7,022 | M3 |
| hold-out: B0 | 5–9 | 5.53 (5.85) | — | — | 23.4 | 7,018 | M4 |
| hold-out: `R` | 5–9 | 10.63 (1.46) | +5.10 | 5/5 | 23.7 | 7,018 | M4 |
| hold-out: `RFA` | 5–9 | 2.74 (7.01) | −2.79 | 3/5 | 26.5 | 7,294 | M4 |
| **B0, ten seeds** | 0–9 | 8.01 (4.62) | — | — | 21.1 | 7,003 | M5 |
| **F1 = re-routing + ≤ 2 transfers where needed** | 0–9 | **11.11 (1.37)** | **+3.10** | **10/10** | 22.6 | 7,003 | M5 |
| F2 = F1 + multi-hop enumerated for every OD | 0–9 | 11.49 (1.30) | +3.48 (+0.38 vs F1, 6/10) | 10/10 | 23.8 | 7,041 | M5 |
| F1 + adaptive budget (`F1A`) | 0–9 | 0.61 (8.21) | −7.39 | 4/10 | 26.7 | 7,256 | M5 |

HiGHS 300 s (opt-in; ctl3 tree; seeds 0–4, batch M2): B0 10.89 (1.52) · `R` 13.29 (**+2.41, 5/5**) · `RFA` 9.44 (−1.45, 0/5)
· `RTF` 12.77 (+1.89, 5/5; Task 21). The same ordering as CBC: re-routing helps, the adaptive budget does not.

Why cost-aware ranking loses under CBC (diagnosis, not a proof): the path rank that follows the cost of capacity is
also what the LP relaxation prefers, so the relaxation spreads cargo over many fractionally operated services; the
production solve restricts the integer problem to that support, and CBC's 120 s incumbent on it is far poorer
(restricted problems of 262 – 300 services in every variant; the incumbents differ, not the problem size). The
integer plan found on the *fastest*-ranked set happens to be easier. Larger path sets were measured in Tasks 14–16
(cap 30, HiGHS 600 s: 5.29 vs 9.33 M, historical, different conditions) and **not repeated** here.

## 4. Flow re-optimisation (the adopted change)

* **What it is.** After the MILP, every frequency and vessel count is fixed (so every fixed cost is unchanged) and the
  cargo is re-routed by a pure LP over **all** valid, time-feasible paths of the operated services (`src/network/flow_reopt.py`,
  PuLP/CBC): maximise Σ (revenue − per-TEU charges) q subject to demand ≤ weekly TEU per OD, leg capacity per leg of every
  service, and **served TEU ≥ the incumbent's served TEU** (and any coverage floor). The incumbent is feasible in it, so
  profit and coverage can only rise; the ledger recomputes the result independently.
* **Measured mechanism.** Fixed-network LP on the recorded B0 plans (`fixed_network_flow_lp.py`): +1,403,763 /
  +1,459,182 / +2,288,784 USD/week on seeds 0 – 2 (13 – 27 %), 1.4 s; in the pipeline the same seeds gave exactly
  12.31 / 12.08 / 10.72 M (offline LP = in-pipeline result, to the dollar). With two-transfer paths in the LP the gain
  is +35 – 50 k larger and 48 – 588 TEU/week ride two-transfer journeys.
* **Honesty of the status.** A plan it improves is reported `feasible` even if the MILP over the capped paths had
  closed (`optimal`): the plan now uses paths outside the solved model. `network_ledger.optimality.flow_reoptimisation`
  records the gain, paths added and served TEU before / after; `bound_applies_to` says the dual bound belongs to the
  capped model. Orchestrator §N.10 asserts both.
* **What it does not fix.** It cannot create capacity: unserved demand is ≈ 59 % "not economic to open a service at the
  incumbent", 7 % fleet inventory of a class exhausted, 3 % leg capacity exhausted (`strategy_tables_M5.md`).
* **Negative control of the no-regression constraint.** Without it the same LP (tree ctl3) was worth +1.05 M more on
  seed 2 by dropping 1.7 pp of coverage — cargo that loses money per TEU on a CBC incumbent. The constrained form was
  kept so that no "improvement" is bought with coverage.

## 5. Model size and time

Mean per global stage (CBC batches M3 / M5): valid paths 51 – 53 k; kept 12.3 k (B0 12,262; F1 12,262; F2 12,358; ROP
12,542); model 7.0 k variables / 2.9 k constraints; path build 1.1 s (B0), 1.3 s (F1), 12.6 s (F2, multi-hop for all
ODs); flow re-optimisation LP 1.2 – 1.6 s; solver runtime unchanged (119 – 120 s). Table: `evidence/comparisons/path_model_by_variant.md`.

## 6. Quality of the routed cargo (strategy report, means of 10 seeds, `strategy_tables_M5.md`)

| | B0 | F1 (re-routing + ≤ 2 transfers) |
|---|---:|---:|
| direct / feeder / hub-and-spoke / multi-hop share of served TEU | 84.1 / 12.8 / 3.2 / 0.0 % | 78.9 / 15.8 / 3.7 / **1.5 %** |
| network load factor (nm-weighted) | 0.592 (0.626) | **0.667 (0.686)** |
| legs ≥ 95 % full | 22.0 of 72 | 27.7 of 72 |
| idle capacity cost (of service cost) | 19.4 of 47.9 M/wk | 16.6 of 47.8 M/wk |
| transit-limit violations | 0 | 0 (min slack 0.1 d; multi-hop mean transit 37.5 d) |
| ledger violations / reconciled | 0 / 10 of 10 | 0 / 10 of 10 |

## 7. Limits

* Controlled runs bypass the regional GA / MILP hints; the end-to-end gate runs are in `acceptance_report.md`.
* CBC at 120 s is CPU-load sensitive: batches were compared only within a batch; one batch (M6) ran under a degraded
  machine state (18 of 40 runs `not_solved`) and is **not used** for any claim; B0 seed 8 differs between two
  batches (5.05 vs 9.40 M) for the same reason (documented in `results_matrix.md`).
* Ten seeds of one generator; the paired difference of F1 vs B0 is large against its spread (+3.10 M, paired sd 3.8, smallest single-seed gain +1.32 M, t ≈ 2.6),
  that of F2 vs F1 (+0.38 M, paired sd 1.1, 6/10, t ≈ 1.1) is **inconclusive**.
