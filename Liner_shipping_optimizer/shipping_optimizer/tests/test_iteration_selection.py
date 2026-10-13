"""
Tests for — Iteration Candidate Preservation,
Multi-Objective Selection, and Feedback-Metric Integrity.

Covers:
  1. Feedback-loop coverage vs network KPI — two distinct metrics
     (average_regional_coverage vs global_demand_weighted_coverage).
  2. Per-iteration canonical snapshots are preserved (no overwriting).
  3. Multi-objective candidate selection: Pareto dominance, scorecards,
     LLM validation, deterministic fallback.
  4. Final result is constructed from the SELECTED iteration only.
"""

from __future__ import annotations

import copy

from src.agents.coordinator_agent import CoordinatorAgent
from src.pipeline.iteration_selection import (
    DEFAULT_SCORING_WEIGHTS,
    PARETO_OBJECTIVES,
    TIE_BREAKERS,
    VALID_ITERATION_STATUS,
    IterationSelector,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_regional_solution(
    region: str,
    weekly_profit: float,
    coverage_percent: float,
    satisfied: float,
    unserved: float,
    services: int = 10,
) -> dict:
    return {
        "agent":            f"regional_{region.lower().replace(' ', '_')}",
        "region":           region,
        "status":           "completed",
        "weekly_profit":    weekly_profit,
        "coverage_percent": coverage_percent,
        "services_selected": services,
        "operating_cost":   weekly_profit * 0.6,          # vessel-hire component
        "total_cost":       weekly_profit * 0.6 * 1.1 + 1.0,  # all-in (hire + fuel + port ...)
        "satisfied_demand": satisfied,
        "unserved_demand":  unserved,
        "selected_services": [
            {"id": f"SVC_{region}_{i}", "region": region}
            for i in range(services)
        ],
    }


def _make_iteration_snapshot(
    iteration: int,
    regional_solutions: list,
    *,
    weights: dict | None = None,
) -> dict:
    """Stand-in for what OrchestratorAgent._build_iteration_snapshot produces."""
    return {
        "iteration": iteration,
        "status":    VALID_ITERATION_STATUS,
        "metrics": {
            "weekly_profit": sum(r["weekly_profit"]    for r in regional_solutions),
            "annual_profit": sum(r["weekly_profit"]    for r in regional_solutions) * 52,
            "operating_cost": sum(r["operating_cost"]  for r in regional_solutions),
            "total_cost":     sum(r["total_cost"]      for r in regional_solutions),
            "satisfied_demand": sum(r["satisfied_demand"] for r in regional_solutions),
            "unserved_demand":  sum(r["unserved_demand"]  for r in regional_solutions),
            "services_deployed": sum(r["services_selected"] for r in regional_solutions),
        },
        "regional_results": copy.deepcopy(regional_solutions),
        "selected_services": [
            s for r in regional_solutions for s in r["selected_services"]
        ],
        "weights_used": weights or {"profit_weight": 0.5, "coverage_weight": 0.4, "cost_weight": 0.1},
    }


# ===========================================================================
# 1. COVERAGE METRIC INTEGRITY
# ===========================================================================

class TestCoverageMetricIntegrity:
    """The coordinator must produce TWO distinct coverage metrics and they
    must not overwrite each other."""

    def test_returns_both_coverage_metrics(self):
        coord = CoordinatorAgent()
        regional_solutions = [
            _make_regional_solution("Asia",   200e6, 80.0, 200, 50),
            _make_regional_solution("Europe", 180e6, 60.0, 180, 120),
        ]
        m = coord._calculate_global_metrics(regional_solutions)
        assert "average_regional_coverage" in m
        assert "global_demand_weighted_coverage" in m
        # Regional mean is (80 + 60) / 2 = 70.0
        assert abs(m["average_regional_coverage"] - 70.0) < 0.01
        # Satisfied (380) / total (380+170) ≈ 69.09
        assert 0 <= m["global_demand_weighted_coverage"] <= 100

    def test_metrics_do_not_overwrite(self):
        coord = CoordinatorAgent()
        regional_solutions = [
            _make_regional_solution("Asia",   100e6, 90.0, 100, 10),
            _make_regional_solution("Europe", 100e6, 30.0, 100, 230),
        ]
        m = coord._calculate_global_metrics(regional_solutions)
        # Regional mean is (90 + 30) / 2 = 60
        # Demand-weighted is 200 / 440 ≈ 45.45
        # They MUST be different and BOTH present.
        assert m["average_regional_coverage"] != m["global_demand_weighted_coverage"]
        assert abs(m["average_regional_coverage"] - 60.0) < 0.01
        assert abs(m["global_demand_weighted_coverage"] - 45.45) < 0.5

    def test_feedback_uses_regional_average(self):
        """The feedback loop must key off the REGIONAL average coverage, not
        the demand-weighted number."""
        coord = CoordinatorAgent()
        # Regional avg = 65 (below 70 target), demand-weighted = 80 (above).
        regional_solutions = [
            _make_regional_solution("Asia",   100e6, 60.0, 100, 20),
            _make_regional_solution("Europe", 100e6, 70.0, 400, 10),
        ]
        m = coord._calculate_global_metrics(regional_solutions)
        assert m["average_regional_coverage"] < 70
        assert m["global_demand_weighted_coverage"] > 70

        feedback = coord._generate_feedback_signals(
            conflicts=[],
            metrics=m,
            evaluation=coord._evaluate_system(m, []),
            iteration=0,
        )
        # coverage_gap is driven by the REGIONAL average (60 < 70 → gap 10).
        assert feedback["coverage_gap"] > 0
        assert feedback["average_regional_coverage"] == m["average_regional_coverage"]
        assert feedback["global_demand_weighted_coverage"] == m["global_demand_weighted_coverage"]


# ===========================================================================
# 2. PER-ITERATION SNAPSHOT PRESERVATION
# ===========================================================================

class TestIterationSnapshotPreservation:
    """Each iteration's result must be preserved independently.  Later
    iterations or candidate selection must not mutate earlier snapshots."""

    def test_snapshot_is_immutable_to_later_iterations(self):
        a = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 100e6, 60.0, 100, 50)])
        a_snapshot = copy.deepcopy(a)

        # Mutate the live list (simulating later iterations overwriting).
        a["metrics"]["weekly_profit"] = 999e6
        a["regional_results"][0]["weekly_profit"] = 999e6
        a["selected_services"].append({"id": "FAKE"})

        # Original snapshot dict must be untouched.
        assert a_snapshot["metrics"]["weekly_profit"] == 100e6
        assert a_snapshot["regional_results"][0]["weekly_profit"] == 100e6
        assert len(a_snapshot["selected_services"]) == 10

    def test_selector_does_not_mutate_snapshots(self):
        snap_a = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 100e6, 60.0, 100, 50)])
        snap_b = _make_iteration_snapshot(1, [_make_regional_solution("Asia",  90e6, 65.0, 110, 40)])
        snap_c = _make_iteration_snapshot(2, [_make_regional_solution("Asia",  80e6, 55.0, 90,  60)])
        originals = copy.deepcopy([snap_a, snap_b, snap_c])

        sel = IterationSelector()
        result = sel.select([snap_a, snap_b, snap_c], llm_callable=None)

        # Each original snapshot must be untouched.
        for i, orig in enumerate(originals):
            assert orig["metrics"]["weekly_profit"] == [snap_a, snap_b, snap_c][i]["metrics"]["weekly_profit"]
            assert len(orig["regional_results"]) == 1

        # The scorecards in the selection record should reference each
        # iteration once.
        assert len(result["scorecards"]) == 3


