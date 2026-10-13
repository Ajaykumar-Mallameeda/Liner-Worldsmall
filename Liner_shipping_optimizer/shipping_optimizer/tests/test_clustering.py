"""
Test Port Clustering
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.network_loader import NetworkLoader
from src.decomposition.port_clustering import PortClustering


def test_clustering():

    print("\n" + "="*70)
    print("TESTING PORT CLUSTERING")
    print("="*70)

    loader = NetworkLoader()
    network = loader.load_network()

    ports = network["ports"]

    clustering = PortClustering()

    clusters = clustering.cluster_ports(ports)

    print(f"\nClusters created: {len(clusters)}")

    for cid, pids in clusters.items():
        print(f"Cluster {cid}: {len(pids)} ports")

    assert len(clusters) > 0

    print("\n✓ Clustering working")


if __name__ == "__main__":
    test_clustering()