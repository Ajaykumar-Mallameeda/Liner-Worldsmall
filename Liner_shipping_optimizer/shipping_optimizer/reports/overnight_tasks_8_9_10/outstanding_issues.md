# Outstanding issues (Tasks 8A · 8B · 9 · 10)

Classified as: **CODE** (defect in the repository), **MODEL** (assumption the numbers depend on), **DATA** (source-data gap),
**SOLVER** (limitation of the optimisation method), **DEFERRED** (deliberately not done). No failed gate is hidden.

## Failed or partially met gates
| # | Item | Class | State |
|---|---|---|---|
| G1 | Task 8B regional pricing is not shown to improve profit and has no licensed, multi-port data | DATA | PARTIAL by design: interface, snapshot format, validation, per-service resolution, ledger verification and tests are complete; only 5 of 47 ports have a public observation; the default stays the labelled legacy 600 USD/t |
| G2 | Orchestrator in `regional_snapshot` mode fails 2 of 339 assertions ("[Asia]/[Europe] Services selected > 0") | MODEL | Honest result of ~$0.15 M/wk at October-2026 prices against benchmark-era revenues (1 operated service). The six `profit > 0` assertions pass. Not relaxed; the default-mode gate is 342/342 |
| G3 | The global MILP ends `feasible`, never `optimal`, and uses most of its 120 s limit with the final pool | SOLVER | Optimality is unproven; exact optimum on one seed (8.20 M, proven) is above the production incumbent (6.4 M) |

## Code
| # | Item | State |
|---|---|---|
| C1 | `HubDetector` demand-score cache served a freed problem's scores to another problem (`id` reuse) → non-reproducible hubs, loops, feeders | **fixed** here (weak-reference check, 4 tests; the id-reuse test originally relied on the allocator reusing an address and failed once in a large test process — it now forces the stale entry when the address is not reused, and was confirmed to fail on the baseline code) |
| C2 | `RegionalAgent._filter_services` margin test `capacity × 0.5 × 150 USD > one vessel's weekly hire` is a hard-coded revenue guess; it alone removes every Feeder_450 | open — replacing it with per-rotation economics is a separate change (screened classes were measured to gain nothing from bypassing it) |
| C3 | `map_capacity_to_vessel_class` is imported by two agents and called by none | open, harmless — kept for compatibility |
| C4 | `tests/architecture/test_output_contract.py::test_regions_count_and_keys_frozen` expects 5 regional results; WorldSmall (47 ports) yields 3 clusters | baseline failure, unchanged |
| C5 | `backend/server.py` and `backend/unified_main.py` still contain a legacy hard-coded margin/"mock streaming" path (only the margin lookup in `unified_main` was corrected) | open |
| C6 | The unseeded legacy sections (`CandidateServiceGenerator`) and the GAs use the global `random` module from threads; the pipeline as a whole is not bit-reproducible | open — the demand-coherent generator and the class screening are deterministic |

## Model assumptions (all emitted in `network_ledger.assumptions`)
* `Capacity FFE` read as TEU (provisional) — fleet-capacity feasibility is conditional on it.
* 24 h per port call; 48 h minimum transfer + 3.5 d expected wait; `TransitTime` in days (unverified unit).
* Sailing at class design speed only; no consumption-versus-speed law (none invented).
* Fuel grade VLSFO without scrubbers; one declared bunkering port per service (cheapest observed on the rotation — an
  optimistic bound); legacy uniform 600 USD/t is a benchmark-era assumption, not a market price.
* Stand-alone profit (used by the generator and the screener) ignores transfer cargo — a rotation that only works as a feeder
  is never "promising" and keeps its legacy class.
* The regional split of cost is an accounting convention (changed here from "proposing region" to "using region",
  representation first); totals are unaffected.
* The advisory coordinator evaluation uses a 15 % margin target (an existing verdict band).

## Source-data gaps
* No licensed, dated, multi-port bunker prices; the free public pages show weekday and month-day only (year inferred) and
  state no reuse licence.
* No fuel-grade or scrubber data per class; no bunkering-call data (where fuel is actually bought).
* No documentation confirming the unit of `Capacity FFE` or `TransitTime`.

## Solver limitations
* The LP-guided restriction (relaxation → keep used services → integer solve) degrades as the pool grows: profit falls with
  more alternatives per rotation, with a demand-loop budget above 90 and with "every class". It is the binding limit now.
* The unrestricted integer problem does not close in 280 s at 600 USD/t on the legacy pool (incumbent far below the restricted
  solve), but closes in under 3 minutes on the final pool at one seed and in 18–53 s at higher fuel prices.
* Time-limited incumbents depend on CPU availability: runs that end at the 120 s limit can differ between machines/loads.

## Deliberately deferred (instructed)
* Task 11 — two-transfer paths (feeder → trunk → feeder).
* Task 12 — route-level GA operators (insert/delete/swap port).
* Replacing the legacy generator sections, the regional GA objective, or the path model.

## Decisions
**Approved by the product owner (message of 2026-10-11; verification in `overnight_tasks_8_9_10_final_report.md` §11):**
1. Fuel pricing — USD 600/t stays the default legacy benchmark; a separate, explicitly selected, pinned, dated,
   grade-specific market-price scenario exists; revenue is not re-based; 600 is not labelled a current market median;
   each market price records source, grade, unit, observation date and bunkering-location assumption.
2. Generator defaults — demand loops (budget 60) and class screening k = 1 are on by default subject to the acceptance
   gates; both set to 0 restores the prior candidate pool exactly (**verified**, see final report §11); rollback
   configuration = `LINER_DEMAND_LOOP_BUDGET=0`, `LINER_CLASS_SCREEN=0`, `BUNKER_PRICING_MODE` unset.
3. Regional cost allocation — usage-based, provided regional totals reconcile exactly to network totals within tolerance
   and no shared cost is counted twice (**verified**, see final report §11).
4. Release gates — the gates were re-run after each major change (final report §11).
5. Scope — Tasks 11 and 12 are not implemented.

**Still open (not covered by the approval):**
* The 15 % margin target of the advisory coordinator verdict (an existing verdict band, kept as is).
* Recertification sign-off of the Tier-0 components touched (coordinator metrics, iteration selection, payload assembly).
