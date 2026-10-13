# Phase 4 — targeted candidate / path expansion (E0 – E3 ladder, path inclusion, search-only variants)

**Status (final, §9):** class variants in the pool (MILP-visible; the validated setting is the positive-stand-alone-only one, 5 % and 10 % give the same pool) are the one expansion that helps — part of the accepted combination, **INCONCLUSIVE**
as an increment over C1 + LS (dev 9/10, hold-out 7/10); search-only variants **EXPERIMENTAL ONLY**; multi-hop evaluator and path inclusion **REJECT**.
Trees: `snap_T3_expansion` (ladder, path inclusion; manifest `40b1f7f5…`), `snap_T5_lsvariants` (search-only variants; `212e331d…`),
`snap_T6_lsmultihop` (multi-hop evaluator; `0031ec7c…`), `snap_T7_final` / `snap_T8_floorknob` (combinations, floor knob).  Solver and total budget unchanged: CBC 2.10.3, 120 s; all flags default OFF.
Every expansion arm is **C1 + LS** (the Phase 2 / 3 conclusions) plus the one variable under test, so each difference is a single change.

## 1. Diagnosis reproduced on the plans of this campaign (seed 0, full 85 k-path set, exact flow LP)

Method (`evidence/tools/od_offline_t22.py`, `od_offline_body.py`): for each OD the first applicable cause in the order below; the LP over all
valid paths of the operated services reproduces each plan's profit **to the dollar** (evaluator check in the JSON: 14,630,989.72 ledger vs
14,630,989.72 LP over the model's own paths; 14,645,785.72 over all valid paths).  Shares are % of total demand (276,447 TEU/wk).

| category | production incumbent (13.45 M) | C1 incumbent (15.01 M) | **ladder plan E2 = C1 + LS + 10 % class variants, floor −0.5 M (14.63 M)** |
|---|---:|---:|---:|
| C2 transit limit below sailing time (not servable) | 3.37 | 3.37 | 3.37 |
| C3 no compatible candidate in the pool | 2.53 | 2.53 | 2.43 |
| C4 valid path exists only outside the capped model | 0.06 | 2.21 | 3.40 |
| C5 vessel-class inventory blocks opening | 1.69 | 16.33 | 19.54 |
| C6 leg capacity of operated services | 5.22 | 5.40 | 6.34 |
| C7 not justified at the incumbent (single-service view, per-TEU margin ≤ 0) | 47.4 | 30.6 | 29.96 |
| C8a opening ONE service raises profit at the incumbent | 8.92 | 5.99 | **0.46** |
| C8b needs ≥ 2 new services | 5.65 | 5.67 | 5.22 |
| served | 25.2 | 27.9 | 29.3 |

Marginal value of opening one more service at the plan (exact LP):

| | production | C1 | **final plan** |
|---|---:|---:|---:|
| unopened services with positive add-one profit (all valid paths) | **46** | 20 | **1** (+57 k USD/wk, in the LP support) |
| … with only the paths the capped model held | 10 | 1 | 0 |
| greedy add/drop/±f search on top | +1.29 M | +1.10 M | +0.09 M (35 services, 182 vessels: nothing left worth the move) |

Reading: the structural bottlenecks the audit found (weak relaxation → poor incumbent; cap-hidden openings; inventory-blocked rotations) are
exactly the ones C1, LS and the class variants address; on the E2 plan (seed 0) the single-service opportunity list is empty (46 → 1).  What
remains is C7 (30 % of demand whose own margin cannot pay a service) and C5, which is now *conditional on the plan*: with the plan's class
mix (Panamax_2400 23 used / 51 free, Post_panamax 36 / 22 free, Feeder_450 7 / 17 free) the add-one test finds nothing profitable there.

## 2. What was added (and nothing else)

