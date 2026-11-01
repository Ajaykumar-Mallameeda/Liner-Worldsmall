"""
benchmarks/benchmark_performance.py

Runtime and memory profiling for the optimization pipeline.
Run from the shipping_optimizer/ directory:

    python benchmarks/benchmark_performance.py [--quick] [--instance large]
"""

import argparse
import json
import time
import sys
import tracemalloc
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))


def benchmark_clustering(problem) -> Dict[str, Any]:
    from src.decomposition.port_clustering import PortClustering

    start = time.perf_counter()
    clustering = PortClustering(n_clusters=5)
    clusters = clustering.cluster_ports(problem.ports)
    elapsed = time.perf_counter() - start

    return {
        "component": "PortClustering",
        "elapsed_sec": round(elapsed, 3),
        "clusters": len(clusters),
        "ports_assigned": sum(len(v) for v in clusters.values()),
    }


def benchmark_service_generation(problem) -> Dict[str, Any]:
    from src.agents.service_generator_agent import ServiceGeneratorAgent
    from src.utils.config import Config

    agent = ServiceGeneratorAgent(name="bench_svc_gen", model=Config.REGIONAL_MODEL)
    start = time.perf_counter()
    services = agent.generate_services(problem)
    elapsed = time.perf_counter() - start

    return {
        "component": "ServiceGeneratorAgent",
        "elapsed_sec": round(elapsed, 3),
        "services_generated": len(services),
    }


def benchmark_ga(problem) -> Dict[str, Any]:
    from src.optimization.hierarchical_ga import HierarchicalGA

    ga = HierarchicalGA(problem, pop_size=40, generations=30, max_runtime_sec=30.0)
    start = time.perf_counter()
    chromosome = ga.run()
    elapsed = time.perf_counter() - start

    return {
        "component": "HierarchicalGA",
        "elapsed_sec": round(elapsed, 3),
        "services_selected": sum(chromosome["services"]),
        "coverage_estimate_pct": round(chromosome["coverage_estimate"], 2),
        "_chromosome": chromosome,
    }


def benchmark_milp(problem, chromosome) -> Dict[str, Any]:
    from src.optimization.hub_milp import HubMILP

    milp = HubMILP(problem, chromosome, time_limit=60)
    start = time.perf_counter()
    result = milp.solve()
    elapsed = time.perf_counter() - start

    return {
        "component": "HubMILP",
        "elapsed_sec": round(elapsed, 3),
        "status": result["status"],
        "coverage_pct": round(result["coverage"], 2),
        "profit_usd": round(result["profit"], 0),
        "transfer_pairs": result["num_transfer_vars"],
    }


def load_problem(instance: str):
    from src.data.network_loader import NetworkLoader
    from src.optimization.data import Problem, Port, Service, Demand

    path = f"data/datasets/{instance}_shipping_problem.json"
    with open(path) as f:
        data = json.load(f)

    loader = NetworkLoader()
    distance_matrix = loader.load_distance_matrix()

    return Problem(
        ports=[Port(**p) for p in data["ports"]],
        services=[Service(**s) for s in data["services"]],
        demands=[Demand(**d) for d in data["demands"]],
        distance_matrix=distance_matrix,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Skip GA and MILP")
    parser.add_argument("--instance", default="large", help="Dataset instance name")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  LINER SHIPPING OPTIMIZER — PERFORMANCE BENCHMARKS")
    print(f"  Instance : {args.instance}")
    print(f"  Mode     : {'quick (clustering + service gen only)' if args.quick else 'full'}")
    print(f"{'='*60}\n")

    tracemalloc.start()
    wall_start = time.perf_counter()

    print("Loading problem...")
    problem = load_problem(args.instance)
    print(f"  {len(problem.ports)} ports  |  {len(problem.demands)} demands  |  "
          f"{len(problem.services)} candidate services\n")

    results = []

    print("Benchmarking PortClustering...")
    r = benchmark_clustering(problem)
    results.append(r)
    print(f"  {r['elapsed_sec']:.3f}s  →  {r['clusters']} clusters, "
          f"{r['ports_assigned']} ports assigned\n")

    print("Benchmarking ServiceGeneratorAgent...")
    r = benchmark_service_generation(problem)
    results.append(r)
    print(f"  {r['elapsed_sec']:.3f}s  →  {r['services_generated']} services generated\n")

    chromosome = None
    if not args.quick:
        print("Benchmarking HierarchicalGA (pop=40, gen=30, budget=30s)...")
        r = benchmark_ga(problem)
        chromosome = r.pop("_chromosome")
        results.append(r)
        print(f"  {r['elapsed_sec']:.3f}s  →  {r['services_selected']} selected, "
              f"{r['coverage_estimate_pct']}% estimated coverage\n")

        if chromosome:
            print("Benchmarking HubMILP (time_limit=60s)...")
            r = benchmark_milp(problem, chromosome)
            results.append(r)
            print(f"  {r['elapsed_sec']:.3f}s  →  {r['status']}, "
                  f"{r['coverage_pct']}% coverage, "
                  f"${r['profit_usd']:,.0f} profit, "
                  f"{r['transfer_pairs']} transfer pairs\n")

    total_wall = time.perf_counter() - wall_start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"{'='*60}")
    print(f"  Total wall time : {total_wall:.2f}s")
    print(f"  Peak memory     : {peak / 1024**2:.1f} MB")
    print(f"{'='*60}\n")
    print(f"  {'Component':<30} {'Time (s)':>10}")
    print(f"  {'-'*42}")
    for r in results:
        print(f"  {r['component']:<30} {r['elapsed_sec']:>10.3f}")
    print()


if __name__ == "__main__":
    main()
