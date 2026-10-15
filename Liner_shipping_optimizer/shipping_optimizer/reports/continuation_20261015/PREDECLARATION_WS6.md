# Predeclaration - Workstream 6: network marginal-value screening study (written BEFORE the runs)

Question: do the LP duals of the current pool rank previously rejected rotations (grown by the trunk / lane generators and discarded for a
non-positive STAND-ALONE profit) better than the stand-alone profit does, measured against the ACTUAL increment of the real model?
Tool: `src/network/dual_screen.py` (dual-priced restricted LP per candidate, direct and one-transfer paths through operated services) and the
hook `T_STUDY=dual` of `tools/study_hooks.py`; the production pool and plan of the run are not changed (post-solve study).
Seeds 0-2 (cost: 15 actual LP re-solves of ~25 s per seed), C3 flags, CBC 120 s, nothing else running.
Per seed: all distinct rejected rotations are dual-priced; 5 top by dual value, 5 top by stand-alone profit (the existing rule's best of the
rejected) and 5 random ones are evaluated with the ACTUAL LP bound of pool + candidate (one at a time).
Reported: Spearman rank correlation of the dual price with the actual LP increment (and of the stand-alone profit), share of rejected rotations with a
positive actual increment, the actual increment of each selection.  Gate (Gate 6 of the brief): the existing screening rule stays unless the dual
ranking selects rotations with a clearly larger actual increment AND the plan-level benefit can be shown in the real MILP; this study alone can only
justify a follow-up arm, not a change.  An LP increment is a bound-side estimate and is never reported as integer-plan profit.
