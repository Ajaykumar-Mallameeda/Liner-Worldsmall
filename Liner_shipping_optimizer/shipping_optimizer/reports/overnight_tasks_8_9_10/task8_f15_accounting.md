# Task 8A — F-15: one definition of cost, profit and margin in the decision layer

**Status: PASS.** Orchestrator 327/327 at the gate (310 prior + 17 new F-15 assertions; 342/342 in the final code after the pricing and pool sections), focused tests 135 passed, ledger zero violations,
replay of the captured U7 and M0 artifacts attributes every change to the metric definition (plan, ledger and selected iteration unchanged).

## 1. Original metric flow (before the change)

| Where | Field | Definition in the code | Scope |
|---|---|---|---|
| `reconcile.region_updates` (regional results) | `operating_cost` | vessel hire only (`x["vessel"]`) | component |
| same | `total_cost`, `weekly_profit`, `profit_margin_pct` | hire + fuel + port calls + per-TEU port + transshipment; profit = revenue − total; margin = profit / revenue | all-in |
| `CoordinatorAgent._calculate_global_metrics` → **`decision_output.global_metrics`** | `total_cost` | `Σ regional operating_cost` = **hire only** | narrower than its name |
| same | `profit_margin_pct` | `profit / (profit + total_cost)` with the hire-only cost → **25.9 %** (U7) / **26.7 %** (M0) | inconsistent |
| `OrchestratorAgent._build_iteration_snapshot` → iteration `metrics` | `total_cost` | `Σ regional total_cost` (all-in) | all-in |
| same | `operating_cost`, `profit_margin_pct` | hire only; `profit/(profit+hire)` | hire-only margin next to an all-in cost |
| `summary_metrics`, `network_ledger.weekly_usd` | `total_cost`, margin | all-in | authoritative |

Consumers of the hire-only numbers:

| Consumer | Use | Effect |
|---|---|---|
| `CoordinatorAgent._evaluate_system` | check `total_cost < total_profit` ("cost exceeds profit") | point in the 0–5 evaluation score; with hire-only cost it compared the wrong cost, and even all-in it needs a >50 % margin |
| `CoordinatorAgent._generate_decisions` | LLM prompt quotes "Total cost" and "Profit margin" | LLM reasoned on 26 % margin while the ledger said 11 % |
| `IterationSelector` (Tier 0) | `operating_cost` is a Pareto objective, a 0.15-weight score term, a tie-breaker and the `cost_rank`; `profit_margin_pct` is a tie-breaker | iterations were compared on vessel hire only |
| Dashboard | `backend/server.py` computes margin from `summary_metrics` (all-in) and forwards `decision_output` unchanged | the dashboard could show 11 % in one place and 26 % in another |

Feedback signals (`needs_rerun`, convergence, weights) do **not** read cost or margin — they use coverage, profit and conflicts —
so the rerun logic and the three-iteration budget are unaffected.

## 2. Corrected definitions (`src/network/metrics.py::canonical_network_economics`)

```
revenue      = ledger revenue                                       (weekly USD)
total_cost   = hire + fuel + port calls + handling + transshipment + per-TEU port   (all-in)
profit       = revenue − total_cost                                  (unserved penalty never inside)
margin_pct   = 100 · profit / revenue        None when revenue ≤ 0 or accounting is not verified
vessel_hire_cost = the hire component, kept as a diagnostic under its own name
```

* A **verified** ledger is the authority; the regional numbers (an additive partition of it) are cross-checked to ≤ 1 USD or
  1e-6 relative. A disagreement makes the accounting `unverified` — it is never averaged away.
* **Unverified / missing ledger**: `profit_margin_pct = None`, `accounting_verified = False`, the coordinator evaluation
  cannot award the margin point, the executive summary is prefixed `ACCOUNTING NOT VERIFIED`, and the LLM prompt says
  "n/a (not verified)".
* A region without a `total_cost` is listed in `accounting_issues`; it is never summed as 0.

## 3. Downstream consumers updated

