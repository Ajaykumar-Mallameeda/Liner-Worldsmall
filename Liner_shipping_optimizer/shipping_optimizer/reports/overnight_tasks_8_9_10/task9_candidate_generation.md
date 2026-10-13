# Task 9 — demand-coherent multi-port closed-rotation generation

**Status: PASS.** 27 new unit/integration tests, orchestrator **342/342** with the generator on by default, 0 ledger
violations in all 90 controlled runs, and in a 5-seed paired experiment the weekly profit rises from a mean of
**$3.25 M to $5.96 M** (better on 5 of 5 seeds) and coverage from **8.5 % to 12.9 %**.

## 1. Where candidate quality was lost (traced before changing anything)

`RegionalAgent.process` → `ServiceGeneratorAgent.generate_services` → `RegionalAgent._filter_services` → (GA, regional MILP) →
`last_candidate_pool` → `reconcile` (union + de-duplication) → global MILP. The GA output is not what the global stage sees; it
sees the **filtered generator pool** of every region.

| Finding (measured on 15 regional problems, 5 seeds) | Consequence |
|---|---|
| Sections A–E: direct (top OD pairs, 2 ports), hub loops (hub + 5 spokes, fixed sizing targets), trunks (hub↔hub), feeders, and a **random** heuristic section (`CandidateServiceGenerator`, `random.random`, unseeded) | pool is 80 % two-port; hub loops are 6-port loops of the same ten hubs |
| 11,190 generated → 11,190 accepted; **no candidate is ever rejected** | feasibility screening exists but nothing exercises it: unprofitable routes are not filtered by evidence |
| Stand-alone profit at f=1: direct 6.2 / 516, heuristic 4.4 / 397, hub loops 0 / 120, trunks 0 / 108 → **10.6 of 1,140** | the pool offers the optimiser almost no consolidation service that pays for its vessels |
| `_filter_services` keeps a candidate only if `capacity × 0.5 × 150 USD > weekly hire of ONE vessel` (hard-coded revenue guess) and caps the rest by `capacity / (hire + 1)` | removes every Feeder_450 (450 × 75 = 33,750 < 35,000) irrespective of its economics; favours big ships irrespective of demand |
| the same rotation is proposed by several regions (19 % duplicates, de-duplicated later) | pool slots are spent on copies |
| class = nearest capacity to a standard size 500…16,000 TEU | quantisation: Panamax_1200 is never "nearest" (see Task 10) |

## 2. What was built — `src/services/demand_coherent.py`

For fixed inputs the generator is **deterministic** (no random draw anywhere; `random.seed` has no effect on it).

1. **Seeds.** The strongest directed OD opportunities of the region's own origins (`weekly_teu × (rate − per-TEU port charges)`),
   one undirected pair once, at most `seed_pairs = 80`.
2. **Growth.** From a 2-port seed, up to `max_ports = 5`: try each of the `neighbourhood = 12` ports with the strongest
   demand to the loop, at every insertion position, and keep the best — *only if* it strictly improves
   `(complementarity-weighted net revenue − full weekly cost) / vessels`. A port that does not pay for its vessel time is not
   added (`extra_port_does_not_pay_for_its_vessel_time`).
3. **Value of a rotation** (same model the optimiser and the ledger use): directed distances (a missing leg rejects the
   insertion — nothing invented), class speed/capacity/hire/fuel with the pinned fuel price, cycle = ceil(sailing + 24 h/port),
   vessels = ceil(cycle·f/7), **ride time per OD vs `TransitTime`** (sailing + one stay per intermediate port), leg loads scaled
   to `cap·f` on every leg, vessels within class inventory. Cargo already servable directly by the pool is worth 0.25.
4. **Class.** Exactly as the other sections choose it (nearest capacity to a demand-derived target, next-nearest if the
   rotation needs more vessels than the class owns) so Task 9 changes route *structure* only; Task 10 changes class choice.
5. **Selection under a budget** (`LINER_DEMAND_LOOP_BUDGET`, default **60 per regional problem**, `0` disables):
   rank by the complementarity-aware score; keep ≤ 34 % of the budget as *complementarity* rotations (stand-alone profit ≤ 0 but
   with uncovered ride-feasible demand) flagged `standalone_profitable = False`; reject duplicates of the pool and
   near-duplicates (Jaccard ≥ 0.8) with a reason.
