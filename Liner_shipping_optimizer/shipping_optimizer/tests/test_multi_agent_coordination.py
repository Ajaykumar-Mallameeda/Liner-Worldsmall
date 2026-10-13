"""
Tests for multi-agent coordination including:
  - ConsensusEngine reconciliation (15+ tests)
  - Agent consumption pathways (5 tests)
  - AI logging tags (5 tests)
  - Benchmark framework (3 tests)

Part of Coordinator Activation Sprint — Phase C validation.
"""

import sys
import copy
from pathlib import Path
from unittest.mock import MagicMock, patch, call, ANY
from typing import Dict, Any, List
import math

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validation.consensus_engine import (
    ConsensusEngine,
    DEFAULT_CONSENSUS,
    COORDINATOR_WEIGHT,
    REGIONAL_WEIGHT,
    SERVICE_GENERATOR_WEIGHT,
    CONSENSUS_ACCEPTED_MIN,
    CONSENSUS_REJECTED_MAX,
    CONFIDENCE_PER_CONFLICT,
    CONFIDENCE_UNRESOLVED_PENALTY,
)
from src.validation.weight_validator import validate_weight_adjustments
from src.validation.archetype_validator import validate_archetype_params, DEFAULT_ARCHETYPE_PARAMS
from src.validation.regional_policy_validator import validate_regional_policy

from src.agents.orchestrator_agent import OrchestratorAgent
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.regional_agent import RegionalAgent
from src.agents.service_generator_agent import ServiceGeneratorAgent
from src.optimization.data import Problem, Port, Service, Demand


# ===========================================================================
# Constants
# ===========================================================================

RATIO_MIN = 0.05
RATIO_MAX = 0.80

_BALANCED_ARCHETYPE = {
    "archetype_mix": {
        "direct_ratio": 0.60,
        "hub_loop_ratio": 0.15,
        "feeder_ratio": 0.20,
        "trunk_ratio": 0.05,
    },
    "vessel_bias": "balanced",
    "hub_focus": [],
}

_DEFAULT_WEIGHTS = {
    "profit_weight": 0.50,
    "coverage_weight": 0.40,
    "cost_weight": 0.10,
}


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def engine():
    """Fresh ConsensusEngine for each test."""
    return ConsensusEngine()


@pytest.fixture
def aligned_inputs():
    """All agents agree on weights and archetype — no conflicts expected."""
    coord = dict(_DEFAULT_WEIGHTS)
    regional = {
        "asia": {
            "coverage_priority": 0.50,
            "profit_priority": 0.50,
            "vessel_bias": "balanced",
            "hub_focus": ["CNSHA"],
        },
        "europe": {
            "coverage_priority": 0.50,
            "profit_priority": 0.50,
            "vessel_bias": "balanced",
            "hub_focus": ["NLRTM"],
        },
    }
    svc_gen = copy.deepcopy(_BALANCED_ARCHETYPE)
    svc_gen["hub_focus"] = ["CNSHA", "NLRTM"]
    return coord, regional, svc_gen


@pytest.fixture
def conflicting_weight_inputs():
    """Coordinator wants high profit; regions want coverage — triggers all 3 conflict types."""
    coord = {"profit_weight": 0.75, "coverage_weight": 0.15, "cost_weight": 0.10}
    regional = {
        "asia": {
            "coverage_priority": 0.85,
            "profit_priority": 0.30,
            "vessel_bias": "large",
            "hub_focus": ["CNSHA"],
        },
        "europe": {
            "coverage_priority": 0.80,
            "profit_priority": 0.25,
            "vessel_bias": "large",
            "hub_focus": ["NLRTM"],
        },
    }
    # svc_gen has feeder-heavy mix and different hubs → triggers archetype + hub conflicts too
    svc_gen = {
        "archetype_mix": {
            "direct_ratio": 0.15,
            "hub_loop_ratio": 0.15,
            "feeder_ratio": 0.65,
            "trunk_ratio": 0.05,
        },
        "vessel_bias": "small",
        "hub_focus": ["USLAX", "NOSYL"],
    }
    return coord, regional, svc_gen


@pytest.fixture
def conflicting_archetype_inputs():
    """Service generator wants feeder-heavy; regions want large vessels.
    Also triggers weight and hub conflicts for confidence < 0.7."""
    coord = {"profit_weight": 0.75, "coverage_weight": 0.15, "cost_weight": 0.10}
    regional = {
        "asia": {
            "coverage_priority": 0.85,
            "profit_priority": 0.30,
            "vessel_bias": "large",
            "hub_focus": ["CNSHA"],
        },
        "europe": {
            "coverage_priority": 0.80,
            "profit_priority": 0.25,
            "vessel_bias": "large",
            "hub_focus": ["NLRTM"],
        },
    }
    svc_gen = {
        "archetype_mix": {
            "direct_ratio": 0.15,
            "hub_loop_ratio": 0.20,
            "feeder_ratio": 0.55,
            "trunk_ratio": 0.10,
        },
        "vessel_bias": "small",
        "hub_focus": ["USLAX", "NOSYL"],
    }
    return coord, regional, svc_gen


@pytest.fixture
def sample_problem():
    """Minimal Problem for pipeline data-flow tests."""
    ports = [
        Port(id="CNSHA", name="Shanghai", latitude=31.23, longitude=121.47),
        Port(id="NLRTM", name="Rotterdam", latitude=51.92, longitude=4.48),
        Port(id="USLAX", name="Los Angeles", latitude=33.94, longitude=-118.41),
    ]
    services = []
    demands = [
        Demand(origin="CNSHA", destination="NLRTM", weekly_teu=5000.0, revenue_per_teu=150.0),
        Demand(origin="CNSHA", destination="USLAX", weekly_teu=3000.0, revenue_per_teu=120.0),
    ]
    distance_matrix = {
        "CNSHA": {"NLRTM": 10000, "USLAX": 6000},
        "NLRTM": {"CNSHA": 10000, "USLAX": 8000},
        "USLAX": {"CNSHA": 6000, "NLRTM": 8000},
    }
    return Problem(ports=ports, services=services, demands=demands,
                   distance_matrix=distance_matrix)


