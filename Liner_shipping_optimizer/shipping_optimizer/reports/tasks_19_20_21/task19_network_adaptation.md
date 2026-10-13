# Task 19 — network-adaptive routing strategy and vessel utilisation

**Date:** 2026-10-12 · WorldSmall only · numbers are read from `evidence/outputs/*.json` / `evidence/runs/*.pipeline_output.json`
(`results_matrix.md` lists every run). Production solver CBC 120 s unless stated.

## 1. Verdict

| Item | Result |
|---|---|
| Hard-coded strategy ratios | The 60 / 15 / 20 / 5 `archetype_mix` is a **generation hint**: only `direct_ratio` acts (it scales the *number of direct two-port candidates*, floor 200, capped by the adaptive target and by the region's OD count); `hub_loop_ratio` and `feeder_ratio` are computed and never read; `trunk_ratio` is only logged. No ratio constrains the final solution. The final mix of direct / feeder / hub / multi-hop cargo **emerges** from the global MILP (`architecture_audit.md` §2) and is now reported as an outcome |
| Network signals | Computed from canonical inputs only and recorded with every result (`path_model.signals`): demand by number of valid paths, demand with a direct path / without any / on a single path, concentration (top-10 / top-100 share, Herfindahl), port connectivity, transfer concentration, path budgets. Drive: the per-OD path budget (adaptive mode), the multi-hop policy, the reuse penalty, the unserved-demand reasons |
| Adaptive budget (value-weighted path allocation) | Implemented and measured: raises coverage (+3 … +8 pp) but **destabilises** the production solve (10 seeds: 0.61 M vs 11.1 M with re-routing alone) and HiGHS (−1.45 M, 0/5). **Opt-in, not adopted** |
| Objective hierarchy | Production stays profit-first under hard constraints and the approved safeguards (verified profit ≥ 0; 15 % advisory, not a gate; no cost budget exists). Opt-in **epsilon constraint on coverage** (`LINER_GLOBAL_MIN_COVERAGE`) and an experimental **lexicographic** staging (harness only). Frontier in §5 |
| Strategy-level reporting | `network_ledger.strategy_report`: per strategy flows / TEU / coverage contribution / revenue / charges / allocated service cost / profit contribution / transfers per TEU / transit distribution and slack; utilisation at leg / service / fleet / network level; unserved demand by principal reason; reconciled against the ledger inside the report **and** against the test's independent recomputation (§N.9) |
| Utilisation gain, correctly attributed | Better use of services already selected (flow re-routing): network load factor **0.603 → 0.632** (10 paired seeds, M7), legs ≥ 95 % full 22 → 28 of 72 (M5 `F1`); additional demand through added services and through transshipment are reported separately in §4 |

## 2. What was audited (before any change)

See `architecture_audit.md` §2.1 / §3 / §4. In short: which values *constrain* the model are the per-OD path cap
(10 fastest), the regional cap, the class-screening rule and the demand-loop budget; which are *reporting* are the strategy
text, the unused ratios and the `direct / transfer` label of a flow.  The global optimiser **can** evaluate alternatives
that the path cap discarded only if a retained path uses them — the flow re-optimisation (Task 20) is what gives it
those alternatives without enlarging the MILP.

## 3. Adaptive decision mechanism (what is derived from what)

| Decision | Signal(s) | Rule | Default |
|---|---|---|---|
| paths retained per OD (adaptive mode) | OD opportunity = weekly TEU × (revenue per TEU − cheapest per-TEU charges); number of valid paths | the baseline's total number of retained paths is redistributed ∝ opportunity^0.5, bounds 3 … 20 | off |
| two-transfer enumeration | number of valid direct / one-transfer paths of the OD | enumerated only if fewer than `LINER_PATH_MULTI_HOP_MIN_ALT` (1): ODs with none | on |
| re-routing columns | operated services | every valid path whose services are all operated | on |
| class of a rotation | cargo that each class can carry inside the transit limits (canonical service model) | a class that carries nothing is not kept as "legacy" when another can | on |
| repair | plan profit vs the approved floor 0 | switch off the worst-attributed services until the floor is met | on (acts only below 0) |

Missing signals are never replaced by zero economics: a candidate that cannot be evaluated is ranked last and counted
(`economics_unavailable`), an OD without a port record is skipped and counted.

## 4. Strategy mix as an outcome (CBC 120 s, means of 10 seeds, batch M5; `evidence/comparisons/strategy_tables_M5.md`)

| | B0 (frozen) | re-routing + ≤ 2 transfers (`F1`) | + time-feasible class (`F1T`) |
|---|---:|---:|---:|
| direct share of served TEU | 84.1 % | 78.9 % | 74.8 % |
| feeder (capacity-tier change at one transfer) | 12.8 % | 15.8 % | 18.1 % |
| hub-and-spoke (same tier) | 3.2 % | 3.7 % | 4.8 % |
| multi-hop (two transfers) | 0.0 % | 1.5 % | 2.4 % |
| served TEU per week | 58,307 | 62,487 | 70,402 |
| coverage % | 21.1 | 22.6 | 25.5 |
| profit M/wk (sd) | 8.01 (4.62) | 11.11 (1.37) | 11.14 (1.49) |
| network load factor | 0.592 | 0.667 | 0.628 |
| vessels used (of 263) | 131 | 131 | 147 |
| profit contribution of feeder / hub / multi-hop cargo, M/wk | 3.4 / 0.8 / 0.0 | 3.7 / 0.8 / 0.1 | 5.2 / 1.5 / 0.6 |
| unserved: not economic to open a service | 60.7 % | 58.9 % | 49.4 % |
| unserved: class inventory exhausted | 7.8 % | 7.4 % | 15.3 % |
| unserved: transit limit below the sailing time (not servable) | 3.4 % | 3.4 % | 3.4 % |

* Additional demand per incremental vessel (`F1T` vs `F1`): +7,915 TEU/wk for +16 vessels = **495 TEU per added
  vessel** (the network average is 481); additional profit per added TEU ≈ 0 (profit +0.03 M for +7.9 k TEU): the
  added cargo carries its own cost (cost +8.7 M/wk) and is ≈ margin-neutral.
* **Apparent utilisation gains caused by dropping demand:** none — the re-routing LP is constrained to serve at least
  the incumbent's cargo, so the load-factor gain of `F1` over B0 is cargo *added* on paid-for capacity (+4.2 k TEU, +1.5 pp).
  The load factor of `F1T` is lower than `F1`'s because it opens services for new cargo (147 vs 131 vessels); that is a
  coverage-for-utilisation exchange and is reported as such.
* Ledger identity of the report: Σ strategies' profit − idle-capacity cost = ledger profit, to the cent, in every run
  (`strategy_report.reconciliation.all`, asserted in §N.9 of the orchestrator test against an independent recomputation).
* Quality: 0 transit-limit violations; multi-hop mean transit 35 – 37 d (p90 41 – 42 d) with ≥ 0.4 d minimum slack;
  transfer dwell = 48 h + 3.5 d per transfer (assumption, stated in the output).

## 5. Coverage–profit frontier (experimental strategies; production solve otherwise)

Epsilon constraint (profit-max s.t. served TEU ≥ x × demand) and lexicographic staging (profit-max, then max served
TEU s.t. profit ≥ (1 − ε) × stage 1) on the re-routing configuration `R`, CBC 120 s.

| strategy | seeds | profit M/wk | coverage % | note |
|---|---|---:|---:|---|
| profit-first (production) | 0 – 2 | 11.35 | 20.6 | `FRprod` |
| coverage ≥ 25 % | 0 – 2 | 11.19 | 26.8 | −0.16 M for +6.2 pp |
| coverage ≥ 30 % | 0, 2 (seed 1 no result) | 2.10 | 31.6 | unstable: 7.08 and −2.87 M |
| coverage ≥ 35 % | 0 – 2 | — | — | no usable result in 120 s |
| lexicographic ε = 0 / 5 / 10 % | 0 – 2 | 6.99 | 21.0 | stage 2 never improved on stage 1 (60 s each); the stage-1 half-budget incumbent of seed 0 was −1.9 M |

On the **accepted default configuration** (ten seeds, batch M10 vs M7, same pools, CBC 120 s,
`LINER_GLOBAL_MIN_COVERAGE=0.25`, re-routing and repair still applied afterwards):

| | profit M/wk | coverage % | margin % | services | vessels |
|---|---:|---:|---:|---:|---:|
| default, profit-first | 11.52 (1.20) | 25.3 | 14.4 | 27.8 | 148 |
| coverage floor 25 % | 9.96 (2.00) | 27.4 | 11.3 | 31.5 | 171 |
| paired difference | **−1.55 M** (1/10 seeds better; sd 2.05) | **+2.09 pp** (8/10 higher) | | | |
| seeds where the floor binds (default coverage < 25 %, n = 5) | −1.50 M | +4.14 pp | | | |

Price of coverage on these pools: **≈ 0.36 M USD/week per percentage point** where the floor binds (single seeds range from
−0.4 M to −6.1 M: seed 1 falls from 11.57 to 5.45 M).  Every run is `feasible`, ledger-verified, 0 violations.

Reading: a coverage floor of 25 % costs little on these pools under the production solver, a floor of 30 % or more is not
reliably attainable in the 120 s budget (the MILP finds no good integer plan), and lexicographic staging does not
work within the budget.  The floor is a **policy parameter** (owner decision), not an approved bound: no default is set.

## 6. Limits

* The adaptive budget and the frontier were measured on a single dataset and generator; CBC at 120 s is load sensitive
  (batches compared only within a batch).
* The strategy labels `feeder` / `hub_and_spoke` are descriptive conventions (capacity tier of the two services), not
  constraints; owners may prefer another definition (`remaining_tasks.md` B-5).
* Utilisation is in the model's capacity unit (`Capacity FFE` read as TEU, provisional).