6. **Integration.** Section F of `ServiceGeneratorAgent` (after E; existing sections untouched, so `budget = 0` reproduces the
   previous pool exactly). Candidates carry `origin_section`; the regional filter does not apply its crude margin guess or its
   cap to them (their own economics replace it), so enabling the generator can only **add** candidates. The regional splitter
   passes `global_demands` (a reference) so a loop is valued against the reverse and cross-region flows it carries.

Rejection reasons recorded per call (mean per regional problem, loops60): budget exhausted 131.9, near-duplicate 27.4, no
ride-feasible demand 18.1, no class within inventory 14.9, no uncovered demand and not profitable 10.1, extra port does not pay
9.7, duplicate of the pool 0.1.

## 3. Controlled experiment (`evidence/tools/pool_experiment.py`)
Same WorldSmall problem, KMeans split (`random_state = 42`), same production generator + regional filter + global stage
(`NetworkPlanner` = path MILP + independent ledger, single-threaded CBC, 120 s); only the generator toggles. The legacy
sections' randomness is seeded per region (`random.seed(100·seed + region)`), seeds 0–4. Replays are exact: seed 0 `old`
gives 5,616,781 in three separate runs.

| configuration | pool (unique) | 2 / 3 / 4 / 5 / 6+ ports | stand-alone profitable | profit USD/wk mean (sd) | min .. max | margin % | coverage % | services | vessels | MILP s | violations |
|---|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| **old** (budget 0) | 1,140 | 912 / 108 / 0 / 0 / 120 | 10.6 | **3.25 M** (1.88) | 0.43 .. 5.62 | 10.8 | **8.5** | 9.6 | 42 | 20 | 0 |
| loops30 | 1,222 | 912 / 134 / 23 / 33 / 120 | 55.6 | 3.93 M (0.29) | 3.56 .. 4.45 | 9.1 | 13.0 | 11.6 | 82 | 20 | 0 |
| loops45 | 1,252 | 912 / 150 / 31 / 39 / 120 | 71.2 | 4.83 M (0.65) | 3.88 .. 5.72 | 9.6 | 15.0 | 11.6 | 92 | 21 | 0 |
| **loops60 (default)** | 1,272 | 912 / 162 / 33 / 44 / 120 | 75.8 | **5.96 M** (0.53) | 5.08 .. 6.59 | 13.5 | **12.9** | 11.2 | 80 | 28 | 0 |
| loops90 | 1,302 | 912 / 178 / 40 / 52 / 120 | 75.8 | 5.85 M (0.64) | 4.99 .. 6.62 | 12.9 | 13.3 | 12.4 | 84 | 22 | 0 |
| loops120 | 1,332 | 912 / 191 / 50 / 59 / 120 | 75.8 | 4.86 M (0.82) | 3.46 .. 5.80 | 12.2 | 12.1 | 9.8 | 74 | 17 | 0 |

Paired weekly-profit difference vs `old` (same seed, USD M): **loops60 +0.97 / +0.99 / +3.42 / +5.97 / +2.20 (mean +2.71,
5/5 seeds)**; loops30 −1.65 / −1.45 / +1.54 / +4.02 / +0.93 (3/5); loops120 +0.18 … +4.94 (5/5, mean +1.61).
Per-seed values and class use: `evidence/comparisons/task9_candidate_generation_tables.md`.

* **Quality of what was added.** 50 % of the demand-loop candidates are stand-alone profitable (65 of 132) against 1.2 % of the
  direct and 1.1 % of the heuristic candidates; the 3/4/5-port candidates supply 68 of the 76 profitable ones.
* **Dose-response with a peak.** Profit rises with the budget up to 60–90 and falls at 120: more candidates make the production
  restriction heuristic worse again (the same effect `solver_findings.md` measured). 60 is the default.
* **Variance.** The legacy pool's run-to-run profit swings 0.43 → 5.62 M with the random heuristic section; the loop pool is
  0.5 M wide: the pool no longer depends on a lucky draw.
