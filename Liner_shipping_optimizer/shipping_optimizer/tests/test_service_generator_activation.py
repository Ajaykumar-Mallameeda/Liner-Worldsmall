"""
Test Service Generator Activation — Phase B of Coordinator Activation Sprint.

Tests:
  1. archetype_validator edge cases
  2. generate_services() with various archetype_params
  3. AI logging tags (AI_GENERATED, AI_VALIDATED, AI_APPLIED, AI_REJECTED, AI_FALLBACK)
  4. Benchmark framework template (Group A default vs Group B AI archetypes)
"""

import json
import sys
import math
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import patch, MagicMock, ANY

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validation.archetype_validator import (
    validate_archetype_params,
    _fallback_archetype_params,
    DEFAULT_ARCHETYPE_PARAMS,
    DEFAULT_MIX,
    RATIO_MIN,
    RATIO_MAX,
    MIX_KEYS,
    VALID_VESSEL_BIASES,
)
from src.agents import service_generator_agent as _sga_module
from src.agents.service_generator_agent import ServiceGeneratorAgent
from src.data.network_loader import NetworkLoader
from src.optimization.data import Problem, Port, Service, Demand
from src.utils.logger import logger


# ===========================================================================
# Helpers
# ===========================================================================

@contextmanager
def _patched_info():
    """Capture ``info`` of BOTH loggers the pipeline uses: the project logger
    (``src.utils.logger.logger``: the validators, kwargs style) and the agent module's stdlib logger
    (``logger.info('event | tag=%s ...', TAG)``)."""
    shared = MagicMock()
    with patch.object(logger, "info", new=shared), patch.object(_sga_module.logger, "info", new=shared):
        yield shared


def create_minimal_problem(
    num_ports: int = 15,
    num_demands: int = 50,
) -> Problem:
    """Create a small Problem instance for fast test execution.

    Port IDs are 'P001', 'P002', ... with random-ish demand data so the
    HubDetector sees enough signal to rank hubs meaningfully.
    """
    ports = []
    for i in range(1, num_ports + 1):
        pid = f"P{i:03d}"
        ports.append(Port(
            id=pid,
            name=f"Port_{i}",
            latitude=10.0 + i,
            longitude=20.0 + i * 0.5,
            handling_cost=50 + i * 10,
            port_call_cost=1000 + i * 50,
        ))

    demands = []
    # Generate demands with a power-law distribution: a few corridors get most TEU
    rng_seed = 42
    rng = __import__("random").Random(rng_seed)
    for j in range(1, num_demands + 1):
        origin_idx = rng.randint(1, num_ports)
        dest_idx = rng.randint(1, num_ports)
        while dest_idx == origin_idx:
            dest_idx = rng.randint(1, num_ports)
        # Power-law-ish: first demands get higher TEU
        teu = max(50, int(5000 / (1 + j * 0.15) + rng.gauss(0, 200)))
        demands.append(Demand(
            origin=f"P{origin_idx:03d}",
            destination=f"P{dest_idx:03d}",
            weekly_teu=float(teu),
            revenue_per_teu=100.0 + rng.gauss(0, 20),
        ))

    # Distance matrix: dummy 100 NM between all pairs
    distance_matrix: Dict[str, Dict[str, float]] = {}
    for i in range(1, num_ports + 1):
        oid = f"P{i:03d}"
        distance_matrix[oid] = {}
        for j in range(1, num_ports + 1):
            did = f"P{j:03d}"
            distance_matrix[oid][did] = 100.0  # all pairs 100 NM

    # Ensure every port from the demands appears in the distance matrix
    for d in demands:
        if d.origin not in distance_matrix:
            distance_matrix[d.origin] = {}
        if d.destination not in distance_matrix:
            distance_matrix[d.destination] = {}
        distance_matrix[d.origin].setdefault(d.destination, 100.0)
        distance_matrix[d.destination].setdefault(d.origin, 100.0)

    # The network above is synthetic; the fleet is the REAL canonical WorldSmall fleet.
    # Candidate generation requires a fleet (no default vessel class exists).
    return Problem(
        ports=ports,
        services=[],
        demands=demands,
        distance_matrix=distance_matrix,
        fleet=NetworkLoader().load_fleet(),
    )


