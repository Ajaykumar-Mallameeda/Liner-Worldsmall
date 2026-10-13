# Task 21 — route-level operators, elitism and candidate diversity

**Date:** 2026-10-12 · WorldSmall only · numbers from `evidence/outputs/*.json`; paired seeds, CBC 120 s unless stated.

## 1. Verdict

| Item | Result |
|---|---|
| Audit: where were useful alternatives lost? | (a) **A class defect, not a lack of operators**: 43 ODs (4.67 % of demand, seed 0) had only a 14-knot Feeder_800 two-port candidate that cannot meet their transit limit while Panamax / Post / Super classes can; the Task 10 screen keeps the "legacy" class when no class is profitable stand-alone, even when it carries nothing. (b) 41 ODs (3.4 %) are below the sailing time at the fastest class: not servable by any pool. (c) The regional GA only switches candidates on and off — there was no route-level operator and nothing remembered a rotation across iterations |
| Time-feasible class correction (`LINER_CLASS_TIME_FEASIBLE`, **default ON**) | Pool size unchanged (1,166 unique candidates, class replaced in place); demand without any path 8.05 % → 5.90 % (seed 0), 5.60 % (seed 1). Paired, 10 seeds, same code otherwise (`F1T` vs `F1`): profit **+0.03 M** (4/10 seeds), coverage **+2.86 pp** (9/10), served TEU +7.9 k (+12.7 %), vessels 131 → 147; HiGHS 300 s (5 seeds, vs re-routing alone): −0.52 M, +0.7 pp |
| Route-level operators (`LINER_ROUTE_OPERATORS=n`, opt-in) | 90 variants per seed generated, deterministic, canonical economics, every variant feasible; **no measurable gain**: 11.21 M (sd 0.41) vs 11.29 M (sd 0.85) for the same pools without them (5 seeds, −0.08 M); 2 of 21 operated services came from operators (seed 0). Not adopted |
| Elitism across iterations (`LINER_ELITISM=1`, opt-in) | Later iterations improve (iteration 1: +2.2 M mean, 4/5 seeds; iteration 2: +0.3 M) but the **best of three** moves only **+0.14 M** (3/5 seeds); with operators +0.23 M (3/5). Inconclusive; not adopted |
| Candidate-pool growth policy | bounded and counted: operators ≤ n per regional problem, exempt from the regional cap only for the `elite` / `route_operator` sections; defaults add **0** candidates |

## 2. Pipeline counts (seed 0, production defaults; `pool.generator` of the controlled outputs)

| stage | Asia | Europe | Americas | total |
|---|---:|---:|---:|---:|
| generated (sections A–F, before screening / filter) | 626 | 494 | 571 | 1,691 |
| retained by the economic regional filter (cap 508 / 405 / 499 for non-loops, loops exempt) | 563 | 441 | 547 | 1,551 |
| unique after cyclic de-duplication across regions (= modelled, 0 rejected) | | | | **1,166** |
| operated by the global solution (B0 / re-routing + time-feasible class) | | | | 26 / 31 services |
| with `LINER_ROUTE_OPERATORS=30` | 656 → 593 | 524 → 471 | 601 → 577 | unique 1,253 |

## 3. Operators (what they do and how they are kept honest)

`src/services/route_operators.py`. Starting from elite rotations — the previous iteration's operated rotations when
the orchestrator supplies them, otherwise the pool's best canonical stand-alone rotations — it applies
**insert** (a port with real demand towards the rotation; unserved demand of the previous network counts fully),
**remove**, **swap** and **reclass**, evaluates every variant with the canonical service model (`demand_coherent._Evaluator`:
cycle, vessels, capacity, ride times and transit limits, hire, fuel at the pinned price, port calls), rejects a rotation that
is already in the pool (same cyclic order and class) or a near-duplicate (Jaccard ≥ 0.8, same class) of a selected
variant, and keeps at most `budget` variants; a variant with no positive stand-alone profit is kept only if it covers
demand no pool service carries directly and only up to 34 % of the budget.  Nothing is drawn at random; nothing here
accounts cargo, revenue or cost.  Tests: `tests/test_route_operators.py` (16).

## 4. Downstream effect on the global solve

| | candidates | model variables | solver runtime | result |
|---|---:|---:|---:|---|
| B0 | 1,166 | 7,003 | 119 s | — |
| time-feasible class (default) | 1,166 | 7,053 | 120 s | coverage +2.9 pp at equal profit |
| + operators (30 per region) | 1,253 (seed 0) | 6,661 (mean of 5) | 119 s | profit −0.08 M, services 18.6 vs 21.6 (fewer, larger) |

The restricted CBC problem stays at 260 – 300 services whatever the pool; the integer incumbent, not the pool size,
is the limiting factor (see `task20_path_selection.md` §3).

## 5. Limits

* The elitism experiment (`M9`) is the three-iteration emulation of the controlled harness (no regional GA / MILP hints,
  independent generator seeds per iteration); the end-to-end effect was not measured separately.
* The operators were evaluated on one dataset; their stand-alone-profit ranking is an *ordering signal*, not a verdict:
  several operated services have a negative stand-alone profit and a positive network role.
