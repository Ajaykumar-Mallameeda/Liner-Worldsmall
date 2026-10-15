# Class-mismatch campaign — predeclared before any 20-seed run (2026-10-15)

**Diagnosis (read-only, seed 0, current model `49ecd92`; `tools/class_diag.py`, `tools/trunk_proto.py`, `outputs/*.json`)**
- Pool of 1,205 rotations: assigned class Feeder_450 950, Feeder_800 160, Panamax_2400 67, Panamax_1200 26, Super_panamax 2, **Post_panamax 0**.
  Only 76 of the 1,204 Feeder_450-feasible rotations earn money stand-alone: the rest keep the legacy nearest-capacity class (`class_screening`: "no profitable class -> legacy class kept").
- Evaluating every pool rotation in every class: Post_panamax feasible on 250, **positive stand-alone on 0**; Super_panamax feasible on 404, positive on 0
  (draft excludes 752 / 507 rotations, canals 203 / 149). The pool holds only thin 2-5 port rotations that an 8,400-TEU ship cannot fill.
- Growing rotations WITH the large class fixed (eight ports, draft-eligible hubs): Post_panamax 53 of 56 grown rotations have positive stand-alone profit
  (best +8.5 M/week, 10 vessels), Super_panamax 32 of 51 (best +13.1 M/week), Panamax_2400 60 of 60 (best +6.9 M/week). Stand-alone profits overlap and are NOT additive.

**Fix F1 (new, opt-in, default OFF):** `LINER_TRUNK_CANDIDATES=N` (`src/network/trunk_candidates.py`, wired in `reconcile.py`): N class-forced trunk rotations per under-subscribed class.

**Arms (all = arm B settings `LINER_MILP_VUB=1 LINER_LOCAL_SEARCH=1`; same frozen base `49ecd92` + the trunk module; CBC single thread, 120 s, `PYTHONHASHSEED=0`; seeds 0-19; sequential, arm order rotating with the seed)**
| tag | extra setting | targets |
|---|---|---|
| T | `LINER_TRUNK_CANDIDATES=6` | idle large classes / class mismatch (F1) |
| V | `LINER_CLASS_VARIANTS=0.10 LINER_CLASS_VARIANTS_FLOOR=-500000` | candidates hidden by the stand-alone screen (existing flag, new cost model) |
| P | `LINER_PATH_BUDGET=adaptive` | per-OD path cap of 10 (existing flag) |
| Bc | none (control, seeds 0-3 only, on the new tree) | drift / equivalence with arm B of `current_code_experiment` |
Comparison: paired with arm B of `current_code_experiment/per_seed_A_B.csv` (same seeds). Limitation stated in advance: B was run hours earlier; Bc checks drift.

**Retention criteria per arm (all must hold, otherwise REJECTED; retained = stays an experimental flag with evidence, never a default):**
1. all runs solved, ledger-valid, 0 hard-constraint / transit violations, `independent_check.py` passes every plan.
2. paired mean profit difference > 0 and profit higher on >= 14 of 20 seeds.
3. no seed loses more than 3.0 M USD/week against its B pair.
4. vessels per class never above the inventory.
5. the arm must move its target: T -> Post/Super_panamax vessels used rises (mean > 5 vessels combined); V -> services or coverage up (>= +1.0 pp); P -> coverage >= +1.0 pp.
**Combination rule (fixed now):** one arm "TC" = T plus every other arm that individually met 1-5, 20 seeds, same protocol; reported as exploratory.
**Not done on purpose:** no default changed, no input or assumption changed, no sub-weekly frequency, no solver-limit change, no WorldLarge.

## Addendum 1 — second trunk arm (predeclared 2026-10-15 13:50, after the T/V/P results, before any run of it)
Observation (T vs B, 20 seeds): Super_panamax 0.1 -> 10.0 of 10 vessels, profit +3.02 M (20/20), but Post_panamax stays 0 of 58 although 6 Post_panamax
trunks (best +8.5 M stand-alone) are offered (`outputs/trunk_offer_seed0.json`): the offered trunks of all classes share the same Asia-Europe hubs, so the Super_panamax trunk
absorbs the cargo. **Change (opt-in, default OFF):** `LINER_TRUNK_DIVERSE=1` — classes served largest first; every selected trunk marks the ODs it carries as covered
(25 % weight in the growth score of later trunks); ranking by that marginal score; stand-alone profit must still be > 0.
**Arm T2** = arm B + `LINER_TRUNK_CANDIDATES=6 LINER_TRUNK_DIVERSE=1`, seeds 0-19 (single arm, same tree/protocol). **Criteria:** (a) criteria 1-4 of the main predeclaration vs B;
(b) T2 supersedes T only if the paired mean profit vs T is >= +0.3 M AND T2 is higher on >= 14 of 20 seeds; otherwise T stays the recommended trunk setting;
(c) mean Post_panamax vessels used must be > 0 (target of the change). Limitation: T was run ~2 h earlier than T2; no drift control is run.

