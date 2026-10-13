# Migration note — network economics (Tier-0 components modified)

**Date:** 2026-10-11 · **Change control:** `CHANGE_CONTROL.md` §1 record · **Evidence:** `reports/network_economics_redesign/`

`PROTECTED_COMPONENTS.md` places the MILP structure (T0-4), the GA mathematics (T0-5) and the payload assembly (T0-2) in
Tier 0 ("explicit product-owner approval + full recertification + dedicated migration note"). This note is that migration note.

## 1. Approval basis
The product owner instructed, in the working session of 2026-10-10/11, to resolve the Task 3 blockers (fleet check, zero
frequency, failure propagation, logging), to derive frequency and cycle time from real sailing and port time, and to carry the
work through all remaining phases. That instruction is the approval for the components in §2. **Recertification sign-off
(§5) remains with the product owner.**

## 2. Affected components (1 — mandatory change record)
| Tier-0 item | File | Change |
|---|---|---|
| T0-4 MILP objective & constraints | `src/optimization/hub_milp.py` | now an adapter over `src/network/network_milp.py`: path-based network MILP (integer departures and vessels, per-leg capacity, per-class inventory, transit-time-feasible paths); **objective is true operating profit — the coverage reward is gone**; the optimiser penalty is reported apart. Verbatim legacy: `hub_milp_legacy.py` |
| T0-5 GA mathematics | `service_ga.py`, `frequency_ga.py`, `hierarchical_ga.py` | fitness through the canonical service model; frequency ceiling `⌊7·N/T⌋` replaces `0..3`; fleet limit is the real per-class inventory (not 300); `f = 0` leaves the mask. Legacy copies: `*_legacy.py` |
| T0-2 payload assembly | `src/agents/orchestrator_agent.py` | global reconciliation stage; `status` ∈ {`complete`, `incomplete_accounting`}; new top-level `network_ledger`. Iteration budget, snapshot machinery, `best_snapshot` restore and the canonical coverage override are **unchanged** |
| T0-3 canonical coverage | `src/agents/coordinator_agent.py` | **not modified** |
| T0-1 iteration selection | `src/pipeline/iteration_selection.py` | **not modified** (inputs are now correct; weights untouched) |

Non-Tier-0: `src/network/*` (new), `src/utils/fuel_cost.py` (+legacy), `src/services/service_feasibility.py` (new),
`src/agents/{regional_agent,service_generator_agent}.py`, `src/data/network_loader.py`, `src/decomposition/regional_splitter.py`,
`src/optimization/data.py`, logger-call conversions in stdlib-logger modules.

## 3. Expected behaviour change
* Reported profit is the independently recomputed operating profit of a **feasible** plan (fleet, leg capacity, demand
  conservation, transit time). Legacy: −$303 M/week at "86 %" coverage on a plan needing more vessels than exist; now:
  +$3–5 M/week at 9–10 % coverage (honest, run-to-run varying).
* Coverage is `satisfied / true demand` everywhere (F-16); the service record count equals the headline (F-25).
* A stage that cannot model its input fails with a reason; `status` is `incomplete_accounting` unless the ledger verified.
* Frequency and cycle time are physical; hard-coded values are commented out with notes.

## 4. Regression risk (frozen contracts nearby)
* `pipeline_output.json`: **additive only** — +`network_ledger`, +`frequency_per_week`/`vessels`/`cycle_time_days` on service
  rows; `status` value domain widened by one value. `PIPELINE_OUTPUT_CONTRACT.json` and
  `tests/architecture/test_output_contract.py` were updated in the same change. No key renamed, removed or re-typed; no unit changed.
* ~~Not repaired, deliberately: **F-15**~~ — repaired on 2026-10-11 under the Task 8A authorisation, see §7.
* Per-region profit is an accounting partition (cargo → origin region, service → proposing region); a region can be negative
  while the network is positive.

## 5. Recertification evidence (to be countersigned)
| Gate | Result |
|---|---|
| orchestrator test, fresh snapshot (U6) | 310/310 assertions, 0 failed |
| suite vs baseline, artifact-free / artifact-present | 0 newly failing; 2 / 3 fixed; remaining failures identical to baseline (51 / 53) |
| tier-0 behaviours: iteration budget 3, selection authority, canonical coverage | unchanged code; covered by `tests/test_iteration_selection.py` (passing) and orchestrator sections |
| independent recomputation | equal to the dollar; tampered plans rejected |

## 6. Rollback
Nothing was deleted. Restore `hub_milp.py`, `service_ga.py`, `frequency_ga.py`, `hierarchical_ga.py`, `fuel_cost.py` from their
`*_legacy.py` copies (identical signatures), revert the orchestrator seam (`_reconcile_iteration` and the `network_ledger` key)
and `PIPELINE_OUTPUT_CONTRACT.json`/`test_output_contract.py`. Pre-change tests: `reports/overnight_tasks_2_to_4/legacy_tests/`.

## 7. Addendum 2026-10-11 — Tasks 8A, 8B, 9, 10 (explicit user authorisation for this run)

