"""Phase P — controlled full pipeline benchmark.

Runs the orchestrator with the canonical configuration
    MIN_ITERATIONS = 3
    MAX_ITERATIONS = 3
    GA_POPULATION_SIZE = 80
    GA_GENERATIONS = 120
    MILP_TIME_LIMIT = 120
captures wall-clock time and LLM telemetry, then writes
``RUNTIME_PIPELINE_BENCHMARK.json``.

Usage::

    python scripts/run_pipeline_benchmark.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_problem(dataset: str = None):
    """Load the canonical dataset and assemble a ``Problem`` object.

    Args:
        dataset: Instance name. Only "WorldSmall" is supported.
            Defaults to the INSTANCE environment variable, then "WorldSmall".
    """
    from src.data.network_loader import NetworkLoader
    from src.optimization.data import Problem, Fleet
    import os

    instance = dataset or os.environ.get("INSTANCE", "WorldSmall").strip()
    loader = NetworkLoader()

    try:
        if instance.lower() == "worldsmall":
            ws_dir = loader.data_dir / "WorldSmall"
            ports = loader.load_ports(ws_dir / "ports.csv")
            demands = loader.load_demands(ws_dir / "Demand_WorldSmall_Fixed_Sep.csv")
            distance_matrix = loader.load_distance_matrix(ws_dir / "dist_dense.csv")
            fleet = loader.load_fleet(
                ws_dir / "fleet_WorldSmall.csv",
                ws_dir / "fleet_data.csv",
            )
        else:
            # The loader's no-argument defaults are WorldSmall; calling them here would
            # silently load WorldSmall data under a different instance name.
            raise ValueError(
                f"instance {instance!r} is not supported: the loader reads only "
                f"data/raw/WorldSmall (set INSTANCE=WorldSmall)"
            )
    except Exception as e:                                    # noqa: BLE001
        raise RuntimeError(f"dataset load failed: {e}") from e

    # Ensure every port has a row in the matrix.
    for p in ports:
        distance_matrix.setdefault(p.id, {})

    return Problem(
        ports=ports, services=[],
        demands=demands, distance_matrix=distance_matrix,
        fleet=fleet,
    )


def run() -> int:
    from src.agents.orchestrator_agent import OrchestratorAgent
    from src.llm.client import llm_client

    # Reset telemetry so this run stands alone.
    if hasattr(llm_client, "_router") and llm_client._router is not None:
        llm_client._router.attempts = 0
        llm_client._router.successes = 0
        llm_client._router.failures = 0
        llm_client._router.fallback_uses = 0
        llm_client._router.cache_hits = 0
        llm_client._router.provider_switches = 0
        llm_client._router.circuit_breaker_events = 0
        llm_client._router.error_type_counts = {}

    print(f"[bench] MIN_ITER={os.getenv('GA_POPULATION_SIZE', '?')}-style "
          f"config: GA_POP={os.getenv('GA_POPULATION_SIZE')}, "
          f"GA_GEN={os.getenv('GA_GENERATIONS')}, "
          f"MILP={os.getenv('MILP_TIME_LIMIT')}")

    t0 = time.perf_counter()
    orchestrator = OrchestratorAgent()
    problem = _load_problem()
    result = orchestrator.process({"problem": problem})
    total_sec = round(time.perf_counter() - t0, 2)

    telem = llm_client.telemetry() if hasattr(llm_client, "telemetry") else {}

    out = {
        "total_sec": total_sec,
        "iterations": result.get("iterations") if isinstance(result, dict) else None,
        "objective": result.get("objective") if isinstance(result, dict) else None,
        "llm": {
            "attempts": telem.get("attempts"),
            "successes": telem.get("successes"),
            "failures": telem.get("failures"),
            "fallback_uses": telem.get("fallback_uses"),
            "cache_hits": telem.get("cache_hits"),
            "provider_switches": telem.get("provider_switches"),
            "circuit_breaker_events": telem.get("circuit_breaker_events"),
            "error_type_counts": telem.get("error_type_counts", {}),
        },
        "config": {
            "GA_POPULATION_SIZE": os.getenv("GA_POPULATION_SIZE", "80"),
            "GA_GENERATIONS":     os.getenv("GA_GENERATIONS", "120"),
            "MILP_TIME_LIMIT":    os.getenv("MILP_TIME_LIMIT", "120"),
        },
    }
    out_path = PROJECT_ROOT / "RUNTIME_PIPELINE_BENCHMARK.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"[bench] Wrote {out_path}")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