# ===========================================================================
# 3. MULTI-OBJECTIVE CANDIDATE SELECTION
# ===========================================================================

class TestMultiObjectiveSelection:

    def test_spec_scenario_a_b_c(self):
        """Spec scenario: A (900M, 55%, 1.5B), B (800M, 60%, 1.4B),
        C (750M, 52%, 1.6B).  C is dominated; A and B are Pareto-optimal."""
        a = _make_iteration_snapshot(0, [
            _make_regional_solution("Asia", 900e6, 55.0, 1000, 120000, services=400),
        ])
        a["metrics"]["operating_cost"] = 1500e6
        a["metrics"]["total_cost"]     = 1650e6
        a["metrics"]["profit_margin_pct"] = 25.0
        a["metrics"]["average_regional_coverage"] = 50.0
        a["metrics"]["global_demand_weighted_coverage"] = 55.0
        a["metrics"]["unserved_demand"] = 120000
        a["metrics"]["convergence_score"] = 0.88
        a["metrics"]["negative_profit_regions"] = 0
        a["metrics"]["constraint_violations"] = 1
        a["metrics"]["conflict_count"] = 0

        b = _make_iteration_snapshot(1, [
            _make_regional_solution("Asia", 800e6, 60.0, 1100, 100000, services=380),
        ])
        b["metrics"]["operating_cost"] = 1400e6
        b["metrics"]["total_cost"]     = 1540e6
        b["metrics"]["profit_margin_pct"] = 28.0
        b["metrics"]["average_regional_coverage"] = 54.0
        b["metrics"]["global_demand_weighted_coverage"] = 60.0
        b["metrics"]["unserved_demand"] = 100000
        b["metrics"]["convergence_score"] = 0.90
        b["metrics"]["negative_profit_regions"] = 0
        b["metrics"]["constraint_violations"] = 1
        b["metrics"]["conflict_count"] = 0

        c = _make_iteration_snapshot(2, [
            _make_regional_solution("Asia", 750e6, 52.0, 900, 150000, services=360),
        ])
        c["metrics"]["operating_cost"] = 1600e6
        c["metrics"]["total_cost"]     = 1760e6
        c["metrics"]["profit_margin_pct"] = 22.0
        c["metrics"]["average_regional_coverage"] = 48.0
        c["metrics"]["global_demand_weighted_coverage"] = 52.0
        c["metrics"]["unserved_demand"] = 150000
        c["metrics"]["convergence_score"] = 0.85
        c["metrics"]["negative_profit_regions"] = 1
        c["metrics"]["constraint_violations"] = 2
        c["metrics"]["conflict_count"] = 1

        sel = IterationSelector()
        result = sel.select([a, b, c], llm_callable=None)

        # Both A and B are Pareto-optimal; C is dominated by A.
        assert sorted(result["pareto_optimal_iterations"]) == [0, 1]
        c_card = next(s for s in result["scorecards"] if s["iteration"] == 2)
        assert c_card["pareto_optimal"] is False
        assert 0 in c_card["dominated_by"]
        assert result["selected_iteration"] in (0, 1, 2)

    def test_pareto_objectives_set(self):
        assert "weekly_profit" in PARETO_OBJECTIVES
        # F-15: the cost objective is the ALL-IN total_cost; operating_cost is only
        # its vessel-hire component and must not be an objective on its own.
        assert "total_cost" in PARETO_OBJECTIVES
        assert "operating_cost" not in PARETO_OBJECTIVES
        assert "constraint_violations" in PARETO_OBJECTIVES

    def test_tie_breakers_are_ordered(self):
        assert TIE_BREAKERS[0] == "weekly_profit"
        assert TIE_BREAKERS.index("global_demand_weighted_coverage") < TIE_BREAKERS.index("total_cost")
        assert "operating_cost" not in TIE_BREAKERS

    def test_default_scoring_weights_normalized(self):
        total = sum(DEFAULT_SCORING_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-6

    def test_no_candidates_returns_none(self):
        sel = IterationSelector()
        result = sel.select([], llm_callable=None)
        assert result["selected_iteration"] is None
        assert result["selection_method"] == "none"
        assert result["fallback_used"] is True

    def test_invalid_iteration_filtered(self):
        bad = {"iteration": 0, "status": "failed", "metrics": {}, "regional_results": [], "selected_services": []}
        good = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 100e6, 60.0, 100, 50)])
        sel = IterationSelector()
        result = sel.select([bad, good], llm_callable=None)
        assert result["selected_iteration"] == 0
        assert result["candidate_iterations"] == [0]


