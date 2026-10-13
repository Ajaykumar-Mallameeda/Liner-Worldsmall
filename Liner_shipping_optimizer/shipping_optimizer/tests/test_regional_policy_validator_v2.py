"""
Tests for regional_policy_validator_v2 — Phase F4.

Covers the stricter V2 rules:
  - Anti-neutral check
  - Coverage/profit balance
  - Vessel-bias sanity
  - Baseline drift
  - Evidence citation requirement
"""

import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validation.regional_policy_validator_v2 import (
    validate_regional_policy_v2,
    _is_neutral,
    _coverage_profit_balance_ok,
    _vessel_matches_lane_volume,
    _evidence_cites_metrics,
    _policy_drift,
    V2_POLICY_KEYS,
    VALID_SERVICE_STYLES,
)
from src.utils.logger import logger


# Sample baseline policy
SAMPLE_BASELINE = {
    "coverage_priority": 0.80,
    "profit_priority":   0.30,
    "min_service_margin": 0.10,
    "vessel_bias": "small",
    "hub_focus": ["P001"],
    "corridor_focus": [["P001", "P002"]],
    "notes": "sparse network, low concentration",
}

SAMPLE_METRICS = {
    "median_lane_volume": 8.0,
    "total_demand": 5000.0,
    "top3_corridor_share": 5.0,
    "network_density": 70.0,
    "hub_centrality": 14.0,
    "import_export_imbalance": 90.0,
    "dominant_vessel_requirement": "feeder",
    "derived": {
        "concentration_level": "moderate",
        "density_level": "dense",
    },
}


# ── Neutral detection ──────────────────────────────────────────────
class TestNeutralDetection:
    def test_truly_neutral_detected(self):
        policy = {
            "coverage_priority": 0.5,
            "profit_priority":   0.5,
            "vessel_bias":       "balanced",
            "hub_focus":         [],
            "corridor_focus":    [],
        }
        assert _is_neutral(policy) is True

    def test_non_neutral_detected(self):
        policy = {
            "coverage_priority": 0.7,
            "profit_priority":   0.3,
            "vessel_bias":       "large",
            "hub_focus":         ["P001"],
            "corridor_focus":    [],
        }
        assert _is_neutral(policy) is False


# ── Coverage/profit balance ────────────────────────────────────────
class TestCoverageProfitBalance:
    def test_balanced(self):
        assert _coverage_profit_balance_ok({"coverage_priority": 0.5, "profit_priority": 0.5}) is True

    def test_skewed_but_ok(self):
        assert _coverage_profit_balance_ok({"coverage_priority": 0.8, "profit_priority": 0.3}) is True

    def test_too_skewed(self):
        assert _coverage_profit_balance_ok({"coverage_priority": 0.9, "profit_priority": 0.9}) is False


# ── Vessel-bias sanity ─────────────────────────────────────────────
class TestVesselSanity:
    def test_small_lanes_small_vessel_ok(self):
        assert _vessel_matches_lane_volume("small", 8) is True

    def test_small_lanes_large_vessel_rejected(self):
        # 8 TEU/lane is tiny — large vessel inappropriate
        assert _vessel_matches_lane_volume("large", 8) is False

    def test_large_lanes_large_vessel_ok(self):
        assert _vessel_matches_lane_volume("large", 8000) is True

    def test_none_lane_volume_skips_check(self):
        assert _vessel_matches_lane_volume("balanced", None) is True


# ── Evidence citation ──────────────────────────────────────────────
class TestEvidenceCitation:
    def test_valid_evidence(self):
        assert _evidence_cites_metrics("high density 70% demands large vessels") is True

    def test_no_evidence(self):
        assert _evidence_cites_metrics("") is False

    def test_vague_evidence(self):
        assert _evidence_cites_metrics("just do it") is False

    def test_list_evidence(self):
        assert _evidence_cites_metrics(["concentration=high", "density=dense"]) is True


# ── Policy drift ───────────────────────────────────────────────────
class TestPolicyDrift:
    def test_identical_zero_drift(self):
        p1 = p2 = SAMPLE_BASELINE
        assert _policy_drift(p1, p2) == 0.0

    def test_some_drift(self):
        p1 = dict(SAMPLE_BASELINE, coverage_priority=0.5)
        assert _policy_drift(p1, SAMPLE_BASELINE) > 0.0