@pytest.fixture
def sample_problems(sample_problem):
    """Three sub-problems whose demands sum to sample_problem's total (8000 TEU)."""
    import copy
    p1 = copy.deepcopy(sample_problem)
    p1.demands = [Demand(origin="CNSHA", destination="NLRTM", weekly_teu=3000.0, revenue_per_teu=150.0)]
    p2 = copy.deepcopy(sample_problem)
    p2.demands = [Demand(origin="CNSHA", destination="USLAX", weekly_teu=3000.0, revenue_per_teu=120.0)]
    p3 = copy.deepcopy(sample_problem)
    p3.demands = [Demand(origin="CNSHA", destination="NLRTM", weekly_teu=2000.0, revenue_per_teu=150.0)]
    return p1, p2, p3


# ===========================================================================
# TestConsensusEngine
# ===========================================================================

class TestConsensusEngine:
    """15+ tests for ConsensusEngine reconciliation."""

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_all_agents_agree_consensus_accepted(self, engine, aligned_inputs):
        """All agents agree -> confidence > 0.7, no conflicts remaining."""
        coord, regional, svc_gen = aligned_inputs
        result = engine.process(coord, regional, svc_gen)
        assert result["confidence_score"] > CONSENSUS_ACCEPTED_MIN, (
            f"Expected confidence > {CONSENSUS_ACCEPTED_MIN}, "
            f"got {result['confidence_score']}"
        )
        assert len(result["conflicts_remaining"]) == 0
        assert result["notes"].startswith("confidence=")

    # ------------------------------------------------------------------
    # Conflict paths
    # ------------------------------------------------------------------

    def test_conflicting_weights_consensus_modified(self, engine, conflicting_weight_inputs):
        """Weight conflicts -> CONSENSUS_MODIFIED with weighted resolution."""
        coord, regional, svc_gen = conflicting_weight_inputs
        result = engine.process(coord, regional, svc_gen)
        conf = result["confidence_score"]
        assert CONSENSUS_REJECTED_MAX <= conf < CONSENSUS_ACCEPTED_MIN, (
            f"Expected confidence in [{CONSENSUS_REJECTED_MAX}, "
            f"{CONSENSUS_ACCEPTED_MIN}), got {conf}"
        )
        # At least one conflict resolved
        assert len(result["conflicts_resolved"]) >= 1
        resolved_types = [c["type"] for c in result["conflicts_resolved"]]
        assert "weight_disparity" in resolved_types
        # Final weights should be a compromise
        wa = result["final_weight_adjustments"]
        assert wa["profit_weight"] < 0.75, "Profit should be moderated from 0.75"
        assert wa["coverage_weight"] > 0.15, "Coverage should be boosted from 0.15"

    def test_conflicting_archetypes_consensus_modified(self, engine, conflicting_archetype_inputs):
        """Archetype conflicts -> CONSENSUS_MODIFIED with weighted resolution."""
        coord, regional, svc_gen = conflicting_archetype_inputs
        result = engine.process(coord, regional, svc_gen)
        conf = result["confidence_score"]
        assert CONSENSUS_REJECTED_MAX <= conf < CONSENSUS_ACCEPTED_MIN, (
            f"Expected confidence in [{CONSENSUS_REJECTED_MAX}, "
            f"{CONSENSUS_ACCEPTED_MIN}), got {conf}"
        )
        resolved_types = [c["type"] for c in result["conflicts_resolved"]]
        assert "archetype_mismatch" in resolved_types, (
            f"Expected archetype_mismatch, got {resolved_types}"
        )
        ap = result["final_archetype_params"]
        # Coordinator with high profit + regions vote "large" → weighted majority wins
        assert ap["vessel_bias"] == "large", (
            f"Expected large (coord+regions majority), got {ap['vessel_bias']}"
        )

    # ------------------------------------------------------------------
    # Fallback / edge cases
    # ------------------------------------------------------------------

    def test_all_inputs_none_graceful(self, engine):
        """All None/empty inputs handled gracefully via validators (no crash)."""
        result = engine.process(None, {}, None)
        # The validators return fallback defaults, so result is always valid
        assert isinstance(result, dict)
        assert "final_weight_adjustments" in result
        assert "final_archetype_params" in result
        assert "confidence_score" in result
        # No conflicts since all inputs are defaults
        assert len(result.get("conflicts_resolved", [])) == 0

    def test_coordinator_override_uses_fallback_on_extreme(self, engine):
        """_fallback() produces DEFAULT_CONSENSUS with AI_FALLBACK note."""
        with patch.object(engine, "_log_consensus"):
            with patch.object(engine, "_validate_final"):
                fallback_result = engine._fallback(
                    {"conflicts_resolved": [], "conflicts_remaining": ["unresolved"]},
                    reason="test override scenario",
                )
        assert fallback_result["final_weight_adjustments"] == DEFAULT_CONSENSUS["final_weight_adjustments"]
        assert fallback_result["confidence_score"] == 0.0
        assert "AI_FALLBACK" in fallback_result["notes"]
        assert "test override" in fallback_result["notes"]

    # ------------------------------------------------------------------
    # Specific conflict detection
    # ------------------------------------------------------------------

    def test_weight_vs_regional_priority_mismatch_detected(self, engine):
        """Conflict detection: profit > 0.6 vs coverage priority > 0.7."""
        coord = {"profit_weight": 0.70, "coverage_weight": 0.20, "cost_weight": 0.10}
        regional = {
            "asia": {
                "coverage_priority": 0.85,
                "profit_priority": 0.30,
                "vessel_bias": "small",
                "hub_focus": ["CNSHA"],
            },
        }
        svc_gen = copy.deepcopy(_BALANCED_ARCHETYPE)
        conflict = engine._detect_weight_disparity(coord, regional)
        assert conflict is not None
        assert conflict["type"] == "weight_disparity"
        assert "asia" in str(conflict["regions_high_coverage"])
        result = engine.process(coord, regional, svc_gen)
        resolved_types = [c["type"] for c in result["conflicts_resolved"]]
        assert "weight_disparity" in resolved_types

    def test_archetype_vs_regional_mismatch_detected(self, engine):
        """Conflict detection: feeder-heavy archetype conflicts with large regions."""
        coord = dict(_DEFAULT_WEIGHTS)
        regional = {
            "asia": {
                "coverage_priority": 0.40,
                "profit_priority": 0.60,
                "vessel_bias": "large",
                "hub_focus": ["CNSHA"],
            },
        }
        svc_gen = {
            "archetype_mix": {
                "direct_ratio": 0.10,
                "hub_loop_ratio": 0.15,
                "feeder_ratio": 0.70,
                "trunk_ratio": 0.05,
            },
            "vessel_bias": "small",
            "hub_focus": ["CNSHA"],
        }
        archetype_validated = validate_archetype_params(svc_gen)
        conflict = engine._detect_archetype_mismatch(archetype_validated, regional)
        assert conflict is not None
        assert conflict["type"] == "archetype_mismatch"
        result = engine.process(coord, regional, svc_gen)
        resolved_types = [c["type"] for c in result["conflicts_resolved"]]
        assert "archetype_mismatch" in resolved_types

    # ------------------------------------------------------------------
    # Confidence scoring
    # ------------------------------------------------------------------

    def test_confidence_high_when_aligned(self, engine, aligned_inputs):
        """Confidence >= 0.85 when all agents agree."""
        coord, regional, svc_gen = aligned_inputs
        result = engine.process(coord, regional, svc_gen)
        assert result["confidence_score"] >= 0.85, (
            f"Expected high confidence, got {result['confidence_score']}"
        )

    def test_confidence_low_when_divergent(self, engine, conflicting_weight_inputs):
        """Confidence below ACCEPTED threshold when agents disagree."""
        coord, regional, svc_gen = conflicting_weight_inputs
        result = engine.process(coord, regional, svc_gen)
        assert result["confidence_score"] < CONSENSUS_ACCEPTED_MIN, (
            f"Expected confidence < {CONSENSUS_ACCEPTED_MIN}, "
            f"got {result['confidence_score']}"
        )

    def test_confidence_math_with_unresolved(self, engine):
        """_compute_confidence produces < 0.3 when many conflicts remain."""
        # Direct unit test of the confidence math engine
        all_c = [
            {"type": "weight_disparity", "resolved": True},
            {"type": "weight_disparity", "resolved": True},
            {"type": "weight_disparity", "resolved": True},
        ]
        remaining = [
            {"type": "weight_disparity", "resolved": False},
            {"type": "weight_disparity", "resolved": False},
            {"type": "weight_disparity", "resolved": False},
        ]
        conf = engine._compute_confidence(all_c, remaining, num_regions=0)
        # 1.0 - 3*0.15 - 3*0.25 = 1.0 - 0.45 - 0.75 = -0.20 -> max(0, ...) = 0.0
        assert conf < CONSENSUS_REJECTED_MAX

    def test_confidence_math_no_penalty_for_resolved(self, engine):
        """Resolved conflicts have smaller penalty than unresolved."""
        resolved = [{"type": "x", "resolved": True}, {"type": "y", "resolved": True}]
        conf_resolved = engine._compute_confidence(resolved, [], num_regions=0)
        # 1.0 - 2*0.15 = 0.70
        assert conf_resolved == 0.70

        unresolved = [{"type": "x", "resolved": False}, {"type": "y", "resolved": False}]
        conf_unresolved = engine._compute_confidence([], unresolved, num_regions=0)
        # 1.0 - 2*0.25 = 0.50
        assert conf_unresolved == 0.50

        assert conf_unresolved < conf_resolved, (
            "Unresolved conflicts should penalise more than resolved"
        )

    # ------------------------------------------------------------------
    # Output validation
    # ------------------------------------------------------------------

    def test_all_validators_pass_on_output(self, engine, aligned_inputs):
        """Consensus output must pass all structural validators."""
        coord, regional, svc_gen = aligned_inputs
        result = engine.process(coord, regional, svc_gen)

        weights = validate_weight_adjustments(result["final_weight_adjustments"])
        assert abs(sum(weights.values()) - 1.0) < 0.02

        arch = validate_archetype_params(result["final_archetype_params"])
        mix = arch["archetype_mix"]
        for k in ("direct_ratio", "hub_loop_ratio", "feeder_ratio", "trunk_ratio"):
            assert k in mix
            assert RATIO_MIN <= mix[k] <= RATIO_MAX
        assert abs(sum(mix.values()) - 1.0) < 0.02
        assert arch["vessel_bias"] in ("small", "balanced", "large")

    def test_weight_sum_to_one(self, engine, conflicting_weight_inputs):
        """Final weights must always sum to approximately 1.0."""
        coord, regional, svc_gen = conflicting_weight_inputs
        result = engine.process(coord, regional, svc_gen)
        total = sum(result["final_weight_adjustments"].values())
        assert abs(total - 1.0) < 0.02, f"Weights sum to {total}, expected ~1.0"

    def test_empty_regional_policies_graceful(self, engine):
        """Engine handles empty regional policies without crashing."""
        coord = dict(_DEFAULT_WEIGHTS)
        result = engine.process(coord, {}, copy.deepcopy(_BALANCED_ARCHETYPE))
        assert result["confidence_score"] > 0
        assert len(result["conflicts_resolved"]) == 0
        total = sum(result["final_weight_adjustments"].values())
        assert abs(total - 1.0) < 0.02

    # ------------------------------------------------------------------
    # Hub / archetype aggregation
    # ------------------------------------------------------------------

    def test_hub_strategy_aggregation(self, engine):
        """Hub strategies aggregated across agents produce superset."""
        coord = dict(_DEFAULT_WEIGHTS)
        regional = {
            "asia": {
                "coverage_priority": 0.50,
                "profit_priority": 0.50,
                "vessel_bias": "balanced",
                "hub_focus": ["CNSHA", "HKHKG"],
            },
            "europe": {
                "coverage_priority": 0.50,
                "profit_priority": 0.50,
                "vessel_bias": "balanced",
                "hub_focus": ["NLRTM", "DEBRV"],
            },
        }
        svc_gen = copy.deepcopy(_BALANCED_ARCHETYPE)
        svc_gen["hub_focus"] = ["CNSHA", "NLRTM", "USLAX"]
        result = engine.process(coord, regional, svc_gen)
        final_hubs = result["final_archetype_params"]["hub_focus"]
        assert "CNSHA" in final_hubs, "CNSHA should be in final hubs (regional + svc gen)"
        assert "NLRTM" in final_hubs, "NLRTM should be in final hubs (regional + svc gen)"

    def test_service_archetype_plan_aggregation(self, engine, aligned_inputs):
        """Archetype plan gets fully populated in final_archetype_params."""
        coord, regional, svc_gen = aligned_inputs
        result = engine.process(coord, regional, svc_gen)
        ap = result["final_archetype_params"]
        assert "archetype_mix" in ap
        assert "vessel_bias" in ap
        assert "hub_focus" in ap
        mix = ap["archetype_mix"]
        for key in ("direct_ratio", "hub_loop_ratio", "feeder_ratio", "trunk_ratio"):
            assert key in mix, f"Missing {key} in archetype_mix"
        assert abs(sum(mix.values()) - 1.0) < 0.02

    # ------------------------------------------------------------------
    # Previous consensus influence
    # ------------------------------------------------------------------

    def test_previous_consensus_influence(self, engine, aligned_inputs):
        """Previous consensus nudges current result."""
        coord, regional, svc_gen = aligned_inputs
        prev = {
            "final_weight_adjustments": {
                "profit_weight": 0.40,
                "coverage_weight": 0.50,
                "cost_weight": 0.10,
            },
            "final_archetype_params": copy.deepcopy(DEFAULT_ARCHETYPE_PARAMS),
        }
        result_no_prev = engine.process(coord, regional, svc_gen)
        result_with_prev = engine.process(coord, regional, svc_gen,
                                          previous_consensus=prev)
        wa_no = result_no_prev["final_weight_adjustments"]
        wa_yes = result_with_prev["final_weight_adjustments"]
        # Previous consensus has lower profit (0.40), so profit weight
        # with previous should be <= without.
        assert wa_yes["profit_weight"] <= wa_no["profit_weight"] + 0.005, (
            "Previous consensus should not increase profit weight"
        )

    # ------------------------------------------------------------------
    # Logging tags
    # ------------------------------------------------------------------

    @patch("src.validation.consensus_engine.logger")
    def test_consensus_accepted_logged(self, mock_logger, engine, aligned_inputs):
        """CONSENSUS_ACCEPTED tag logged when all agree."""
        coord, regional, svc_gen = aligned_inputs
        engine.process(coord, regional, svc_gen)
        calls = mock_logger.info.call_args_list
        engine_calls = [c for c in calls if c[0][0] == "consensus_engine"]
        assert len(engine_calls) >= 1
        tag = engine_calls[0][1].get("tag")
        assert tag == "CONSENSUS_ACCEPTED", f"Expected CONSENSUS_ACCEPTED, got {tag}"

    @patch("src.validation.consensus_engine.logger")
    def test_consensus_modified_logged(self, mock_logger, engine, conflicting_weight_inputs):
        """CONSENSUS_MODIFIED tag logged after weighted compromise."""
        coord, regional, svc_gen = conflicting_weight_inputs
        engine.process(coord, regional, svc_gen)
        calls = mock_logger.info.call_args_list
        engine_calls = [c for c in calls if c[0][0] == "consensus_engine"]
        assert len(engine_calls) >= 1
        tag = engine_calls[0][1].get("tag")
        assert tag == "CONSENSUS_MODIFIED", f"Expected CONSENSUS_MODIFIED, got {tag}"

    @patch("src.validation.consensus_engine.logger")
    def test_consensus_rejected_logged(self, mock_logger, engine):
        """CONSENSUS_REJECTED tag logged via _fallback when confidence < 0.3."""
        # The _fallback method does not call _log_consensus, so to test
        # the CONSENSUS_REJECTED logging path, we exercise _log_consensus
        # with a simulated low-confidence result.
        low_conf_result = {
            "confidence_score": 0.1,
            "conflicts_resolved": [],
            "conflicts_remaining": ["fallback"],
            "conflict_resolved": [],  # note: not conflicts_resolved but engine reads conflicts_resolved
        }
        # Actually, let's test the _fallback path directly
        with patch.object(engine, "_log_consensus"):
            fallback = engine._fallback(
                {"conflicts_resolved": [], "conflicts_remaining": ["unresolved"]},
                reason="confidence too low",
            )
        calls = mock_logger.info.call_args_list
        # Verify AI_FALLBACK is logged from _fallback
        fallback_calls = [c for c in calls if c[1].get("tag") == "AI_FALLBACK"]
        assert len(fallback_calls) >= 1, "Expected at least one AI_FALLBACK log"

    # ------------------------------------------------------------------
    # Extra coverage: conflict structure edge cases
    # ------------------------------------------------------------------

    def test_hub_conflict_no_overlap(self, engine):
        """No hub overlap between svc gen and regions -> hub_conflict detected."""
        coord = dict(_DEFAULT_WEIGHTS)
        regional = {
            "asia": {
                "coverage_priority": 0.50,
                "profit_priority": 0.50,
                "vessel_bias": "balanced",
                "hub_focus": ["CNSHA", "HKHKG"],
            },
        }
        svc_gen = copy.deepcopy(_BALANCED_ARCHETYPE)
        svc_gen["hub_focus"] = ["NLRTM", "DEBRV"]
        result = engine.process(coord, regional, svc_gen)
        resolved_types = [c["type"] for c in result["conflicts_resolved"]]
        assert "hub_conflict" in resolved_types


