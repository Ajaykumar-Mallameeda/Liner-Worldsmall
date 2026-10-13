"""
Test Hub MILP optimizer (supports transshipment version)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.network_loader import NetworkLoader
from src.services.candidate_service_generator import CandidateServiceGenerator
from src.optimization.hub_milp import HubMILP
from src.optimization.data import Problem, Service

def test_milp():


    print("\n" + "="*70)
    print("TESTING HUB MILP")
    print("="*70)

    # --------------------------------
    # Load network data
    # --------------------------------

    loader = NetworkLoader()
    network = loader.load_network()

    print(f"\nPorts: {len(network['ports'])}")
    print(f"Demands: {len(network['demands'])}")

    # --------------------------------
    # Create problem object
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

    # Normalize services
    normalized_services = []

    for i, s in enumerate(services):

        if isinstance(s, Service):
            normalized_services.append(s)

        else:
            normalized_services.append(
                Service(
                    id=f"svc_{i}",
                    ports=s["ports"],
                    capacity=s.get("capacity", 5000),
                    weekly_cost=s.get("weekly_cost", 800000),
                    cycle_time=s.get("cycle_time", 28)
                )
            )

    problem.services = normalized_services

    print(f"Candidate services generated: {len(problem.services)}")

    # --------------------------------
    # Activate subset of services
    # --------------------------------

    n = len(problem.services)
    active = min(100, n)

    chromosome = {
        "services": [1 if i < active else 0 for i in range(n)],
        "frequencies": [1 if i < active else 0 for i in range(n)]
    }

    # --------------------------------
    # Run MILP
    # --------------------------------

    milp = HubMILP(problem, chromosome)

    result = milp.solve()

    # -----------------------------------------
    # Print results
    # -----------------------------------------
    print("\nMILP result:")
    for k, v in result.items():
        print(f"{k}: {v}")

    # -----------------------------------------
    # Assertions
    # -----------------------------------------
    assert result["status"] in ["Optimal", "Optimal Solution Found"]
    assert result["profit"] is not None
    assert result["num_services_used"] > 0
    assert result["num_variables"] >= 0
    assert result["satisfied_demand"] >= 0

    print("\n✓ Hub MILP working with transshipment")


if __name__ == "__main__":
    test_milp()