# ── V2 validator — end-to-end ──────────────────────────────────────
class TestV2Validator:
    def test_neutral_policy_without_evidence_rejected(self):
        """A neutral LLM output with no evidence falls back to baseline."""
        raw = {
            "coverage_priority": 0.5,
            "profit_priority":   0.5,
            "vessel_bias":       "balanced",
            "hub_focus":         [],
            "corridor_focus":    [],
        }
        result = validate_regional_policy_v2(
            raw, source="test", baseline_policy=SAMPLE_BASELINE,
        )
        # Should fall back to baseline values
        assert result["coverage_priority"] == 0.80
        assert result["vessel_bias"] == "small"

    def test_neutral_policy_with_evidence_accepted(self):
        """A neutral policy that cites metrics passes."""
        raw = {
            "coverage_priority": 0.5,
            "profit_priority":   0.5,
            "vessel_bias":       "balanced",
            "hub_focus":         [],
            "corridor_focus":    [],
            "evidence":          "concentration=moderate, density=moderate — neutral justified",
        }
        result = validate_regional_policy_v2(raw, source="test")
        assert result["coverage_priority"] == 0.5

    def test_balanced_cov_prof_rejected(self):
        """High coverage AND high profit is rejected."""
        raw = {
            "coverage_priority": 0.9,
            "profit_priority":   0.9,
            "vessel_bias":       "balanced",
        }
        result = validate_regional_policy_v2(
            raw, source="test", baseline_policy=SAMPLE_BASELINE,
        )
        # Falls back to baseline (which has 0.8/0.3)
        assert result["coverage_priority"] == 0.80

    def test_vessel_mismatch_rejected(self):
        """Large vessel bias for tiny median lane volume → baseline."""
        raw = {
            "coverage_priority": 0.7,
            "profit_priority":   0.3,
            "vessel_bias":       "large",
        }
        metrics = dict(SAMPLE_METRICS, median_lane_volume=5.0)
        result = validate_regional_policy_v2(
            raw, source="test", baseline_policy=SAMPLE_BASELINE,
            regional_metrics=metrics,
        )
        # Baseline vessel_bias=small wins
        assert result["vessel_bias"] == "small"

    def test_high_drift_without_evidence_rejected(self):
        """A wildly different policy without evidence is replaced by baseline."""
        raw = {
            "coverage_priority": 0.1,
            "profit_priority":   0.1,
            "min_service_margin": 0.0,
            "vessel_bias":       "small",
        }
        result = validate_regional_policy_v2(
            raw, source="test", baseline_policy=SAMPLE_BASELINE,
        )
        # Drift > 0.6 — should fall back
        assert result["coverage_priority"] == 0.80

    def test_high_drift_with_evidence_accepted(self):
        """A high-drift policy with metric evidence passes."""
        raw = {
            "coverage_priority": 0.2,
            "profit_priority":   0.8,
            "min_service_margin": 0.25,
            "vessel_bias":       "large",
            "evidence":          "top-3 share=55% concentration very_high → profit_priority=0.8",
        }
        metrics = dict(SAMPLE_METRICS, median_lane_volume=8000.0)
        result = validate_regional_policy_v2(
            raw, source="test", baseline_policy=SAMPLE_BASELINE,
            regional_metrics=metrics,
        )
        assert result["coverage_priority"] == 0.2
        assert result["profit_priority"]   == 0.8
        assert result["vessel_bias"]       == "large"

    def test_valid_policy_passes(self):
        raw = {
            "coverage_priority":  0.7,
            "profit_priority":    0.3,
            "min_service_margin": 0.10,
            "vessel_bias":        "small",
            "service_style":      "feeder",
        }
        result = validate_regional_policy_v2(raw, source="test")
        assert result["coverage_priority"] == 0.7
        assert result["service_style"] == "feeder"
        assert result["confidence"] == 0.5  # default

    def test_returns_all_v2_keys(self):
        raw = {
            "coverage_priority":  0.7,
            "profit_priority":    0.3,
        }
        result = validate_regional_policy_v2(raw, source="test")
        for key in V2_POLICY_KEYS:
            assert key in result, f"V2 key {key} missing"

    def test_invalid_service_style_falls_back(self):
        raw = {
            "coverage_priority":  0.7,
            "profit_priority":    0.3,
            "service_style":      "made_up_style",
        }
        result = validate_regional_policy_v2(raw, source="test")
        assert result["service_style"] == "hybrid"

    def test_valid_service_styles_pass(self):
        for style in VALID_SERVICE_STYLES:
            raw = {
                "coverage_priority":  0.7,
                "profit_priority":    0.3,
                "service_style":      style,
            }
            result = validate_regional_policy_v2(raw, source="test")
            assert result["service_style"] == style


# ── Anti-collapse regression — different inputs yield different policies
class TestAntiCollapse:
    """Region-A vs Region-B should produce different outputs from the V2 chain."""

    def test_different_metrics_yield_different_baselines(self):
        from src.agents.regional_metrics import compute_regional_metrics
        from src.agents.regional_policy_mapping import derive_regional_policy
        from src.optimization.data import Problem, Port, Demand

        def make_problem(median_teu: float, n_lanes: int) -> Problem:
            ports = [Port(id=f"P{i:03d}", name=f"P{i}", latitude=10.0, longitude=20.0)
                     for i in range(1, 11)]
            demands = []
            for i in range(n_lanes):
                demands.append(Demand(
                    origin="P001",
                    destination="P002",
                    weekly_teu=median_teu,
                    revenue_per_teu=150.0,
                ))
            dm = {p.id: {q.id: 100.0 for q in ports} for p in ports}
            return Problem(ports=ports, services=[], demands=demands, distance_matrix=dm)

        # Region A: tiny lanes, sparse
        prob_a = make_problem(median_teu=5, n_lanes=5)
        # Region B: large lanes, dense
        prob_b = make_problem(median_teu=10000, n_lanes=80)

        m_a = compute_regional_metrics(prob_a, region_name="A")
        m_b = compute_regional_metrics(prob_b, region_name="B")
        p_a = derive_regional_policy(m_a, problem=prob_a)
        p_b = derive_regional_policy(m_b, problem=prob_b)

        assert p_a["vessel_bias"] != p_b["vessel_bias"]
        assert p_a["min_service_margin"] != p_b["min_service_margin"]