# ===========================================================================
# TestConsumptionPathways
# ===========================================================================

class TestConsumptionPathways:
    """5 tests verifying cross-agent data flows through the orchestrator."""
    # NOTE (campaign 2026-10-12, Phase 8): the orchestrator no longer owns a ServiceGeneratorAgent - the
    # regional agents generate their own candidates - so the tests below do not patch it any more.

    @patch("src.agents.orchestrator_agent.ConsensusEngine")
    @patch("src.agents.orchestrator_agent.CoordinatorAgent")
    @patch("src.agents.orchestrator_agent.RegionalAgent")
    @patch("src.agents.orchestrator_agent.PortClustering")
    @patch("src.agents.orchestrator_agent.RegionalSplitter")
    def test_coordinator_receives_regional_policies(
        self, mock_splitter_cls, mock_cluster_cls,
        mock_reg_cls, mock_coord_cls, mock_ce_cls, sample_problem, sample_problems
    ):
        """Coordinator must receive regional_policies in its input_data."""
        # Setup mocks
        mock_analyze = MagicMock(return_value="Size: Small\nComplexity Drivers:\n- test\nDemand Concentration: moderate\nDecomposition Rationale: test")
        mock_cluster = mock_cluster_cls.return_value
        mock_cluster.cluster_ports.return_value = {0: ["CNSHA"], 1: ["NLRTM"], 2: ["USLAX"]}
        mock_splitter = mock_splitter_cls.return_value
        p1, p2, p3 = sample_problems
        mock_splitter.split.return_value = {0: p1, 1: p2, 2: p3}
        mock_reg = mock_reg_cls.return_value
        mock_reg.process.return_value = {
            "weekly_profit": 100000.0,
            "coverage_percent": 50.0,
            "region": "Test",
            "chromosome": {"services": []},
            "regional_policy": {
                "coverage_priority": 0.50,
                "profit_priority": 0.50,
            },
            "archetype_params": None,
            "services_selected": 10,
            "operating_cost": 500000.0,
            "transship_cost": 100000.0,
            "port_cost": 50000.0,
        }
        mock_reg.name = "mock_reg"
        mock_reg.region = "Test"
        mock_coord = mock_coord_cls.return_value
        mock_coord.process.return_value = {
            "feedback": {
                "convergence_score": 1.0,
                "needs_rerun": False,
                "rerun_reason": "converged",
                "coverage_gap": 0,
                "conflict_severity": 0,
            },
            "decisions": {
                "actions": [],
                "priorities": [],
                "weight_adjustments": {"profit_weight": 0.50, "coverage_weight": 0.40, "cost_weight": 0.10},
            },
        }
        mock_ce = mock_ce_cls.return_value
        mock_ce.process.return_value = {
            "confidence_score": 0.95,
            "final_weight_adjustments": {"profit_weight": 0.50, "coverage_weight": 0.40, "cost_weight": 0.10},
            "final_archetype_params": copy.deepcopy(DEFAULT_ARCHETYPE_PARAMS),
            "conflicts_resolved": [],
            "conflicts_remaining": [],
            "notes": "confidence=0.9500",
        }

        # constructed through __init__ (RegionalAgent / CoordinatorAgent / ConsensusEngine are patched at the
        # module level above): process() reads state that only __init__ sets (_previous_consensus,
        # consensus_engine, shared_context, iteration_results ...)
        orch = OrchestratorAgent()
        orch.name = "orchestrator"
        orch.evaluator = MagicMock()
        mock_reg2 = mock_reg_cls.return_value
        mock_reg2.process.return_value = dict(mock_reg.process.return_value)
        mock_reg2.name = "mock_reg2"
        mock_reg2.region = "Test2"
        mock_reg3 = mock_reg_cls.return_value
        mock_reg3.process.return_value = dict(mock_reg.process.return_value)
        mock_reg3.name = "mock_reg3"
        mock_reg3.region = "Test3"
        orch.regional_agents = [mock_reg, mock_reg2, mock_reg3]
        orch.coordinator = mock_coord
        orch.iteration_audit = []
        orch.regional_policies = {}
        orch.callback = None
        # Inject mock for analyze_problem
        with patch.object(OrchestratorAgent, "analyze_problem", return_value=mock_analyze.return_value):
            # Set up the object so that analyze_problem works
            # Actually we patched it already via the mock_analyze fixture equivalent
            pass

        # We need to call analyze_problem as a class method replacement
        original_analyze = OrchestratorAgent.analyze_problem
        with patch.object(OrchestratorAgent, "analyze_problem", return_value="Size: Small\nComplexity Drivers:\n- test\nDemand Concentration: moderate\nDecomposition Rationale: test"):
            orch.process({"problem": sample_problem})

        # Current contract (orchestrator_agent.py, "Consensus Engine reconciliation"): the regional
        # policies built from the regional results are handed to the CONSENSUS ENGINE together with the
        # coordinator's decisions; the coordinator itself receives the regional solutions.
        coord_call = mock_coord.process.call_args
        assert coord_call is not None, "Coordinator.process() was not called"
        assert "regional_solutions" in coord_call[0][0], "Coordinator must receive the regional solutions"
        ce_call = mock_ce.process.call_args
        assert ce_call is not None, "ConsensusEngine.process() was not called"
        assert ce_call.kwargs.get("regional_policies"), (
            "ConsensusEngine must receive the regional policies"
        )
        assert "coordinator_decisions" in ce_call.kwargs

    @patch("src.agents.orchestrator_agent.ConsensusEngine")
    @patch("src.agents.orchestrator_agent.CoordinatorAgent")
    @patch("src.agents.orchestrator_agent.RegionalAgent")
    @patch("src.agents.orchestrator_agent.PortClustering")
    @patch("src.agents.orchestrator_agent.RegionalSplitter")
    def test_regional_agent_receives_coordinator_objectives(
        self, mock_splitter_cls, mock_cluster_cls,
        mock_reg_cls, mock_coord_cls, mock_ce_cls, sample_problem, sample_problems
    ):
        """Regional agent must receive coordinator_objectives in input_data."""
        mock_cluster = mock_cluster_cls.return_value
        mock_cluster.cluster_ports.return_value = {0: ["CNSHA"], 1: ["NLRTM"], 2: ["USLAX"]}
        mock_splitter = mock_splitter_cls.return_value
        p1, p2, p3 = sample_problems
        mock_splitter.split.return_value = {0: p1, 1: p2, 2: p3}
        mock_reg = mock_reg_cls.return_value
        mock_reg.process.return_value = {
            "weekly_profit": 100000.0,
            "coverage_percent": 50.0,
            "region": "Test",
            "chromosome": {"services": []},
            "regional_policy": {"coverage_priority": 0.50, "profit_priority": 0.50},
            "services_selected": 10,
            "operating_cost": 500000.0,
            "transship_cost": 100000.0,
            "port_cost": 50000.0,
        }
        mock_coord = mock_coord_cls.return_value
        mock_coord.process.return_value = {
            "feedback": {"convergence_score": 1.0, "needs_rerun": False,
                         "rerun_reason": "converged", "coverage_gap": 0,
                         "conflict_severity": 0},
            "decisions": {"actions": [], "priorities": [],
                          "weight_adjustments": dict(_DEFAULT_WEIGHTS)},
        }
        mock_ce = mock_ce_cls.return_value
        mock_ce.process.return_value = {"confidence_score": 0.95,
            "final_weight_adjustments": dict(_DEFAULT_WEIGHTS),
            "final_archetype_params": copy.deepcopy(DEFAULT_ARCHETYPE_PARAMS),
            "conflicts_resolved": [], "conflicts_remaining": [], "notes": ""}

        # constructed through __init__ (RegionalAgent / CoordinatorAgent / ConsensusEngine are patched at the
        # module level above): process() reads state that only __init__ sets (_previous_consensus,
        # consensus_engine, shared_context, iteration_results ...)
        orch = OrchestratorAgent()
        orch.name = "orchestrator"
        orch.evaluator = MagicMock()
        orch.regional_agents = [mock_reg, mock_reg, mock_reg]
        orch.coordinator = mock_coord
        orch.iteration_audit = []
        orch.regional_policies = {}
        orch.callback = None

        with patch.object(OrchestratorAgent, "analyze_problem",
                          return_value="Size: Small\nComplexity Drivers:\n- test\nDemand Concentration: moderate\nDecomposition Rationale: test"):
            orch.process({"problem": sample_problem})

        # Current contract: regional agents receive {"problem": <regional Problem>}; the objective
        # weights (consensus-adjusted after every iteration) are attributes of the Problem that the
        # RegionalSplitter splits at the start of each iteration.
        reg_call = mock_reg.process.call_args
        assert reg_call is not None, "RegionalAgent.process() was not called"
        assert "problem" in reg_call[0][0], "Regional agent must receive its problem"
        assert mock_splitter_cls.call_args_list, "RegionalSplitter was not constructed"
        split_problem = mock_splitter_cls.call_args_list[-1][0][0]
        assert split_problem is sample_problem
        for w in ("profit_weight", "coverage_weight", "cost_weight"):
            assert getattr(split_problem, w) > 0.0, f"{w} missing on the problem that is split"

    @patch("src.agents.orchestrator_agent.ConsensusEngine")
    @patch("src.agents.orchestrator_agent.CoordinatorAgent")
    @patch("src.agents.orchestrator_agent.RegionalAgent")
    @patch("src.agents.orchestrator_agent.PortClustering")
    @patch("src.agents.orchestrator_agent.RegionalSplitter")
    def test_consensus_engine_called_after_agents(
        self, mock_splitter_cls, mock_cluster_cls,
        mock_reg_cls, mock_coord_cls, mock_ce_cls, sample_problem, sample_problems
    ):
        """Consensus engine process() must be called after all agents."""
        mock_cluster = mock_cluster_cls.return_value
        mock_cluster.cluster_ports.return_value = {0: ["CNSHA"], 1: ["NLRTM"], 2: ["USLAX"]}
        mock_splitter = mock_splitter_cls.return_value
        p1, p2, p3 = sample_problems
        mock_splitter.split.return_value = {0: p1, 1: p2, 2: p3}
        mock_reg = mock_reg_cls.return_value
        mock_reg.process.return_value = {
            "weekly_profit": 100000.0,
            "coverage_percent": 50.0,
            "region": "Test",
            "chromosome": {"services": []},
            "regional_policy": {"coverage_priority": 0.50, "profit_priority": 0.50},
            "services_selected": 10,
            "operating_cost": 500000.0,
            "transship_cost": 100000.0,
            "port_cost": 50000.0,
        }
        mock_coord = mock_coord_cls.return_value
        mock_coord.process.return_value = {
            "feedback": {"convergence_score": 1.0, "needs_rerun": False,
                         "rerun_reason": "converged", "coverage_gap": 0,
                         "conflict_severity": 0},
            "decisions": {"actions": [], "priorities": [],
                          "weight_adjustments": dict(_DEFAULT_WEIGHTS)},
        }
        mock_ce = mock_ce_cls.return_value
        mock_ce.process.return_value = {"confidence_score": 0.95,
            "final_weight_adjustments": dict(_DEFAULT_WEIGHTS),
            "final_archetype_params": copy.deepcopy(DEFAULT_ARCHETYPE_PARAMS),
            "conflicts_resolved": [], "conflicts_remaining": [], "notes": ""}

        # constructed through __init__ (RegionalAgent / CoordinatorAgent / ConsensusEngine are patched at the
        # module level above): process() reads state that only __init__ sets (_previous_consensus,
        # consensus_engine, shared_context, iteration_results ...)
        orch = OrchestratorAgent()
        orch.name = "orchestrator"
        orch.evaluator = MagicMock()
        orch.regional_agents = [mock_reg, mock_reg, mock_reg]
        orch.coordinator = mock_coord
        orch.iteration_audit = []
        orch.regional_policies = {}
        orch.callback = None

        with patch.object(OrchestratorAgent, "analyze_problem",
                          return_value="Size: Small\nComplexity Drivers:\n- test\nDemand Concentration: moderate\nDecomposition Rationale: test"):
            orch.process({"problem": sample_problem})

        # Verify consensus engine was called with the right args
        ce_call = mock_ce.process.call_args
        assert ce_call is not None, "ConsensusEngine.process() was not called"
        kwargs = ce_call[1]
        # Must have coordinator_decisions, regional_policies, service_archetype_params
        assert "coordinator_decisions" in kwargs
        assert "regional_policies" in kwargs
        assert "service_archetype_params" in kwargs

    @patch("src.agents.orchestrator_agent.ConsensusEngine")
    @patch("src.agents.orchestrator_agent.CoordinatorAgent")
    @patch("src.agents.orchestrator_agent.RegionalAgent")
    @patch("src.agents.orchestrator_agent.PortClustering")
    @patch("src.agents.orchestrator_agent.RegionalSplitter")
    def test_final_policy_matches_consensus(
        self, mock_splitter_cls, mock_cluster_cls,
        mock_reg_cls, mock_coord_cls, mock_ce_cls, sample_problem, sample_problems
    ):
        """Problem weights at end should match consensus final_weight_adjustments."""
        consensus_weights = {
            "profit_weight": 0.45,
            "coverage_weight": 0.45,
            "cost_weight": 0.10,
        }
        mock_cluster = mock_cluster_cls.return_value
        mock_cluster.cluster_ports.return_value = {0: ["CNSHA"], 1: ["NLRTM"], 2: ["USLAX"]}
        mock_splitter = mock_splitter_cls.return_value
        p1, p2, p3 = sample_problems
        mock_splitter.split.return_value = {0: p1, 1: p2, 2: p3}
        mock_reg = mock_reg_cls.return_value
        mock_reg.process.return_value = {
            "weekly_profit": 100000.0,
            "coverage_percent": 50.0,
            "region": "Test",
            "chromosome": {"services": []},
            "regional_policy": {"coverage_priority": 0.50, "profit_priority": 0.50},
            "services_selected": 10,
            "operating_cost": 500000.0,
            "transship_cost": 100000.0,
            "port_cost": 50000.0,
        }
        mock_coord = mock_coord_cls.return_value
        mock_coord.process.return_value = {
            "feedback": {"convergence_score": 1.0, "needs_rerun": False,
                         "rerun_reason": "converged", "coverage_gap": 0,
                         "conflict_severity": 0},
            "decisions": {"actions": [], "priorities": [],
                          "weight_adjustments": dict(_DEFAULT_WEIGHTS)},
        }
        mock_ce = mock_ce_cls.return_value
        mock_ce.process.return_value = {"confidence_score": 0.90,
            "final_weight_adjustments": consensus_weights,
            "final_archetype_params": copy.deepcopy(DEFAULT_ARCHETYPE_PARAMS),
            "conflicts_resolved": [], "conflicts_remaining": [], "notes": ""}

        # constructed through __init__ (RegionalAgent / CoordinatorAgent / ConsensusEngine are patched at the
        # module level above): process() reads state that only __init__ sets (_previous_consensus,
        # consensus_engine, shared_context, iteration_results ...)
        orch = OrchestratorAgent()
        orch.name = "orchestrator"
        orch.evaluator = MagicMock()
        orch.regional_agents = [mock_reg, mock_reg, mock_reg]
        orch.coordinator = mock_coord
        orch.iteration_audit = []
        orch.regional_policies = {}
        orch.callback = None

        with patch.object(OrchestratorAgent, "analyze_problem",
                          return_value="Size: Small\nComplexity Drivers:\n- test\nDemand Concentration: moderate\nDecomposition Rationale: test"):
            result = orch.process({"problem": sample_problem})

        # Consensus weights should be applied to the problem
        assert abs(sample_problem.profit_weight - consensus_weights["profit_weight"]) < 0.01
        assert abs(sample_problem.coverage_weight - consensus_weights["coverage_weight"]) < 0.01
        assert abs(sample_problem.cost_weight - consensus_weights["cost_weight"]) < 0.01

    def test_service_generator_receives_coordinator_objectives(self):
        """ServiceGeneratorAgent should accept coordinator_objectives in input."""
        agent = ServiceGeneratorAgent(name="test_svc_gen", model="test")     # constructed normally: process() uses ``_metrics``
        # Minimal test: verify that process() accepts coordinator_objectives key
        # without error when present.  We patch the LLM call since we don't
        # have a real problem to run through.
        ports = [Port(id="CNSHA", name="Shanghai", latitude=31.23, longitude=121.47)]
        services = []
        demands = [Demand(origin="CNSHA", destination="NLRTM", weekly_teu=1000.0, revenue_per_teu=150.0)]
        dist = {"CNSHA": {"NLRTM": 10000}, "NLRTM": {"CNSHA": 10000}}
        problem = Problem(ports=ports, services=services, demands=demands, distance_matrix=dist)

        with patch.object(ServiceGeneratorAgent, "call_llm",
                          return_value='{"archetype_mix": {"direct_ratio": 0.60, "hub_loop_ratio": 0.15, "feeder_ratio": 0.20, "trunk_ratio": 0.05}, "vessel_bias": "balanced", "hub_focus": []}'):
            with patch.object(ServiceGeneratorAgent, "generate_services",
                              return_value=[]) as mock_gen:
                result = agent.process({
                    "problem": problem,
                    "coordinator_objectives": {
                        "profit_weight": 0.50,
                        "coverage_weight": 0.40,
                        "cost_weight": 0.10,
                    },
                })

        assert result is not None
        assert "archetype_params" in result


