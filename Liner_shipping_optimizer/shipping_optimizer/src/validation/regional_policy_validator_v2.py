"""
Regional Policy Validator

Builds on the original validator with stricter rules that prevent
default-neutral policies from passing without evidence.

Key additions over V1
---------------------
* **Anti-neutral check** — A policy with coverage=0.5, profit=0.5,
  vessel_bias=balanced, hub_focus=[], corridor_focus=[] is rejected
  unless the `evidence` field cites at least one regional metric that
  justifies the neutral choice.
* **Metric-citation check** — All major decisions must cite a metric
  from the regional profile (e.g. "high top-3 share 30% → profit_priority=0.7").
* **Baseline comparison** — If the LLM output drifts too far from the
  deterministic baseline without an explanation, log a warning.
* **Vessel bias sanity** — vessel_bias must align with median_lane_volume
  (small lanes → small/feeder; large lanes → large).
* **Coverage-profit trade-off** — The pair (coverage, profit) should
  sum to roughly 1.0 (±0.4) to avoid double-prioritisation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from src.utils.logger import logger
from src.validation.regional_policy_validator import (
    validate_regional_policy,
    DEFAULT_REGIONAL_POLICY,
    POLICY_KEYS,
    COVERAGE_PRIORITY_MIN,
    COVERAGE_PRIORITY_MAX,
    PROFIT_PRIORITY_MIN,
    PROFIT_PRIORITY_MAX,
    MIN_SERVICE_MARGIN_MIN,
    MIN_SERVICE_MARGIN_MAX,
    VALID_VESSEL_BIASES,
)


# ── V2 extended key set ─────────────────────────────────────────────
V2_POLICY_KEYS = POLICY_KEYS + [
    "service_style",
    "risk_notes",
    "confidence",
    "evidence",
]


VALID_SERVICE_STYLES = {"direct", "hub_and_spoke", "feeder", "hybrid"}


def _is_neutral(policy: Dict[str, Any]) -> bool:
    """A policy is neutral if all decision fields are at their default."""
    return (
        policy.get("coverage_priority",  0.5) == 0.5
        and policy.get("profit_priority",   0.5) == 0.5
        and policy.get("vessel_bias", "balanced") == "balanced"
        and not policy.get("hub_focus", [])
        and not policy.get("corridor_focus", [])
    )


def _coverage_profit_balance_ok(policy: Dict[str, Any], tol: float = 0.4) -> bool:
    """Coverage + profit should sum to roughly 1.0 to avoid double-prioritisation."""
    cov = policy.get("coverage_priority", 0.5)
    prof = policy.get("profit_priority", 0.5)
    return abs(cov + prof - 1.0) <= tol


def _vessel_matches_lane_volume(
    vessel_bias: str, median_lane_volume: Optional[float]
) -> bool:
    """Sanity check: vessel bias should agree with median lane volume."""
    if median_lane_volume is None:
        return True
    if median_lane_volume < 50:
        return vessel_bias in ("small", "balanced")
    if median_lane_volume < 500:
        return vessel_bias in ("small", "balanced")
    if median_lane_volume < 5000:
        return vessel_bias in ("small", "balanced", "large")
    return True  # large lanes tolerate any bias


def _evidence_cites_metrics(evidence: Any) -> bool:
    """Evidence must reference at least one numeric or metric keyword."""
    if not evidence:
        return False
    if not isinstance(evidence, (str, list)):
        return False
    text = " ".join(evidence) if isinstance(evidence, list) else evidence
    text_lower = text.lower()
    # At least one of these patterns indicates metric citation
    keywords = [
        "concentration", "density", "imbalance", "hub", "median", "avg",
        "top-3", "top3", "lane volume", "vessel", "demand",
        "service", "fragmentation", "centrality",
    ]
    return any(kw in text_lower for kw in keywords)


def validate_regional_policy_v2(
    raw: Any,
    valid_port_ids: Optional[Set[str]] = None,
    source: str = "llm",
    regional_metrics: Optional[Dict[str, Any]] = None,
    baseline_policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate a regional policy with V2 stricter rules.

    Parameters
    ----------
    raw : dict or None
        The raw LLM output (or fallback).
    valid_port_ids : set, optional
        Valid port IDs for filtering hub_focus and corridor_focus.
    source : str
        Where the policy came from ("llm" / "fallback" / "baseline").
    regional_metrics : dict, optional
        The Phase F1 metrics for this region — used to validate the
        vessel-bias sanity check and to permit neutral policies with
        evidence.
    baseline_policy : dict, optional
        The Phase F2 deterministic baseline — if the LLM output drifts
        too far without justification, the baseline is preferred.

    Returns
    -------
    dict
        A fully validated policy.  Falls back to the baseline if the
        LLM output fails V2 checks.
    """
    # Run the V1 validator first — it handles structural normalisation
    v1_result = validate_regional_policy(raw, valid_port_ids=valid_port_ids, source=source)

    # V2 metadata — confidence, evidence, service_style, risk_notes
    v1_result["confidence"] = _safe_float(raw.get("confidence") if isinstance(raw, dict) else None, 0.5)
    v1_result["service_style"] = _safe_service_style(raw.get("service_style") if isinstance(raw, dict) else None)
    v1_result["risk_notes"] = str(raw.get("risk_notes", "")) if isinstance(raw, dict) else ""
    evidence = raw.get("evidence", "") if isinstance(raw, dict) else ""
    if isinstance(evidence, list):
        evidence = "; ".join(str(e) for e in evidence)
    v1_result["evidence"] = str(evidence)

    # ── Anti-neutral check ────────────────────────────────────────
    if _is_neutral(v1_result):
        if _evidence_cites_metrics(v1_result["evidence"]):
            logger.info(
                "regional_policy_v2_validation",
                tag="V2_NEUTRAL_WITH_EVIDENCE",
                source=source,
                evidence=v1_result["evidence"][:200],
            )
        else:
            logger.info(
                "regional_policy_v2_validation",
                tag="V2_REJECT_NEUTRAL",
                source=source,
                reason="neutral policy without evidence; replacing with baseline",
            )
            if baseline_policy:
                return _policy_from_baseline(baseline_policy, reason="neutral_no_evidence")
            return _policy_from_baseline(v1_result, reason="neutral_no_evidence")

    # ── Coverage/profit balance check ─────────────────────────────
    if not _coverage_profit_balance_ok(v1_result):
        logger.info(
            "regional_policy_v2_validation",
            tag="V2_REJECT_BALANCE",
            source=source,
            cov=v1_result["coverage_priority"],
            prof=v1_result["profit_priority"],
        )
        if baseline_policy:
            return _policy_from_baseline(baseline_policy, reason="cov_prof_imbalance")

    # ── Vessel-bias sanity check ──────────────────────────────────
    if regional_metrics and not _vessel_matches_lane_volume(
        v1_result["vessel_bias"],
        regional_metrics.get("median_lane_volume"),
    ):
        logger.info(
            "regional_policy_v2_validation",
            tag="V2_REJECT_VESSEL_MISMATCH",
            source=source,
            vessel_bias=v1_result["vessel_bias"],
            median_lane_volume=regional_metrics.get("median_lane_volume"),
        )
        if baseline_policy:
            return _policy_from_baseline(baseline_policy, reason="vessel_mismatch")

    # ── Baseline drift check ──────────────────────────────────────
    if baseline_policy and isinstance(raw, dict):
        drift = _policy_drift(v1_result, baseline_policy)
        if drift > 0.6:
            logger.info(
                "regional_policy_v2_validation",
                tag="V2_REJECT_DRIFT",
                source=source,
                drift=round(drift, 3),
            )
            if not _evidence_cites_metrics(v1_result["evidence"]):
                return _policy_from_baseline(baseline_policy, reason="drift_no_evidence")

    logger.info(
        "regional_policy_v2_validation",
        tag="V2_VALIDATED",
        source=source,
        policy=v1_result,
    )
    return v1_result


