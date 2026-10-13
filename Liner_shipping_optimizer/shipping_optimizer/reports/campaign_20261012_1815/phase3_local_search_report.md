# Phase 3 — C2: exact-LP local search (`LINER_LOCAL_SEARCH`), inside the existing 120 s stage budget

**Status:** `ACCEPT FOR OWNER APPROVAL` as an optional post-MILP step (production default OFF).
Finding the owner needs: **LS and C1 are substitutes, not complements** — the strongest single change in this campaign is the local
search on the *unmodified* model (+2.64 M, 10/10 seeds, +2.8 pp coverage); adding C1 to it does not add profit (−0.12 M, n.s.).
Tree: `snap_T2_ls` (accepted tree + flags; manifest `0027fd18…9ef8`). Solver and total budget unchanged: CBC 2.10.3, 120 s.

## 1. What it is (`src/network/local_search.py`, wired in `NetworkPlanner.plan`)

Greedy best-improvement search over the operated service set, every candidate move priced EXACTLY:

    profit(F) = LP_margin(F) − Σ_s weekly_fixed_cost(s, f_s)

`LP_margin` is the optimum of the same cargo LP as `flow_reopt.reoptimize_flows` (OD demand once; capacity of every leg of every
service ≤ cap_s · f_s; margin = revenue − per-TEU port charges per path) over all valid, time-feasible paths of the operated
services (HiGHS LP through SciPy, a pinned requirement; the production CBC LP of the re-routing is unchanged);
`weekly_fixed_cost` = vessel hire of ⌈T f / 7⌉ vessels + fuel + fixed port calls from `ServiceModel` — the terms of the MILP
objective and of the independent ledger.

| move | definition | hard checks before it is evaluated |
|---|---|---|
| `add` | an unoperated service at f = 1 | class inventory Σ⌈T f/7⌉ ≤ limit; `f ≤ max_departures(limit)` |
| `drop` | an operated service leaves | — |
| `up` / `down` | f ± 1 of an operated service | inventory; `f+1 ≤ max_departures`; `f ≥ 1` |

Always in force: OD demand and leg capacity (inside the LP), transit limits (inside the path set), **served TEU never below the
incumbent's** (a coverage floor of the solved model included): the search cannot buy profit with coverage. The plan's own paths are
always columns, so the incumbent is feasible in the evaluator by construction. A move is accepted only if profit rises by more than
1,000 USD/week; the search stops at a local optimum, at 60 iterations or at the absolute deadline.

**Budget.** The MILP gets `T − reserve` (reserve default 15 s, never more than half of `T`); the search runs until
`start of the solve + T`. The complete stage therefore never exceeds `T`. Measured (mean of 10 seeds): LS-only arm — MILP 104.4 s +
search 8.2 s (set-up 1.7 s, 816 – 1,779 LP evaluations per run) + re-routing 0.16 s + ledger < 0.01 s = **114.1 s ≤ 120 s** (max 116.8);
C1+LS arm — 105.9 + 4.5 + 0.16 = 112.0 s (max 114.1). Baseline arm 120.7 s (max 121.6), C1 arm 122.3 s: LS *shortens* the stage.

**Status semantics.** A plan changed by the search is `feasible`, never `optimal`; the dual bound stays that of the capped model;
`network_ledger.optimality.local_search` carries the full record (moves, evaluations, time, termination, gain) and
`stage_timing` the seconds per step.

## 2. Tests (13 in `tests/test_local_search.py` + 4 interaction checks, all pass)
parsing / default OFF / half-budget cap; improves a deliberately poor incumbent and never exceeds the brute-force optimum over
f ∈ {0,1,2}^services (exact MILP with imposed frequencies); ledger-verified through the planner and `feasible` status; an add that
raises coverage but loses money is refused; a drop that would lower served TEU is refused (coverage floor); class inventory blocks
an add; an expired deadline changes nothing; an incomplete incumbent (no flows) is reported, not guessed; moves can be restricted;
re-routing after a move never lowers profit. Defect found by the gate and fixed: `reoptimize_flows` reported a **negative** `gain_usd`
when the incumbent used paths outside its enumeration (after the search) — not applied, but the orchestrator's "never lowers the
plan's profit" assertion reads that field; it now reports 0 and records the difference separately.

