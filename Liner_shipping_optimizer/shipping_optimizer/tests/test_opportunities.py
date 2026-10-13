"""Issue 5 - executive opportunity register: marginal economics and the status vocabulary."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.opportunities import PathIndex, build_register, network_profit
from src.network.paths import build_paths
from src.network.plan import Candidate, NetworkPlanner
from src.optimization.data import Demand, Fleet, FleetClass, Port, Problem

DM = {"A": {"B": 1000.0, "C": 1600.0}, "B": {"A": 1000.0, "C": 600.0}, "C": {"A": 1600.0, "B": 600.0}}


def _setup(quantity=5, model_quantity=None):
    ports = [Port(p, p, 0.0, 0.0, handling_cost=0.0, port_call_cost=1000.0,
                  transshipment_cost=0.0, variable_port_call_cost=0.0) for p in "ABC"]
    v = FleetClass(vessel_class="V", quantity=model_quantity or quantity, capacity_teu=500.0, tc_rate_daily=3000.0,
                   min_speed=10.0, design_speed=14.0, max_speed=16.0,
                   bunker_consumption_tons_per_day=10.0, idle_consumption_tons_per_day=1.0)
    dem = [Demand("A", "B", 400.0, 1500.0), Demand("B", "A", 300.0, 1500.0), Demand("B", "C", 300.0, 1200.0)]
    pr = Problem(ports=ports, services=[], demands=dem, distance_matrix=DM, fleet=Fleet(classes=[v]))
    pl = NetworkPlanner(pr)
    cands = [Candidate("ab", ("A", "B"), "V"), Candidate("bc", ("B", "C"), "V"), Candidate("abc", ("A", "B", "C"), "V")]
    models, rej = pl.build_models(cands)
    paths, _ = build_paths(pr.demands, models, pl.port_lookup, pl.assumptions, max_paths_per_od=1000, config=pl.path_config)
    return pr, models, paths, rej


def test_profit_of_empty_and_single_service_consistent_with_costs():
    pr, models, paths, _ = _setup()
    idx = PathIndex(paths)
    assert network_profit(models, pr.demands, idx, {})["profit"] == 0.0
    r = network_profit(models, pr.demands, idx, {0: 1})
    assert r["profit"] == pytest.approx(r["margin"] - models[0].weekly_fixed_cost(1))
    assert r["served_teu"] <= 700.0 + 1e-6


def test_register_statuses_and_marginals():
    # models are built with an inflated inventory (as the register tool does) so that candidates that need
    # more vessels than exist are evaluated and reported as CONDITIONALLY_FEASIBLE, not dropped
    pr, models, paths, rej = _setup(quantity=1, model_quantity=20)
    reg = build_register(models, pr.demands, paths, {0: 1}, {"V": 1}, rejected=rej, top_k=10, report_k=10)
    op = reg["operated"][0]
    assert op["operational_status"] == "FEASIBLE"
    # dropping the only service loses its whole profit
    assert op["network_marginal_profit_usd_wk"] == pytest.approx(reg["network"]["profit_usd_wk"])
    # the single vessel is used: every alternative needs vessels that are not idle -> conditional, with the condition stated
    assert reg["opportunities"]
    for o in reg["opportunities"]:
        assert o["operational_status"] == "CONDITIONALLY_FEASIBLE"
        assert o["unmet_conditions"] and o["unmet_conditions"][0]["additional_vessels_required"] >= 1
        assert o["commercial_status"] in ("POSITIVE_MARGIN", "NEGATIVE_MARGIN", "UNCERTAIN")


def test_idle_inventory_makes_an_alternative_feasible():
    pr, models, paths, rej = _setup(quantity=50)
    reg = build_register(models, pr.demands, paths, {0: 1}, {"V": 50}, rejected=rej, top_k=10, report_k=10)
    assert any(o["operational_status"] == "FEASIBLE" for o in reg["opportunities"])
    for o in reg["opportunities"]:
        if o["operational_status"] == "FEASIBLE":
            assert o["unmet_conditions"] == []


def test_rejected_candidates_are_infeasible_with_reasons():
    pr, models, paths, _ = _setup()
    reg = build_register(models, pr.demands, paths, {0: 1}, {"V": 5},
                         rejected=[{"service": "x", "reasons": ["missing_directed_distance"]}], top_k=5, report_k=5)
    assert reg["infeasible"] == [{"service_id": "x", "operational_status": "INFEASIBLE",
                                  "reasons": ["missing_directed_distance"]}]
