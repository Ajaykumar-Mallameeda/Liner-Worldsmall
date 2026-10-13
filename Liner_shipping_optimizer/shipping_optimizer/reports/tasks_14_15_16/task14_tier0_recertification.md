# Task 14 — Tier-0 recertification and the 15 % margin verdict

**Date:** 2026-10-11 · **Scope:** WorldSmall only (no WorldLarge read) · **Priority:** P0 · **Status of this document:**
results of this run only; "previously reported" evidence is labelled as such.

## 1. Owner decision recorded

> The 15 % profit-margin threshold is an advisory verdict band. It is not a hard feasibility constraint, a minimum
> coverage target, or a requirement that every feasible network be profitable. A physically feasible network with
> independently verified positive profit must not be rejected solely because its margin is below 15 %. The system must
> report the actual margin and classify the result according to the approved verdict semantics.

Decision date: 2026-10-11 (owner instruction opening this run). It is implemented as exactly that and nothing wider:
the number 15 is unchanged, no gate was added or removed, and the four statuses the decision says must stay distinct
— physical feasibility, independently verified accounting, solver status, and the advisory verdict — are carried in
separate fields (§5).

## 2. Baseline and integrity (newly verified in this run)

| Item | Result |
|---|---|
| Repository root | `C:\Users\WINDOWS\Liner-Worldsmall\Liner_shipping_optimizer\shipping_optimizer` (project directory is **untracked**; `git` HEAD `74bf770` is "Revert … Add liner shipping optimizer worldsmall", so no commit identifies the baseline — the frozen snapshot does) |
| Tasks 8–10 patch | `reports/overnight_tasks_8_9_10/patches/overnight_tasks_8_9_10_final.patch` sha256 `fd67615ac4c4fb64b34c86311b3535adf82b5b586fb188327bbc55f5acd9487d` — **matches** the recorded checksum |
| Live tree vs the Tasks 8–10 final snapshots | `src/`, `backend/`, `data/`, `tests/`: 211/211 files byte-identical to `snap_fin10_focus`, `snap_fin11_reg`, `snap_fin9_g3`; one file differs from `snap_fin9_g1` (`tests/test_regional_ownership.py`: +49 lines, the test added after that snapshot — as the Tasks 8–10 report states) |
| Frozen baseline of this run | snapshot `B0` (`D:\liner_scratch\snap_B0_orch1`, taken before any edit); `evidence/comparisons/baseline_tree_identity_B0_vs_final_tasks_8_9_10.txt`: 211/211 identical to the Tasks 8–10 final tree |
| Baseline orchestrator (this run, `B0_orch1`) | `tests/test_orchestrator.py` **342/342**, exit 0; ledger verified, 0 violations; profit 8,710,134 USD/wk, margin 13.32 %, coverage 20.06 %, 17 services, 120 vessels (single unseeded run) |
| Baseline suite (artifact-free) | 51 failed / 1,143 passed / 46 skipped — the Tasks 8–10 report's figure for the final tree (51 / 1,143 / 46) reproduced exactly |

## 3. What was inspected (the whole path, not only the comparison)