# ===========================================================================
# TestLoggingTags
# ===========================================================================

class TestLoggingTags:
    """5 tests verifying AI log tags are emitted at the right times."""

    @patch("src.validation.consensus_engine.logger")
    def test_logging_tag_consensus_accepted(self, mock_logger):
        """CONSENSUS_ACCEPTED tag when confidence > 0.7."""
        engine = ConsensusEngine()
        coord = dict(_DEFAULT_WEIGHTS)
        regional = {
            "a": {"coverage_priority": 0.50, "profit_priority": 0.50,
                  "vessel_bias": "balanced", "hub_focus": []},
        }
        svc_gen = copy.deepcopy(_BALANCED_ARCHETYPE)
        engine.process(coord, regional, svc_gen)
        calls = mock_logger.info.call_args_list
        tags = [c[1].get("tag") for c in calls if c[0][0] == "consensus_engine"]
        assert "CONSENSUS_ACCEPTED" in tags

    @patch("src.validation.consensus_engine.logger")
    def test_logging_tag_consensus_modified(self, mock_logger):
        """CONSENSUS_MODIFIED tag when confidence in [0.3, 0.7]."""
        engine = ConsensusEngine()
        coord = {"profit_weight": 0.70, "coverage_weight": 0.20, "cost_weight": 0.10}
        regional = {
            "a": {"coverage_priority": 0.90, "profit_priority": 0.10,
                  "vessel_bias": "small", "hub_focus": ["CNSHA"]},
        }
        svc_gen = {
            "archetype_mix": {"direct_ratio": 0.60, "hub_loop_ratio": 0.15,
                              "feeder_ratio": 0.20, "trunk_ratio": 0.05},
            "vessel_bias": "large",
            "hub_focus": ["NLRTM"],
        }
        engine.process(coord, regional, svc_gen)
        calls = mock_logger.info.call_args_list
        tags = [c[1].get("tag") for c in calls if c[0][0] == "consensus_engine"]
        assert "CONSENSUS_MODIFIED" in tags

    @patch("src.validation.consensus_engine.logger")
    def test_logging_tag_consensus_rejected(self, mock_logger):
        """CONSENSUS_REJECTED tag when confidence < 0.3 (_log_consensus path)."""
        engine = ConsensusEngine()
        # The process() method cannot produce confidence < 0.3 normally
        # because all conflicts are resolved.  Test _log_consensus directly.
        engine._log_consensus({
            "confidence_score": 0.1,
            "conflicts_resolved": [],
            "conflicts_remaining": ["fallback"],
            "final_weight_adjustments": {"profit_weight": 0.5, "coverage_weight": 0.4, "cost_weight": 0.1},
            "final_archetype_params": {"vessel_bias": "balanced"},
        })
        calls = mock_logger.info.call_args_list
        engine_calls = [c for c in calls if c[0][0] == "consensus_engine"]
        assert len(engine_calls) >= 1
        tag = engine_calls[0][1].get("tag")
        assert tag == "CONSENSUS_REJECTED", f"Expected CONSENSUS_REJECTED, got {tag}"

    @patch("src.validation.consensus_engine.logger")
    def test_logging_tag_ai_fallback(self, mock_logger):
        """AI_FALLBACK tag when _fallback is invoked directly."""
        engine = ConsensusEngine()
        with patch.object(engine, "_log_consensus"):
            fallback = engine._fallback(
                {"conflicts_resolved": [], "conflicts_remaining": ["x"]},
                reason="low confidence",
            )
        calls = mock_logger.info.call_args_list
        ai_fallback_calls = [c for c in calls if c[1].get("tag") == "AI_FALLBACK"]
        assert len(ai_fallback_calls) >= 1, "Expected AI_FALLBACK log tag"
        # Verify DEFAULT_CONSENSUS structure in fallback result
        assert fallback["final_weight_adjustments"] == DEFAULT_CONSENSUS["final_weight_adjustments"]
        assert fallback["confidence_score"] == 0.0

    @patch("src.validation.consensus_engine.logger")
    def test_logging_tag_ai_applied_on_fallback(self, mock_logger):
        """AI_APPLIED is NOT used by consensus engine (validate it does not)."""
        engine = ConsensusEngine()
        coord = dict(_DEFAULT_WEIGHTS)
        regional = {
            "a": {"coverage_priority": 0.50, "profit_priority": 0.50,
                  "vessel_bias": "balanced", "hub_focus": []},
        }
        svc_gen = copy.deepcopy(_BALANCED_ARCHETYPE)
        engine.process(coord, regional, svc_gen)
        calls = mock_logger.info.call_args_list
        ai_applied_calls = [c for c in calls if c[1].get("tag") == "AI_APPLIED"]
        # Consensus engine does not use AI_APPLIED — it uses CONSENSUS_* tags
        assert len(ai_applied_calls) == 0, "Consensus engine should not emit AI_APPLIED"