| Component | Change |
|---|---|
| `coordinator_agent.py` | `global_metrics` carries `total_cost` (all-in), `vessel_hire_cost`, `revenue`, `profit_margin_pct`, `accounting_status/verified/basis/issues`; `process()` accepts the iteration's `network_ledger`; evaluation check 3 is now *margin on revenue ≥ 15 %* (`MARGIN_TARGET_PCT`, the "Moderate" verdict floor the orchestrator/regional summaries already use) — advisory, does not drive reruns or selection |
| `orchestrator_agent.py` | passes `network_ledger` to the coordinator; snapshot metrics use the canonical economics (`operating_cost` keeps its component meaning, `vessel_hire_cost` is an alias, `total_cost`/`revenue`/`profit_margin_pct` are canonical); executive summary flags unverified accounting |
| `iteration_selection.py` | cost objective, Pareto set, score weight, tie-break and `cost_rank` use `total_cost`; an iteration whose ledger is not verified cannot beat a verified one; a missing `total_cost` makes the iteration invalid (never "free") |
| tests | `test_economic_metric_documentation` F-15 tripwires flipped (as their docstring required) and renamed `…_has_one_definition` / `…_is_unambiguous`; `test_iteration_selection` fixtures and two objective-set assertions follow the objective; **no assertion was weakened** |

## 4. Independent reconciliation evidence

Run `T8A_orch1` (orchestrator section O, recomputed from raw data by the test, not by `src.network`):

| item | `global_metrics` | independent recomputation |
|---|---:|---:|
| total cost (all-in) | 28,665,590 | 28,665,590 |
| vessel hire (component) | 10,297,000 | 10,297,000 |
| revenue | 31,386,142 | 31,386,142 |
| profit | 2,720,552 | 2,720,552 |
| margin on revenue | 8.67 % | 8.67 % (vessel-hire-only ratio would read 20.9 %) |

Replay of the **same captured plans** through the old and the new decision code
(`evidence/comparisons/decision_layer_replay_{U7,M0}.md`; routes, candidates, ledger untouched):

| artifact | iteration | profit | ledger margin | OLD margin | NEW margin | OLD / NEW total cost |
|---|---|---:|---:|---:|---:|---|
| U7 | 0 / 1 / 2 | 1.05 M / 3.56 M / 1.42 M | 5.81 / 11.28 / 4.57 % | 14.20 / 25.90 / 11.70 % | **5.81 / 11.28 / 4.57 %** | 6.3 M → 16.9 M … 10.8 M → 29.8 M |
| M0 (fresh baseline) | 0 / 1 / 2 | 2.67 M / 0.77 M / 2.08 M | 11.48 / 2.51 / 7.87 % | 26.70 / 6.50 / 19.00 % | **11.48 / 2.51 / 7.87 %** | 7.3 M → 20.6 M … 8.9 M → 24.4 M |

Selected iteration and Pareto set are identical under the old and the new selector for both artifacts (U7: 1; M0: 0), and the
evaluation score is unchanged (3/5, "good"; the margin point is not awarded at 5.8–11.5 %, as before it was not awarded for
"cost < profit"). The change in displayed profit margin is therefore entirely the correction of the definition.

## 5. Tests added / changed

| File | What |
|---|---|
| `tests/test_decision_economics.py` (new, 25 tests) | all-in cost = sum of categories; profit = revenue − cost; margin = profit/revenue; zero revenue → no margin; unverified/mismatching/missing ledger never "verified"; coordinator metrics, evaluation and LLM prompt; snapshot metrics; selector prefers lower all-in cost even when hire says otherwise; missing cost = invalid; unverified loses to verified; artifact self-consistency (skips without an artifact) |
| `tests/test_orchestrator.py` §O | 17 assertions: the five economics lines vs independent recomputation, one value per name, margin ≠ hire-only ratio, selected iteration and its scorecard use the all-in cost |
| `tests/test_economic_metric_documentation.py` | F-15 tripwires flipped to assert the repaired state |
| `tests/test_iteration_selection.py` | fixture carries `total_cost`; objective-set tests follow `total_cost` |

## 6. Known limitation / decision for the owner
The advisory evaluation's margin threshold (15 %) is an existing in-code verdict band, not a new business rule. It is a
Tier-0 behaviour (coordinator + selector) changed under the explicit Task 8A authorisation; recertification sign-off remains
with the product owner (`docs/architecture/MIGRATION_NOTE_NETWORK_ECONOMICS.md` §7).
