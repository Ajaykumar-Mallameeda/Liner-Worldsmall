"""
Test Hub MILP optimizer (path-based network model with transshipment).

HubMILP is now an adapter over ``src/network`` (one canonical service model, one
independent ledger). The reported ``profit`` is the LEDGER's true operating profit
(revenue - vessel hire - fuel - port calls - handling/transshipment), recomputed
from raw primitives rather than copied from the solver objective.

The earlier version of this test activated the first 100 candidates at frequency 1
without a fleet and with fabricated capacity/cost/cycle defaults. Such a chromosome
needs far more vessels than exist, so it is now an explicit ``Infeasible`` status
(tested below), not a silent "optimal".
"""

import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.service_generator_agent import ServiceGeneratorAgent
from src.data.network_loader import NetworkLoader
from src.network.economics import service_models_for
from src.optimization.data import Problem
from src.optimization.hub_milp import HubMILP


@pytest.fixture(scope="module")
def problem():
    loader = NetworkLoader()
    network = loader.load_network()
    p = Problem(
        ports=network["ports"],
        services=[],
        demands=network["demands"],
        distance_matrix=network["distance_matrix"],
        fleet=loader.load_fleet(),
    )
    random.seed(99)
    np.random.seed(99)
    p.services = ServiceGeneratorAgent(name="milp_test", model="none").generate_services(p)
    return p


def _fleet_feasible_chromosome(problem, max_services=100):
    """Greedy: activate services in pool order at f = 1 while the per-class inventory
    holds (vessels = ceil(T / 7) each)."""
    models = service_models_for(problem)
    inventory = {c.vessel_class: int(c.quantity) for c in problem.fleet.classes}
    used = defaultdict(int)
    mask = [0] * len(problem.services)
    freq = [0] * len(problem.services)
    picked = 0
    for i, m in enumerate(models):
        if m is None or picked >= max_services:
            continue
        need = m.vessels(1)
        if used[m.vessel_class] + need <= inventory[m.vessel_class]:
            used[m.vessel_class] += need
            mask[i], freq[i] = 1, 1
            picked += 1
    return {"services": mask, "frequencies": freq}, dict(used)


def test_milp(problem):

    print("\n" + "=" * 70)
    print("TESTING HUB MILP")
    print("=" * 70)

    print(f"\nPorts: {len(problem.ports)}")
    print(f"Demands: {len(problem.demands)}")
    print(f"Candidate services generated: {len(problem.services)}")

    chromosome, used = _fleet_feasible_chromosome(problem)
    assert sum(chromosome["services"]) > 0

    milp = HubMILP(problem, chromosome, time_limit=120)
    result = milp.solve()

    print("\nMILP result:")
    for k in ("status", "valid", "profit", "revenue", "total_cost", "coverage",
              "satisfied_demand", "num_services_used"):
        print(f"{k}: {result.get(k)}")

    assert result["status"] in ["Optimal", "Optimal Solution Found"]
    assert result["valid"] is True
    assert result["profit"] is not None
    assert result["num_services_used"] > 0
    # (the legacy ``num_variables`` key never existed on HubMILP results; the model
    # size is reported as direct + transfer path variables)
    assert result["num_direct_vars"] + result["num_transfer_vars"] >= 0
    assert result["satisfied_demand"] >= 0

    # accounting identity (the ledger's own numbers)
    assert result["profit"] == pytest.approx(result["revenue"] - result["total_cost"], rel=1e-9)
    assert result["total_cost"] == pytest.approx(
        result["cost"] + result["fuel_cost"] + result["port_cost"] + result["transship_cost"],
        rel=1e-6, abs=1.0)
    assert result["satisfied_demand"] + result["unserved_demand"] == pytest.approx(
        result["total_demand"], rel=1e-9)
    assert 0.0 <= result["coverage"] <= 100.0 + 1e-9

    # the vessels the plan needs fit each class inventory
    inventory = {c.vessel_class: int(c.quantity) for c in problem.fleet.classes}
    for cls, n in result["vessels_by_class"].items():
        assert n <= inventory[cls], (cls, n, inventory[cls])

    # every operated service reports the REAL time it takes and the vessels it ties up
    rows = result["selected_services"]
    assert rows
    for r in rows:
        assert r["frequency_per_week"] >= 1
        assert r["cycle_time_days"] > 0
        assert r["vessels"] == -(-r["cycle_time_days"] * r["frequency_per_week"] // 7)

    print("\n[ok] Hub MILP working with transshipment")


def test_milp_over_subscribed_chromosome_is_explicit_infeasible(problem):
    """100 services at f=1 is more vessels than the fleet owns -> an explicit status."""
    n = len(problem.services)
    models = service_models_for(problem)
    mask = [1 if (i < 100 and models[i] is not None) else 0 for i in range(n)]
    chromosome = {"services": mask, "frequencies": list(mask)}
    needed = defaultdict(int)
    for i, m in enumerate(models):
        if mask[i]:
            needed[m.vessel_class] += m.vessels(1)
    inventory = {c.vessel_class: int(c.quantity) for c in problem.fleet.classes}
    if all(needed[c] <= inventory[c] for c in needed):
        pytest.skip("first 100 candidates happen to fit the fleet for this pool")

    result = HubMILP(problem, chromosome, time_limit=60).solve()
    assert result["status"] == "Infeasible"
    assert result["valid"] is False
    assert result["satisfied_demand"] == 0.0
    assert "fleet" in str(result.get("message", "")).lower() or result.get("violations")


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