* **Exact optimum, not a heuristic accident** (`evidence/outputs/pool_experiment_task9_fullint_reference.json`, 280 s,
  unrestricted integer problem): seed 3 — legacy pool 1.40 M (not closed) vs loops60 **8.20 M, proven optimal in 164 s**;
  seed 0 — 5.79 M vs 7.54 M (both incumbents). The new pool contains better plans than the production strategy extracts
  (6.4 M); that gap is a solver-strategy limit, not addressed here.
* **End-to-end demand represented** (mean ODs of 1,764): with a direct path 1,188 → 1,201; without any admissible path
  181 → 171; transfer-only 395 → 392. Transit-time-infeasible ODs stay unserved and uncounted.
* **Ablation — slot competition.** With the legacy cap applied to the loops as well (so they evict legacy candidates),
  loops30 gives 4.06 M and loops15 3.40 M against 3.24 M (`task9_ablation_competing_slots_tables.md`): slightly better, not
  uniformly; the additive filter is the cleaner design (profit at loops30: 3.93 M vs 4.06 M — equal within the noise —
  but monotone in the budget and with the legacy pool intact).

## 4. Trade-offs, stated
* Vessels deployed 42 → 80 of 263 (more consolidation services; all within class inventory).
* MILP 20 → 28 s mean; pool +12 %.
* Margin on revenue 10.8 → 13.5 % (loops60); coverage still 12.9 % — 87 % of demand is unserved. This is a better
  *pool*, not a solved network.

## 5. Regional ownership of a shared service (found by the orchestrator gate, fixed at its cause — twice)
The first orchestrator run with the generator on (341/342) failed the existing assertion "[Europe] Services selected > 0":
loops are proposed by every region, de-duplication gave each to the first region (Asia), so Europe owned none. A later run
(Task-9-only configuration, 341/342) failed it again under the first fix: with a pure "largest carried cargo" rule Europe's
cargo (4,560 TEU, +$4.0 M "profit" because its services' costs sat in other regions) was served entirely on services owned by
Asia and the Americas; a third failure showed Europe had proposed none of the operated rotations. The assertion was **not** weakened.

The rule in `reconcile` is now **usage-based** (the regions whose own cargo rides a service are the ones that can be
charged for it), deterministic, in two phases:

1. *Representation*: every region that has cargo on the network is given, where possible, one service it uses — the region
   with the fewest unclaimed services to choose from goes first (ties: the larger cargo, then region order) and takes the
   unclaimed service on which its cargo is largest;
2. every other service goes to the region whose cargo uses it most; a tie prefers a region that proposed it, then region
   order; a service with no attributable cargo falls back to its first proposer.

A region that proposed none of the operated rotations (Europe in the failing run: small own demand, its loops were not
selected) is therefore still represented by a service its cargo rides. This changes the *convention* of the regional split
("service → proposing region" became "service → using region"). The product owner approved this on 2026-10-11 on the
condition that regional totals reconcile exactly to the network totals and no shared cost is counted twice (verified, final
report §11.3); it cannot change a network total.

Network totals cannot change (tested: Σ regions = ledger); only the split between regions does
(`tests/test_regional_ownership.py`, 8 tests, the last one reconciling the split line by line against the ledger). The regional split remains an accounting convention, not a measurement.

## 6. Acceptance tests (`tests/test_demand_coherent.py`, 27)
valid closed rotation (distinct ports, every leg and the return leg have a distance); cycle/vessels/cost equal a hand
recomputation; passes the production feasibility screen; served ≤ requested and ≤ cap per leg; missing distance never
substituted; transit-time-infeasible demand not counted; isolated port never added; budget respected / 0 disables;
identical inputs and independence from the global random state; rotations already in the pool not re-proposed; no duplicate
rotations; two-port pool untouched; complementarity flagged and capped; a generated loop is planned and verified by the
independent ledger (served ≤ demand, revenue = Σ teu·rate once); tampered loops (repeated port, missing return leg) rejected;
WorldSmall: new services feasible, ≤ budget, linked to actual demand, only *added* to the legacy pool, same seed → same pool,
a mixed pool plans with zero violations and no duplicate cargo or cost.