| Path | Where | Finding |
|---|---|---|
| Corrected economics | `src/network/metrics.py::canonical_network_economics` | Correct: revenue/all-in cost/profit/margin from the verified ledger; `None` margin when the ledger is unverified, incomplete or revenue ≤ 0; regional partition cross-checked. **Unchanged.** |
| `global_metrics`, total cost | `CoordinatorAgent._calculate_global_metrics` | all-in `total_cost`, `vessel_hire_cost` as a labelled component, margin = profit/revenue. **Unchanged.** |
| Evaluation score | `CoordinatorAgent._evaluate_system` | `MARGIN_TARGET_PCT = 15.0` adds **one** point to a 5-point composite; below target only appends a *reason*. It never rejects, never feeds `needs_rerun`. Defect: the band was not exposed as its own field, and the point was also awarded to a margin computed **without** a ledger (not verified). |
| Rerun / acceptance | `_generate_feedback_signals`; `OrchestratorAgent.process` stop condition | Reruns are driven by coverage < 70 %, profit ≤ 0 floor and overlap conflicts only. Margin is not an input. |
| Iteration selection | `IterationSelector` | Margin is **not** a Pareto objective and **not** a gate; it is a rank and the 4th tie-breaker. Defect: an undefined / unverified margin (`None`) was coerced to **0.0 %** on the scorecard, in the tie-break and in the LLM prompt (a fabricated ratio). |
| Payload assembly | `OrchestratorAgent._build_iteration_snapshot`, final aggregation, `_rule_based_explanation` | Snapshot uses canonical economics. Defects: (a) the executive-summary margin was recomputed from regional sums with `else 0`; (b) verdict text used `> 15` (exactly 15 → "Poor") while the coordinator uses `>= 15`; (c) a region without revenue was labelled "Poor" at "0 %". |
| Missing / unverified ledger | `canonical_network_economics`, summary banner | Unverified → no margin, banner "ACCOUNTING NOT VERIFIED". **Unchanged.** |
| API / report fields | `decision_output.global_metrics`, `.evaluation`, `iteration_selection.scorecards[*]`, `executive_summary`, `regional_results[*].profit_margin_pct/explanation`, `network_ledger` | Frozen output contract (`tests/architecture/test_output_contract.py`) fixes top-level, `summary_metrics`, `iteration_selection` and region keys, so the new field was added **only** to nested, unfrozen blocks (`evaluation`, `scorecards[*]`). |
| Tests encoding the old interpretation | `tests/test_decision_economics.py`, `test_iteration_selection.py`, `test_orchestrator.py` | Already assert all-in cost (F-15). None encodes hire-only or `cost < profit`. No assertion was edited. |

**Answer to "does the 15 % threshold cause an unintended rejection anywhere in the path?" — No.** On the coordinator, the
iteration selector and the orchestrator no code path rejects, re-runs or de-selects a feasible, verified, positive-profit
network because its margin is below 15 %. The defects above are *misclassification / fabricated-value* defects, not
rejections. Evidence: `evidence/outputs/margin_characterization_B0_baseline.json` vs `…_T14_after.json` (same fixtures, same
tool, run on the baseline and on the patched source), and §6.

## 4. Pre-change vs post-change behaviour (hand-built fixtures; same tool on both trees)

| Case | Margin | Baseline | After |
|---|---:|---|---|
| Below target, verified | 9.09 % | score 3, reason "margin 9.1 % < target 15.0 %"; `needs_rerun` driven by coverage only | **identical score and rerun**; reason now says "(advisory)"; `evaluation.margin_verdict.band = below_target`, `blocks_acceptance = false` |
| Exactly at target | 15.0 % | point awarded (coordinator `>=`) | identical; band `at_or_above_target` |
| Above target | 33.3 % | point awarded | identical |
| Loss | −11.1 % | score 2, floor reason + margin reason | identical; band `loss`, margin keeps its negative value |
| Zero revenue | undefined | `margin = None`, reason "unavailable" | identical; band `undefined` |
| Unverified ledger | undefined | `margin = None` | identical; band `unverified` |
| Margin but **no ledger** | 33.3 % (regional identity) | efficiency point awarded | **no point** (`unverified`) — the only behavioural change of the coordinator; not reachable in the pipeline, which always supplies a ledger |
| Selector, undefined margin | `None` | scorecard **0.0**, prompt "0.0 %", tie-break `None == 0.0`, iteration 0 chosen | scorecard `None`, prompt "n/a (undefined or not verified)", a real margin wins the tie-break (iteration 1) |
| Regional explanation at exactly 15.0 % | 15.0 | "Verdict: Poor" | "Verdict: Moderate" |
| Region with no revenue | 0 stored | "Verdict: Poor — margin 0 %" | "Verdict: Undefined — margin n/a (no revenue)" |

## 5. The change (patch `evidence/patches/task14_advisory_margin_verdict.patch`)

sha256 `9270df8393ba0f32a89ffc76043d5da1424b9ee997721222cc0cb72ae331d835` (6 files, built from snapshot `B0` → the tested
snapshot `T14_orch1`; `git apply --check` against `B0`: OK). Rollback: `git apply -R` of that file, or restore the six files
from `B0`.