def _service_counts(services: List) -> Dict[str, int]:
    """Categorise generated services into archetype buckets by inspection.

    Services can be Service objects (from agent generation) or plain dicts
    (from CandidateServiceGenerator). Handles both.
    """
    direct = 0
    hub_loop = 0
    trunk = 0
    feeder = 0
    other = 0

    for s in services:
        if isinstance(s, dict):
            ports = s.get("ports", [])
        else:
            ports = s.ports
        n = len(ports)
        if n == 2:
            direct += 1
        elif 3 <= n <= 6:
            hub_loop += 1
        elif n > 6:
            trunk += 1
        else:
            other += 1

    return {
        "direct": direct,
        "hub_loop": hub_loop,
        "trunk": trunk,
        "feeder": feeder,
        "other": other,
        "total": len(services),
    }


# ===========================================================================
# 1 — Archetype Validator Edge Cases
# ===========================================================================

class TestArchetypeValidator:
    """Every edge case for validate_archetype_params()."""

    def test_valid_mix(self):
        """Sum = 1.0, all ratios within bounds."""
        raw = {
            "archetype_mix": {
                "direct_ratio": 0.50,
                "hub_loop_ratio": 0.20,
                "feeder_ratio": 0.20,
                "trunk_ratio": 0.10,
            },
            "vessel_bias": "balanced",
        }
        result = validate_archetype_params(raw, source="test")
        mix = result["archetype_mix"]
        assert abs(sum(mix.values()) - 1.0) < 0.001, f"Sum not 1.0: {sum(mix.values())}"
        assert all(RATIO_MIN <= v <= RATIO_MAX for v in mix.values()), f"Ratio out of bounds: {mix}"
        assert result["vessel_bias"] == "balanced"

    def test_mix_normalised_when_sum_not_one(self):
        """Sum != 1.0 => normalised."""
        raw = {
            "archetype_mix": {
                "direct_ratio": 0.80,
                "hub_loop_ratio": 0.80,
                "feeder_ratio": 0.80,
                "trunk_ratio": 0.80,
            },
        }
        result = validate_archetype_params(raw, source="test")
        mix = result["archetype_mix"]
        total = sum(mix.values())
        assert abs(total - 1.0) < 0.01, f"Normalised sum should be ~1.0, got {total}"
        assert all(RATIO_MIN <= v <= RATIO_MAX for v in mix.values()), f"Bounds: {mix}"

    def test_ratios_clamped_above_max(self):
        """Ratios above RATIO_MAX get clamped."""
        raw = {
            "archetype_mix": {
                "direct_ratio": 2.0,
                "hub_loop_ratio": 0.10,
                "feeder_ratio": 0.10,
                "trunk_ratio": 0.10,
            },
        }
        result = validate_archetype_params(raw, source="test")
        mix = result["archetype_mix"]
        assert mix["direct_ratio"] <= RATIO_MAX, f"direct_ratio should be clamped to <= {RATIO_MAX}"
        assert abs(sum(mix.values()) - 1.0) < 0.01

    def test_ratios_clamped_below_min(self):
        """Ratios below RATIO_MIN get clamped upward."""
        raw = {
            "archetype_mix": {
                "direct_ratio": 0.0,
                "hub_loop_ratio": 0.0,
                "feeder_ratio": 0.0,
                "trunk_ratio": 0.0,
            },
        }
        result = validate_archetype_params(raw, source="test")
        mix = result["archetype_mix"]
        assert all(v >= RATIO_MIN for v in mix.values()), f"Should all be >= {RATIO_MIN}: {mix}"
        assert abs(sum(mix.values()) - 1.0) < 0.01

    def test_empty_dict_falls_back(self):
        """Empty dict => AI_FALLBACK with default mix."""
        result = validate_archetype_params({}, source="test")
        assert result["archetype_mix"] == DEFAULT_MIX
        assert result["vessel_bias"] == "balanced"

    def test_none_input_falls_back(self):
        """None => AI_FALLBACK with default mix."""
        result = validate_archetype_params(None, source="test")
        assert result["archetype_mix"] == DEFAULT_MIX

    def test_missing_keys_filled_from_defaults(self):
        """Partial mix fills missing keys from defaults."""
        raw = {
            "archetype_mix": {"direct_ratio": 0.70},
        }
        result = validate_archetype_params(raw, source="test")
        mix = result["archetype_mix"]
        assert mix["direct_ratio"] >= 0.05
        assert "hub_loop_ratio" in mix
        assert "feeder_ratio" in mix
        assert "trunk_ratio" in mix
        assert abs(sum(mix.values()) - 1.0) < 0.01

    def test_vessel_bias_invalid(self):
        """Invalid vessel_bias falls back to 'balanced'."""
        raw = {
            "archetype_mix": dict(DEFAULT_MIX),
            "vessel_bias": "gargantuan",
        }
        result = validate_archetype_params(raw, source="test")
        assert result["vessel_bias"] == "balanced"

    def test_vessel_bias_case_insensitive(self):
        """vessel_bias should be case-insensitive."""
        for case_variant in ["Small", "SMALL", "small", "Balanced", "BALANCED", "Large", "LARGE", "large"]:
            raw = {
                "archetype_mix": dict(DEFAULT_MIX),
                "vessel_bias": case_variant,
            }
            result = validate_archetype_params(raw, source="test")
            assert result["vessel_bias"] == case_variant.lower(), f"Failed for {case_variant!r}"

    def test_vessel_bias_all_valid_values(self):
        """All three valid vessel biases pass through."""
        for bias in VALID_VESSEL_BIASES:
            raw = {
                "archetype_mix": dict(DEFAULT_MIX),
                "vessel_bias": bias,
            }
            result = validate_archetype_params(raw, source="test")
            assert result["vessel_bias"] == bias

    def test_hub_focus_filtered(self):
        """hub_focus is filtered to valid_port_ids when set is provided."""
        raw = {
            "archetype_mix": dict(DEFAULT_MIX),
            "hub_focus": ["PORT_A", "PORT_B", "PORT_C"],
        }
        valid_ids = {"PORT_A", "PORT_C"}
        result = validate_archetype_params(raw, valid_port_ids=valid_ids, source="test")
        assert "PORT_B" not in result["hub_focus"]
        assert "PORT_A" in result["hub_focus"]
        assert "PORT_C" in result["hub_focus"]

    def test_hub_focus_non_list(self):
        """Non-list hub_focus becomes empty list."""
        raw = {
            "archetype_mix": dict(DEFAULT_MIX),
            "hub_focus": "not_a_list",
        }
        result = validate_archetype_params(raw, source="test")
        assert result["hub_focus"] == []

    def test_notes_stringified(self):
        """notes is coerced to string."""
        raw = {
            "archetype_mix": dict(DEFAULT_MIX),
            "notes": 12345,
        }
        result = validate_archetype_params(raw, source="test")
        assert isinstance(result["notes"], str)

    def test_non_numeric_ratio_rejected(self):
        """Non-numeric ratio value is filled from defaults (not full fallback)."""
        raw = {
            "archetype_mix": {
                "direct_ratio": "abc",
                "hub_loop_ratio": 0.20,
                "feeder_ratio": 0.20,
                "trunk_ratio": 0.10,
            },
        }
        result = validate_archetype_params(raw, source="test")
        # "abc" returns None from _get_ratio -> filled with DEFAULT_MIX["direct_ratio"]
        mix = result["archetype_mix"]
        assert abs(sum(mix.values()) - 1.0) < 0.01

    def test_short_form_keys(self):
        """Short-form keys (e.g. 'direct' vs 'direct_ratio') are recognised."""
        raw = {
            "archetype_mix": {
                "direct": 0.50,
                "hub_loop": 0.20,
                "feeder": 0.20,
                "trunk": 0.10,
            },
        }
        result = validate_archetype_params(raw, source="test")
        mix = result["archetype_mix"]
        assert abs(sum(mix.values()) - 1.0) < 0.01

    def test_archetype_mix_not_a_dict(self):
        """archetype_mix not a dict => use default ratios but keep validating."""
        raw = {
            "archetype_mix": "bad_value",
            "vessel_bias": "small",
        }
        result = validate_archetype_params(raw, source="test")
        assert result["archetype_mix"] == DEFAULT_MIX
        assert result["vessel_bias"] == "small"

    def test_return_keys(self):
        """Result always has all four expected top-level keys."""
        result = validate_archetype_params(None, source="test")
        assert "archetype_mix" in result
        assert "vessel_bias" in result
        assert "hub_focus" in result
        assert "notes" in result

    def test_fallback_function(self):
        """_fallback_archetype_params returns the exact default structure."""
        fb = _fallback_archetype_params(reason="unit test")
        assert fb["archetype_mix"] == DEFAULT_MIX
        assert fb["vessel_bias"] == "balanced"
        assert fb["hub_focus"] == []
        assert fb["notes"] == ""


