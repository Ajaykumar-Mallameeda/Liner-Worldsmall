# Task 10 — per-rotation vessel-class screening

**Status: PASS.** 35 new tests (+ the generator/filter integration tests), orchestrator **342/342**, 0 ledger violations in
all 90+ controlled runs. On the Task 9 pool the screening raises the mean weekly profit from **$5.95 M to $8.75 M**
(better on 5 of 5 seeds), coverage from 12.9 % to 20.0 %; against the original pool the combined effect is
**$3.30 M → $8.75 M**, coverage 8.8 % → 20.0 %. Offering more than one class per rotation, or every class, is *worse*, and the
screening on the legacy pool alone is neutral — both stated below.

## 1. What `map_capacity_to_vessel_class` and the nearest-capacity rule actually do

| Question | Finding |
|---|---|
| Who calls `map_capacity_to_vessel_class`? | **Nobody.** `regional_agent.py` and `service_generator_agent.py` import it; neither calls it. It is a compatibility function (returns the registered class nearest in capacity, raises if none), left in place |
| What picks a candidate's class? | `ServiceGeneratorAgent._emit` → `rank_vessel_classes(target, fleet)`: the registered class whose capacity is nearest to a *hard-coded "standard size"* (500 … 16,000 TEU) chosen per section; a further class only if the nearest one cannot carry one weekly departure within its inventory |
| Does that use the rotation's cycle, fuel, hire or the cargo? | Only through the inventory check. The same rotation gets different classes from different sections |

## 2. Why were two of the six classes never offered? (measured: 1,284 distinct rotations of the seed-0 pool, all six classes evaluated on all of them — `evidence/outputs/class_diagnostics_seed0.json`)

| class | capacity | inventory | legacy margin rule passes | feasible rotations | infeasible (needs more vessels than owned) | profitable stand-alone | of those removed by the legacy margin rule | legacy rule offers | screening k=1 picks |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| Feeder_450 | 450 | 24 | **no** | 1,273 | 11 | 8 | **8** | 25 | 24 |
| Feeder_800 | 800 | 29 | yes | 1,284 | 0 | 44 | 0 | 909 | 924 |
| Panamax_1200 | 1,200 | 68 | yes | 1,284 | 0 | 35 | 0 | 24 | 22 |
| Panamax_2400 | 2,400 | 74 | yes | 1,284 | 0 | 56 | 0 | 44 | 45 |
| Post_panamax | 4,200 | 58 | yes | 1,284 | 0 | 31 | 0 | 224 | 217 |
| Super_panamax | 7,500 | 10 | yes | 1,159 | 125 | 10 | 0 | 58 | 52 |

* **Feeder_450** is feasible on 1,273 rotations and stand-alone profitable on 8. It is absent because
  `RegionalAgent._filter_services` keeps a candidate only if `capacity × 0.5 × 150 USD > one vessel's weekly hire`:
  450 × 75 = 33,750 < 35,000. That is a hard-coded revenue guess, not feasibility and not measured economics.
* **Panamax_1200** is feasible everywhere and profitable on 35 rotations; the legacy rule never picks it because 1,200 TEU is
  never *nearest* to a standard size (1,000 ties with 800 and the smaller wins; 2,000 is nearer to 2,400). It is absent
  because of quantisation in the generator, not because it is infeasible or uneconomic.
* **Super_panamax** (10 vessels) is infeasible on 125 rotations (more than 10 vessels for one departure).
* All six classes are feasible on ≥ 1,159 of 1,284 rotations; only **95 rotations have any profitable class** and screening
  changes the class of **42** of them (3.3 % of the pool). Every other rotation keeps its legacy class.

## 3. What was built — `src/services/class_screening.py`

For one rotation, **every registered class** is evaluated (diagnostics) with the canonical service model — the same
`ServiceModel` the optimiser and the ledger use (hire, fuel at the pinned price, port calls, cycle, vessels, capacity, ride
times) — and only a configurable number of alternatives is offered:

1. **Feasibility** = the service model builds: class has vessels and valid speed/capacity, every directed leg has a distance,
   the rotation needs no more vessels than the class owns, a price resolves. Reasons are recorded per class.
2. **Economics** for the best weekly frequency `f ≤ ⌊7·inventory/cycle⌋`: capacity `cap·f` on every leg, cargo that meets
   its `TransitTime` along the ride, vessels `⌈cycle·f/7⌉`, `weekly_fixed_cost(f)`; stand-alone profit = served net revenue − that.
3. **Selection** (`k` alternatives, default **1**): among classes with a positive stand-alone profit keep the highest-profit
   class, then (k > 1) the highest profit-per-vessel class (a scarce fleet rewards productivity), then the next best. A rotation
   with **no profitable class keeps its legacy (nearest-capacity) class when feasible** — stand-alone loss is no evidence about
   which class suits a feeder/transfer role and "least loss" would always pick the cheapest, smallest ship. So the screen changes a
   class only where the economics give evidence (95 of 1,284 rotations).
