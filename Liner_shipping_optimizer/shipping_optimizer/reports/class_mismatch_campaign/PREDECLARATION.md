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
