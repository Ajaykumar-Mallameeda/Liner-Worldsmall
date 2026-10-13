"""Regional policy under the ACCEPTED architecture (replacement coverage for the retired AI-policy tests).

Background (campaign 2026-10-12, Phase 8).  ``tests/test_regional_agent_activation.py`` was written for
an earlier design in which the LLM's regional policy JSON drove the regional agent (``_filter_services``
took a ``min_margin`` argument; ``AI_APPLIED`` / ``AI_REJECTED`` were emitted for the LLM's policy).
The accepted architecture derives the regional policy from measured regional metrics
(``source = rule-based``, ``RegionalAgent.process``), validates it with
``validate_regional_policy``, and applies the service filter selected by ``LINER_REGIONAL_FILTER``
(``src/services/regional_filter.py``); the LLM only writes explanatory text.  The retired tests'
expectations therefore describe behaviour the system intentionally no longer has.

These tests pin the CURRENT contract so the retirement leaves no coverage gap:
  * the legacy filter's per-service margin test and corridor test are unchanged;
  * the filter takes no policy margin (a policy value cannot change which services are kept);
  * the regional policy in the result is rule-based, validated, tagged ``AI_VALIDATED``, and does not
    depend on what the LLM returned (nor on the LLM failing);
  * a validation failure falls back to ``DEFAULT_REGIONAL_POLICY`` and is tagged ``AI_FALLBACK``.
"""
import inspect
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents import regional_agent as ra_module
from src.agents.regional_agent import RegionalAgent
from src.optimization.adaptive_budget import AdaptiveBudget, compute_complexity_signals
from src.optimization.data import Demand, Port, Problem, Service
from src.validation.regional_policy_validator import DEFAULT_REGIONAL_POLICY

_EMPTY_MILP = {"status": "Optimal", "profit": 0, "cost": 0, "transship_cost": 0, "port_cost": 0,
               "total_cost": 0, "coverage": 0, "satisfied_demand": 0, "direct_demand": 0,
               "transship_demand": 0, "total_demand": 0, "unserved_demand": 0, "selected_services": []}


def _problem():
    ports = [Port(id=f"P{i:03d}", name=f"Port_{i}", latitude=10.0 + i, longitude=20.0 + i * 0.5,
                  handling_cost=50 + i * 10, port_call_cost=1000 + i * 50) for i in range(1, 13)]
    demands = [
        Demand(origin="P001", destination="P002", weekly_teu=5000.0, revenue_per_teu=150.0),
        Demand(origin="P001", destination="P003", weekly_teu=3000.0, revenue_per_teu=150.0),
        Demand(origin="P005", destination="P006", weekly_teu=8000.0, revenue_per_teu=150.0),
        Demand(origin="P010", destination="P011", weekly_teu=2000.0, revenue_per_teu=150.0),
        Demand(origin="P002", destination="P004", weekly_teu=4000.0, revenue_per_teu=150.0),
        Demand(origin="P003", destination="P007", weekly_teu=3000.0, revenue_per_teu=150.0),
    ]
    dm = {f"P{i:03d}": {f"P{j:03d}": 100.0 for j in range(1, 13)} for i in range(1, 13)}
    prob = Problem(ports=ports, services=[], demands=demands, distance_matrix=dm)
    prob.services = [
        Service(id="S001", ports=["P001", "P002"], capacity=5000, weekly_cost=150000),
        Service(id="S002", ports=["P001", "P003"], capacity=3000, weekly_cost=200000),
        Service(id="S003", ports=["P005", "P006"], capacity=8000, weekly_cost=100000),
        Service(id="S004", ports=["P001", "P002", "P003"], capacity=6000, weekly_cost=180000),
        Service(id="S005", ports=["P010", "P011"], capacity=2000, weekly_cost=250000),
        Service(id="S006", ports=["P008", "P009"], capacity=9000, weekly_cost=1000),   # covers no demand
    ]
    return prob


def _budget(problem):
    return AdaptiveBudget.from_signals(compute_complexity_signals(
        num_ports=len(problem.ports), demands=problem.demands, fleet=None))