4. **Per rotation, not per section.** The result is cached per rotation, so the same rotation proposed by several sections
   (with different sizing targets) gets the same alternatives and the configured maximum holds across the pool. (A test found
   the first version violating this: 4 classes for one rotation.)
5. **De-duplication** of (rotation, class) pairs; `class_fallbacks` keeps its meaning (nearest class could not carry the rotation).

Switches: `LINER_CLASS_SCREEN` = `k` (default 1), `0` = legacy assignment (pool identical to before — tested), `all` =
**diagnostic** enumeration of every feasible class without an economic screen.

## 4. Development record (what was tried and measured — kept because it changed the design)
| Version | Rule | Result | Verdict |
|---|---|---|---|
| A | no profitable class → the single *least-loss* class | the screener picked Feeder_450 for ~1,100 unprofitable rotations; the regional margin rule then deleted all of them, so the pool collapsed 1,270 → 398 and rotations vanished entirely (seed 0 profit was 10.7 M at 26.5 % coverage — a by-product of pruning; only seed 0 was run before the sweep was stopped, so it is a hint, not evidence) | rejected |
| B | no profitable class → legacy class | pool sane; but alternatives per rotation exceeded k (cache keyed by section target) | fixed by a test |
| C | per-rotation cache; screened classes exempt from the margin rule and the cap | mean 8.42 M | superseded |
| D (final) | as C without the exemption | mean **8.76 M** (≥ C on 5/5 seeds; ablation `+noexempt`) | **shipped** |

## 5. Controlled results (40 runs, final code; `evidence/comparisons/task10_class_screening_final_tables.md`)
Same WorldSmall problem, regional split, generator seeds 0–4, same filter, same global stage; only the generator/class
configuration changes.

| configuration | pool | stand-alone profitable | profit USD/wk mean (sd) | min .. max | margin % | coverage % | services | vessels | MILP s | violations |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| old (legacy pool, legacy classes) | 1,140 | 10.6 | 3.30 M (1.86) | 0.43 .. 5.62 | 10.7 | 8.8 | 10.2 | 44 | 20 | 0 |
| old + screening k=1 | 1,082 | 16.6 | 3.48 M (0.32) | 3.00 .. 3.96 | 9.8 | 10.6 | 15.8 | 76 | 63 | 0 |
| old + screening k=2 | 1,083 | 24.4 | 3.97 M (0.61) | 3.26 .. 4.72 | 9.9 | 11.8 | 15.8 | 82 | 53 | 0 |
| loops60 (Task 9) | 1,272 | 75.8 | 5.95 M (0.56) | 4.99 .. 6.59 | 13.5 | 12.9 | 11.4 | 80 | 27 | 0 |
| **loops60 + screening k=1 (default)** | 1,213 | 90.8 | **8.75 M** (0.47) | 8.28 .. 9.66 | 13.8 | **20.0** | 17.6 | 115 | 104 | 0 |
| loops60 + k=2 | 1,255 | 140.8 | 7.44 M (0.47) | 6.78 .. 8.15 | 12.8 | 17.7 | 14.8 | 104 | 99 | 0 |
| loops60 + k=3 | 1,276 | 164.0 | 6.44 M (0.34) | 6.05 .. 6.90 | 12.0 | 16.2 | 15.2 | 97 | 103 | 0 |
| loops60 + every feasible class (diagnostic) | 1,779 | 167.0 | 3.18 M (0.55) | 2.31 .. 3.91 | 11.8 | 8.6 | 8.2 | 62 | 24 | 0 |

Paired differences (same seed, USD M; positive = better), as asked, separating the two effects:

| effect | seed 0 | 1 | 2 | 3 | 4 | mean | better |
|---|---:|---:|---:|---:|---:|---:|---:|
| Task 9 pool vs original pool (both legacy classes) | +0.97 | +0.99 | +3.15 | +5.97 | +2.15 | **+2.65** | 5/5 |
| screening k=1 on the **original** pool | −2.62 | −1.68 | +0.86 | +3.20 | +1.12 | **+0.18** | 3/5 |
| screening k=1 on the **Task 9 pool** (vs loops60) | +3.07 | +2.69 | +2.52 | +2.16 | +3.55 | **+2.80** | 5/5 |
| both vs original | +4.04 | +3.68 | +5.68 | +8.13 | +5.69 | **+5.44** | 5/5 |