| item | where | rule | default |
|---|---|---|---|
| alternative-class variants | `src/network/class_variants.py`, `reconcile.py` (before planning) | a class is *over-subscribed* when its pool holds ≥ 2.0 candidates per vessel; each rotation of an over-subscribed class is evaluated in each non-over-subscribed class with the canonical stand-alone model (`ClassScreener.evaluate_class`: feasibility, vessels per weekly sailing against the class inventory, ride-feasible cargo inside the transit limit, hire + fuel + port calls at the pinned price); a variant is kept only with **positive stand-alone profit**, **at most one per rotation** (best profit per vessel), top `fraction × |pool|` by profit per vessel; every addition carries its provenance (source rotation, class, stand-alone profit, vessels, reason) | `LINER_CLASS_VARIANTS` unset = off |
| search-only variants | `local_search.variants_from_environment`, `plan.py` | same generator, ids `lv####`, modelled **after** the MILP and visible only to the local search (the MILP cannot slow down) | `LINER_LOCAL_SEARCH_VARIANTS` unset = off |
| multi-hop evaluator | `local_search.py`, `plan.py` | the search's path set enumerates two-transfer journeys for every OD | `LINER_LOCAL_SEARCH_MULTIHOP` unset = off |
| restriction-aware path inclusion | `paths.py`, `network_milp.py`, `plan.py` | after the LP, rebuild per-OD paths (K fastest) from the LP-support services only | `LINER_PATH_INCLUDE` unset = off |

Nothing prices cargo or accounts cost outside the existing model: variants are ordinary candidates; the MILP decides with their real fixed
and variable costs; the independent ledger verifies every plan (valid, 0 violations, reconciled) in every arm below.
No variant is "forced", no coverage floor is introduced, no verdict band is touched.

## 3. Ladder (C1 + LS fixed; **two settings move together**: fraction of the unique pool added as class variants, and their stand-alone-profit floor) — 10 seeds, four arms concurrent

Tree `snap_T3_expansion`, `run_arms.sh`; 18:41 – 19:02 (`evidence/runs/P4.driver.txt`).  Raw `evidence/outputs/P4_E{0..3}_seed*.json`; table `evidence/comparisons/P4_ladder.md`.

| arm | fraction / stand-alone floor (env) | profit M/wk mean (sd) | min / max | margin % | coverage % | served TEU | services / vessels | load factor | ledger / viol. / recon. | stage s mean (max) |
|---|---|---:|---|---:|---:|---:|---|---:|---|---|
| E0 | – | 14.01 (0.93) | 12.73 / 15.78 | 16.2 | 27.1 | 74,879 | 28.9 / 158.5 | 0.675 | 10/10, 0, 10/10 | 112.5 (115.7) |
| E1 | 5 % / 0 (positive only; unset) | 15.12 (1.39) | 12.98 / 17.45 | 16.7 | 29.0 | 80,052 | 31.3 / 167.1 | 0.708 | 10/10, 0, 10/10 | 114.2 (116.5) |
| **E2** | **10 % / −0.5 M/wk** | **15.39 (0.85)** | **14.18 / 16.74** | 16.6 | **30.1** | 83,121 | 34.0 / 176.4 | 0.727 | 10/10, 0, 10/10 | 117.1 (121.5) |
| E3 | 20 % / −1.0 M/wk | 14.65 (1.13) | 12.84 / 16.72 | 16.7 | 28.5 | 78,700 | 31.0 / 167.4 | 0.733 | 10/10, 0, 10/10 | 116.4 (120.1) |

**Attribution (corrected after the Phase 5 hold-out).**  `LINER_CLASS_VARIANTS_FLOOR` was set to −500000 in E2 and −1000000 in E3 and
unset (= 0, positive stand-alone only) in E1 (`env` of each output).  With floor 0 only ~30 – 40 rotations per pool have a positive stand-alone
variant, so **5 % and 10 % give the same pool**: E1 equals the final candidate (10 %, floor 0) to the dollar on 10 of 10 seeds (compare
`P4_E1_*` with `D5_e_*`).  The final candidate's own development-seed increment over C1 + LS is therefore **E1 − E0: +1.12 M, 9/10**
(t 2.7); E2's +1.39 M belongs to a different setting (admitting variants that lose money stand-alone) that was **never carried to the hold-out**.

