# Issue 5 - fleet utilisation, service selection and executive opportunity register (2026-10-13)  -  gate: PASS

Code: `src/network/opportunities.py` (new, read-only analysis; **no decision of the optimiser or any default changed**),
`tests/test_opportunities.py` (4 tests, pass). Evidence: `outputs/register_seed{0,1,2}_s3.json`, `register_tables.md`
(plans: the `LINER_MILP_VUB=1 + LINER_LOCAL_SEARCH=1` arm of `../issue4_coverage/int`, seeds 0-2; pool rebuilt with the same seed).

## Method (global marginal economics, as specified)
Operated service s: marginal = P(F) - P(F without s), P = routed margin over **all** valid time-feasible paths (LP, capacities `capacity x f`)
minus fixed costs - the model's own accounting; it reproduces the ledger profit of the plan exactly (seed 0: 40.99 M).
Alternative c: marginal = max over f in {1, 2} of P(F + c) - P(F), including the hire of any vessels it needs.
Operational status: FEASIBLE if its vessels fit the idle inventory; CONDITIONALLY_FEASIBLE with the exact condition (vessels to add or charter);
INFEASIBLE with the model's rejection reasons; UNKNOWN if a price is missing. Commercial status: sign of the marginal, UNCERTAIN when the sign
changes under fuel +-25 % or the capacity unit read at half. The register is separate from the final operational gate: nothing conditional or
negative is represented as an executable schedule.

## What it shows (3 seeds, S3 plans)
| | seed 0 | seed 1 | seed 2 |
|---|---:|---:|---:|
| network profit M USD/wk / services | 41.0 / 30 | see json | see json |
| operated services with negative network marginal | **0** | **0** | **0** |
| operated services with negative *stand-alone* profit but positive network marginal | **12** | **18** | **10** |
| operated services acting as connectors (>30 % of flow transfers) | 26 of 30 | - | - |
| idle vessels (Post_panamax / Super_panamax / Panamax_2400) | 48 / 9 / 25 | 58 / 9 / 7 | 48 / 10 / 19 |
| alternatives evaluated / with positive marginal | 150 / 24 | 150 / 24 | 150 / 24 |
| top-40 opportunities: conditionally feasible | 40 | 39 | 39 |

1. **Every operated service pays its way in the network** (0 negative marginals), yet 10-18 of ~30 would be rejected by a stand-alone
   profitability test (stand-alone down to -472 k USD/wk): they are feeders or hub connectors that unlock cargo for other services. This is the
   behaviour the decision model requires; no stand-alone threshold is applied by the optimiser at the global stage.
2. **The binding inventory is the small and medium classes** (Feeder_450 and Feeder_800 fully used, Panamax_1200 nearly) **while 48-58
   Post_panamax and 9-10 Super_panamax vessels stay idle.** Idle large vessels are not forced into loss-making service: no alternative that
   uses them appears among the 40 best marginals (alternatives are small/medium classes). Utilisation of the fleet is therefore 83 % of
   vessels and a leg load factor of ~0.6; raising it needs rotations on which a large vessel earns more than it costs (a candidate-design
   question, evidence in Issue 4: class inventory is binding, path ranking is the large lever).
3. **Executive opportunities** (top rows, seed 0): `asia_svc_524` AUBNE-NZAKL-MYTPP-HKHKG Panamax_1200, +0.85 M USD/wk, needs 6 vessels (2 idle,
   **4 to add**), POSITIVE under every sensitivity; `americas_svc_456` Feeder_800, +0.80 M, needs 11 vessels (none idle). They are
   CONDITIONALLY_FEASIBLE: conditions are explicit, hire is already in the margin. Items whose sign flips under +-25 % fuel or half capacity are
   UNCERTAIN (22-29 of 40). A handful are FEASIBLE but NEGATIVE_MARGIN - listed so that they are not mistaken for opportunities.
4. Full tables with load factor, frequency, vessels, standalone/network margin, enabled TEU and sensitivities: `register_tables.md`.

## Limits
* Marginals use a fixed rest-of-network (one service changed at a time); combinations (two new services sharing a hub) are not evaluated.
* Only the 150 alternatives with the highest cheap potential score are evaluated (150 of ~1,200); the top-40 are reported.
* LP-based (fractional cargo, integer frequencies/vessels as given); no solver time limit effects (each LP < 2 s).
* Sensitivity scenarios are the stated ones only; bunker price and the capacity unit remain provisional (A3/A6).

## Rollback
New module and test file only; delete or `git revert` the commit. Pipeline behaviour is unchanged.
