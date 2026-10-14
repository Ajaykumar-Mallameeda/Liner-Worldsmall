"""Output-contract guard for pipeline_output.json.

Phase 0 freezes the schema (see docs/architecture/PIPELINE_OUTPUT_CONTRACT.json).
These tests assert structural expectations that MUST hold in every successful
runtime artifact. Runtime-variable values are not asserted.

Stdlib + a single optional dependency: PyYAML/JSON only — no pytest plugins,
no new external deps (the test must itself not violate the dependency freeze).

If a future phase needs to extend the contract additively, the right path is
to update PIPELINE_OUTPUT_CONTRACT.json + this test in the SAME PR — never to
silently change the production schema.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = REPO_ROOT / "pipeline_output.json"

FROZEN_TOP_LEVEL_KEYS = {
    "orchestrator", "status", "problem_analysis", "regional_results", "decision_output",
    "executive_summary", "summary_metrics", "iteration_audit", "iterations_run",
    "selected_services", "all_selected_services", "iteration_results",
    "iteration_selection", "best_iteration", "final_selected_iteration",
    "health_status", "consensus_result", "shared_context", "llm_runtime_metrics",
    "llm_runtime_aggregate",
    # Added deliberately (network-economics redesign): the verified network plan and its
    # independent ledger. ``status`` is "complete" only when this block is verified.
    "network_ledger",
}
ALLOWED_EXTRA_KEYS = {
    "test_scorecard",  # added by the runner wrapper only
    "maritime_intelligence",  # additive key permitted by IP-5 (Phase 7)
}

FROZEN_SUMMARY_KEYS = {
    "weekly_profit", "annual_profit", "revenue", "operating_cost", "transship_cost",
    "port_cost", "fuel_cost", "total_cost", "cost", "total_services",
    "satisfied_demand", "unserved_demand", "coverage", "total_runtime",
}

FROZEN_SELECTION_KEYS = {
    "candidate_iterations", "pareto_optimal_iterations", "selected_iteration",
    "selection_method", "confidence", "reasoning", "fallback_used", "llm_selection",
    "scorecards", "llm_actuation",
}

FROZEN_REGION_KEYS = {
    "agent", "region", "status", "services_generated", "services_filtered",
    "services_selected", "weekly_profit", "annual_profit", "operating_cost",
    "fuel_cost", "transship_cost", "port_cost", "total_cost", "coverage_percent",
    "satisfied_demand", "unserved_demand", "total_demand", "profit_margin_pct",
    "profit_per_service", "cost_per_service", "uncovered_teu", "hub_ports",
    "archetype_params", "regional_policy", "strategy", "explanation",
    "selected_services", "elapsed_sec", "llm_actuation",
    # Added deliberately (adaptive-budget Phase A/B/C, present in the frozen baseline tree): GA / MILP telemetry
    # of the regional stage.  Diagnostic only, no economic meaning.
    "ga_telemetry", "milp_telemetry",
}

FROZEN_SERVICE_KEYS = {
    "id", "ports", "load", "capacity", "vessel_class", "vessel_cost",
    "fuel_cost", "port_cost", "revenue", "cost", "weekly_profit",
    "margin_pct", "region",
    # Added deliberately: the real time/vessel basis of the service (derived from the
    # distance matrix and class speed, never a constant).
    "frequency_per_week", "vessels", "cycle_time_days",
}


def _artifact():
    if not ARTIFACT.exists():
        pytest.skip(
            f"{ARTIFACT} absent (fresh clone). Skipping contract test; "
            "re-run after a successful pipeline execution."
        )
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_top_level_key_set_is_frozen():
    """Top-level keys are the frozen set + the optional runner-added test_scorecard."""
    data = _artifact()
    keys = set(data.keys())
    extras = keys - FROZEN_TOP_LEVEL_KEYS - ALLOWED_EXTRA_KEYS
    missing = FROZEN_TOP_LEVEL_KEYS - keys
    assert not missing, f"required top-level keys missing: {missing}"
    assert not extras, (
        f"unexpected top-level keys (additive maritime_intelligence key is permitted; "
        f"all others are contract violations): {extras}"
    )


def test_summary_metrics_keys_frozen():
    data = _artifact()
    sm = data["summary_metrics"]
    extras = set(sm) - FROZEN_SUMMARY_KEYS
    missing = FROZEN_SUMMARY_KEYS - set(sm)
    assert not missing, f"summary_metrics missing keys: {missing}"
    assert not extras, f"summary_metrics has unexpected keys: {extras}"


def test_iteration_selection_keys_frozen():
    data = _artifact()
    isel = data["iteration_selection"]
    extras = set(isel) - FROZEN_SELECTION_KEYS
    missing = FROZEN_SELECTION_KEYS - set(isel)
    assert not missing, f"iteration_selection missing keys: {missing}"
    assert not extras, f"iteration_selection has unexpected keys: {extras}"


def test_iteration_budget_three():
    data = _artifact()
    assert data["iterations_run"] == 3
    assert len(data["iteration_audit"]) == 3
    assert len(data["iteration_results"]) == 3


def _expected_region_count():
    """The orchestrator clusters the ports into 3 regions below 50 ports and into 5 otherwise
    (``OrchestratorAgent``: ``n_clusters = 3 if num_ports < 50 else 5``).  WorldSmall has 47 ports -> 3.
    (The test used to hard-code 5, a count that belonged to an earlier larger instance.)"""
    ports_csv = REPO_ROOT / "data" / "raw" / "WorldSmall" / "ports.csv"
    n_ports = sum(1 for line in ports_csv.read_text(encoding="utf-8").splitlines()[1:] if line.strip())
    return 3 if n_ports < 50 else 5


def test_regions_count_and_keys_frozen():
    data = _artifact()
    regions = data["regional_results"]
    expected = _expected_region_count()
    assert len(regions) == expected, f"expected {expected} regional results, got {len(regions)}"
    for i, r in enumerate(regions):
        extras = set(r) - FROZEN_REGION_KEYS
        missing = FROZEN_REGION_KEYS - set(r)
        assert not missing, f"region[{i}] missing keys: {missing}"
        assert not extras, f"region[{i}] has unexpected keys: {extras}"


#: additive keys of the decision phase (leg load factor definitions): see tests/test_utilisation_definitions.py
_UTILISATION_KEYS = {"weekly_capacity_per_leg", "carried_teu_legs", "offered_teu_legs", "leg_load_factor"}


def test_selected_services_keys_frozen():
    data = _artifact()
    services = data["selected_services"]
    assert services, "selected_services must be non-empty on success"
    for i, s in enumerate(services):
        extras = set(s) - FROZEN_SERVICE_KEYS - _UTILISATION_KEYS
        missing = FROZEN_SERVICE_KEYS - set(s)
        assert not missing, f"service[{i}] missing keys: {missing}"
        assert not extras, f"service[{i}] has unexpected keys: {extras}"


def test_selection_authority_invariants():
    """The deterministic-authority invariants must hold in the frozen artifact."""
    data = _artifact()
    assert data["best_iteration"] == data["final_selected_iteration"]
    assert data["best_iteration"] == data["iteration_selection"]["selected_iteration"]
    assert str(data["iteration_selection"]["selection_method"]).startswith("deterministic"), (
        f"selection_method must be deterministic-authoritative: "
        f"{data['iteration_selection']['selection_method']}"
    )


def test_canonic_coverage_invariant():
    """summary_metrics.coverage == coordinator canonical gdwc."""
    data = _artifact()
    assert data["summary_metrics"]["coverage"] == pytest.approx(
        data["decision_output"]["global_metrics"]["global_demand_weighted_coverage"],
        rel=1e-6,
    )