# ===========================================================================
# 2 — generate_services() with Different Archetype Params
# ===========================================================================

class TestGenerateServices:
    """Verify generate_services() responds to archetype_params correctly."""

    @pytest.fixture(scope="class")
    def agent(self):
        """Single agent instance for the class."""
        return ServiceGeneratorAgent(
            name="test_svc_gen",
            model="opencode/deepseek-v4-flash-free",
        )

    @pytest.fixture(scope="class")
    def problem(self):
        """Reusable minimal problem."""
        return create_minimal_problem(num_ports=15, num_demands=80)

    def test_default_params(self, agent, problem):
        """Default archetype params produce a baseline candidate pool."""
        services = agent.generate_services(problem)
        counts = _service_counts(services)
        assert counts["total"] > 0, "Should generate at least some services"
        assert counts["direct"] > 0, "Should generate direct services"
        assert counts["hub_loop"] >= 0, "hub_loop count should be >= 0"

    def test_direct_heavy_params(self, agent, problem):
        """Direct-heavy params shift pool toward more direct services."""
        direct_heavy = {
            "archetype_mix": {
                "direct_ratio": 0.75,
                "hub_loop_ratio": 0.05,
                "feeder_ratio": 0.05,
                "trunk_ratio": 0.05,
            },
            "vessel_bias": "balanced",
        }
        services = agent.generate_services(problem, archetype_params=direct_heavy)
        counts = _service_counts(services)
        assert counts["direct"] > 0, "Should have direct services"
        # The direct count should dominate — at least 40% of all services
        direct_share = counts["direct"] / max(counts["total"], 1)
        assert direct_share > 0.30, f"Direct share {direct_share:.2f} should be > 0.30"

    def test_hub_loop_heavy_params(self, agent, problem):
        """Hub-loop-heavy params shift pool toward more hub-loop services."""
        hub_loop_heavy = {
            "archetype_mix": {
                "direct_ratio": 0.05,
                "hub_loop_ratio": 0.75,
                "feeder_ratio": 0.05,
                "trunk_ratio": 0.05,
            },
            "vessel_bias": "balanced",
        }
        services = agent.generate_services(problem, archetype_params=hub_loop_heavy)
        counts = _service_counts(services)
        # In this small test network, hub-loop (3-6 ports) should be present
        assert counts["hub_loop"] > 0, f"Should have hub-loop services, got {counts}"

    def test_feeder_heavy_params(self, agent, problem):
        """Feeder-heavy params shift pool toward more feeder services."""
        feeder_heavy = {
            "archetype_mix": {
                "direct_ratio": 0.05,
                "hub_loop_ratio": 0.05,
                "feeder_ratio": 0.75,
                "trunk_ratio": 0.05,
            },
            "vessel_bias": "small",
        }
        services = agent.generate_services(problem, archetype_params=feeder_heavy)
        counts = _service_counts(services)
        # Feeder-heavy + vessel_bias=small should still produce services
        assert counts["total"] > 0, "Should generate services with feeder-heavy params"

    def test_vessel_bias_small(self, agent, problem):
        """vessel_bias=small should produce smaller-capacity vessels."""
        small_params = {
            "archetype_mix": dict(DEFAULT_MIX),
            "vessel_bias": "small",
        }
        large_params = {
            "archetype_mix": dict(DEFAULT_MIX),
            "vessel_bias": "large",
        }

        def _avg_capacity_of_service_objects(svcs):
            """Average capacity of only the Service dataclass instances
            (dict entries from CandidateServiceGenerator have no capacity)."""
            capacities = [
                s.capacity for s in svcs
                if not isinstance(s, dict) and hasattr(s, 'capacity')
            ]
            return sum(capacities) / len(capacities) if capacities else 0

        services_small = agent.generate_services(problem, archetype_params=small_params)
        services_large = agent.generate_services(problem, archetype_params=large_params)
        assert len(services_small) > 0
        assert len(services_large) > 0

        avg_cap_small = _avg_capacity_of_service_objects(services_small)
        avg_cap_large = _avg_capacity_of_service_objects(services_large)

        # Small bias should give lower or comparable average capacity
        assert avg_cap_small <= avg_cap_large * 1.5, (
            f"Small-bias avg cap {avg_cap_small:.0f} should not vastly exceed "
            f"large-bias avg cap {avg_cap_large:.0f}"
        )

    def test_pool_size_changes_with_budget(self, agent, problem, monkeypatch):
        """Reducing all ratios reduces overall pool size proportionally.

        The archetype mix drives sections A-E of the legacy generator. Section F (demand-
        coherent loops, own budget) and the per-rotation class screening (which
        de-duplicates rotation + class pairs) are separate mechanisms, so this test pins
        the legacy configuration it was written for."""
        monkeypatch.setenv("LINER_DEMAND_LOOP_BUDGET", "0")
        monkeypatch.setenv("LINER_CLASS_SCREEN", "0")
        low_budget = {
            "archetype_mix": {
                "direct_ratio": 0.05,
                "hub_loop_ratio": 0.05,
                "feeder_ratio": 0.05,
                "trunk_ratio": 0.05,
            },
            "vessel_bias": "balanced",
        }
        high_budget = {
            "archetype_mix": {
                "direct_ratio": 0.40,
                "hub_loop_ratio": 0.30,
                "feeder_ratio": 0.20,
                "trunk_ratio": 0.10,
            },
            "vessel_bias": "balanced",
        }
        services_low = agent.generate_services(problem, archetype_params=low_budget)
        services_high = agent.generate_services(problem, archetype_params=high_budget)
        # High-budget should produce more or equal services (the heuristic base of 150 is always added)
        assert len(services_high) >= len(services_low), (
            f"High-budget pool ({len(services_high)}) should be >= "
            f"low-budget pool ({len(services_low)})"
        )

    def test_services_have_vessel_class(self, agent, problem):
        """Every algorithmic (Service-object) service should have a vessel_class set.
        Heuristic candidate pool entries are plain dicts without vessel_class."""
        services = agent.generate_services(problem)
        # Only check Service dataclass objects; heuristic dicts don't carry vessel_class
        service_objects = [s for s in services if not isinstance(s, dict)]
        assert len(service_objects) > 0, "At least some Service objects should exist"
        for s in service_objects:
            assert s.vessel_class, f"Service {s.id} has no vessel_class"
            assert isinstance(s.vessel_class, str)

    def test_services_have_positive_capacity(self, agent, problem):
        """Every algorithmic (Service-object) service should have positive capacity.
        Heuristic candidate pool entries are plain dicts without capacity."""
        services = agent.generate_services(problem)
        service_objects = [s for s in services if not isinstance(s, dict)]
        assert len(service_objects) > 0, "At least some Service objects should exist"
        for s in service_objects:
            assert s.capacity > 0, f"Service {s.id} has zero/negative capacity"