## 3. Paired experiment — 10 seeds, four arms run concurrently (equal load), CBC, T = 120 s

Tree `snap_T2_ls`; `run_arms.sh`; 18:09 – 18:30. Raw: `evidence/outputs/P3_{base,ls,c1,c1ls}_seed*.json`; table `evidence/comparisons/P3_four_arms.md`.

| arm | profit M/wk mean (sd) | min / max | margin % | coverage % | served TEU | services / vessels | load factor | ledger / viol. / recon. |
|---|---:|---|---:|---:|---:|---|---:|---|
| base (frozen) | 11.52 (1.20) | 9.37 / 13.70 | 14.4 | 25.3 | 69,879 | 27.8 / 147.6 | 0.632 | 10/10, 0, 10/10 |
| C1 | 13.45 (0.98) | 12.27 / 15.50 | 17.2 | 24.7 | 68,327 | 25.7 / 142.0 | 0.671 | 10/10, 0, 10/10 |
| **LS** | **14.15 (1.10)** | 11.74 / 15.68 | 16.0 | **28.0** | 77,515 | 31.4 / 160.5 | 0.673 | 10/10, 0, 10/10 |
| C1 + LS | 14.03 (0.96) | 12.73 / 15.78 | 16.2 | 27.2 | 75,289 | 28.8 / 158.8 | 0.674 | 10/10, 0, 10/10 |

(The base arm reproduces the recorded Tasks 19–21 default arm to the dollar on all ten seeds: mean 11.519 M.)

| paired difference | Δ profit M mean (sd) | seeds higher | min | Δ coverage pp | coverage better / worse | t |
|---|---:|---:|---:|---:|---|---:|
| C1 − base | +1.93 (1.47) | 9/10 | −0.37 | −0.56 | 4 / 6 | 3.9 |
| **LS − base** | **+2.64 (0.92)** | **10/10** | **+1.17** | **+2.76** | 8 / 2 | 8.6 |
| C1+LS − base | +2.52 (1.31) | 9/10 | −0.22 | +1.96 | 6 / 4 | 5.8 |
| C1+LS − C1 | +0.59 (0.53) | 9/10 | −0.04 | +2.52 | 8 / 2 | 3.3 |
| C1+LS − LS | −0.12 (0.98) | 4/10 | −1.46 | −0.81 | 5 / 5 | −0.4 |

Per seed (Δ profit vs base, M): LS +2.48 +3.98 +2.41 +4.03 +1.17 +3.20 +2.88 +1.24 +2.69 +2.27;
C1+LS +2.16 +4.21 +1.34 +3.36 +3.00 +2.96 +3.98 −0.22 +3.15 +1.23.
Replicates: the two C1 arms (Phase 2, 2-way load; Phase 3, 4-way load) agree to the dollar on 9/10 seeds (seed 9: 12.62 vs 12.27 M);
the two baseline arms of the same batches agree on 9/10 seeds as well (seed 4: 11.68 vs 10.57 M); the stand-alone Phase 1 baseline
differs from them on 4/10 seeds. Time-limited CBC is reproducible for a given load pattern, and not across load patterns: all
comparisons in this report are therefore within one concurrent group.

**Where the value comes from (all 10 seeds).** LS-only: 136 moves — 85 adds, 46 drops, 3 f+1, 2 f−1; mean search gain 3.38 M by
its own accounting (the MILP had 15 s less, hence the +2.64 M net). C1+LS: 44 moves (34 add, 9 drop, 1 down), mean search gain 0.94 M.
Move-type ablation on C1, seeds 0 – 4 (`P3c`, four arms concurrently): **add-only +0.45 M (4/5; coverage +3.4 pp, 5/5)**,
drop-only +0.01 M, frequency-only −0.10 M — the value is in opening services that the capped, time-limited MILP did not open
(consistent with the diagnosis: 46 unopened services with a positive add-one value on the production incumbent, 10 visible to the
capped model); drops matter only on poor incumbents (LS-only has 46 of them).