Findings, plainly:
* The class decision matters **only on a pool that contains profitable multi-port rotations**; on the legacy pool, where
  there are 10 profitable candidates, it is neutral (+0.18 M, 3/5 seeds, inside that pool's ±1.9 M seed noise) and merely reduces
  the variance.
* **More alternatives are worse**: k = 1 > 2 > 3 (8.75 > 7.44 > 6.44 M) and offering every feasible class falls *below the
  original pool* (3.18 M, 0/5 vs loops60). Same mechanism as in `solver_findings.md` §1: the production LP-guided restriction
  degrades as the pool is enlarged. So the "small, configurable set" is 1 by default and the code supports more.
* **Class use** (mean vessels deployed, k=1 vs original pool): Panamax_1200 0 → 37.8 of 68; Panamax_2400 12.4 → 33.6 of
  74; Post_panamax 22.0 → 20.8 of 58; Feeder_800 3.4 → 13.8 of 29; Super_panamax 6.0 → 9.2 of 10 (the scarce class is
  used almost fully). **Feeder_450 is deployed 0 in every configuration** — not because it was never offered (25 candidates in
  the pool) but because no plan finds it worth a vessel; the margin rule would have removed it anyway.
* **Cost of the gain**: vessels deployed 44 → 115 of 263; the global MILP 20 → ~100 s of its 120 s limit (several runs end at
  the limit with a feasible incumbent, status `feasible`, LP bound 44 M — optimality is not claimed).

## 6. End-to-end confirmation (full orchestrator incl. regional GA/MILP/coordinator, unseeded, three runs per setting)
| setting | weekly profit | margin | coverage | services | vessels | assertions |
|---|---|---|---|---|---|---|
| frozen baseline M0 | 2.67 M | 11.5 % | 6.5 % | 8 | 40 | 310/310 |
| legacy configuration on the new code (`BUDGET=0`, `SCREEN=0`) ×3 | 3.19 / 1.18 / 4.23 M | 11.4 / 4.5 / 11.7 % | 8.2 / 7.5 / 10.7 % | 10 / 8 / 13 | 36 / 39 / 50 | 342/342 each |
| **final default** (loops 60 + screening 1) ×3 | **8.99 / 10.93 / 8.32 M** | 13.9 / 16.1 / 14.0 % | 20.0 / 21.4 / 18.1 % | 16 / 19 / 14 | 107 / 119 / 97 | 342/342 each |
| legacy configuration, later code state (`LEGACY6_run1..3`) | 2.34 / 3.44 / 3.21 M | 8.7 / 12.0 / 11.5 % | 7.7 / 8.7 / 8.2 % | 8 / 10 / 10 | 38 / 36 / 36 | 342/342 each |
| **final default on the final code** (`FINAL7_default_run1..3`) | **9.02 / 9.11 / 9.03 M** | 14.2 / 13.9 / 11.8 % | 18.8 / 20.1 / 24.4 % | 15 / 17 / 22 | 109 / 113 / 143 | 342/342 each |

The lowest final-default run (8.32 M, earlier code state; 9.02 M on the final code) is above the highest legacy-configuration run (4.23 M).

## 7. Tests (`tests/test_class_screening.py`, 35) — mapped to the acceptance list
1 class selection from canonical data (hand-computed V/W economics: profit 498,183 vs 323,051) · 2 no unregistered or
unavailable class (inventory 0 → `vessel_class_has_no_vessels`; invalid speed → `invalid_vessel_speed`) · 3 frequency ceiling
`⌊7·inventory/cycle⌋` and vessels per class · 4 per-leg capacity `cap·f`, cycle time · 5 fuel and hire class-specific ·
6 a nominal capacity match never overrides feasibility or inventory · 7 missing/invalid class data fails with a reason, no fleet
is an error · 8 deterministic · 9 maximum alternatives respected (also across generator sections on WorldSmall) ·
10 the independent ledger confirms the chosen class and vessel counts and rejects unknown classes, classes with no vessels and
over-subscription · 11 all six registered classes are evaluated on WorldSmall while ≤ k are offered · plus: unprofitable
rotation keeps the legacy class, transit-time-infeasible cargo is not valued, `0` reproduces the legacy pool exactly,
the regional filter is not bypassed.

## 8. Limits and what to do next (not done here)
* Stand-alone profit ignores transfer cargo: a rotation that is only valuable as a feeder is not "promising" and keeps its legacy class.
* The crude margin rule in `_filter_services` still removes Feeder_450 whatever its economics; replacing it with the
  per-rotation economics is a separate decision (measured gain: none).
* The pool-size sensitivity (k, budget) is a property of the LP-guided restriction: recommended next task is the global-stage
  strategy (accept the unrestricted solve when it closes; economic pruning of rotations with no stand-alone and no
  complementarity value — version A's 398-candidate pool is a hint, unconfirmed on more seeds).
