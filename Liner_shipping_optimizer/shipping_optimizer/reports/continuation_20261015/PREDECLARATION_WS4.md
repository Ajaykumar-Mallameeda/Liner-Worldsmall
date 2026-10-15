# Predeclaration - Workstream 4: trans-Pacific / Atlantic trunk-lane family (written BEFORE the 20-seed runs)

Date: 2026-10-15. Code under test: tree `tree_lanes1` = commit `3bff834` source + opt-in `src/network/trunk_lanes.py`,
the optional restrictions of `trunk_candidates.augment_trunk_candidates` and the hook in `reconcile.py` (all default OFF).
Base of both arms = C3 (VUB, Local Search, trunks 12 x 10 ports diverse, support cap 105), CBC single thread 120 s,
`PYTHONHASHSEED=0`, WorldSmall only, input hashes as frozen (`ws1_provenance/C3_baseline_freeze.json`).

Arms (seeds 0-19, strictly sequential, arm order alternating with the seed parity):
* `C3c`  control: the C3 flags on `tree_lanes1` (lane flag unset; shows that flag-off = previous behaviour and gives a same-time control)
* `L1`   C3 flags + `LINER_TRUNK_LANES=all` (transpacific, atlantic) + `LINER_TRUNK_LANE_COUNT=3` (classes Post_panamax, Super_panamax)

Why a concurrent control: the drift check of the frozen C3 against `HEAD` gave seed 0 identical, seed 2 -1.9 M, seed 1 -11.4 M (CBC wall-clock
incumbent), so differences against hours-old runs are not trusted; the paired comparison is L1 vs C3c of the same seed.

Retention criteria (all must hold; otherwise the family stays opt-in, labelled rejected or inconclusive):
1. 20/20 solved and ledger-valid in both arms; 0 hard-constraint / transit / draft / fleet violations; independent checks pass.
2. mean paired profit difference L1 - C3c >= +0.5 M USD/week and L1 higher on >= 14 of 20 seeds.
3. no seed loses more than 3 M USD/week against its control.
4. mean coverage not lower than the control by more than 0.5 percentage points.
5. stage wall time <= 125 s and no `not_solved` / `invalid_plan` run in L1 that is solved in C3c.
Failed or adverse seeds are reported, none is removed. Gate 4 of the brief additionally requires that the benefit is not produced by
removing a cost or a constraint (the family only adds ordinary candidates).

Addendum (written before the clean re-run; the first lane batch is kept on record as CONTAMINATED): while the first lane batch ran, up to three
solver processes ran at the same time on the 16-thread / 16 GB machine while Windows servicing (TiWorker, ~6-7.5 GB) held most of the
memory and the system drive hit 0 bytes free twice.  The control arm itself returned `not_solved` on seeds 8-11 (it solved all 20 seeds in the
frozen runs), i.e. CBC's time to its first incumbent is load- and memory-sensitive.  Those results (`per_seed_L1_partial.csv`, `paired_L1_partial.json`)
are NOT used for the verdict.  The family is therefore re-run in ONE strictly sequential batch together with the targeted-path arm (`PREDECLARATION_WS5.md`):
arms `C3z` (control), `L1z` (lanes, as above), `P2z` (targeted paths, second attempt), seeds 0-9, order rotating with the seed, nothing else
running; then seeds 10-19 for `C3z` and `L1z`.  Retention criteria unchanged (criterion 1 now also counts a `not_solved` control as a failed seed
of BOTH arms' comparison: a seed counts only if both arms solved; the number of such seeds is reported).