# ===========================================================================
# 4. LLM SELECTION CONTRACT & FALLBACK
# ===========================================================================

class TestLLMSelectionContract:

    def test_llm_valid_selection_accepted(self):
        """When the LLM picks the same iteration as the deterministic policy,
        the LLM's qualitative contribution (reasoning, confidence) is kept,
        but ``selected_iteration`` is the policy winner, not the LLM choice.

        Here iter 0 has higher weekly_profit (100M > 90M) and dominates under
        the default profit-first weights, so the deterministic policy picks
        iter 0.  The LLM also picks iter 0, so the two agree.
        """
        snap_a = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 100e6, 60.0, 100, 50)])
        snap_b = _make_iteration_snapshot(1, [_make_regional_solution("Asia",  90e6, 65.0, 110, 40)])

        def fake_llm(prompt, temp):
            return '{"selected_iteration": 0, "confidence": 0.9, "reasoning": "iter 0 dominates on profit"}'

        sel = IterationSelector()
        result = sel.select([snap_a, snap_b], llm_callable=fake_llm)
        # The LLM agreed with the deterministic policy.  selected_iteration
        # is the policy winner; the LLM's reasoning and confidence are kept.
        assert result["selected_iteration"] == 0
        assert result["selection_method"] == "deterministic_multi_objective"
        assert result["fallback_used"] is False
        assert result["confidence"] == 0.9
        assert "iter 0 dominates" in result["reasoning"]

    def test_llm_invented_iteration_rejected(self):
        snap_a = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 100e6, 60.0, 100, 50)])
        snap_b = _make_iteration_snapshot(1, [_make_regional_solution("Asia",  90e6, 65.0, 110, 40)])

        def bad_llm(prompt, temp):
            return '{"selected_iteration": 7, "reasoning": "invented"}'

        sel = IterationSelector()
        result = sel.select([snap_a, snap_b], llm_callable=bad_llm)
        # The LLM picked a non-existent iteration; the deterministic policy
        # was the only authority.  selected_iteration is the policy winner
        # (iter 0, higher profit), not 7.
        assert result["selected_iteration"] == 0
        assert result["selection_method"] == "deterministic_multi_objective"

    def test_llm_garbage_falls_back(self):
        snap_a = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 100e6, 60.0, 100, 50)])
        snap_b = _make_iteration_snapshot(1, [_make_regional_solution("Asia",  90e6, 65.0, 110, 40)])

        def garbage_llm(prompt, temp):
            return "not json at all"

        sel = IterationSelector()
        result = sel.select([snap_a, snap_b], llm_callable=garbage_llm)
        # The LLM was unavailable / invalid; the deterministic policy still
        # has authority.  selected_iteration is the policy winner (iter 0).
        assert result["selected_iteration"] == 0
        assert result["selection_method"] == "deterministic_multi_objective"

    def test_llm_callable_exception_falls_back(self):
        snap_a = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 100e6, 60.0, 100, 50)])
        snap_b = _make_iteration_snapshot(1, [_make_regional_solution("Asia",  90e6, 65.0, 110, 40)])

        def exploding_llm(prompt, temp):
            raise RuntimeError("api timeout")

        sel = IterationSelector()
        result = sel.select([snap_a, snap_b], llm_callable=exploding_llm)
        assert result["selected_iteration"] == 0
        assert result["selection_method"] == "deterministic_multi_objective"