**Approval basis.** The product owner authorised Tasks 8, 9 and 10 for the overnight run of 2026-10-11 (F-15 accounting
correction incl. coordinator evaluation and iteration selection; region-aware fuel pricing; demand-coherent candidate
generation; per-rotation class screening). Not authorised and not done: two-transfer paths, route-level GA operators.
Recertification sign-off stays with the product owner.

| Tier-0 item | File | Change |
|---|---|---|
| T0-3 coordinator | `src/agents/coordinator_agent.py` | `global_metrics.total_cost` / `profit_margin_pct` now the all-in cost and margin on revenue (F-15); evaluation check 3 is margin ≥ 15 % (advisory); coverage computation and feedback signals **unchanged** |
| T0-1 iteration selection | `src/pipeline/iteration_selection.py` | cost objective/Pareto/score/tie-break/cost rank use `total_cost` (was `operating_cost` = vessel hire); an unverified iteration cannot beat a verified one; a missing cost is invalid. Weights, determinism and LLM-cannot-override rule **unchanged** |
| T0-2 payload | `src/agents/orchestrator_agent.py` | passes the iteration ledger to the coordinator; snapshot metrics use `src/network/metrics.py`; summary flags unverified accounting |
| T0-4 / T0-5 | `hub_milp.py`, GAs | **not modified** (they receive pricing through `assumptions_for_problem`) |

Non-Tier-0: `src/network/{metrics,bunker_prices}.py` (new); `economics.py`, `ledger.py`, `plan.py`, `reconcile.py` (per-service
fuel price; ownership tie-break; settings and pool composition in the ledger block); `src/services/{demand_coherent,
class_screening}.py` (new); `service_generator_agent.py` (sections F + class screening), `regional_agent._filter_services`
(demand-loop candidates - already stand-alone-profitable by construction - bypass the crude margin guess and the cap;
class-screened candidates are **not** exempt: measured to gain nothing), `regional_splitter.py` (`global_demands`),
`backend/unified_main.py` (margin read from a key that did not exist), `src/services/hub_detector.py` (demand-score cache keyed by `id(problem)` served a freed problem's scores to another problem - now validated with a weak reference; this was a source of non-reproducible candidate pools), `data/pricing/` (snapshot).

**Defaults and switches** (all environment, all recorded in `network_ledger.assumptions`):
`BUNKER_PRICING_MODE` (default `legacy_uniform` 600 USD/t, labelled assumed), `LINER_DEMAND_LOOP_BUDGET` (default 60 per
regional problem, `0` = off), `LINER_CLASS_SCREEN` (default 1, `0` = legacy nearest-capacity). With the last two at 0 the
candidate pool is the previous one exactly (tested).

**Behaviour change.** Same economics definition and ledger; a better and differently composed candidate pool. Measured on
identical inputs (5 seeds): weekly profit $3.25 M → $8.42 M, coverage 8.5 % → 20.3 %; end-to-end orchestrator, three runs
per configuration — see `reports/overnight_tasks_8_9_10/overnight_tasks_8_9_10_final_report.md`.

**Regression risk.** Output contract additive only (`PIPELINE_OUTPUT_CONTRACT.json` `addenda`). Tests changed to follow
deliberate behaviour (F-15 tripwires flipped; objective-set assertions; two generator tests pinned to the legacy
configuration they were written for; the per-region "services selected > 0" assertion is **not** weakened — the ownership
rule was fixed instead). Regional profit is still an accounting partition; the convention for a service's cost changed from the proposing region to the using region (representation first; totals unchanged) - decision (4) below.

**Decisions approved by the product owner (2026-10-11).** (1) *Fuel pricing:* USD 600/t remains the default legacy
benchmark for reproducibility; the market-price scenario is a separate, explicitly selected one built on a pinned, dated,
fuel-grade-specific snapshot (`data/pricing/bunker_snapshot_2026-10-09_vlsfo.json`; each price records source, grade, unit,
observation date and bunkering-location assumption); revenue is **not** re-based; 600 is **not** labelled a current market
median. (2) *Generator defaults:* demand-driven loops (budget 60) and class screening k = 1 are on by default subject to all
acceptance gates; both at 0 restores the prior candidate pool exactly (verified, final report §11); no coverage or profit
improvement is forced. (3) *Regional cost allocation:* usage-based, accepted provided regional totals reconcile exactly to
the network totals within tolerance and no shared cost is counted twice (verified, final report §11). (4) *Release gates:*
focused tests, `tests/test_orchestrator.py` and independent ledger validation re-run after each major change; legacy and
market-price scenarios compared on equivalent captured inputs; a near-break-even or unprofitable market-price scenario is
reported as found. (5) *Scope:* Tasks 11 and 12 are not implemented.

**Decisions still open.** The 15 % margin target of the advisory coordinator evaluation; recertification sign-off of the
Tier-0 components touched.

**Rollback.** Set `LINER_DEMAND_LOOP_BUDGET=0` and `LINER_CLASS_SCREEN=0` (candidate pool identical to before);
`BUNKER_PRICING_MODE` unset is the previous pricing. F-15: revert `coordinator_agent.py`, `iteration_selection.py` and the
snapshot block of `orchestrator_agent.py` together with the flipped tests.