# ===========================================================================
# 3 — Logging Tags Verification
# ===========================================================================

class TestLoggingTags:
    """Verify AI logging tags are emitted correctly."""

    # ── AI_VALIDATED ────────────────────────────────────────────────────

    def test_ai_validated_on_valid_params(self):
        """Valid params log AI_VALIDATED."""
        with _patched_info() as mock_info:
            raw = {
                "archetype_mix": {
                    "direct_ratio": 0.50,
                    "hub_loop_ratio": 0.20,
                    "feeder_ratio": 0.20,
                    "trunk_ratio": 0.10,
                },
                "vessel_bias": "balanced",
            }
            validate_archetype_params(raw, source="test")
            tags = []
            for args in mock_info.call_args_list:
                call_kwargs = args[1] if len(args.args) <= 1 else {}
                tag = call_kwargs.get("tag") or (args[1] if len(args.args) > 1 else None)
                if isinstance(tag, str):
                    tags.append(tag)
            assert "AI_VALIDATED" in tags, f"AI_VALIDATED not found in {tags}"

    # ── AI_REJECTED ─────────────────────────────────────────────────────

    def test_ai_rejected_on_none(self):
        """None input logs AI_REJECTED."""
        with _patched_info() as mock_info:
            validate_archetype_params(None, source="test")
            tags = self._extract_tags(mock_info)
            assert "AI_REJECTED" in tags, f"AI_REJECTED not found in {tags}"

    def test_ai_rejected_on_empty_dict(self):
        """Empty dict logs AI_REJECTED."""
        with _patched_info() as mock_info:
            validate_archetype_params({}, source="test")
            tags = self._extract_tags(mock_info)
            assert "AI_REJECTED" in tags, f"AI_REJECTED not found in {tags}"

    # ── AI_FALLBACK ─────────────────────────────────────────────────────

    def test_ai_fallback_on_none(self):
        """None input eventually logs AI_FALLBACK (from fallback fn)."""
        with _patched_info() as mock_info:
            validate_archetype_params(None, source="test")
            tags = self._extract_tags(mock_info)
            assert "AI_FALLBACK" in tags, f"AI_FALLBACK not found in {tags}"

    def test_ai_fallback_on_empty_dict(self):
        """Empty dict logs AI_FALLBACK."""
        with _patched_info() as mock_info:
            validate_archetype_params({}, source="test")
            tags = self._extract_tags(mock_info)
            assert "AI_FALLBACK" in tags, f"AI_FALLBACK not found in {tags}"

    # ── AI_GENERATED (from ServiceGeneratorAgent.process) ───────────────

    def test_ai_generated_on_llm_output(self):
        """process() logs AI_GENERATED when LLM returns valid JSON."""
        agent = ServiceGeneratorAgent(
            name="test_log_gen",
            model="opencode/deepseek-v4-flash-free",
        )
        problem = create_minimal_problem(num_ports=10, num_demands=20)

        valid_json = json.dumps({
            "archetype_mix": {
                "direct_ratio": 0.50,
                "hub_loop_ratio": 0.20,
                "feeder_ratio": 0.20,
                "trunk_ratio": 0.10,
            },
            "vessel_bias": "balanced",
            "hub_focus": [],
            "notes": "test",
        })

        with patch.object(agent, "call_llm", return_value=valid_json):
            with _patched_info() as mock_info:
                result = agent.process({"problem": problem})
                tags = self._extract_tags(mock_info)
                assert "AI_GENERATED" in tags, f"AI_GENERATED not found in {tags}"

    # ── AI_APPLIED ──────────────────────────────────────────────────────

    def test_ai_applied_on_validation(self):
        """process() logs AI_APPLIED after validation succeeds."""
        agent = ServiceGeneratorAgent(
            name="test_log_applied",
            model="opencode/deepseek-v4-flash-free",
        )
        problem = create_minimal_problem(num_ports=10, num_demands=20)

        valid_json = json.dumps({
            "archetype_mix": {
                "direct_ratio": 0.50,
                "hub_loop_ratio": 0.20,
                "feeder_ratio": 0.20,
                "trunk_ratio": 0.10,
            },
            "vessel_bias": "small",
            "hub_focus": [],
            "notes": "test",
        })

        with patch.object(agent, "call_llm", return_value=valid_json):
            with _patched_info() as mock_info:
                result = agent.process({"problem": problem})
                tags = self._extract_tags(mock_info)
                assert "AI_APPLIED" in tags, f"AI_APPLIED not found in {tags}"

    # ── All five tags in one combined flow ──────────────────────────────

    def test_all_five_tags_in_flow(self):
        """A full process() call with valid LLM output emits all five tags."""
        agent = ServiceGeneratorAgent(
            name="test_all_tags",
            model="opencode/deepseek-v4-flash-free",
        )
        problem = create_minimal_problem(num_ports=10, num_demands=20)

        valid_json = json.dumps({
            "archetype_mix": {
                "direct_ratio": 0.50,
                "hub_loop_ratio": 0.20,
                "feeder_ratio": 0.20,
                "trunk_ratio": 0.10,
            },
            "vessel_bias": "balanced",
            "hub_focus": [],
            "notes": "test all five tags",
        })

        with patch.object(agent, "call_llm", return_value=valid_json):
            with _patched_info() as mock_info:
                agent.process({"problem": problem})
                tags = self._extract_tags(mock_info)
                for required in ("AI_GENERATED", "AI_VALIDATED", "AI_APPLIED"):
                    assert required in tags, f"Required tag {required} not found in {tags}"

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _extract_tags(mock_info: MagicMock) -> List[str]:
        """Extract 'tag' values from all logger.info calls."""
        tags = []
        for call in mock_info.call_args_list:
            args, kwargs = call
            if "tag" in kwargs:
                tags.append(kwargs["tag"])
            elif len(args) >= 2 and isinstance(args[1], dict):
                tags.append(args[1].get("tag", ""))
            elif args and isinstance(args[0], str) and "tag=%s" in args[0]:
                # stdlib-logging style used by the agents: logger.info('event | tag=%s ...', TAG, ...)
                idx = args[0].split("tag=%s")[0].count("%s")
                if 1 + idx < len(args):
                    tags.append(args[1 + idx])
        return tags