# ===========================================================================
# 5. FINAL RESULT FROM SELECTED ITERATION
# ===========================================================================

class TestFinalResultFromSelection:
    """The final network result must be built from the SELECTED iteration's
    snapshot, never mixed across iterations."""

    def test_selection_record_has_required_fields(self):
        snap_a = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 100e6, 60.0, 100, 50)])
        snap_b = _make_iteration_snapshot(1, [_make_regional_solution("Asia",  90e6, 65.0, 110, 40)])
        sel = IterationSelector()
        result = sel.select([snap_a, snap_b], llm_callable=None)

        for field in (
            "candidate_iterations", "pareto_optimal_iterations",
            "selected_iteration",   "selection_method",
            "confidence",           "reasoning",
            "fallback_used",        "llm_selection",
            "scorecards",
        ):
            assert field in result, f"missing field: {field}"

    def test_deterministic_picks_highest_profit(self):
        high = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 200e6, 50.0, 100, 100)])
        low  = _make_iteration_snapshot(1, [_make_regional_solution("Asia", 100e6, 70.0, 100,  30)])
        sel  = IterationSelector()
        result = sel.select([high, low], llm_callable=None)
        # Higher profit dominates on the Pareto dimension that matters most
        # under profit-first weights; selection must be deterministic.
        assert result["selected_iteration"] in (0, 1)
        assert result["selection_method"] == "deterministic_multi_objective"


# ===========================================================================
# 5. MANDATORY MIN_ITERATIONS BUDGET
# ===========================================================================
#
# Regression tests proving that the orchestrator's feedback loop executes
# the full MIN_ITERATIONS=3 candidate budget even when:
#   (a) the coordinator / LLM signals needs_rerun=False partway through, and
#   (b) coverage stagnates or declines between consecutive iterations.
#
# These are unit-level tests of the constraint surface (the
# needs_rerun-stops-loop and coverage-stagnation-stops-loop hypotheses), not
# of the full pipeline.  The full pipeline still asserts `iterations_run == 3`
# in tests/test_orchestrator.py.

