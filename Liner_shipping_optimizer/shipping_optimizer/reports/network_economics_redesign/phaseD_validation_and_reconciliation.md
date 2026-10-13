# Phase D — independent validation and ledger reconciliation

Goal: make the reported economics checkable by something that does not share the optimiser's code, and show that the
optimiser's own objective, the ledger and the test's recomputation say the same thing.

## 1. Three independent computations of the same plan

| Layer | Code | Role |
|---|---|---|
| network MILP objective | `src/network/network_milp.py` (PuLP/CBC) | chooses departures, vessels, flows |
| ledger | `src/network/ledger.py` — recomputes from raw primitives (fleet, distance matrix, port costs, demand); returns structured violations | the number that is reported |
| test recomputation | `tests/test_orchestrator.py::_recompute_network` — loader data only, no `src.network` import | the number the test trusts |

Run U6 (the verified run of record), USD per week:

| item | reported (ledger) | recomputed (test) | MILP objective |
|---|---|---|---|
| revenue | 29,209,812.38 | 29,209,812.38 | — |
| vessel hire | 9,212,000.00 | 9,212,000.00 | — |
| fuel | 11,363,506.70 | 11,363,506.70 | — |
| port calls (fixed) | 159,444 | 159,444 | — |
| handling | 4,267,880 | 4,267,880 | — |
| transshipment | 635,194 | 635,194 | — |
| per-TEU port variable | 325,889 | 325,889 | — |
| **operating profit** | **3,245,898.68** | **3,245,898.68** | 3,245,898.68 (Δ = −4.7e-10) |

Also recomputed and equal: vessels per class (Feeder_800 7, Panamax_2400 5, Post_panamax 22, Super_panamax 7 — all ≤ inventory),
served TEU 24,220, total demand 276,446.8, per-service cycle time / vessels / frequency, regional sums of profit and cost,
`summary_metrics.weekly_profit`.

## 2. The validator can fail (sensitivity)
Section N.7 feeds `_recompute_network` two deliberately broken copies of the real plan and requires rejection:
* +10,000,000 TEU on one flow → `demand_overserved` / `leg_capacity_exceeded`;
* +1,000 departures/week on one service → `fleet_exceeded`.
Both are flagged in every run. `tests/test_network_economics.py::TestLedgerCatchesInvalidPlans` does the same for the ledger
on hand-built plans (leg capacity, fleet, over-service, transit time, inactive service, invalid path/frequency/class).

## 3. What the numbers mean (and do not)
* **Verified** means: capacity, fleet, demand conservation, transit time and the accounting identity hold, and MILP = ledger.
  It does **not** mean optimal: status is `feasible`, LP bound $47.9 M/week (loose because departures are integers).
* **Conditional** on the stated assumptions: capacity unit provisional (TEU), 24 h port stay, 48 h + 3.5 d transfer dwell,
  $600/t bunkers, `TransitTime` in days. All are emitted in `network_ledger.assumptions`.
* Regional profits are an accounting partition: negative regional profit (U6: Americas −$4.6 M) can coexist with a positive
  network because cargo is attributed to its origin region and a service to the region that proposed it. They sum exactly to
  the network.

## 4. Variability (the pipeline is unseeded; GA and generator sample randomly)
| run | best-iteration profit | iteration profits (0 / 1 / 2) | coverage | services |
|---|---|---|---|---|
| U3 | $5.10 M | 2.42 / 3.12 / 5.10 M | 10.1 % | 11 |
| U5 | $4.35 M | — | 9.8 % | 10 |
| U6 | $3.25 M | 1.54 / 3.25 / 0.73 M | 8.8 % | 11 |
| U7 (final code) | $3.56 M | 1.05 / 3.56 / 1.42 M | 9.1 % | 11 |
| baseline S0 (legacy accounting) | −$303 M | — | "86 %" | 287 |

The spread (0.7 – 5.1 M) comes from which regional candidate pools the random generators/GAs produce, not from the
accounting: for identical candidates the global stage is reproducible (replay: 4,212,367 on every replay of the captured
inputs, `evidence/tools/replay_global.py`).

## 5. Reproduce
```
python evidence/tools/snapshot_tree.py <project> <fresh_dir> <manifest.json>
python -m pytest tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider   # from <fresh_dir>
python -m pytest tests --ignore=tests/test_orchestrator.py -q -p no:cacheprovider
python evidence/tools/compare_suites.py S0clean=<baseline.xml> NEW=<new.xml>
```