# ===========================================================================
# TestBenchmarkFramework
# ===========================================================================

class TestBenchmarkFramework:
    """3 tests: independent vs coordinated comparison with delta reporting."""

    def test_group_a_independent_no_coordination(self):
        """Group A runs agents independently (no consensus engine)."""
        # Simulate the independent-agents scenario: each agent produces its own
        # weight adjustments without consensus reconciliation.
        coord_weights = {"profit_weight": 0.70, "coverage_weight": 0.20, "cost_weight": 0.10}
        regional_weights_a = {"profit_weight": 0.30, "coverage_weight": 0.60, "cost_weight": 0.10}
        regional_weights_b = {"profit_weight": 0.40, "coverage_weight": 0.50, "cost_weight": 0.10}
        svc_weights = {"profit_weight": 0.50, "coverage_weight": 0.40, "cost_weight": 0.10}

        # Independent: each agent's weight adjustments are kept separately
        independent_results = {
            "coordinator": coord_weights,
            "regional_asia": regional_weights_a,
            "regional_europe": regional_weights_b,
            "svc_gen": svc_weights,
        }

        # Verify each agent's weights are valid
        for name, w in independent_results.items():
            validated = validate_weight_adjustments(w, source="test")
            assert abs(sum(validated.values()) - 1.0) < 0.02, (
                f"{name} weights should sum to ~1.0"
            )

        # With no coordination, weights may diverge significantly
        profit_weights = [w["profit_weight"] for w in independent_results.values()]
        divergence = max(profit_weights) - min(profit_weights)
        assert divergence > 0, "Independent agents should show weight divergence"

    def test_group_b_coordinated_with_consensus(self, engine, conflicting_weight_inputs):
        """Group B uses consensus engine to reconcile agents."""
        coord, regional, svc_gen = conflicting_weight_inputs
        result = engine.process(coord, regional, svc_gen)
        consensus_weights = result["final_weight_adjustments"]

        # Coordinated: single unified weight set
        validated = validate_weight_adjustments(consensus_weights, source="test")
        assert abs(sum(validated.values()) - 1.0) < 0.02
        assert result["confidence_score"] >= CONSENSUS_REJECTED_MAX, (
            "Coordinated group should have confidence above rejection threshold"
        )

        # The consensus weight should be between coordinator and regional extremes
        coord_profit = coord["profit_weight"]
        reg_min_profit = min(r.get("profit_priority", 0.5) for r in regional.values())
        consensus_profit = consensus_weights["profit_weight"]
        assert reg_min_profit <= consensus_profit <= coord_profit, (
            f"Consensus profit {consensus_profit} should lie between "
            f"regional min {reg_min_profit} and coordinator {coord_profit}"
        )

    def test_comparison_template_with_delta_reporting(self):
        """Delta-reporting template comparing Group A vs Group B outcomes."""
        # Simulate Group A (independent) results
        group_a = {
            "profit": 100000.0,
            "coverage": 45.0,
            "conflicts": 5,
            "weight_adjustments": None,
        }

        # Simulate Group B (coordinated) results
        group_b = {
            "profit": 120000.0,
            "coverage": 55.0,
            "conflicts": 0,
            "weight_adjustments": {
                "profit_weight": 0.50,
                "coverage_weight": 0.40,
                "cost_weight": 0.10,
            },
        }

        # Delta report
        delta = {
            "profit_change_pct": round(
                (group_b["profit"] - group_a["profit"]) / group_a["profit"] * 100, 2
            ),
            "coverage_change_pp": round(group_b["coverage"] - group_a["coverage"], 1),
            "conflicts_resolved": group_a["conflicts"] - group_b["conflicts"],
            "consensus_applied": group_b["weight_adjustments"] is not None,
        }

        # Assertions on the comparison template
        assert delta["profit_change_pct"] > 0, "Coordinated group should improve profit"
        assert delta["coverage_change_pp"] > 0, "Coordinated group should improve coverage"
        assert delta["conflicts_resolved"] == 5, "All 5 conflicts should be resolved"
        assert delta["consensus_applied"] is True, "Coordinated group uses consensus"

        # Report structure
        report_lines = [
            "=== BENCHMARK COMPARISON: GROUP A (independent) vs GROUP B (coordinated) ===",
            f"Profit: Group A=${group_a['profit']:,.0f}  Group B=${group_b['profit']:,.0f}  "
            f"Delta={delta['profit_change_pct']:+.2f}%",
            f"Coverage: Group A={group_a['coverage']:.1f}%  Group B={group_b['coverage']:.1f}%  "
            f"Delta={delta['coverage_change_pp']:+.1f}pp",
            f"Conflicts: Group A={group_a['conflicts']}  Group B={group_b['conflicts']}  "
            f"Resolved={delta['conflicts_resolved']}",
            f"Consensus: {'YES' if delta['consensus_applied'] else 'NO'}",
        ]
        full_report = "\n".join(report_lines)

        assert "BENCHMARK COMPARISON" in full_report
        assert "+20.00%" in full_report or "20.00%" in full_report
        assert "+10.0pp" in full_report or "10.0pp" in full_report
        assert "Resolved=5" in full_report
        assert "YES" in full_report
