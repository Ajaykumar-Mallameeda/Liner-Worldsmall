# Issue 6 - remaining assumptions (2026-10-13)  -  gate: PASS WITH BLOCKERS (assumptions exposed in every result; four need owner decisions)

Rule applied: no assumption was tuned to improve profit or coverage; no cost was invented. Where the primary source is unavailable the
assumption stays as is and is now **declared in the output**.

## 1. Code: assumptions are propagated to every result
`src/network/assumption_register.py` + `reconcile.py`: `assumptions.assumption_register` (13 entries: id, value in force, status, source,
what it affects). Statuses: SOURCED_SECONDARY / PROVISIONAL / UNVERIFIED / NOT_MODELLED. `tests/test_assumption_register.py` (3 tests);
related suites 124 passed. Behaviour of the optimiser is unchanged.

## 2. One assumption at a time (corrected units, S3 profile = VUB + LS, seeds 0-4, same-seed concurrent groups, 120 s; scratch tree copies
differ from the production tree in exactly one value; `per_seed_scenarios.csv`)
| assumption changed | profit M/wk (ref 39.13) | paired delta | seeds higher | coverage pp | status of the assumption |
|---|---:|---:|---:|---:|---|
| transit file: revised upstream `TransitTime` (105 ODs, +10 d mean) | 43.17 | **+4.04** | 5/5 | +3.8 | PROVISIONAL (authors recommend the revised file) |
| transfer wait 1.75 d (ref 3.5) | 42.93 | +3.80 | 5/5 | +2.8 | PROVISIONAL (convention, no source) |
| transfer wait 7.0 d | 32.06 | -7.08 | 0/5 | -5.6 | |
| port stay 12 h (ref 24 h) | 40.66 | +1.53 | 4/5 | +2.4 | SOURCED_SECONDARY (benchmark page: 24 h) |
| port stay 48 h | 31.05 | -8.08 | 0/5 | -6.2 | |
| port-cost columns read per TEU instead of per FFE | 22.67 | **-16.46** | 0/5 | -7.0 | PROVISIONAL (loader contract) |
All 35 runs: solved, ledger valid, 0 hard violations, 0 transit violations. In the old units the revised file showed no measurable effect;
under correct capacity it is worth +4 M and +3.8 pp - the earlier "no effect" conclusion does not carry over.

## 3. Findings by assumption
| item | evidence | action |
|---|---|---|
| Revised vs unrevised transit file | the revision loosens 104 of 105 differing limits; +4.0 M, 5/5; adopting it means replacing a canonical input | **owner decision (D-04)**; not adopted (canonical data is not rewritten); status exposed |
| Transfer dwell / port stay | dwell 3.5 d is a convention; +-2x moves profit -7.1/+3.8 M; port stay from the benchmark page | kept; exposed; owner to supply the operating convention (D-06) |
| Sub-weekly frequency | no source; needs a model change (fortnightly service) | **blocked: owner decision (D-07)**; not implemented |
| **Canal fees** | fees exist in `fleet_data.csv` (Suez all classes; Panama blank for Post/Super-panamax) but the model charges **none**. Exposure of recorded S3 plans: 13-15 of 28-35 services transit Suez, 3-5 Panama; **7.4-8.2 M USD/wk = 19-21 % of reported profit** if the fee is per transit per departure; ~65-75 M/wk if read as per assigned vessel (paper Eq. 35 literally) - semantics undetermined | **P0-class finding; blocked: owner decision (D-08)**: whether/how to charge. Not charged here (semantics unverified; adding a guessed cost would be inventing one). Exposed as NOT_MODELLED in the register; `canal_exposure.json` |
| Fuel price provenance | 600 USD/t is the benchmark's value; regional snapshot covers 5 of 47 ports, no licence; +-25 % fuel is in the register sensitivities (Issue 5) | kept; exposed |
| Fuel grade / fuel systems | no data in the fleet file | UNVERIFIED, exposed |
| Cost units (per FFE) | -16.5 M if the columns were per TEU - the largest single swing after capacity | PROVISIONAL, exposed; owner/data custodian to confirm (D-01 family) |
| TransitTime scope (port time included?) | upstream rule reproduces the unit, not the scope | UNVERIFIED, exposed |

## 4. Consequence for the headline numbers
Reported profits (24.6 M default, ~35-39 M with VUB + LS) are conditional on: capacity unit (secondary source), per-FFE cost reading
(+-16 M), dwell (+4/-7 M), port stay (+2/-8 M), transit file (+4 M) and **omit canal fees (-7.4 .. -8.2 M if per departure)**. The ranking of
configurations (VUB/LS vs default) was established under a fixed assumption set; it was not re-tested under each scenario here.

## 5. Owner decisions raised
D-04 transit file; D-06 dwell/port-stay convention; D-07 sub-weekly frequency; **D-08 canal-fee semantics and charging**; confirmation of cost units.

## Rollback
`git revert` the commit (adds a register module, one line in `reconcile.py`, tests, reports). Scenario trees were scratch copies (not tracked).
