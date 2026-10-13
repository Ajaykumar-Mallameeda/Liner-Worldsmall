# Network-economics redesign — final report (Tasks 3 → 7, Phase D)

**Date:** 2026-10-11 · **Scope:** WorldSmall only · **Status: all phases implemented and verified; one open KPI item (F-15) and one
optimisation-quality limit are stated in §6.**

This report supersedes the "BLOCKED / NOT STARTED" status in `reports/overnight_tasks_2_to_4/` (kept unmodified as history).

## 1. What was wrong (understood before anything was changed)

The earlier overnight run stopped at the Task 3 gate: with *real* cycle times the pipeline crashed
(`TypeError: A False object cannot be passed as a constraint`, then `TypeError` from logger calls in the error handlers). The crash
was not the defect; it exposed four defects that constant 7/14/21-day cycle times had been hiding:

| # | Defect (evidence) | Effect |
|---|---|---|
| D1 | zero frequency rounded **up** to one departure (`max(1, round(f))`); GA pruning ignored `f = 0` | 38 of 57 "selected" services had f = 0 but were costed as one departure; 260 vessels "needed" vs 75 real |
| D2 | fleet check built a Python `bool` into a PuLP constraint; handlers then died on stdlib-logger keyword args | crash, and a "fix" of only the logging would have turned it into silent zeros |
| D3 | time and cost on different bases: constant cycle times, `max_freq = 3`, capacity × `7 / cycle_time`, fuel table that disagreed with the fleet file (speeds above class maximum, 5000/8000 vs 4200/7500 TEU) | revenue, capacity, vessels and fuel did not describe the same service |
| D4 | no single accounting: region-local MILPs each priced the same shared services (cluster double charging), unserved penalty folded into "profit", missing port records became cost 0 | baseline reported −$303 M/week at 86 % coverage on a plan needing more vessels than exist |

## 2. What was built

One canonical economic model, used by every stage (`src/network/`):

| Concept | Definition (all derived; no constants) |
|---|---|
| sailing time | leg nm ÷ (class **design speed** × 24) — design speed is the only speed with a source consumption |
| port time | 24 h per call (**assumed**, LINERLIB documentation; stated in the output) |
| rotation time `T` | sailing + port days; declared cycle = ⌈T⌉; closed loop, return leg counted once |
| vessels | `N(f) = ⌈cycle · f / 7⌉`; `f = 0` → 0 vessels, not operated |
| max frequency | `⌊7 · class inventory / cycle⌋` — derived per service, not `3` |
| capacity | `capacity_teu · f` on **every** leg |
| fuel | (sea days · bunker t/day @ design + port days · idle t/day) × 600 USD/t (**assumed** price) |
| fleet | per-class inventory is a hard constraint in the MILP and re-checked by the ledger |
| paths | direct, or one transfer; transit = sailing + intermediate port stays + 48 h + 3.5 d dwell; limit = demand `TransitTime` (days) |
| profit | revenue − vessel hire − fuel − port calls − handling − transshipment − per-TEU port charges (penalty reported apart) |

* `ledger.py` recomputes everything from raw primitives and returns **structured violations** (leg capacity, fleet, transit time,
  demand over-service, invalid path, missing port record …) — it shares no code with the optimiser.
* `reconcile.py` runs one global network MILP over the union of the regional candidate pools, verifies it with the ledger, then
  partitions the result back to regions additively (cargo by origin region, service costs by first-proposing region).
* Adapters keep the public API: `HubMILP`, `ServiceGA`, `FrequencyGA`, `HierarchicalGA`, `fuel_cost` (verbatim legacy copies are
  `*_legacy.py`). `RegionalAgent` failures are explicit results; the orchestrator's `status` is `complete` **only** when
  `network_ledger.verified` is true, otherwise `incomplete_accounting`.

Per-task detail: `task3_blockers_resolved.md`, `task4_fuel_from_canonical_fleet.md`, `task5_6_7_acceptance.md`,
`phaseD_validation_and_reconciliation.md`, `solver_findings.md`.

## 3. Verification (same interpreter, same commands, fresh snapshot per run, nothing deleted)

| Check | Result |
|---|---|
| `tests/test_orchestrator.py`, final code (U7, incl. section N) | **310 / 310 assertions, 0 failed**, 12 warnings, exit 0, 49 s |
| same test, earlier runs | U3 265/265 · U5 309/310 (one wrong test expectation: regional `revenue` is not in the frozen schema; fixed) · U6 310/310 |
| rest of suite, artifact-free (U7 vs S0clean) | 980 pass / 51 fail — **0 newly failing**, 2 fixed (`test_ga`, `test_milp`) |
| rest of suite, artifact present (U7 vs S0) | 1,001 pass / 53 fail — **0 newly failing**, 3 fixed |
| new tests added | `test_network_economics` (25, hand-computed), `test_service_feasibility` (67), `test_capacity_units` (23), `test_network_failure_propagation` (12), reworked `test_shared_contracts` (30), `test_ga` (2), `test_milp` (2) |
| the 51–53 remaining failures | identical to baseline with the same messages: 29 missing `MULTI_AGENT_*.json` audit artifacts, LLM-mock/activation tests, phase-8 command centre, SHA pins of the regenerated artifact, `test_setup::test_config` |
| the six `profit > 0` assertions | **unmodified and now pass** because the plan is feasible and profitable — not because anything was relaxed |
| independent recomputation (section N) | revenue, every cost line, profit, vessels per class, served TEU agree with the pipeline to the dollar; tampered plans (+10 M TEU on a flow, +1000 departures) are rejected |
| MILP objective vs ledger profit | difference 0.0 (−4.7e-10) — reconciled |

