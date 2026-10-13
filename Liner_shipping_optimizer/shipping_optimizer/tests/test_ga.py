"""
Test all Genetic Algorithms (ServiceGA, FrequencyGA, HierarchicalGA).

The GAs now price every candidate through the canonical service model
(``src/network/economics.py``): sailing time from the distance matrix and the
class design speed, 24 h per port call, vessels = ceil(T * f / 7), fuel from the
fleet specification.  A candidate without a vessel class / fleet / distance is
not "priced with a default" -- it is excluded.  Therefore this test loads the REAL
fleet and builds candidates through the production generator (the earlier version
fabricated capacity=5000 / weekly_cost=800000 / cycle=28 for every service, which
the model now correctly refuses).

Frequency is not a hard-coded constant any more: each service's ceiling is
floor(7 * class_inventory / T) from its real rotation time.
"""

import math
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
from src.optimization.frequency_ga import FrequencyGA
from src.optimization.hierarchical_ga import HierarchicalGA
from src.optimization.service_ga import ServiceGA


def _build_problem(seed: int = 4242) -> Problem:
    loader = NetworkLoader()
    network = loader.load_network()
    problem = Problem(
        ports=network["ports"],
        services=[],
        demands=network["demands"],
        distance_matrix=network["distance_matrix"],
        fleet=loader.load_fleet(),
    )
    random.seed(seed)
    np.random.seed(seed)
    problem.services = ServiceGeneratorAgent(name="ga_test", model="none").generate_services(problem)
    return problem


def _vessels_by_class(problem, mask, freq):
    models = service_models_for(problem)
    used = defaultdict(int)
    for i, (m, f) in enumerate(zip(mask, freq)):
        if m and f > 0:
            assert models[i] is not None, f"service {problem.services[i].id} is selected but unmodellable"
            used[models[i].vessel_class] += models[i].vessels(int(f))
    return used


def test_genetic_algorithms():

    print("\n" + "=" * 70)
    print("TESTING GENETIC ALGORITHMS")
    print("=" * 70)

    problem = _build_problem()
    n = len(problem.services)
    assert n > 0
    inventory = {c.vessel_class: int(c.quantity) for c in problem.fleet.classes}
    models = service_models_for(problem)

    # =================================================
    # Service GA
    # =================================================
    print("\n--- Testing ServiceGA ---")
    random.seed(1)
    np.random.seed(1)
    service_ga = ServiceGA(problem, pop_size=40, generations=20)
    best_services = service_ga.run()

    assert isinstance(best_services, list)
    assert len(best_services) == n
    assert set(best_services) <= {0, 1}
    selected = sum(best_services)
    print("Selected services:", selected)
    assert selected > 0
    # a selected service must be modellable (real rotation time + fleet class)
    assert all(models[i] is not None for i, b in enumerate(best_services) if b)

    # =================================================
    # Frequency GA
    # =================================================
    print("\n--- Testing FrequencyGA ---")
    random.seed(2)
    np.random.seed(2)
    freq_ga = FrequencyGA(problem, best_services, pop_size=40, generations=20)
    best_freq = freq_ga.run()

    assert isinstance(best_freq, list)
    assert len(best_freq) == n
    assert all(isinstance(f, (int, np.integer)) and f >= 0 for f in best_freq)
    assert sum(1 for f in best_freq if f > 0) > 0
    # unselected services never get frequency; selected ones obey the real-time ceiling
    for i, f in enumerate(best_freq):
        if not best_services[i]:
            assert f == 0
        elif f > 0:
            assert f <= models[i].max_departures(inventory[models[i].vessel_class]), (
                problem.services[i].id)
    used = _vessels_by_class(problem, best_services, best_freq)
    assert all(used[k] <= inventory[k] for k in used), dict(used)

    # =================================================
    # Hierarchical GA
    # =================================================
    print("\n--- Testing HierarchicalGA ---")
    random.seed(3)
    np.random.seed(3)
    result = HierarchicalGA(problem, pop_size=40, generations=20, max_runtime_sec=120).run()

    assert isinstance(result, dict)
    assert "services" in result
    assert "frequencies" in result
    # HierarchicalGA pre-filters problem.services IN PLACE (unmodellable services and
    # services touching no admissible demand corridor leave the pool); the chromosome
    # indexes the filtered list, as the regional agent and HubMILP consume it.
    n_kept = len(problem.services)
    assert 0 < n_kept <= n
    assert len(result["services"]) == n_kept
    assert len(result["frequencies"]) == n_kept
    assert sum(result["services"]) > 0
    assert all(m is not None for m in service_models_for(problem)), "an unmodellable service survived"

    # mask/frequency agreement: no zero-frequency service is counted as operated,
    # no unselected service carries frequency
    for m, f in zip(result["services"], result["frequencies"]):
        assert (m == 1) == (f > 0)

    # the vessels the chromosome needs fit the real fleet inventory, per class
    used = _vessels_by_class(problem, result["services"], result["frequencies"])
    assert all(used[k] <= inventory[k] for k in used), (dict(used), inventory)
    assert sum(used.values()) <= sum(inventory.values())
    if "vessels_by_class" in result:
        assert {k: int(v) for k, v in result["vessels_by_class"].items()} == dict(used)

    print("\n[ok] All GA modules working correctly on the real fleet")


def test_frequency_follows_real_rotation_time():
    """The frequency ceiling is derived from time actually taken, not constant."""
    problem = _build_problem(seed=7)
    models = [m for m in service_models_for(problem) if m is not None]
    assert models
    # distinct rotation times produce distinct vessel needs and distinct ceilings
    assert len({m.cycle_time_days for m in models}) > 1
    assert len({m.max_departures() for m in models}) > 1
    for m in models:
        # time actually taken = sailing + port stays; the declared cycle is its ceiling
        assert m.cycle_days == pytest.approx(m.sea_days + m.port_days, rel=1e-9)
        assert m.cycle_days > 0 and m.cycle_days <= m.cycle_time_days < m.cycle_days + 1
        # vessels(f) is exactly ceil(T * f / 7); no vessels for no departures
        for f in (1, 2, 5):
            assert m.vessels(f) == math.ceil(m.cycle_time_days * f / 7.0 - 1e-9)
        assert m.vessels(0) == 0
        # the ceiling is what the class inventory can sustain, and one more is not
        top = m.max_departures()
        assert m.vessels(top) <= m.class_inventory
        assert m.vessels(top + 1) > m.class_inventory


if __name__ == "__main__":
    test_genetic_algorithms()
    test_frequency_follows_real_rotation_time()