| paired difference | Δ profit M mean (sd) | seeds higher | min / max | Δ coverage pp | coverage better / worse | t |
|---|---:|---:|---|---:|---|---:|
| E1 − E0 | +1.12 (1.26) | 9/10 | −1.01 / +3.33 | +1.87 | 8 / 2 | 2.66 |
| **E2 − E0** | **+1.39 (1.01)** | **9/10** | **−0.43 / +2.80** | **+2.98** | 8 / 2 | **4.11** |
| E3 − E0 | +0.64 (1.77) | 7/10 | −2.94 / +3.15 | +1.38 | 7 / 3 | 1.09 |

* The response is **non-monotone** in the combined setting: E1 and E2 help, E3 (20 %, floor −1 M) is no longer distinguishable from E0 (t = 1.1)
  and has the largest losses (−2.94 M on seed 1).  Because fraction and floor moved together, the loss cannot be split between pool size
  (a larger pool slows the time-limited CBC: the relaxation gap grows back, E3 gaps −15 … +16 %; same direction as the Task 10 finding) and the
  admission of loss-making stand-alone variants.  E2 has the best mean; its worst seed (−0.43 M) is the smallest loss of the three arms.
* All gates hold in all 40 plans: ledger valid 40/40, **0 violations**, reconciled 40/40, no negative-profit plan, status `feasible`.
* Time: E2's stage mean is 117.1 s (max 121.5 s).  The overrun beyond 120 s is model/path construction (≈ 1.4 s, outside the MILP budget in
  the baseline too: baseline max 121.6 s) plus CBC's own overrun of its limit (≤ 1.9 s); after this campaign's final edit the search deadline
  is anchored at the start of the plan so the stage ends within `T` (see §8).

### 3.1 Provenance — what the variants actually do in the plans