**Quality gates (all 40 plans):** ledger valid 40/40, 0 violations, reconciled 40/40, regional partition verified; transit
violations 0; maximum per-strategy p90 transit 33.6 – 38.0 d (LS) / 34.0 – 45.7 d (C1+LS) vs 39.3 – 46.4 d (base); minimum slack
0.0006 – 0.07 d (the existing rule allows flows exactly at their limit); transfers ≤ 2; no negative-profit plan.

## 4. Interactions (explicit)
| interaction | handled / evidence |
|---|---|
| flow re-optimisation after a move | runs after the search with `only_services = operated`; gain 0 after the search in 40/40 plans except one negative report (fixed, above) |
| profit-floor repair | runs after the search; never triggered (no plan below 0) |
| a move that adds served TEU and lowers profit | refused (unit test; the acceptance rule is profit) |
| a move without vessel inventory | never evaluated (unit test; 0 fleet violations in 40 plans) |
| invalid / incomplete incumbent | `no_incumbent` / `error` reported, plan untouched (unit tests) |
| deadline | no evaluation starts after it (unit test; 0 of 20 runs hit it: all ended at a local optimum in 3 – 11 s) |
| optimality claim | status `feasible`; bound belongs to the capped model (`bound_applies_to`) |
| coverage floor (`LINER_GLOBAL_MIN_COVERAGE`) | the search honours the floor; the profit-floor repair keeps its documented skip (unchanged) |

## 5. Limits
* The unused part of the 15 s reserve (4 – 11 s) is not given back to the MILP; the reserve could be tuned (not tested).
* Moves are single steps; no swaps or class changes of an operated service (the candidate-expansion arms in Phase 4 give the
  search class variants to add).
* Ten seeds of one generator on one dataset; end-to-end orchestrator runs with LS are in Phase 5.
* LS makes the plan depend on the exact LP, whose columns are the enumerated valid paths of the whole pool (≤ 2 transfers where
  the shorter journeys are too few); the final re-routing recovers the remaining multi-hop columns.

## 6. Rollback
`LINER_LOCAL_SEARCH` unset (default). File rollback: reverse-apply `patches/phase2_T1_flags.patch` (LS is in it, first version)
and `patches/` of this directory; no accounting or data code is touched.

## 7. Late change (after the experiments above): the search deadline is anchored at the start of the plan

In the first version the search ran until *start of the solve + T*.  Model and path construction (≈ 1.0 – 1.6 s) precede the solve and CBC
may overrun its own limit by up to ≈ 2 s, so the complete stage could end at 121 – 122 s with the search using its whole reserve (seen in the
class-variant arms of Phase 4: maximum 121.5 – 122.1 s; the baseline's own maximum is 121.6 s).  `NetworkPlanner.plan` now passes
`deadline = t0 + time_limit_sec` (`t0` = entry of `plan()`), so those two items come out of the reserve and the stage ends within `T`
plus the re-routing and ledger (< 0.2 s).  Measured after the change (Phase 4 §6, tree `snap_T7_final`): stage mean 113.8 s, **maximum
116.8 s** (C1 + LS + 10 % variants), 120.0 s for the one arm whose search needs the whole reserve; the unit tests are unchanged and pass.
Nothing else in the search changed; the Phase 3 numbers above were produced by the earlier anchoring and are reported as they were.

## 8. Late change 2 (found by the Phase 5 hold-out gate): idle services are pruned after the re-routing

One hold-out plan carried a service with **zero cargo** (a Feeder_450 opened by the search's last move for a 9 k USD/week gain; the final
re-routing then found better paths and left it empty — 74.5 k USD/week of hire, fuel and port calls for nothing).  The search itself is
correct (its LP priced the move before the re-routing); the omission was a clean-up step.  `prune_idle_services` (in `local_search.py`,
called from `NetworkPlanner.plan` only when the search is enabled and applied) now drops every operated service that carries no cargo after
the re-routing and the profit-floor repair; it updates frequencies, vessels and the cost terms from the same service models the MILP and
the ledger use, and reports `local_search.idle_pruned`.  An idle service changes neither cargo nor coverage, so the step can only raise
profit.  Default behaviour is unchanged (flag-gated).  Tests: `TestIdleServicePrune` (2).  See `phase5_combined_acceptance_report.md` §3.
Across the ~330 plans of this campaign scanned before the fix it would have acted once.
