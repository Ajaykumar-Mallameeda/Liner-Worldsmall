"""
Test Regional Agent
"""

import math
import sys
from pathlib import Path
from src.data.network_loader import NetworkLoader

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.regional_agent import RegionalAgent
from src.optimization.data import Problem
from src.utils.config import Config


def load_problem():
    """The canonical WorldSmall Problem (ports, demands, directed distances, fleet).

    This helper used to combine ``data/datasets/large_shipping_problem.json``
    (WorldLarge ports and demands) with ``NetworkLoader().load_distance_matrix()``
    -- which now returns the WorldSmall matrix -- so most legs were missing and
    were silently priced at an invented 500 nm. A single, isolated dataset is
    used instead.
    """
    return NetworkLoader().load_problem()


def test_regional_agent():

    print("\n" + "="*70)
    print("TESTING REGIONAL AGENT")
    print("="*70)

    agent = RegionalAgent(
        name="regional_asia",
        region="Asia",
        model=Config.REGIONAL_MODEL
    )

    problem = load_problem()

    result = agent.process({"problem": problem})

    print(f"\nservices_generated: {result['services_generated']}")
    print(f"services_filtered: {result['services_filtered']}")
    print(f"services_selected: {result['services_selected']}")
    print(f"weekly_profit: ${result['weekly_profit']:,.0f}")
    print(f"operating_cost: ${result['operating_cost']:,.0f}")
    print(f"coverage: {result['coverage_percent']:.1f}%")

    # Structural integrity only (the economics are audited elsewhere): the run
    # produced a candidate pool, finite money fields and a coverage in [0, 100].
    assert result["services_generated"] > 0
    assert result["services_filtered"] <= result["services_generated"]
    for key in ("weekly_profit", "operating_cost", "total_cost"):
        assert math.isfinite(result[key]), key
    assert 0.0 <= result["coverage_percent"] <= 100.0


if __name__ == "__main__":
    test_regional_agent()