class TestLegacyFilterContract:
    @pytest.fixture(autouse=True)
    def _legacy(self, monkeypatch):
        monkeypatch.setenv("LINER_REGIONAL_FILTER", "legacy")

    def test_margin_test_and_corridor_test(self):
        """capacity x 0.5 x 150 > weekly cost, and both ports of a demand corridor on the rotation."""
        pr = _problem()
        agent = RegionalAgent(name="arch", region="Test", model="test")
        kept = {s.id for s in agent._filter_services(pr, _budget(pr)).services}
        # S001: 375,000 > 150,000   S002: 225,000 > 200,000   S003: 600,000 > 100,000   S004: 450,000 > 180,000
        assert {"S001", "S002", "S003", "S004"} <= kept
        assert "S005" not in kept            # 150,000 < 250,000 : fails the margin test
        assert "S006" not in kept            # no corridor: fails the coverage test

    def test_filter_takes_no_policy_margin(self):
        params = list(inspect.signature(RegionalAgent._filter_services).parameters)
        assert params == ["self", "problem", "adaptive_budget"], params


def _run(agent, problem, llm):
    """RegionalAgent.process with the heavy collaborators mocked; returns (result, info-call list)."""
    with patch.object(agent, "call_llm", **llm):
        with patch("src.agents.regional_agent.ServiceGeneratorAgent") as svc:
            svc.return_value.process.return_value = {"services": []}
            with patch("src.agents.regional_agent.HierarchicalGA") as ga:
                ga.return_value.run.return_value = {"services": [], "frequencies": [],
                                                    "coverage_estimate": 0.0, "skip_milp": False}
                with patch("src.agents.regional_agent.HubMILP") as milp:
                    milp.return_value.solve.return_value = dict(_EMPTY_MILP)
                    with patch.object(agent, "split_by_hubs", return_value={"hub": problem.ports}):
                        with patch.object(agent, "_filter_services", return_value=problem):
                            with patch.object(ra_module.logger, "info") as info:
                                out = agent.process({"problem": problem})
    return out, info


def _tags(info: MagicMock):
    tags = []
    for call in info.call_args_list:
        args, kwargs = call
        if "tag" in kwargs:
            tags.append(kwargs["tag"])
        elif args and isinstance(args[0], str) and "tag=%s" in args[0]:
            idx = args[0].split("tag=%s")[0].count("%s")
            if 1 + idx < len(args):
                tags.append(args[1 + idx])
    return tags


class TestRuleBasedPolicy:
    def test_policy_is_validated_and_tagged(self):
        agent = RegionalAgent(name="arch_a", region="Test", model="test")
        out, info = _run(agent, _problem(), dict(side_effect=Exception("LLM provider unavailable")))
        assert "AI_VALIDATED" in _tags(info)
        pol = out["regional_policy"]
        for k in ("coverage_priority", "profit_priority", "min_service_margin", "vessel_bias"):
            assert k in pol
        assert 0.0 <= pol["coverage_priority"] <= 1.0 and 0.0 <= pol["profit_priority"] <= 1.0

    def test_policy_does_not_depend_on_the_llm_text(self):
        aggressive = json.dumps({"coverage_priority": 0.95, "profit_priority": 0.05, "min_service_margin": 0.3,
                                 "vessel_bias": "large", "hub_focus": ["P001"], "notes": "x"})
        a, _ = _run(RegionalAgent(name="arch_b1", region="Test", model="test"), _problem(),
                    dict(return_value=aggressive))
        b, _ = _run(RegionalAgent(name="arch_b2", region="Test", model="test"), _problem(),
                    dict(return_value="not json at all {{{"))
        assert a["regional_policy"] == b["regional_policy"]

    def test_validation_failure_falls_back_to_the_default_policy(self):
        agent = RegionalAgent(name="arch_c", region="Test", model="test")
        with patch.object(ra_module, "validate_regional_policy", side_effect=ValueError("bad policy")):
            out, info = _run(agent, _problem(), dict(return_value="{}"))
        assert "AI_FALLBACK" in _tags(info)
        assert out["regional_policy"] == DEFAULT_REGIONAL_POLICY
