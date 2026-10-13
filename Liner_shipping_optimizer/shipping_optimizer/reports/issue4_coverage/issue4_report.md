# Issue 4 - coverage diagnostics and one intervention (2026-10-13)  -  gate: PASS (bottleneck quantified; intervention NOT retained)

Tree: `707c2f8` (Issues 1-3). No source file was changed in this issue (diagnostics are read-only scripts under `tools/`).
Corrected units throughout. Coverage of the unchanged default is 28.5-30.6 %; the 70 % target is not reached and is not near.

## 1. Where the demand goes (principal reason, mutually exclusive; mean of 10 seeds, default arm, `per_seed_issue2.csv`)
| reason | % of total demand |
|---|---:|
| served | 28.7 |
| fleet class inventory exhausted | 30.8 |
| not economic to open a service (at the incumbent) | 29.1 |
| no time-feasible service in the pool (path missing / cap) | 5.3 |
| time limit below the fastest sailing time (physically unattainable) | 3.4 |
| leg capacity exhausted | 2.4 |
| not profitable to carry | 0.3 |
The categories are an exclusive attribution (one principal reason per unserved TEU), so they sum to 100 %; they are *not* independent
causes - removing one moves cargo into another. The LP experiments below measure interactions directly.

## 2. What each upstream restriction costs (LP relaxation with the VUB inequality; `outputs/diag_seed*.json`; HiGHS, proven optimal)
An LP value is an upper bound with fractional frequencies; it measures the value of the restriction, not an achievable plan.
| scenario (M USD/wk; served % of demand) | seed 0 | seed 1 | seed 2 |
|---|---|---|---|
| A production pool, per-OD cap 10 fastest | 37.4 (35.8 %) | 35.9 (34.3 %) | 35.5 (34.2 %) |
| B cap lifted (all 53,310 valid paths) | **59.3 (50.6 %)** | - | - |
| C regional filter lifted (pool before filter), cap 10 | 32.4 (29.5 %) | 32.7 | 30.4 |
| E class screening off (all feasible classes offered), filter on, cap 10 | 20.2 (22.2 %) | - | - |
| F class inventories x100 | 49.1 (55.7 %) | 47.9 (54.7 %) | 48.6 (57.1 %) |
| P cost-aware path ranking, cap 10 | 46.7 (44.5 %) | 48.0 (45.9 %) | 47.0 (44.8 %) |
| Q hybrid path ranking, cap 10 | 43.6 (42.8 %) | 45.3 | 43.2 |
| R adaptive per-OD budget | 44.6 (41.4 %) | - | - |
| S cap 20 fastest | 46.5 (43.7 %) | - | - |
(Scenarios D and H, "everything lifted", were not run: one 53k-path LP takes ~16 min.)

Conclusions, each measured:
1. **The per-OD path cap with fastest-first ranking is the largest modelling restriction**: lifting it is worth +22 M/wk in the relaxation
   (+59 %), and merely changing the *ranking* at the same cap 10 (same model size, 11,773 paths) is worth +9 .. +12 M/wk on all three seeds.
2. **More candidates make the capped relaxation worse** (C, E): extra candidates fill the 10 slots with fast, uneconomic paths. Widening the
   pool or the class set without fixing the ranking is counter-productive - consistent with the old rejected pool experiments.
3. **Class inventory is binding** under corrected units (+11.7 M, +20 pp coverage when relaxed): Feeder_450 / Feeder_800 / Panamax_1200 are
   exhausted while Post/Super-panamax stay idle (Issue 2). It is an input (fleet), not a modelling error; it cannot be "fixed" without
   acquiring vessels (a *conditionally feasible* opportunity for Issue 5).
4. Integer weekly frequency: not isolated here (no sub-weekly model exists; needs owner decision A10).
5. 3.4 % of demand is physically unattainable (limit below sailing time at the fastest class) and stays unserved in any network.

## 3. One intervention tested: cost-aware path ranking (`LINER_PATH_SELECTION=cost_aware`, existing flag, cap unchanged)
Paired batch, seeds 0-9, CBC 120 s, 4 arms concurrent (`per_seed_issue4.csv`, `summary` below):
| arm | solved | profit M/wk mean | coverage % | margin % | leg LF | cost/TEU |
|---|---|---:|---:|---:|---:|---:|
| base | 8/10 (2 `not_solved`) | 23.7 (of solved) | 28.5 | 25.9 | 0.53 | 848 |
| ca (cost-aware alone) | **1/10** | n/a | - | - | - | - |
| s3 (VUB + LS) | 10/10 | 35.4 | 31.0 | 35.7 | 0.59 | 744 |
| s3ca (VUB + LS + cost-aware) | 10/10 | 36.8 | 35.7 | 32.7 | 0.57 | 769 |
* cost-aware ranking alone is **unusable with the production solver**: CBC returned no incumbent in 120 s on 9/10 seeds.
* on the strengthened solve it adds coverage (+4.7 pp) and +1.4 M mean over s3 but only **5/10 seeds higher**; margin falls 3 pp, cost per served TEU
  rises 3 %, p90 transit rises 38.6 -> 45.4 d, and the model bound gap widens to 21 %. By the acceptance policy (>= 8/10, no concealed quality loss)
  this is **inconclusive: not retained, default unchanged.** Trade-off for the owner: +4.7 pp coverage for -3 pp margin.
* the batch ran under heavier machine load (the default itself failed to solve 2/10 seeds, 0/20 in earlier batches): another sign that
  120 s CBC is the limiting factor, not the path ranking.

## 4. What this means for the 70 % target
Under the stated fleet, costs and rules the best measured relaxations reach 50-57 % coverage (path cap lifted; inventory x100) *as upper bounds*,
and achieved plans reach 31-36 %. 70 % is **not demonstrated and not supported by any measurement here**; the measured ceilings are the fleet
inventory (binding), the economics of thin lanes (29 %), and 3.4 % physical unattainability. Path ranking is the one modelling lever with a
large relaxation value; exploiting it needs a solver that can handle it (tractability), which is a separate piece of work.

## 5. Next evidence needed (not done)
* solve the uncapped / cost-aware model with a stronger MILP method (HiGHS 300 s is an owner decision, D-09) before judging ranking policies;
* scenarios D and H of the diagnostic;
* the same experiment on hold-out seeds 10-19 if a ranking change is pursued.

## Rollback
Nothing to roll back (reports and read-only tools).
