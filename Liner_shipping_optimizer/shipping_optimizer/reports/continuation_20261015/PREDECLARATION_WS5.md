# Predeclaration - Workstream 5: targeted path additions (written BEFORE the runs)

Date: 2026-10-15. Code: tree `tree_pt1` = tree_lanes1 + `src/network/targeted_paths.py` and its hook (`path_augment` in
`network_milp.solve_network`, wired in `plan.py`); everything default OFF; the default 10-path cap is unchanged.

Mechanism (one round, bounded): after the first LP relaxation, every demand that the relaxation leaves partly unserved is
examined; its excluded valid paths (<= 2 transfers, time-feasible, services with LP rows) are priced with the LP duals
(reduced profit = revenue - port charges - dual(demand) - sum dual(leg capacity)); only paths with a positive reduced profit
qualify; the top K = 30 demands by (weekly TEU x best reduced profit) get their M = 3 best paths; the LP is solved once more;
on any failure the original LP and paths are kept.  Caps: 30 ODs, 3 paths per OD, 90 paths in total, 1 round.
Dual units and signs were validated by finite differences (tests/test_targeted_paths.py) before use.

Arms (seeds 0-9, strictly alternating, base = C3 flags, CBC single thread 120 s, `PYTHONHASHSEED=0`):
* `C3d` control (flag unset)   * `P1` `LINER_PATH_TARGETED=30,3`
Both arms also run the post-solve coverage diagnosis (`T_STUDY=coverage`), which only reads the finished plan.
The batch runs concurrently with the lane batch (2 single-thread solves on a 16-thread machine); each batch is internally
paired, so the paired differences are comparable within a batch, absolute levels across batches are not.

Retention (screening rule of the class-mismatch campaign): mean paired difference >= +0.3 M USD/week, higher on >= 7 of 10 seeds,
no run failed (`not_solved` / `invalid_plan` where the control solved), no seed loses more than 3 M, ledger / transit / draft /
fleet violations 0, stage wall <= 125 s.  Reported as well: columns added, LP bound before/after, the share of added paths
that carry flow in the final plan, runtime.  Otherwise the flag stays opt-in and the result is rejected or inconclusive.

Addendum (same day, before any P1 result existed): the first launch of this batch failed in the targeted arm because the env list
separator split `LINER_PATH_TARGETED=30,3`; the flag now also accepts `30:3`, the batch was stopped (process kill only; no result of the
failed launch is used; the one control output `C3d_seed0` of that launch stays in `outputs/` unused) and restarted with tags `C3e` (control)
and `P1b` (`LINER_PATH_TARGETED=30:3`).  Criteria unchanged.

Addendum 2 (written after P1b seeds 0-8 were all `not_solved` and before the runs below): the targeted arm produced no incumbent on 9 of 9
seeds (CBC `Not Solved`, LP bound +2.4 M higher, LP support 95 services instead of the 105 the support cap leaves in the control).  To
learn whether the failure depends on the SIZE of the augmentation (and is not an implementation defect) an EXPLORATORY follow-up is run on
seeds 2-4 only: `P1s` = `LINER_PATH_TARGETED=10:2` (at most 20 added paths).  It is reported as exploratory and cannot change the verdict
of the predeclared arm.  `P1b` seed 9 (output lost to a full disk and renamed `.invalid_disk_full`) is re-run.

Addendum 3 (after P1b 0/10 solved and the exploratory P1s 0/3; mechanism found BEFORE this run): the diagnostic run `P1f` (seed 2,
formulation recorded) showed that the targeted round itself took 32 s of the ~105 s MILP budget - the cap-free enumeration of the valid
paths of ALL 1,764 demands plus the second LP - after which CBC (which needs about 90 s to its first incumbent on these pools) no longer
reaches one.  The round was changed to enumerate only the highest-value candidate demands (largest LP-unserved revenue; the top max(100, 4K)
demands, then the top K by priced value as before).  Second attempt `P2` = `LINER_PATH_TARGETED=30:3` with the changed round, seeds 0-9,
a fresh concurrent control `C3g`, SAME retention criteria.  The first attempt (P1b) stays on record as a failed arm.

Addendum 4: the same contamination applies to every WS5 run made while other batches were running (P1b, P1s, P1f, C3e/C3d); P1b/P1s remain on record
(0 of 13 solved; mechanism documented in addendum 3 - the first-round overhead).  The verdict for the targeted-path family comes from the clean sequential
batch (arms `C3z`, `P2z`, seeds 0-9) described in `PREDECLARATION_WS4.md`'s addendum.

Addendum 5 (after the clean batch Z1): P2z solved 3 of 10 (control C3z 6 of 10) although the cap-free enumeration was reduced to 120 demands. The
recorded `round_sec` was still 27-42 s: it is dominated by the second LP solve (a full LP of this pool takes ~25 s), not by the enumeration.  Third and
last attempt `P3` = `LINER_PATH_TARGETED=30:3:0` - NO second LP: the first LP's support is kept, only paths of services already in that support are
priced (same duals) and added to the integer problem; the round costs the enumeration of 120 demands only.  Seeds 0-9, strictly sequential with a fresh
control `C3y`, same retention criteria; whatever the outcome this is the last attempt of this family in this campaign.