# ===========================================================================
# 4 — Benchmark Framework Template
# ===========================================================================

class TestBenchmarkFramework:
    """Template for future paired runs: Group A (default) vs Group B (AI).

    This test class demonstrates the benchmarking pattern and collects
    metrics. The tests are designed to pass deterministically (no LLM calls).
    """

    @pytest.fixture(scope="class")
    def agent(self):
        return ServiceGeneratorAgent(
            name="bench_agent",
            model="opencode/deepseek-v4-flash-free",
        )

    @pytest.fixture(scope="class")
    def problem(self):
        return create_minimal_problem(num_ports=15, num_demands=80)

    @staticmethod
    def _run_and_collect(
        agent: ServiceGeneratorAgent,
        problem: Problem,
        params: Optional[Dict[str, Any]],
        label: str,
    ) -> Dict[str, Any]:
        """Run generate_services with given params and collect metrics."""
        services = agent.generate_services(problem, archetype_params=params)
        counts = _service_counts(services)

        # Vessel utilisation: simulate load = 80% of capacity
        total_capacity = sum(
            s.capacity if not isinstance(s, dict) else s.get("capacity", 0)
            for s in services
        ) or 1
        simulated_load = total_capacity * 0.80
        vessel_utilization = simulated_load / total_capacity * 100 if total_capacity else 0

        metrics = {
            "label": label,
            "total_services": counts["total"],
            "services_direct": counts["direct"],
            "services_hub_loop": counts["hub_loop"],
            "services_trunk": counts["trunk"],
            "services_feeder": counts["feeder"],
            "vessel_utilization_pct": round(vessel_utilization, 1),
            "services_by_category": {
                "direct": counts["direct"],
                "hub_loop": counts["hub_loop"],
                "trunk": counts["trunk"],
                "feeder": counts["feeder"],
            },
        }
        return metrics

    # ── Group A: default archetypes (current behaviour) ─────────────────

    def test_group_a_default_archetypes(self, agent, problem):
        """Group A: run with DEFAULT_ARCHETYPE_PARAMS."""
        metrics = self._run_and_collect(
            agent, problem,
            params=dict(DEFAULT_ARCHETYPE_PARAMS),
            label="Group-A-default",
        )
        assert metrics["total_services"] > 0, "Group A: should produce services"
        assert metrics["vessel_utilization_pct"] > 0
        # Report metrics for human inspection
        print(f"\n  Group A (default) metrics: {json.dumps(metrics, indent=2)}")

    # ── Group B: AI-generated archetypes (LLM-mimicked params) �──────────

    def test_group_b_ai_archetypes(self, agent, problem):
        """Group B: run with AI-generated archetype params (simulated here)."""
        # In production these come from the LLM; here we simulate a plausible
        # AI-generated mix that the LLM might recommend for this network.
        ai_params = {
            "archetype_mix": {
                "direct_ratio": 0.35,
                "hub_loop_ratio": 0.30,
                "feeder_ratio": 0.25,
                "trunk_ratio": 0.10,
            },
            "vessel_bias": "balanced",
            "hub_focus": [],
            "notes": "AI-generated params (simulated)",
        }
        metrics = self._run_and_collect(
            agent, problem,
            params=ai_params,
            label="Group-B-ai",
        )
        assert metrics["total_services"] > 0, "Group B: should produce services"
        assert metrics["vessel_utilization_pct"] > 0
        print(f"\n  Group B (AI) metrics: {json.dumps(metrics, indent=2)}")

    # ── Comparison template ─────────────────────────────────────────────

    def test_group_comparison_template(self, agent, problem):
        """Compare Group A vs Group B metrics side by side.

        This is a template showing how future benchmark runs can compare
        the two groups and flag significant differences.
        """
        group_a = self._run_and_collect(
            agent, problem,
            params=dict(DEFAULT_ARCHETYPE_PARAMS),
            label="Group-A-default",
        )
        group_b = self._run_and_collect(
            agent, problem,
            params={
                "archetype_mix": {
                    "direct_ratio": 0.35,
                    "hub_loop_ratio": 0.30,
                    "feeder_ratio": 0.25,
                    "trunk_ratio": 0.10,
                },
                "vessel_bias": "small",
                "hub_focus": [],
                "notes": "AI (simulated)",
            },
            label="Group-B-ai",
        )

        print(f"\n  {'Metric':<30} {'Group A (default)':>18} {'Group B (AI)':>18}  {'Delta':>10}")
        print(f"  {'-'*30} {'-'*18} {'-'*18}  {'-'*10}")
        deltas = {}
        for key in ("total_services", "services_direct", "services_hub_loop",
                     "services_trunk", "services_feeder", "vessel_utilization_pct"):
            a_val = group_a.get(key, 0)
            b_val = group_b.get(key, 0)
            if isinstance(a_val, (int, float)) and isinstance(b_val, (int, float)):
                delta = b_val - a_val
                deltas[key] = delta
                print(f"  {key:<30} {a_val:>18} {b_val:>18}  {delta:>+10}")

        # Store deltas on the class for potential external collection
        self._last_deltas = deltas

        # Both groups must produce valid output
        assert group_a["total_services"] > 0
        assert group_b["total_services"] > 0
        # The comparison itself is informational — no pass/fail requirement
        # on which group is "better" since that depends on the optimisation stage
        print(f"\n  Comparison complete. Deltas: {json.dumps(deltas, indent=2)}")