def _policy_from_baseline(
    baseline: Dict[str, Any],
    reason: str,
) -> Dict[str, Any]:
    """Build a V2-valid policy from a baseline dict."""
    fallback = {
        "coverage_priority":  baseline.get("coverage_priority",  0.5),
        "profit_priority":    baseline.get("profit_priority",    0.5),
        "min_service_margin": baseline.get("min_service_margin", 0.05),
        "vessel_bias":        baseline.get("vessel_bias",        "balanced"),
        "hub_focus":          baseline.get("hub_focus",          []),
        "corridor_focus":     baseline.get("corridor_focus",     []),
        "notes":              baseline.get("notes",              ""),
        "service_style":      "hybrid",
        "risk_notes":         f"V2 fallback: {reason}",
        "confidence":         0.7,
        "evidence":           "deterministic baseline from regional metrics",
    }
    logger.info(
        "regional_policy_v2_validation",
        tag="V2_FALLBACK_BASELINE",
        reason=reason,
        policy=fallback,
    )
    return fallback


def _policy_drift(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    """Euclidean distance over (coverage, profit, margin, vessel) — vessel
    encoded as 0/0.5/1 for small/balanced/large."""
    vessel_code = {"small": 0.0, "balanced": 0.5, "large": 1.0}
    cov_d = p1.get("coverage_priority",  0.5) - p2.get("coverage_priority",  0.5)
    prof_d = p1.get("profit_priority",   0.5) - p2.get("profit_priority",   0.5)
    mar_d = p1.get("min_service_margin", 0.05) - p2.get("min_service_margin", 0.05)
    v1 = vessel_code.get(p1.get("vessel_bias", "balanced"), 0.5)
    v2 = vessel_code.get(p2.get("vessel_bias", "balanced"), 0.5)
    v_d = v1 - v2
    return (cov_d ** 2 + prof_d ** 2 + mar_d ** 2 + v_d ** 2) ** 0.5


def _safe_float(val: Any, default: float) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except (ValueError, TypeError):
            return default
    return default


def _safe_service_style(val: Any) -> str:
    if isinstance(val, str) and val.lower() in VALID_SERVICE_STYLES:
        return val.lower()
    return "hybrid"