| File | Change |
|---|---|
| `src/network/metrics.py` | one definition: `MARGIN_TARGET_PCT = 15.0`, band constants, `classify_margin(margin, accounting_verified)`, `margin_verdict_label(...)` |
| `src/agents/coordinator_agent.py` | `_evaluate_system` classifies through `classify_margin`; adds `evaluation.margin_verdict`; score/point semantics for a verified ledger unchanged; `MARGIN_TARGET_PCT` still importable from this module |
| `src/pipeline/iteration_selection.py` | `profit_margin_pct` stays `None` when undefined/unverified; `margin_verdict` per scorecard; `None` sorts below any real margin in rank and tie-break; prompt prints "n/a" |
| `src/agents/orchestrator_agent.py` | `_margin_report` (executive summary from the canonical economics + band); `_rule_based_explanation` via the shared classifier |
| `src/agents/regional_agent.py` | fallback verdict via the shared classifier (same `>=` boundary) |
| `tests/test_margin_verdict.py` | 29 new tests (§6) |

**Semantics (advisory; never a gate)**

| Band | Condition | Label (exec. summary / regional) | Effect |
|---|---|---|---|
| `at_or_above_target` | verified, margin ≥ 15 % | Moderate, or Good above 20 % / 25 % | none |
| `below_target` | verified, 0 ≤ margin < 15 % | Poor + one sentence that feasibility, verified profit and solver status are unchanged | none |
| `loss` | verified, margin < 0 | Poor | none beyond the existing profit-floor feedback (unchanged) |
| `undefined` | verified ledger, revenue ≤ 0 | Undefined | margin `None` |
| `unverified` | ledger absent / not verified | Not verified | margin `None`; no efficiency point |

Not changed: the number 15; coverage target 70 %; profit floor 0; rerun logic; Pareto objectives; tie-breaker order;
physical constraints; ledger; the upper label bands (see §8).

## 6. Tests — actual results

| Run | Command | Result |
|---|---|---|
| New tests | `pytest tests/test_margin_verdict.py` | 29 passed (also inside the suite run below) |
| Targeted economics / coordinator / selection | `pytest tests/test_margin_verdict.py tests/test_decision_economics.py tests/test_iteration_selection.py -p no:cacheprovider` | 79 passed, 5 skipped (the 5 need a `pipeline_output.json` artifact) |
| Orchestrator, patched tree (`T14_orch1`, fresh snapshot, LLM 429 ignored as instructed, 2 fallbacks recorded) | `pytest tests/test_orchestrator.py -v -s --tb=short` | **342/342**, exit 0, 398 s; ledger verified, **0 violations**, `reconciled = true`; profit 9,192,548 USD/wk, margin **14.67 %**, coverage 19.5 %, 19 services, 121 vessels; status `complete`; iteration 0 selected |
| Suite, artifact-free, baseline vs patched (`B0_suite_free` / `T14_suite_free`) | `pytest tests --ignore=tests/test_orchestrator.py` | 51 failed / 1,143 passed / 46 skipped → 51 / **1,172** / 46; **0 newly failing**, 0 fixed, 51 failing in both (the documented baseline: missing `MULTI_AGENT_*` audit artifacts, LLM mock/activation, phase-8, SHA pins, `test_setup`, region count), +29 new tests, all passing (`evidence/comparisons/suite_diff_B0_vs_T14_artifact_free.md`) |

The requested case table, mapped to tests (all in `tests/test_margin_verdict.py` unless noted):

| Required case | Test |
|---|---|
| feasible, positive, < 15 % | `TestCoordinator::test_below_target_network_keeps_feasible_verified_and_positive`, `TestIterationSelection::test_a_single_below_target_iteration_is_selected_not_rejected` |
| at 15 % | `TestClassifier::test_exactly_at_target_is_at_or_above`, `TestCoordinator::test_margin_at_exactly_15_earns_the_point_like_a_higher_margin` |
| above 15 % | `TestClassifier::test_above_target`, `TestReportWriters::test_at_target_and_above` |
| feasible, negative profit | `TestCoordinator::test_loss_is_reported_with_the_real_negative_margin`, `TestReportWriters::test_loss` |
| zero revenue / undefined | `TestCoordinator::test_zero_revenue_has_no_margin_and_no_fabricated_ratio`, `TestIterationSelection::test_undefined_margin_stays_none_on_the_scorecard`, `TestReportWriters::test_zero_revenue_is_undefined` |
| invalid / unverified ledger | `TestCoordinator::test_unverified_ledger_exposes_no_margin_or_profitability_claim`, `…test_without_a_ledger_the_regional_margin_earns_no_point`, `TestIterationSelection::test_unverified_iteration_exposes_no_verified_margin` |
| two candidates, different margins and costs | `TestIterationSelection::test_selection_uses_all_in_cost_not_vessel_hire`, `…test_higher_profit_wins_even_with_the_lower_margin` |
| advisory verdict does not reject | `TestCoordinator::test_margin_does_not_create_a_rerun_or_change_the_feedback`, `TestIterationSelection::test_a_single_below_target_iteration_is_selected_not_rejected` |

