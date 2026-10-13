# Change Control

**Phase:** 0 · **Date:** 2026-08-26 · **Applies to:** all future modification of this repository (maritime phases and beyond)

## 1. Mandatory change record

Every future PR/commit that touches runtime behavior MUST state, in its description:

1. **Affected component** — per `PROTECTED_COMPONENTS.md` tier registry (file + function/class).
2. **Integration boundary** — which sanctioned boundary is used (IP-1/2/3/5, Tier-2 pattern), or "none — internal fix" with justification.
3. **Expected behavior change** — flags-off semantics vs flags-on semantics.
4. **Regression risk** — which frozen contracts are nearby; why they are not violated.
5. **Tests** — new/updated tests + full-suite result (`venv/Scripts/python.exe -m pytest tests/ --ignore=tests/test_orchestrator.py`) and, for anything touching pipeline behavior, a golden-run comparison against PHASE_0_BASELINE.md.
6. **Performance impact** — measured delta vs baseline (~319 s class run); maritime snapshot budget ≤5 s once per run.
7. **Rollback mechanism** — flag / module removal / revert; name the level (1–4) per INTEGRATION_BOUNDARIES.md.

## 2. Automatic rejections

A change is rejected without further review if it:

- Directly modifies any **Tier 0** component without explicit product-owner approval AND a recertification plan.
- Adds network calls inside optimization loops or optimizer modules (network-isolation test fails).
- Silently changes the output contract (renames/removes/re-types keys in `pipeline_output.json`, WS event names/shapes, REST response shapes consumed by the frontend).
- Bypasses or loosens validation (validators, clamp ranges, consensus reconciliation).
- Allows external data to override deterministic policy — including indirect routes through weights beyond validated/clamped channels.
- Introduces unbounded retries or unbounded latency into the pipeline path.
- Makes maritime features default-ON, or lets source/stale/invalid/network failure degrade the deterministic baseline.
- Installs dependencies without updating PHASE_0_DEPENDENCY_BASELINE.md.
- Modifies certification assertions to make a failing check pass.

## 3. Review checklist (for the reviewer)

- [ ] Tier of every touched file identified; Tier-0 untouched or explicitly approved.
- [ ] Flags-off behavior proven identical (golden/schema test output attached).
- [ ] Failure-path behavior: source failure / stale / invalid / network-down ⇒ deterministic baseline.
- [ ] No new imports in optimizer modules from network-capable libraries (`tests/architecture/test_network_isolation.py` green).
- [ ] Output contract: additive-only diff against `docs/architecture/PIPELINE_OUTPUT_CONTRACT.json`.
- [ ] Performance budget respected; stage timings reported for pipeline-touching changes.
- [ ] Rollback story is real (flag actually flips behavior off; removal doesn't strand references).

## 4. Emergency fixes

Production-breakage hotfixes still require the record above, filed retroactively within
24 h, plus immediate regression evidence. Emergency fixes may never be the vehicle for
Tier-0 retuning.

## 5. Documentation hygiene

No new audit-report proliferation: architectural artifacts live under `docs/architecture/`
and must stay concise, current, and non-duplicative. Update-in-place beats new-document.

## 6. Change records

### 2026-10-11 — Network economics (Tasks 3–7, Phase D)
1. **Affected components:** `hub_milp.py` (T0-4), `service_ga.py` / `frequency_ga.py` / `hierarchical_ga.py` (T0-5),
   `orchestrator_agent.py` payload assembly (T0-2); new `src/network/*`. Full list and approval basis:
   [`MIGRATION_NOTE_NETWORK_ECONOMICS.md`](MIGRATION_NOTE_NETWORK_ECONOMICS.md).
2. **Integration boundary:** none — internal correction at product-owner instruction (Tier-0 exception, migration note filed).
3. **Expected behaviour change:** reported economics are those of a verified feasible plan; `status` may be
   `incomplete_accounting`; frequency/cycle time are derived from physical time.
4. **Regression risk:** output contract changed additively (+`network_ledger`, +3 service fields, +1 `status` value) with the
   contract JSON and test updated together; F-15 deliberately not touched.
5. **Tests:** orchestrator 310/310; suite 0 newly failing vs baseline in both artifact states
   (`reports/network_economics_redesign/evidence/comparisons/`).
6. **Performance impact:** orchestrator run 54 s (U6) – 148 s (U3) vs ~319 s class run at Phase 0; global stage ≤ 31 s.
7. **Rollback:** restore the `*_legacy.py` modules and revert the orchestrator seam (level 3 per INTEGRATION_BOUNDARIES.md).

### 2026-10-11 — Decision-layer economics, fuel pricing, candidate generation (Tasks 8A, 8B, 9, 10)
1. **Affected components:** `coordinator_agent.py` (T0-3, metrics only), `iteration_selection.py` (T0-1),
   `orchestrator_agent.py` payload (T0-2); new `src/network/{metrics,bunker_prices}.py`,
   `src/services/{demand_coherent,class_screening}.py`. Full list and decisions:
   [`MIGRATION_NOTE_NETWORK_ECONOMICS.md`](MIGRATION_NOTE_NETWORK_ECONOMICS.md) §7.
2. **Integration boundary:** none — internal; user authorisation for Tasks 8–10 and the approved decisions of 2026-10-11 (default
   pricing stays legacy 600 USD/t; market-price scenario separate and pinned; generator defaults on; usage-based regional
   allocation) are recorded in the note.
3. **Expected behaviour change:** `global_metrics` carries all-in cost/margin (F-15); iteration selection ranks on all-in cost;
   candidate pool gains demand-coherent multi-port rotations and per-rotation class choice (both switchable); pricing
   default unchanged (legacy, labelled).
4. **Regression risk:** contract additive (`addenda` in `PIPELINE_OUTPUT_CONTRACT.json`); F-15 tripwire tests flipped and renamed;
   regional split of service cost is now usage-based (regions whose cargo rides a service; representation first) instead of first-proposer (totals unchanged).
5. **Tests:** orchestrator 342/342; new `test_decision_economics` (25), `test_bunker_pricing` (67), `test_demand_coherent` (27),
   `test_class_screening` (35), `test_regional_ownership` (8), `test_hub_detector_cache` (4); suite 0 newly failing vs the frozen baseline in both artifact
   states (evidence under `reports/overnight_tasks_8_9_10/evidence/comparisons/`).
6. **Performance impact:** global MILP 20 → ~30–115 s depending on pool and time limit (120 s cap); orchestrator 152–259 s.
7. **Rollback:** environment switches above; code revert list in the migration note §7.
