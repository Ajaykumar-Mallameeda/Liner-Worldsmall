# Solver and candidate-pool findings (measured, controlled)

Question asked before touching the solver: *is the low coverage / modest profit a defect of the optimiser, or a property of the
candidate pool?* Method: capture the exact inputs of the global stage from one real pipeline run (3 iterations, 1,082 – 1,097
candidates, `evidence/tools/capture_global_inputs.py`) and replay them under different strategies
(`replay_global.py`). Same demand, same fleet, same candidates; only the strategy changes. Single-threaded CBC.

## 1. Strategy comparison on identical inputs (call 2 of capture U4)
| strategy | time | profit/wk | services | vessels | coverage |
|---|---|---|---|---|---|
| **production** — LP relaxation → restrict to LP-used services (430 of 1,081) → integer solve | 16 s | **$4.21 M** | 11 | 42 | 10.1 % |
| full integer problem, all 1,081 services, 280 s limit | 278 s | $4.12 M | 17 | 80 | 14.5 % |
| every rotation offered in all 6 classes (3,831 modelled), same restriction | 9 s | $1.82 M | 5 | 33 | 6.7 % |
| relax-and-fix dive (round up top-used fractional services) | 2 s | **−$26.9 M** (169 vessels) | 34 | 169 | — |

Reading: the production strategy is as good as a 17×-longer unrestricted search on this pool. The LP bound ($48.6 M) is not a
target — the LP uses 430 services at tiny fractional departures, which integrality (whole weekly departures, whole vessels)
makes unreachable. The dive was implemented, measured, and **rejected**: committing the most-used fractional services exhausts
the class inventories and yields a loss; production code was restored (`legacy_tests/network_milp.py.with_dive_rejected.txt`
preserves it). An all-classes pool made the *restriction* worse (a superset gave a worse answer), so naive pool enlargement is not
a fix either.

## 2. The pool is the limit
Stand-alone profit at f = 1 (own capacity, direct cargo only, LP per service, `standalone_profit.py`):

* **12 of 1,082** candidates have positive stand-alone profit (8 two-port, 4 three-port); their profits sum to $2.7 M using
  82 vessels with overlap un-netted. The global plan ($4.2 M) beats that only through transshipment (71 % of served TEU).
* composition: 873 two-port, 90 three-port, 119 six-port rotations; classes Post_panamax 478, Feeder_800 458, Super_panamax 128,
  Panamax_2400 18, **Feeder_450 0, Panamax_1200 0** (the generator maps demand to legacy "standard sizes" 500…16,000 TEU, which
  select only 4 of the 6 real classes).
* six-port hub loops serve a median of 8 ride-feasible OD pairs (≈1,556 TEU/week of 4,200 TEU per leg).
* paths: 809,217 – 819,158 paths per build are dropped by the transit-time limit; 171 of 1,764 ODs have no admissible path.

Fleet cost structure (USD per 1,000 TEU-nm at design speed, sea): Super_panamax 42.9, Post_panamax 50.7, Panamax_2400 60.2,
Panamax_1200 82.0, Feeder_800 82.7, Feeder_450 125.6 — bigger is cheaper per TEU, but average OD demand is 157 TEU/week, so
profit requires consolidation (multi-port loops, hubs), which the pool provides poorly.

## 3. `TransitTime` unit evidence
limit ÷ direct sailing days (fastest class): percentiles 0/5/25/50/75/95 = 0.12 / 1.23 / 1.58 / **1.88** / 2.33 / 3.78. Read as
days, limits sit at roughly twice direct sailing time (a normal liner allowance). As hours the median ratio would be 0.08
(impossible), as weeks 13.2 (vacuous). 2.3 % of ODs (3.4 % of TEU) are shorter than direct sailing time and cannot be served in time.

## 4. What would raise the ceiling (not done — each needs its own controlled comparison)
| Lever | Why it should matter | Risk |
|---|---|---|
| demand-coherent multi-port loop generation (seed on strong OD pairs, insert ports that add ride-feasible cargo per day) | pool has few profitable consolidation services | generator is Tier-1; must not regress candidate-quality tests |
| class screening per rotation (offer the 2 best classes by stand-alone estimate, not the nearest legacy size) | two classes (92 of 263 vessels) are never offered | pool growth hurt the LP restriction (§1) — needs the screening, not "all classes" |
| two-transfer paths (feeder → trunk → feeder) | hub-and-spoke between regions needs 3 segments; model allows 2 | path count; dwell 5.5 d each consumes transit allowance |
| route-level GA operators (insert/delete/swap port) | ServiceGA is a subset GA over a fixed pool | new algorithmic surface |

Tooling for those experiments is in `evidence/tools/` and reproduces the numbers above.
