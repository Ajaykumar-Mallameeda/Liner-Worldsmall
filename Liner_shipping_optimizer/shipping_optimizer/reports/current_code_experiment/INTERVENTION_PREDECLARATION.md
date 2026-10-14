# One controlled coverage intervention - predeclared 2026-10-14 (before any run of it)

**Bottleneck evidence (current code, 20 seeds, arm B = VUB + Local Search, `summary_A_B.md`)**: of the 66 % of demand left unserved,
41.8 % of total demand is attributed to `fleet_inventory_exhausted` (small and medium classes fully used while 58 Post_panamax stay idle),
8.9 % `not_economic_to_open_service`, 7.9 % `no_time_feasible_service_in_pool`, 3.8 % capacity, 3.4 % physically unattainable.
Earlier measurements (Issue 4, pre-decision-phase model): per-OD path cap and its ranking were the largest model restriction (LP with the cap lifted
reached 50.6 % against 31 % for the plan); cost-aware ranking was unusable on plain CBC (9/10 `not_solved`) but gave +1.4 M and +4.7 pp with VUB + LS on 10 seeds.

**Intervention (exactly one change):** `LINER_PATH_SELECTION=cost_aware` on top of arm B (the per-OD retained path set of 10 is ranked by journey
cost instead of by transit time). Same tree (`49ecd92` economics), same inputs, CBC single thread, 120 s, `PYTHONHASHSEED=0`, seeds 0-19, run
sequentially, arm order alternating with the seed parity. Comparison: arm B of the batch in `per_seed_A_B.csv`, same seeds (paired).

**Hypothesis:** fastest-first ranking discards cheaper journeys from the capped set; cost-aware ranking raises coverage without lowering profit.

**Retention criteria (all must hold; otherwise rejected):**
1. 20/20 runs solved, ledger-valid, 0 hard-constraint violations, 0 transit violations; `independent_check.py` passes every plan.
2. Paired mean profit difference > 0 and profit higher on at least 14 of 20 seeds.
3. Paired mean coverage difference >= +1.0 percentage point.
4. No seed loses more than 3.0 M USD/week against its B pair.
5. Vessels per class never exceed the inventory (independent check).
Retained means "stays an experimental flag with documented evidence"; it is never made a default here.

Not done on purpose: no global coverage floor, no forced utilisation, no sub-weekly frequency, no change of any assumption.
