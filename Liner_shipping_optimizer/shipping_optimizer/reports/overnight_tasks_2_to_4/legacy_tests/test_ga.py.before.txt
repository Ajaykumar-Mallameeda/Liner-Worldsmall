"""
Test all Genetic Algorithms
(ServiceGA, FrequencyGA, HierarchicalGA)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.network_loader import NetworkLoader
from src.services.candidate_service_generator import CandidateServiceGenerator
from src.optimization.service_ga import ServiceGA
from src.optimization.frequency_ga import FrequencyGA
from src.optimization.hierarchical_ga import HierarchicalGA
from src.optimization.data import Problem
from src.optimization.data import Service

def test_genetic_algorithms():

    print("\n" + "="*70)
    print("TESTING GENETIC ALGORITHMS")
    print("="*70)

    # --------------------------------
    # Load dataset
    # --------------------------------
    loader = NetworkLoader()
    network = loader.load_network()

    # --------------------------------
    # Build problem object
    # --------------------------------
    problem = Problem(
        ports=network["ports"],
        services=[],
        demands=network["demands"],
        distance_matrix=network["distance_matrix"]
    )

    # --------------------------------
    # Generate candidate services
    # --------------------------------
    generator = CandidateServiceGenerator(problem)

    services = generator.generate_services()

    # ---------------------------------------
    # Convert dict services → Service objects
    # ---------------------------------------

    normalized_services = []

    for i, s in enumerate(services):

        if isinstance(s, Service):
            normalized_services.append(s)

        else:
            normalized_services.append(
                Service(
                    id=s.get("id", f"svc_{i}"),
                    ports=s["ports"],
                    capacity=s.get("capacity", 5000),
                    weekly_cost=s.get("weekly_cost", 800000),
                    cycle_time=s.get("cycle_time", 28)
                )
            )

    problem.services = normalized_services
    # =================================================
    # Test Service GA
    # =================================================

    print("\n--- Testing ServiceGA ---")

    service_ga = ServiceGA(problem)

    best_services = service_ga.run()

    assert isinstance(best_services, list)
    assert len(best_services) == len(services)

    selected = sum(best_services)

    print("Selected services:", selected)

    assert selected > 0

    # =================================================
    # Test Frequency GA
    # =================================================

    print("\n--- Testing FrequencyGA ---")

    freq_ga = FrequencyGA(problem, best_services)

    best_freq = freq_ga.run()

    assert isinstance(best_freq, list)
    assert len(best_freq) == len(services)

    active_freq = sum(1 for f in best_freq if f > 0)

    print("Services with frequency:", active_freq)

    assert active_freq > 0

    # =================================================
    # Test Hierarchical GA
    # =================================================

    print("\n--- Testing HierarchicalGA ---")

    hierarchical_ga = HierarchicalGA(problem)

    result = hierarchical_ga.run()

    assert isinstance(result, dict)
    assert "services" in result
    assert "frequencies" in result

    assert len(result["services"]) == len(services)
    assert len(result["frequencies"]) == len(services)

    selected_services = sum(result["services"])

    print("Hierarchical GA selected services:", selected_services)

    assert selected_services > 0

    print("\n✓ All GA modules working correctly")
    

if __name__ == "__main__":
    test_genetic_algorithms()