LLM rate limits (HTTP 429 → deterministic fallback text) were ignored as instructed and are recorded in every log
(`Analysis/Executive summary produced by runtime FALLBACK`).

## 4. Result (run U6, detailed; U7 on the final code gave $3.56 M/week, 11.3 %, 9.1 % coverage, 11 services, 44 vessels, reconciled, 0 violations)

| | |
|---|---|
| status / verified / MILP status | `complete` / true / `feasible` |
| weekly revenue | $29.21 M |
| weekly cost | $25.96 M = vessel hire 9.21 + fuel 11.36 + port calls 0.16 + handling 4.27 + transshipment 0.64 + per-TEU port 0.33 |
| weekly operating profit | **$3.25 M** (11.1 % of revenue) |
| demand served | 24,220 of 276,447 TEU/week (**8.8 %**) |
| services operated | 11, all two-port, all weekly (f = 1); cycle times 3 … 40 days — ten distinct values, each from its own distance. 71 % of served TEU is transshipment cargo; four services show negative stand-alone attribution because they mostly carry transfer cargo whose revenue is split by ride-days |
| vessels | 41 of 263 — Feeder_800 7/29, Panamax_2400 5/74, Post_panamax 22/58, Super_panamax 7/10 |
| LP upper bound | $47.9 M/week (loose: fractional departures) — the plan is feasible and verified, **not proven optimal** |

Compared with the baseline (−$303 M/week, 287 services, 86 % "coverage", fleet exceeded), the new numbers are small but
**true**: every vessel exists, every leg fits its ship, every cargo meets its transit limit.

## 5. Assumptions that remain assumptions (all stated in `network_ledger.assumptions`)

1. `Capacity FFE` read as TEU, no ×2 — **provisional**; fleet-capacity feasibility is conditional on it
   (`capacity_feasibility_is_conditional: true`).
2. 24 h per port call; 48 h minimum + 3.5 d expected wait per transfer; bunker $600/t — none are in the canonical data files.
3. `TransitTime` read as days. Evidence: median(limit ÷ direct sailing days at the fastest class) = 1.88 — plausible; hours (0.08)
   and weeks (13.2) are not. 2.3 % of ODs (3.4 % of TEU) have a limit below direct sailing time and can never be served on time.
4. Sailing speed = class design speed (consumption is only given at that speed).

## 6. Open items — stated, not hidden

| Item | Why it is open | Proposed resolution |
|---|---|---|
| **F-15** two `total_cost` / `profit_margin_pct` values in one artifact (`decision_output.global_metrics` = vessel hire only, margin 29.6 % vs true 11–13 % on revenue) | the coordinator's evaluation and the Tier-0 iteration-selection objective read these fields; changing them silently changes decisions | needs the product owner's approval as a separate, recertified change; the unambiguous figures are in `network_ledger.weekly_usd` (`profit_margin_on_revenue`) |
| **Plan quality** (8–10 % coverage, 0.7–5.1 M/week run-to-run) | the regional candidate pool, not the solver: only 12 of 1,082 candidates are profitable even standalone; path model allows one transfer (no feeder–trunk–feeder); pool offers 4 of 6 classes, mostly 2-port rotations | demand-coherent multi-port loops, class-screened multi-class offering, two-transfer paths — `solver_findings.md` has the replay harness and the evidence |
| LP bound is loose | integer weekly departures | none needed; reported honestly as `feasible` with the bound |
| Tier-0 components modified | see `docs/architecture/MIGRATION_NOTE_NETWORK_ECONOMICS.md` | requires the product owner's recertification sign-off |

## 7. Reversibility

Nothing was deleted. Legacy implementations are preserved as `src/optimization/*_legacy.py`, `src/utils/fuel_cost_legacy.py`;
pre-change test files as `reports/overnight_tasks_2_to_4/legacy_tests/*.before.txt`. To go back to the legacy optimiser path,
swap the adapters for the `*_legacy.py` modules (they keep the original signatures).

## 8. Evidence index
* `evidence/runs/` — meta, logs, JUnit XML for U2, U3, U5, U6, U7 (suite and orchestrator), capture run U4
* `evidence/comparisons/` — suite diffs against the frozen baselines (S0 artifact-present, S0clean artifact-free)
* `evidence/outputs/` — `pipeline_output_{U3,U6,U7}.json` (full artifacts of the verified runs)
* `evidence/tools/` — snapshot / run / compare tools and the capture-replay-standalone-profit harness
* `patches/network_economics_vs_task3_final.patch` (+ `patches.sha256`) — all source/test/doc changes since the Task 3 gate;
  it also contains one runtime-generated maritime snapshot under `data/maritime/` that is not part of the change
* `../../docs/architecture/MIGRATION_NOTE_NETWORK_ECONOMICS.md`, `CHANGE_CONTROL.md` §6 — governance record
