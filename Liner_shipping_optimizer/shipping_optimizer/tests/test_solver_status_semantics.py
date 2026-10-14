"""Application-level conclusion of a MILP solve (never "Optimal" for an unclosed, gapped incumbent)."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.reconcile import _capped_gap, _capped_model_block, _final_plan_block
from src.network.solve_semantics import classify_final_plan, classify_solve

KW = dict(usable=True, closed=False, restricted=False, time_limit_reached=False, incumbent=30e6, bound=40e6)


def test_proven_optimum_needs_closure_and_the_whole_model():
    c = classify_solve(**{**KW, "closed": True, "incumbent": 40e6})
    assert c["conclusion"] == "proven_optimal" and c["proven_optimal"] is True and c["gap_pct_of_bound"] == 0.0


def test_closed_on_the_restricted_set_is_not_a_global_proof():
    c = classify_solve(**{**KW, "closed": True, "restricted": True})
    assert c["conclusion"] == "optimal_for_restricted_service_set" and c["proven_optimal"] is False


def test_time_limited_incumbent_with_a_material_gap_is_not_optimal():
    c = classify_solve(**{**KW, "time_limit_reached": True})
    assert c["conclusion"] == "feasible_time_limit_gap_unresolved" and c["proven_optimal"] is False
    assert c["gap_pct_of_bound"] == pytest.approx(25.0)


def test_unclosed_without_time_limit_is_gap_unresolved():
    assert classify_solve(**KW)["conclusion"] == "feasible_gap_unresolved"


def test_small_gap_is_within_tolerance_but_still_not_proven():
    c = classify_solve(**{**KW, "incumbent": 39.8e6, "time_limit_reached": True})
    assert c["conclusion"] == "feasible_within_gap_tolerance" and c["proven_optimal"] is False


def test_no_incumbent():
    c = classify_solve(**{**KW, "usable": False, "incumbent": None})
    assert c["conclusion"] == "no_incumbent" and c["gap_usd_per_week"] is None


def test_incumbent_above_bound_is_flagged_not_a_negative_gap():
    c = classify_solve(**{**KW, "incumbent": 45e6})
    assert c["incumbent_exceeds_bound"] is True and c["gap_usd_per_week"] is None and c["gap_pct_of_bound"] is None


def test_final_plan_above_bound_makes_no_optimality_claim():
    f = classify_final_plan(final=45e6, bound=40e6)
    assert f["exceeds_capped_model_bound"] and f["optimality_claim"] == "none"
    assert "different_model" in f["conclusion"]
    g = classify_final_plan(final=35e6, bound=40e6)
    assert not g["exceeds_capped_model_bound"] and g["optimality_claim"] == "none"


def _plan(**ms):
    base = {"incumbent_profit_usd_per_week": 30e6, "relaxation_bound_usd_per_week": 40e6, "status": "feasible",
            "solver_status": "Optimal"}
    base.update(ms)
    return SimpleNamespace(milp_stage=base, flow_reopt={"applied": True}, local_search={"applied": False}), \
        SimpleNamespace(operating_profit=45e6)


def test_report_keeps_the_raw_status_and_adds_the_conclusion():
    plan, led = _plan(**classify_solve(**{**KW, "time_limit_reached": True}))
    blk = _capped_model_block(plan, led)
    assert blk["solver_status"] == "Optimal"                       # raw backend value preserved
    assert blk["conclusion"] == "feasible_time_limit_gap_unresolved" and blk["proven_optimal"] is False
    assert "does not by itself prove optimality" in blk["solver_status_semantics"]
    assert _final_plan_block(plan, led)["optimality_claim"] == "none"


def test_legacy_plan_without_closure_facts_is_never_reported_proven():
    plan, led = _plan()                                            # no conclusion keys: older artifact shape
    assert _capped_model_block(plan, led)["conclusion"] != "proven_optimal"
    assert _capped_gap(plan)[0] == pytest.approx(10e6)