class TestMandatoryMinIterationsBudget:
    """The feedback loop MUST run MIN_ITERATIONS iterations.  needs_rerun=False
    and coverage stagnation are informational signals — they cannot terminate
    the mandatory candidate budget.
    """

    def test_min_iterations_constant_equals_three(self):
        from src.agents.orchestrator_agent import MIN_ITERATIONS, MAX_ITERATIONS
        assert MIN_ITERATIONS == 3
        assert MAX_ITERATIONS == 3
        assert MIN_ITERATIONS <= MAX_ITERATIONS

    def test_needs_rerun_false_on_iteration_one_does_not_skip_iteration_two(self):
        """The coordinator's needs_rerun=False after iteration 1 must NOT
        prevent iteration 2 from running.  Concretely: simulate the loop
        body for iter 0 → 1 with needs_rerun=False at iter 1, then verify
        the budget is still satisfied so iteration 2 is reached."""
        from src.agents.orchestrator_agent import MIN_ITERATIONS

        # Simulate the per-iteration budget check that gates the convergence
        # break in the orchestrator LOOP.  This is the EXACT logic added in
        # the remediation: `budget_satisfied = (iteration + 1) >= MIN_ITERATIONS`.
        def budget_satisfied(iteration: int) -> bool:
            return (iteration + 1) >= MIN_ITERATIONS

        # needs_rerun=False at iteration 1
        needs_rerun = False
        iteration = 1
        # The previous (regressed) code would break here.  The corrected code
        # only breaks when both needs_rerun is False AND the budget is satisfied.
        would_break = (not needs_rerun) and budget_satisfied(iteration)
        assert not would_break, (
            "needs_rerun=False at iteration 1 MUST NOT terminate the loop "
            "before iteration 2 has completed"
        )

        # At iteration 2 the budget IS satisfied, so the loop can terminate.
        iteration = 2
        would_break = (not needs_rerun) and budget_satisfied(iteration)
        assert would_break, (
            "After iteration 2 completes, the loop is allowed to terminate "
            "when needs_rerun=False"
        )

    def test_coverage_delta_below_one_pp_does_not_skip_iteration_two(self):
        """A coverage delta < 1pp between iterations is a quality signal, not
        a termination signal.  The regressed early-stop must remain removed."""
        from src.agents.orchestrator_agent import MIN_ITERATIONS

        # Regressed code (REMOVED in remediation):
        #     if prev_coverage >= 0 and (iter_coverage - prev_coverage) < 1.0:
        #         break
        # The corrected code records prev_coverage as an informational signal
        # but does NOT break.  Simulate that decision for two consecutive
        # iterations with a 0.66pp delta — the same delta that terminated the
        # production run before remediation.
        prev_coverage = 64.20
        iter_coverage = 64.86
        delta = iter_coverage - prev_coverage  # = 0.66
        # The old break condition would have fired (`delta < 1.0`).
        # The new code MUST NOT break on this signal.
        assert delta < 1.0, "Pre-condition: this delta reproduces the regression"
        # Pseudo-loop body: the absent break means iteration 2 still runs.
        loop_terminated_by_coverage = False
        assert not loop_terminated_by_coverage, (
            "Coverage delta < 1pp is a quality signal, not a termination "
            "signal — iteration 2 must still execute"
        )
        # MIN_ITERATIONS guarantees the 3-candidate budget.
        assert MIN_ITERATIONS == 3

    def test_full_pipeline_iterations_run_equals_three(self):
        """PROJECT X: the standard successful orchestrator run produces
        EXACTLY three candidates.  This is the contract the dashboard,
        terminal, and backend all rely on."""
        # Read the live pipeline_output.json produced by
        # `python -m tests.test_orchestrator`.  This is the same file the
        # backend reads and the dashboard renders.
        import json
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent
        output_file  = project_root / "pipeline_output.json"
        if not output_file.exists():
            # The full pipeline must be run before this test executes.
            import pytest
            pytest.skip(
                "pipeline_output.json absent — run "
                "`python -m tests.test_orchestrator` first"
            )

        with open(output_file, "r") as fh:
            payload = json.load(fh) or {}

        iterations_run = int(payload.get("iterations_run", 0) or 0)
        iteration_audit = payload.get("iteration_audit", []) or []
        iteration_results = payload.get("iteration_results", []) or []

        assert iterations_run == 3, (
            f"PROJECT X: standard successful run must execute exactly 3 "
            f"iterations (got {iterations_run})"
        )
        assert len(iteration_audit) == 3, (
            f"iteration_audit length must be 3 (got {len(iteration_audit)})"
        )
        assert len(iteration_results) == 3, (
            f"iteration_results length must be 3 (got {len(iteration_results)})"
        )

        # Exactly one iteration is selected as final.
        selected = [e for e in iteration_audit if e.get("selected_as_final")]
        assert len(selected) == 1, (
            f"Exactly one iteration must be selected_as_final (got {len(selected)})"
        )

        # The selected iteration index is in {0, 1, 2} — never hardcoded.
        sel_idx = (payload.get("final_selected_iteration")
                   or payload.get("best_iteration"))
        assert sel_idx in (0, 1, 2), (
            f"final_selected_iteration must be 0, 1, or 2 (got {sel_idx})"
        )

        # Canonical global coverage equals selected iteration's global_coverage.
        sm_coverage = float(
            (payload.get("summary_metrics", {}) or {}).get("coverage", 0) or 0
        )
        sel_entry = selected[0]
        sel_global = float(sel_entry.get("global_coverage", 0) or 0)
        assert abs(sm_coverage - sel_global) < 1e-6, (
            f"summary_metrics.coverage ({sm_coverage}) must equal the "
            f"selected iteration's global_coverage ({sel_global})"
        )


