# Issue 3 - solver quality (2026-10-13)  -  gate: PASS for evidence and hardening; promotion NOT performed (needs owner approval)

Base commit `66f3191` (+ the hardening below, which was applied only after all measurement batches finished; the guard run in
`guard_check/` confirms it does not alter outcomes where a plan exists). CBC single thread, 120 s, identical data hashes (Issue 0/2),
`PYTHONHASHSEED=0`, `LINER_SEED` unset; arms of a seed run concurrently. Flags always tested alone first.

## Experiments (per-seed tables: `../issue2_corrected_baseline/per_seed_issue2.csv`, `per_seed_dev_repl.csv`, `per_seed_holdout.csv`)
| batch | seeds | arms | what it shows |
|---|---|---|---|
| I2 (Issue 2) | 0-9 dev | base, ls, vub, e | first look |
| I3 hold-out | 10-19 | base, ls, vub, lsvub | **hold-out**, flags alone and combined |
| I3d replicate | 0-9 | base, vub, lsvub | replicate of the dev seeds, combined arm |

Paired differences in profit (M USD/week; every difference is inside one concurrent batch):
| batch | pair | mean | min .. max | seeds higher |
|---|---|---:|---|---|
| I2 dev | **ls - base** | +10.93 | +2.79 .. +27.63 | 9/9 solved (seed 8 `not_solved`) |
| I3 hold-out | **ls - base** | +3.99 | -29.78 .. +20.87 | 7/9 (seed 10 `invalid_plan`, seed 16 `not_solved`) |
| I2 dev | **vub - base** | +10.34 | +0.83 .. +34.13 | 10/10 |
| I3d dev repl | **vub - base** | +7.31 | +0.83 .. +20.61 | 10/10 |
| I3 hold-out | **vub - base** | +8.23 | -0.40 .. +25.10 | 9/10 |
| I3d dev repl | lsvub - base | +9.78 | +0.79 .. +22.11 | 10/10 |
| I3 hold-out | lsvub - base | +11.29 | +1.11 .. +26.23 | 10/10 |
| I3d dev repl | lsvub - vub | +2.47 | -0.04 .. +5.41 | 9/10 |
| I3 hold-out | lsvub - vub | +3.06 | -0.40 .. +4.74 | 9/10 |

Other means (hold-out, base / vub / lsvub): coverage 30.6 / 31.9 / 34.1 %; margin 28.4 / 35.5 / 35.8 %; leg load factor 0.55 / 0.60 / 0.60;
cost per served TEU 806 / 733 / 735 USD; gap to the model bound 65 / 3.7 / -4.5 % (negative: the final plan exceeds the capped-model bound,
see Issue 2 finding 2); stage 121 / 123 / 114 s. Transit violations 0 in every solved plan; ledger violations 0 in every solved plan.

## Findings
1. **`LINER_MILP_VUB` alone**: valid inequality, 30/30 plans solved and ledger-valid, 29/30 seeds higher than the same-batch default,
   +7.3 .. +10.3 M (dev), +8.2 M (hold-out); 0 not_solved. Bound gap collapses from ~65 % to ~1-4 %.
2. **`LINER_LOCAL_SEARCH` alone is not safe under the corrected units**: it takes 15 s from the MILP budget; with the weak default
   relaxation CBC then ended without an incumbent in 2/20 plans and, in one case (hold-out seed 10), returned all-zero values with solver
   status "Optimal" that the independent ledger rejected (`invalid_plan`, 1,748 x `demand_not_conserved`). Not accepted on its own.
3. **VUB + LS combined**: 20/20 solved, valid, higher than the default on 20/20 seeds and higher than VUB alone on 18/20
   (+2.5 / +3.1 M) with a shorter stage. The combination removes the fragility because the strengthened model finds incumbents early.
4. **The default itself is unstable**: replicating the Issue-2 default on the same seeds changed 3 of 10 plans (seed 6: 4.7 -> 34.1 M;
   seed 5: 26.0 -> 32.6 M; seed 7: 30.5 -> 32.0 M); the other 7 were bit-identical. CBC's wall-clock incumbent, not the model, drives the spread.

## Hardening implemented (correctness, not a default change)
`src/network/network_milp.py::solve_network`: a CBC result with `sol_status == NoSolutionFound`, or whose values do not conserve demand
(`sum q + u != demand`, tolerance 1e-6 rel + 1e-3), is reported `not_solved` (never an empty "feasible" plan).
`tests/test_milp_no_incumbent.py` (3 tests; written with a monkeypatched empty CBC result). Related suites (MILP, VUB, backend, local search,
trim, network economics): 86 passed. `guard_check/`: 6 re-runs, all solved and valid, no outcome that previously existed was changed.

## Decision
* **No production default was changed.** Owner rule in force: "all production-default promotions require explicit owner approval".
* **Recommended for owner approval (profile "S3")**: `LINER_MILP_VUB=1` + `LINER_LOCAL_SEARCH=1` together (never LS alone).
  Evidence: 20/20 seeds higher, 0 violations, 20/20 solved, mean +9.8 (dev) / +11.3 (hold-out) M over the unchanged default.
  Rollback: unset both variables (no file change). Fall-back if the owner wants the smaller step: `LINER_MILP_VUB=1` alone.
* Later issues evaluate their own changes against both the unchanged default and the S3 profile where relevant.

## Rollback of the code change
`git revert` of this issue's commit (guard + test file only).
