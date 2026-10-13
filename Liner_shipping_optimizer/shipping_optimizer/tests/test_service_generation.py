"""
Test Candidate Service Generator
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.network_loader import NetworkLoader
from src.services.candidate_service_generator import CandidateServiceGenerator
from src.optimization.data import Problem


def test_service_generation():

    print("\n" + "="*70)
    print("TESTING SERVICE GENERATION")
    print("="*70)

    loader = NetworkLoader()
    network = loader.load_network()

    problem = Problem(
        ports=network["ports"],
        services=[],
        demands=network["demands"],
        distance_matrix=network["distance_matrix"]
    )

    generator = CandidateServiceGenerator(problem)

    services = generator.generate_services()

    print(f"\nServices generated: {len(services)}")

    assert len(services) > 0

    print("\n✓ Service generation working")


if __name__ == "__main__":
    test_service_generation()