Operated services with ids `cv####` (from each plan's service list; mean over 10 seeds):

| arm | variant services operated | of all services | share of carried TEU-legs | their load factor | classes (10 seeds) |
|---|---:|---:|---:|---:|---|
| E1 (5 %, floor 0 = final candidate) | 3.9 | 31.3 | 13.1 % | 0.913 | Panamax_1200 30, Feeder_450 6, Panamax_2400 2, Super_panamax 1 |
| E2 (10 %, floor −0.5 M) | 7.6 | 34.0 | 15.8 % | 0.869 | Feeder_450 40, Panamax_1200 31, Panamax_2400 4, Super_panamax 1 |
| E3 (20 %, floor −1 M) | 8.4 | 31.0 | 19.9 % | 0.861 | Feeder_450 41, Panamax_1200 37, Panamax_2400 5, Super_panamax 1 |

* The variants are used, well loaded (0.86 – 0.91 against 0.68 – 0.73 network-wide) and fall into the classes the production pool
  starves: **Feeder_450 — never operated in any recorded baseline plan — carries 40 variant services in E2 (6 in E1, the final candidate's variants)** (stand-alone profit is
  positive on only 8 of 1,149 rotations, best 190 k USD/wk against 0.9 – 3.0 M for the other classes: see `maritime_assumption_validation.md`;
  it is rarely a rotation's best class and the seed-2 pool holds only 26 of 1,163 candidates in it, so the baseline never used one).  A variant has to pass the
  same canonical stand-alone test and fit the class inventory; it is not a different kind of service from the pool's: same model, same
  costs, same ledger.
* Coverage rises with them (+3.0 pp), consistent with the class-inventory blocking (C5: 16 % of demand on the strengthened incumbent) being
  relieved without adding vessels of the exhausted class; this is an interpretation of the per-OD diagnosis, not a separate test.

## 4. Restriction-aware path inclusion (`LINER_PATH_INCLUDE = K`) — **REJECT**

Idea (audit item B): the per-OD cap (10 fastest) hides 36 of 46 profitable openings from the MILP, so after the LP rebuild per-OD paths from
the LP-support services only with a larger K.  Tree `snap_T3_expansion`, C1 + LS fixed, four arms concurrent, seeds 0 – 9, 19:04 – 19:23 (`evidence/runs/P4b.driver.txt`).

| arm | K | `feasible` / 10 | profit M mean (feasible only) | note |
|---|---:|---:|---:|---|
| K0 | – (baseline) | 10 | 13.91 | reference arm of the batch (E0) |
| K10 | 10 | **4** | 13.99 (n = 4) | `not_solved` on 6 seeds |
| K20 | 20 | **2** | 14.95 (n = 2) | `not_solved` on 8 seeds |
| K40 | 40 | **2** | 15.32 (n = 2) | `not_solved` on 8 seeds |

Mechanism (logged, not inferred): the integer problem built on the LP-support services plus K paths per OD is far larger than the capped
one; CBC finds **no incumbent** inside `T − reserve` on most seeds (`not_solved`, gap 100 %, ledger `None`) — the plan would be empty.
The seeds that do solve are not better on average (paired K10 − K0 +0.29 M, t = 0.3, 2/4 seeds higher); the K20 / K40 means are
2-seed means of the seeds that happened to solve and cannot be read as an effect.  Under the stated rule (a change that fails to deliver a
plan on 60 – 80 % of seeds cannot be promoted) **REJECT**; the code stays behind the flag (default OFF, documented) so the result is
reproducible, and C2 already recovers the cap-hidden openings *after* the solve, which is where they are cheap.
Raw: `evidence/outputs/P4b_K*_seed*.json`; table `evidence/comparisons/P4b_path_include.md`.

## 5. Search-only variants (`LINER_LOCAL_SEARCH_VARIANTS`) — P4c, tree `snap_T5_lsvariants`

Motivation: the ladder's loss at +20 % is a *solver* cost (a bigger MILP), not a candidate-quality cost.  The same variants can be offered
**only to the local search**, which prices each move exactly and cannot be slowed down by pool size: the MILP is solved first on the
unchanged pool, the variants (ids `lv####`) are modelled afterwards and are visible to the search only.

Four arms concurrent, seeds 0 – 9, 19:25 – 19:45 (`evidence/runs/P4c.driver.txt`).  **Two factors move together in this ladder** (fraction
and stand-alone floor; recorded in each output's `env`), so it measures a *direction*, not the effect of either alone:

| arm | fraction of the pool | stand-alone floor USD/wk | variants offered (seed 0) | profit M/wk mean (sd) | coverage % | served TEU | ledger / viol. / recon. | stage s mean (max) |
|---|---:|---:|---:|---:|---:|---:|---|---|
| E0 (C1 + LS) | – | – | – | 13.99 (1.08) | 27.3 | 75,501 | 10/10, 0, 10/10 | 114.9 (117.9) |
| L05 | 5 % | 0 (positive only) | 30 | 14.36 (1.02) | 27.9 | 77,213 | 10/10, 0, 10/10 | 116.3 (120.8) |
| L10 | 10 % | −0.5 M | 117 | 14.49 (1.01) | 28.3 | 78,306 | 10/10, 0, 10/10 | 117.9 (122.1) |
| L20 | 20 % | −1.0 M | 233 | 14.59 (1.04) | 28.9 | 79,768 | 10/10, 0, 10/10 | 118.8 (122.1) |

| paired vs E0 | Δ profit M mean (sd) | seeds higher | min / max | Δ coverage pp | coverage better / worse | t |
|---|---:|---:|---|---:|---|---:|
| L05 | +0.37 (0.24) | 9/10 | −0.11 / +0.73 | +0.62 | 6 / 4 | 4.6 |
| L10 | +0.50 (0.24) | 9/10 | −0.09 / +0.76 | +1.02 | 7 / 3 | 6.2 |
| **L20** | **+0.60 (0.18)** | **10/10** | **+0.37 / +0.92** | **+1.54** | **10 / 0** | **10.1** |

Reading.  (1) The effect is **small, very consistent and monotone over the range tested**, and it is the cheapest kind of improvement:
nothing about the MILP changes, so no seed can lose to a harder solve (min +0.37 M at L20).  (2) Variants that *lose* money stand-alone
(floor down to −1 M/wk) are worth opening as complements: the search accepts a move only if the exact plan profit rises by > 1,000 USD/wk,
so a negative floor widens the menu, not the risk.  (3) Operated search-only variants: 1.5 / 3.4 / 4.7 per plan (5.3 / 6.6 / 8.0 % of the
carried TEU-legs), load factor 0.88 / 0.83 / 0.82, Feeder_450 again the largest class (2 / 20 / 30 service-seeds out of 10 plans).
(4) The search spends more of its reserve (mean 8.0 / 9.5 / 10.6 s against 6.6 s; evaluations 765 / 966 / 1,131 against 650).
(5) The stage maxima of 120.8 – 122.1 s on this tree are the overrun the deadline anchoring in §8 removes (search ended at
start of solve + 120 s while model construction preceded it).
Raw: `evidence/outputs/P4c_*_seed*.json`; table `evidence/comparisons/P4c_search_variants.md` / `.csv`.

## 6. Combinations and the multi-hop evaluator — P4d, tree `snap_T7_final` (C1 + LS fixed in every arm)

Four arms concurrent, seeds 0 – 9, 19:46 – 20:07 (`evidence/runs/P4d.driver.txt`).  *Note on intent:* the batch was meant to use the negative
floor of P4c for the search-only arms; the knob that separates the search-only floor from the MILP-variant floor did not exist yet
(`LINER_CLASS_VARIANTS_FLOOR` was shared), so G1 / G2 ran at the **positive-only** floor.  The batch is reported as it ran; P4e (§7) repeats the
question with the separate knob.  (Stopping the batch was refused by the permission layer, so it ran to completion.)

| arm | configuration | profit M/wk mean (sd) | coverage % | ledger / viol. / recon. | stage s mean (max) | LS s mean (max) | LP evaluations |
|---|---|---:|---:|---|---|---|---:|
| G0 | MILP variants 10 %, floor 0 (= the final candidate = E1's pool) | 15.12 (1.39) | 29.0 | 10/10, 0, 10/10 | 113.8 (116.8) | 6.3 (9.0) | 648 |
| G1 | G0 + search-only variants 50 %, floor 0 | 15.12 (1.39) | 29.0 | 10/10, 0, 10/10 | 114.1 (117.1) | 6.6 (9.5) | 656 |
| G2 | no MILP variants; search-only 100 %, floor 0 | 14.39 (0.87) | 28.0 | 10/10, 0, 10/10 | 113.2 (115.0) | 5.7 (7.1) | 643 |
| G3 | G0 + multi-hop LS evaluator | 14.88 (1.13) | 28.3 | 10/10, 0, 10/10 | 119.8 (120.0) | 12.3 (12.8) | 438 |

| paired vs G0 | Δ profit M mean (sd) | seeds higher | min / max | Δ coverage pp | t |
|---|---:|---:|---|---:|---:|
| G1 | **0.000** (0.000) | 0/10 (10 identical) | 0 / 0 | 0.00 | – |
| G2 | −0.73 (1.33) | 3/10 | −3.19 / +1.14 | −0.97 | −1.65 |
| G3 | −0.24 (0.49) | 6/10 | −1.27 / +0.21 | −0.62 (better in 1/10) | −1.49 |

* **G1 = G0 to the dollar on all ten seeds.**  Once the MILP has the positive-stand-alone variants, the positive-only search-only variants are
  either already in the pool or never chosen: they add nothing (3 – 11 were offered per plan; none was accepted).  A search-only arm only
  matters with a negative floor (§7).
* **G2 < G0:** with the positive-only floor the search-only route offers ≤ 30 variants (one per rotation, positive stand-alone) and is worse
  than letting the MILP see 10 % of the pool — the MILP finds combinations the greedy search cannot.
* **G3 (multi-hop evaluator) is not better and is the only arm to use the whole reserve** (setup 10.4 s of path enumeration against 2.0 s,
  438 LP evaluations against 648): the richer path set costs the search the iterations it would have used.  **REJECT** as a default; kept behind
  `LINER_LOCAL_SEARCH_MULTIHOP` (default off, tested) for a future larger reserve.
* **Time:** with the deadline anchored at the start of the plan (§8) the stage maximum is 116.8 – 117.1 s in the three arms that do not
  enumerate multi-hop paths (baseline code: 121.6 s) and 120.0 s in G3, whose search stops exactly at the deadline.
Raw: `evidence/outputs/P4d_*_seed*.json`; table `evidence/comparisons/P4d_combinations.md` / `.csv`.

## 7. Negative stand-alone floor for the search-only variants, and C1 with variants — P4e, tree `snap_T8_floorknob`

New knob `LINER_LOCAL_SEARCH_VARIANTS_FLOOR` (stand-alone profit floor of the search-only variants, USD/wk ≤ 0, independent of
`LINER_CLASS_VARIANTS_FLOOR`; unset = the generator's default; 20 tests in `tests/test_local_search.py` incl. parsing and "a lower floor admits
at least as many variants and the plan stays ledger-verified").  Four arms concurrent, seeds 0 – 9, 20:08 – 20:28
(`evidence/runs/P4e.driver.txt`).  Every arm has the local search; "C1" = `LINER_MILP_VUB`.

| arm | configuration | profit M/wk mean (sd) | min / max | coverage % | ledger / viol. / recon. | stage s mean (max) | variants operated per plan |
|---|---|---:|---|---:|---|---|---|
| H0 | C1 + LS + 10 % MILP variants, floor 0 (final candidate = E1's pool) | 15.12 (1.39) | 12.98 / 17.45 | 29.0 | 10/10, 0, 10/10 | 114.2 (117.1) | 3.9 MILP variants |
| H1 | LS + 10 % MILP variants, **no C1** | 13.73 (1.16) | 11.52 / 15.73 | 28.1 | 10/10, 0, 10/10 | 116.8 (119.6) | 3.6 MILP variants |
| H2 | H0 + search-only variants 20 %, floor −1.0 M | **15.29 (1.30)** | 13.40 / 17.49 | **29.6** | 10/10, 0, 10/10 | 117.0 (119.8) | 3.9 MILP + 2.4 search-only (21 of 24 Feeder_450) |
| H3 | C1 + LS + search-only 40 %, floor −2.0 M, **no** MILP variants | 14.89 (1.11) | 13.32 / 16.80 | 29.3 | 10/10, 0, 10/10 | 117.9 (120.3) | 6.4 search-only (46 Feeder_450, 14 Panamax_1200, 4 Panamax_2400 over 10 plans) |

| paired vs H0 | Δ profit M mean (sd) | seeds higher | min / max | Δ coverage pp | coverage better / worse | t |
|---|---:|---:|---|---:|---|---:|
| H1 (no C1) | **−1.39 (1.60)** | 1/10 | −5.38 / +0.44 | −0.90 | 3 / 7 | −2.6 |
| H2 (+ search-only variants) | **+0.16 (0.28)** | **8/10** | −0.35 / +0.57 | +0.67 | 8 / 2 | 1.8 |
| H3 (search-only only) | −0.23 (1.45) | 5/10 | −2.65 / +1.69 | +0.39 | 5 / 5 | −0.5 |

Reading.
1. **C1 is not redundant once the pool is expanded.**  On the unexpanded pool C1 and LS are substitutes (Phase 3), but with the 10 %
   variants the MILP is larger and the strengthened relaxation is what keeps CBC's incumbent good: removing it costs 1.39 M (1/10 seeds
   higher, worst seed −5.4 M).  So the pieces are *not* interchangeable: the expansion
   needs C1, and LS needs neither the expansion nor C1.
2. **Search-only variants on top of the floor-0 MILP variants (H2 vs H0) add a small, mostly consistent amount:** +0.16 M (≈ 1 %), 8/10 seeds, coverage +0.7 pp 8/10;
   the two losing seeds lose ≤ 0.35 M.  This meets the 8/10 rule but not by much; it is carried to the hold-out (Phase 5) as a separate arm
   so that its worth is decided there and not here.
3. **Search-only variants *instead of* MILP variants (H3) are not better than MILP variants** even with the larger pool and the lower floor
   (−0.23 M, 5/10): the MILP uses candidates it can combine with the rest of the network; the greedy search can only add them one at a time.
   Feeder_450 is again the class that the search picks (46 of 64 operated search-only variants).
4. The dollar and coverage gain of the whole ladder from the baseline pool to C1 + LS + class variants (+ search-only) is read in Phase 5 on
   concurrent arms, not by chaining batches of different load.
Raw: `evidence/outputs/P4e_*_seed*.json`; table `evidence/comparisons/P4e_negative_floor.md` / `.csv`.

## 8. Time budget: late change in `NetworkPlanner.plan`

See `phase3_local_search_report.md` §7: the search deadline is `t0 + T` (plan entry) instead of `start of the solve + T`.  The stage maximum
over the final-code arms (P4d G0 – G2, P4e H0): **117.1 s**; baseline code 121.6 s.  No budget was added: the 120 s of the stage is
unchanged and the MILP is given `T − reserve` (reserve default 15 s, never more than half of `T`, only when the search is enabled).

## 9. Classification (final numbers in `final_acceptance_report.md`)

| change | flag (default OFF) | dev result (seeds 0 – 9) | classification |
|---|---|---|---|
| class variants in the pool, **floor 0** (E1 = the final candidate's variants; 5 % and 10 % give the same pool) on C1 + LS | `LINER_CLASS_VARIANTS=0.05` or `0.10` | dev **+1.12 M, 9/10** (P4 E1 − E0, same batch); hold-out +0.56 M, 7/10 (C9b) | **INCONCLUSIVE** as an increment (dev 9/10, hold-out 7/10; `phase5_combined_acceptance_report.md` §4.1); part of the **accepted combination** (C1 + LS + these variants vs default: 20/20) |
| class variants with a **negative floor** (E2: 10 %, −0.5 M; E3: 20 %, −1.0 M) | `LINER_CLASS_VARIANTS` + `LINER_CLASS_VARIANTS_FLOOR` | +1.39 M, 9/10 (E2) / +0.64 M, 7/10 (E3), dev only; **never run on the hold-out** | **EXPERIMENTAL ONLY** (E2 holds the best development mean and the largest plans of the campaign: 44 services, 36.2 % coverage on one seed; it needs its own hold-out before any claim) |
| search-only variants (negative floor) on the floor-0 MILP variants | `LINER_LOCAL_SEARCH_VARIANTS`, `_FLOOR` | +0.16 M, 8/10 (dev); hold-out +0.19 M 7/10 and +0.30 M 7/10 (H5, C9) | **EXPERIMENTAL ONLY** (did not pass on the hold-out; its arm exposed the accounting defect of Phase 5 §3, fixed) |
| search-only variants instead of MILP variants | same | −0.23 M, 5/10 | **REJECT** as a replacement for the MILP variants |
| search-only, positive-only floor | same | 0.00 M (identical plans) / −0.73 M without MILP variants | **REJECT** (adds nothing) |
| multi-hop LS evaluator | `LINER_LOCAL_SEARCH_MULTIHOP` | −0.24 M, 6/10; coverage worse 9/10; uses the whole reserve | **REJECT** (kept off) |
| restriction-aware path inclusion | `LINER_PATH_INCLUDE` | `not_solved` on 60 – 80 % of seeds | **REJECT** |
| LS without C1 on the expanded pool | – | −1.39 M, 1/10 | n/a (confirms C1 is part of the combination) |

## 10. Rollback

Every item is an environment variable, default unset = the accepted behaviour (checked at each phase by the baseline arms of the modified
trees).  File rollback: reverse-apply `patches/final_vs_accepted.patch` or restore `snap_C0_base` (manifest `34a8d390…`); commands in
`final_acceptance_report.md`.