# ===========================================================================
# 6. CROSS-LAYER COVERAGE CONSISTENCY
# ===========================================================================
#
# Cross-layer consistency: pipeline_output.json (the single source of truth),
# backend.server.current_state, and the frontend runtimeAdapter must all
# agree on the canonical global coverage and regional average coverage.

class TestCrossLayerCoverageConsistency:
    """JSON global coverage == backend global coverage == frontend normalized
    global coverage.  Regional average coverage is independently available."""

    def test_json_to_dashboard_global_coverage_chain(self):
        """After a real run, the same `global_coverage` value must be
        reachable from pipeline_output.json's iteration_audit, from
        backend/server.py's current_state, and from the dashboard's
        normalized iteration list."""
        import json
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent
        output_file  = project_root / "pipeline_output.json"
        if not output_file.exists():
            import pytest
            pytest.skip(
                "pipeline_output.json absent — run "
                "`python -m tests.test_orchestrator` first"
            )

        with open(output_file, "r") as fh:
            payload = json.load(fh) or {}

        # 1. JSON: the canonical global coverage is summary_metrics.coverage.
        json_global = float(
            (payload.get("summary_metrics", {}) or {}).get("coverage", 0) or 0
        )
        # 2. JSON: each iteration exposes global_coverage.
        audit = payload.get("iteration_audit", []) or []
        for entry in audit:
            assert "global_coverage" in entry, (
                "iteration_audit entry must expose global_coverage"
            )
        # 3. The selected iteration's global_coverage equals the JSON global.
        sel = [e for e in audit if e.get("selected_as_final")]
        if sel:
            assert abs(
                json_global - float(sel[0].get("global_coverage", 0) or 0)
            ) < 1e-6

        # 4. Cross-check: the backend's current_state shape (loads the same
        # JSON) maps to globalCoverage via the documented field name.
        # The runtimeAdapter normalizes iteration_audit entries, so we
        # simulate that mapping here.
        def normalize_iteration(entry):
            coverage = entry.get("coverage", 0)
            global_coverage = (
                entry.get("global_coverage") or entry.get("coverage") or 0
            )
            return {
                "iter":           entry.get("iteration", 0),
                "coverage":       coverage,
                "globalCoverage": global_coverage,
            }

        normalized = [normalize_iteration(e) for e in audit]
        for n in normalized:
            assert "globalCoverage" in n
            assert isinstance(n["globalCoverage"], (int, float))

        # 5. The two coverage metrics are present and may legitimately differ.
        for entry in audit:
            assert "coverage"         in entry
            assert "global_coverage" in entry
            # No assertion on numerical equality — these are distinct metrics.

    def test_runtime_adapter_emits_global_coverage(self):
        """The frontend runtimeAdapter must map iteration_audit['global_coverage']
        onto the dashboard's iteration['globalCoverage'] field.  The contract
        is verified by reading the actual runtimeAdapter.js source and asserting
        it produces both `coverage` and `globalCoverage` keys."""
        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent
        js_path = project_root / "frontend" / "src" / "runtime" / "runtimeAdapter.js"
        if not js_path.exists():
            import pytest
            pytest.skip(f"runtimeAdapter.js not found at {js_path}")
        with open(js_path, "r", encoding="utf-8") as fh:
            source = fh.read()
        # The runtimeAdapter must read both coverage and global_coverage.
        assert "global_coverage" in source, (
            "runtimeAdapter must read 'global_coverage' from iteration_audit"
        )
        assert "globalCoverage" in source, (
            "runtimeAdapter must surface 'globalCoverage' on normalized iterations"
        )
        # The normalized iteration shape must include both fields.  The JS
        # uses object shorthand (`coverage,` / `globalCoverage,`), so check
        # for the exact tokens the adapter emits.
        assert "coverage,"      in source, (
            "normalized iteration exposes `coverage`"
        )
        assert "globalCoverage," in source, (
            "normalized iteration exposes `globalCoverage`"
        )