**The new tests fail on the baseline.** The module needs symbols that do not exist there (import error), and the
behavioural differences of §4 were additionally measured on both trees with the same tool
(`evidence/tools/characterize_margin.py`).

## 7. Independent ledger verification (the patched run)

`T14_orch1.pipeline_output.json`: `network_ledger.verified = true`, status `feasible`, `violations = []`,
`reconciliation.reconciled = true`, revenue 62,678,620, all-in cost 53,486,072, profit 9,192,548 USD/wk
(margin 14.666 %). `decision_output.global_metrics` equals the ledger (`accounting_status = verified`); the test's own
sections N and O (revenue, every cost line, fleet, capacity, transit time recomputed from raw data) passed. The margin of
this verified, feasible, profitable run is **below 15 %**; it was reported as `below_target`, iteration 0 was selected
and the run finished `complete` — the decision's behaviour on a real pipeline result.

## 8. Remaining downstream consumers and limitations (nothing hidden)

| Consumer | State |
|---|---|
| Upper label bands | Executive summary: Good above **20 %**; regional explanations: Good above **25 %**. Both existed; unifying them changes labels in an owner-visible way, so it was **not** done. **Owner decision needed.** |
| `evaluation.status` ("good"/"moderate"/"poor") | composite of 5 points; the `"moderate"` branch (`score == 2.5`) is unreachable for an integer score (pre-existing, unrelated to margin). `frontend/.../CommandCenter.jsx` shows this composite as "Verdict:" and defaults to "Good" when absent. Not executed in this run. |
| `frontend/.../SummaryView.jsx` | "Verdict: Good" vs "Needs Improvement" from the text; both Moderate and Poor read as "Needs Improvement". Not executed. |
| `frontend/.../RegionalAgents.jsx::marginTone` | ≥ 15 available / ≥ 0 warn / < 0 error / null no-data — already consistent with the band. Not executed. |
| `backend/unified_main.py`, `backend/routes/metrics.py`, orchestrator live callbacks | recompute margin as profit/(profit + cost) and show `0` when undefined (display only; no band). Not changed. |
| `backend/pipeline_streamer.py`, `backend/services/pipeline_streamer.py` | synthetic/demo generators with hard-coded numbers (the latter uses a different margin formula). Out of scope. |
| Regional rows | `profit_margin_pct` is `0` for a region without revenue (frozen regional schema); only the verdict text now says "Undefined". |

Tier-0 recertification of the **Python decision layer** (coordinator, iteration selection, payload assembly, ledger
consumption) is supported by the evidence above. **Full** Tier-0 recertification is **not** claimed: the frontend and
backend consumers were read, not executed, and the label-band decision is open.

## 9. Gates

| Gate | Status |
|---|---|
| Coordinator does not reject a feasible, verified, positive-profit network below 15 % | **PASS** (code audit + `T14_orch1`: margin 14.67 %, selected, `complete`) |
| Ledger valid | **PASS** (verified, 0 violations, reconciled) |
| Tier-0 regression tests | **PASS** (79 passed / 5 skipped; suite 0 newly failing) |
| `tests/test_orchestrator.py` | **PASS** 342/342 (baseline 342/342) |
| No assertion weakened | **PASS** (no existing test edited; one test file added) |
| Full Tier-0 recertification | **NOT CLAIMED** — downstream consumers not executed; upper-band decision open |
| Re-check on the **final** tree of Tasks 14–16 (all patches) | orchestrator 342/342 ×2 with no environment variable (`FINAL2_orch_default_run1..2`, ledger verified, 0 violations; margins 13.3 % and 14.4 %, both reported against the 15 % band, both `complete`); whole suite 51 failed / 1,198 passed (artifact-free) and 53 / 1,222 (artifact-present), **0 newly failing** against the baseline in both states |
