"""
Test Network Loader
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.network_loader import NetworkLoader


def test_data_loader():

    print("\n" + "="*70)
    print("TESTING DATA LOADER")
    print("="*70)

    loader = NetworkLoader()

    network = loader.load_network()

    ports = network["ports"]
    demands = network["demands"]
    distance_matrix = network["distance_matrix"]

    print(f"\nPorts loaded: {len(ports)}")
    print(f"Demand lanes loaded: {len(demands)}")
    print(f"Distance matrix size: {len(distance_matrix)}")

    # The loader's default dataset is WorldSmall (data/raw/WorldSmall); the
    # earlier ``len(ports) > 50`` expectation described the WorldLarge defaults.
    assert len(ports) == 47
    assert len(demands) == 1764
    assert len(distance_matrix) == len(ports)

    print("\n✓ Data loader working")


if __name__ == "__main__":
    test_data_loader()