## Addendum 2 — screening of the remaining issues on top of T2 (predeclared 2026-10-15, before any run of these arms)
Base of every arm = T2 settings (`LINER_MILP_VUB=1 LINER_LOCAL_SEARCH=1 LINER_TRUNK_CANDIDATES=6 LINER_TRUNK_DIVERSE=1`) plus ONE change. Seeds 0-9 (5 for Hg), CBC single thread unless stated, 120 s, sequential, rotating order.
Paired comparison: T2 of addendum 1 on the same seeds (run 1-3 h earlier; no drift control — stated limitation).
| tag | change | issue targeted |
|---|---|---|
| T3 | `LINER_TRUNK_CANDIDATES=12 LINER_TRUNK_MAX_PORTS=10` | 47 idle Post_panamax; utilisation; coverage |
| H | `LINER_LOCAL_SEARCH_VARIANTS=0.10 LINER_LOCAL_SEARCH_VARIANTS_FLOOR=-500000` (alternative-class variants visible only to the search, MILP pool unchanged) | services hidden by the stand-alone screen |
| Pa | `LINER_PATH_BUDGET=adaptive` | 10-path cap |
| Rt | tree with the revised transit file (`Demand_WorldSmall_Fixed_Sep.csv` of scenario `S_rev_transit`) | input-side blocks (named scenario, NOT a canonical input change) |
| Hg | `NETWORK_MILP_BACKEND=highs` (scipy/HiGHS, unrestricted integer problem, opt-in) | LP-guided restriction / convergence |
**Screening rule:** an arm is carried to seeds 10-19 only if on seeds 0-9 it has paired mean profit vs T2 >= +0.3 M, higher on >= 7 of 10 seeds, no not-solved run, 0 ledger/transit violations, and no seed loses > 3 M. Otherwise REJECTED (Hg: 5 seeds, higher on >= 4 of 5). Carried arms are then judged on 20 seeds by criteria 1-4 of the main predeclaration against T2 (mean > 0, >= 14/20, no seed loses > 3 M).
Rt is a scenario, not a candidate for promotion: its result is reported as the value of the transit decision on top of T2.
**Not attempted (reason stated in the report):** sub-weekly frequency (model and ledger change; earlier bound <= 2.1 M/week), canal tariff and handling unit (need external sources).

## Addendum 3 — screening result of addendum 2 and the MILP-side fix (predeclared 2026-10-15, before any run of arms L / L2)
Screening of addendum 2 against T2 on seeds 0-9 (rule applied as written): T3 +0.71 M, 6/9 higher, **1 not solved (seed 7) and one seed at 22.95 M (-16.3 M)** -> rejected as it stands;
H +0.57 M but higher on 2/10 -> rejected; Pa 5/10 **not solved** -> rejected; Rt +1.11 M, 7/10 higher, min -11.2 M (seed 1) -> rejected as a candidate (scenario only). Hg: see its own rows.
**Diagnosis:** T3 on the eight seeds where CBC finds a good incumbent gives 39.3-45.5 M and up to 48 % coverage (LP bound ~45-47 M), but with the larger pool CBC sometimes returns no incumbent (`solver stopped without an integer solution`)
or a poor one inside 120 s. The failure is a MILP-start problem, not a candidate problem.
**Change (opt-in, default OFF):** `LINER_MILP_LP_ROUND_START=1` (`src/network/network_milp.py`: `lp_rounded_start`): after the LP relaxation, an integer start is built (frequencies = LP values rounded half-up, a service the LP runs at >= 0.25 sailing opens at 1;
repaired to the class fleet limits by removing sailings from the service with the smallest LP frequency) and handed to CBC as warm start. Nothing else changes (same model, same 120 s, same path set); `tests/test_lp_round_start.py` (3).
**Arms (seeds 0-9, paired with T2 and with T3):** L = T3 settings + `LINER_MILP_LP_ROUND_START=1`; L2 = T2 settings + `LINER_MILP_LP_ROUND_START=1`.
**Screening rule:** carried to seeds 10-19 only if: 10/10 solved, 0 violations, paired mean profit vs T2 >= +0.3 M, higher on >= 7/10 seeds, no seed loses more than 3 M vs T2. L must in addition have no seed below 30 M (robustness target for the failure seen in T3 seeds 7 and 9).
Otherwise rejected. A carried arm is judged on 20 seeds by criteria 1-4 of the main predeclaration against T2.