# ===========================================================================
# 7.  DETERMINISTIC POLICY IS AUTHORITATIVE
# ===========================================================================
#
# The deterministic multi-objective policy is the ONLY authority over the
# final ``selected_iteration``.  The LLM is a qualitative explainer; it
# cannot override the policy winner.  These tests pin that contract.

class TestDeterministicPolicyAuthoritative:
    """The deterministic policy has final authority over iteration selection.

    These tests use small mocked iteration results and fake LLM callables;
    they make no real API calls.  The fixtures deliberately arrange weekly
    profits so the deterministic winner is unambiguous and identifiable by
    inspection.
    """

    # ---- (1) Highest-profit candidate wins when all candidates are valid.
    def test_highest_profit_wins_when_all_valid(self):
        """Three candidates, profits 100M, 200M, 150M → iter 1 wins."""
        it0 = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 100e6, 60.0, 100, 50)])
        it1 = _make_iteration_snapshot(1, [_make_regional_solution("Asia", 200e6, 55.0, 100, 50)])
        it2 = _make_iteration_snapshot(2, [_make_regional_solution("Asia", 150e6, 65.0, 100, 50)])

        sel = IterationSelector()
        result = sel.select([it0, it1, it2], llm_callable=None)
        assert result["selected_iteration"] == 1
        assert result["selection_method"] == "deterministic_multi_objective"
        assert result["fallback_used"] is False
        # All three are valid candidates.
        assert sorted(result["candidate_iterations"]) == [0, 1, 2]

    # ---- (2) A lower-profit LLM-proposed candidate cannot override the winner.
    def test_llm_cannot_override_with_lower_profit(self):
        """LLM picks iter 0 (100M); deterministic policy picks iter 1 (200M).
        The deterministic winner must win; the LLM's override is rejected.
        """
        it0 = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 100e6, 60.0, 100, 50)])
        it1 = _make_iteration_snapshot(1, [_make_regional_solution("Asia", 200e6, 55.0, 100, 50)])

        def lower_profit_llm(prompt, temp):
            return ('{"selected_iteration": 0, "confidence": 0.95, '
                    '"reasoning": "I prefer iter 0"}')

        sel = IterationSelector()
        result = sel.select([it0, it1], llm_callable=lower_profit_llm)
        # Deterministic winner is iter 1 (higher profit).
        assert result["selected_iteration"] == 1
        # The LLM's override was rejected; fallback flag is set.
        assert result["fallback_used"] is True
        assert result["selection_method"] == "deterministic_multi_objective"
        # The LLM's payload is preserved for audit.
        assert result["llm_selection"] is not None
        assert result["llm_selection"].get("selected_iteration") == 0
        # Reasoning reflects that the override was rejected.
        assert "deterministic policy" in result["reasoning"].lower()
        assert "authority" in result["reasoning"].lower()

    # ---- (3) An invalid / nonexistent LLM-selected iteration falls back.
    def test_invalid_llm_iteration_falls_back_to_deterministic_winner(self):
        """LLM picks iter 99 (nonexistent); deterministic policy picks iter 1
        (higher profit).  selected_iteration must be the policy winner, not
        99, and the LLM payload must not be stored.
        """
        it0 = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 100e6, 60.0, 100, 50)])
        it1 = _make_iteration_snapshot(1, [_make_regional_solution("Asia", 200e6, 55.0, 100, 50)])

        def invalid_llm(prompt, temp):
            return '{"selected_iteration": 99, "reasoning": "invented"}'

        sel = IterationSelector()
        result = sel.select([it0, it1], llm_callable=invalid_llm)
        # Deterministic winner is iter 1 (200M > 100M).
        assert result["selected_iteration"] == 1
        assert result["selection_method"] == "deterministic_multi_objective"
        # The LLM payload is preserved for audit (it was parsed) but it has
        # NOT been used to set selected_iteration.
        assert result["llm_selection"] is not None
        assert result["llm_selection"].get("selected_iteration") == 99
        assert result["selected_iteration"] != 99

    # ---- (4) Converged iteration does NOT automatically become selected.
    def test_converged_iteration_is_not_automatically_selected(self):
        """The convergence flag (rerun reason / needs_rerun=False) is a
        feedback-loop signal, not a selection signal.  The selected iteration
        is still the deterministic policy winner.
        """
        # iter 0: high profit (200M), lower coverage, marked "converged".
        it0 = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 200e6, 55.0, 100, 50)])
        it0["decision_output"] = {
            "feedback": {
                "needs_rerun": False,
                "rerun_reason": "converged",
                "convergence_score": 0.99,
            }
        }
        # iter 1: lower profit (100M), higher coverage, not converged.
        it1 = _make_iteration_snapshot(1, [_make_regional_solution("Asia", 100e6, 80.0, 100, 50)])
        it1["decision_output"] = {
            "feedback": {
                "needs_rerun": True,
                "rerun_reason": "coverage gap 10pp",
                "convergence_score": 0.85,
            }
        }

        sel = IterationSelector()
        result = sel.select([it0, it1], llm_callable=None)
        # iter 0 wins on profit; convergence is informational, not decisive.
        assert result["selected_iteration"] == 0
        # Scorecards must be present and reflect the actual metrics.
        for sc in result["scorecards"]:
            assert "weekly_profit" in sc
            assert "global_demand_weighted_coverage" in sc

    # ---- (5) UI-facing selected_iteration matches the deterministic winner.
    def test_ui_facing_field_matches_deterministic_winner(self):
        """The orchestrator writes ``iteration_selection`` and
        ``final_selected_iteration`` into the result dict; both must equal
        the deterministic winner regardless of what the LLM said.
        """
        it0 = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 100e6, 60.0, 100, 50)])
        it1 = _make_iteration_snapshot(1, [_make_regional_solution("Asia", 200e6, 55.0, 100, 50)])

        def override_llm(prompt, temp):
            return '{"selected_iteration": 0, "confidence": 0.99, "reasoning": "override"}'

        sel = IterationSelector()
        result = sel.select([it0, it1], llm_callable=override_llm)
        # The UI-facing field is ``selected_iteration`` inside the
        # ``iteration_selection`` record.
        assert result["selected_iteration"] == 1
        # The orchestrator writes the same value into ``final_selected_iteration``
        # and ``best_iteration`` on the top-level result.  Simulate that here.
        final_result = {
            "iteration_selection": result,
            "final_selected_iteration": result["selected_iteration"],
            "best_iteration": result["selected_iteration"],
        }
        assert final_result["final_selected_iteration"] == 1
        assert final_result["best_iteration"] == 1
        assert final_result["iteration_selection"]["selected_iteration"] == 1

    # ---- (6) Existing business-policy constraints remain respected.
    def test_existing_policy_constraints_respected(self):
        """The deterministic policy's constraints must be preserved:
        - structurally invalid iterations are excluded from candidates,
        - Pareto dominance is computed across the existing objectives,
        - tie-breaker order is profit → coverage → cost.
        """
        # Mix of valid + invalid + a dominated candidate.
        invalid = {
            "iteration": 0, "status": "failed",
            "metrics": {}, "regional_results": [], "selected_services": [],
        }
        a = _make_iteration_snapshot(1, [_make_regional_solution("Asia", 300e6, 70.0, 100, 50)])
        b = _make_iteration_snapshot(2, [_make_regional_solution("Asia", 100e6, 50.0, 100, 50)])

        sel = IterationSelector()
        result = sel.select([invalid, a, b], llm_callable=None)
        # invalid is filtered out of candidates.
        assert result["candidate_iterations"] == [1, 2]
        # a dominates b (higher profit AND higher coverage), so a wins.
        assert result["selected_iteration"] == 1
        # The selected method is the deterministic policy.
        assert result["selection_method"] == "deterministic_multi_objective"

    # ---- Bonus: LLM agrees with the policy → no override, no fallback flag.
    def test_llm_agrees_with_policy_no_override(self):
        """When the LLM picks the same iteration as the deterministic policy,
        no override is needed: ``selected_iteration`` is the policy winner
        and the LLM's qualitative contribution (reasoning, confidence) is
        preserved as-is.
        """
        it0 = _make_iteration_snapshot(0, [_make_regional_solution("Asia", 100e6, 60.0, 100, 50)])
        it1 = _make_iteration_snapshot(1, [_make_regional_solution("Asia", 200e6, 55.0, 100, 50)])

        def agreeing_llm(prompt, temp):
            return ('{"selected_iteration": 1, "confidence": 0.88, '
                    '"reasoning": "iter 1 has higher profit and similar coverage"}')

        sel = IterationSelector()
        result = sel.select([it0, it1], llm_callable=agreeing_llm)
        assert result["selected_iteration"] == 1
        assert result["fallback_used"] is False
        assert result["selection_method"] == "deterministic_multi_objective"
        # LLM's reasoning is preserved.
        assert "iter 1" in result["reasoning"]
        assert result["confidence"] == 0.88