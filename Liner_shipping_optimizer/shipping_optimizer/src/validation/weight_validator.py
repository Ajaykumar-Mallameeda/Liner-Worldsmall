"""
Weight Validator 

Validates, clamps, and normalises GA weight adjustments produced by
the CoordinatorAgent (LLM or rule-based) before they reach the
Orchestrator._apply_feedback() method.

Required log tags:
  AI_GENERATED  — raw weights from the LLM
  AI_VALIDATED  — weights that passed validation
  AI_REJECTED   — weights that failed validation
  AI_FALLBACK   — fallback weights used when source was invalid
"""

from typing import Dict, Any, Optional
from src.utils.logger import logger


# ── Bounds ─────────────────────────────────────────────────────────────
MIN_WEIGHT     = 0.05   # no weight below 5%
MAX_WEIGHT     = 0.90   # no weight above 90%
TOLERANCE      = 0.02   # sum must be within 2% of 1.0


def validate_weight_adjustments(
    raw: Any,
    iteration: int = 0,
    source: str = "llm",
) -> Dict[str, float]:
    """
    Validate, clamp, and normalise a weight_adjustments dict.

    Accepts any input shape (None, {}, {"profit_weight": ...}) and returns
    a guaranteed-valid {profit_weight, coverage_weight, cost_weight} dict
    with values in [MIN_WEIGHT, MAX_WEIGHT] summing to 1.0.

    Logging tags used:
      AI_GENERATED  — raw input printed (only on first structural presence)
      AI_VALIDATED  — weights passed structural checks
      AI_REJECTED   — weights structurally invalid
      AI_FALLBACK   — fell back to default weights
    """

    # ── Structure check ─────────────────────────────────────────────────
    if not isinstance(raw, dict):
        logger.info(
            "coordinator_weight_validation",
            tag="AI_REJECTED",
            iteration=iteration,
            reason=f"expected dict, got {type(raw).__name__}",
            source=source,
        )
        return _fallback_weights(iteration, reason=f"not a dict: {type(raw).__name__}")

    if not raw:
        logger.info(
            "coordinator_weight_validation",
            tag="AI_REJECTED",
            iteration=iteration,
            reason="empty dict",
            source=source,
        )
        return _fallback_weights(iteration, reason="empty dict")

    # ── Extract known keys (case-insensitive on first letter) ───────────
    weights = {
        "profit_weight":   _get(raw, "profit_weight"),
        "coverage_weight": _get(raw, "coverage_weight"),
        "cost_weight":     _get(raw, "cost_weight"),
    }

    # Check that at least one value was actually present
    if all(v is None for v in weights.values()):
        logger.info(
            "coordinator_weight_validation",
            tag="AI_REJECTED",
            iteration=iteration,
            reason="no recognised weight keys found",
            source=source,
            keys=list(raw.keys()),
        )
        return _fallback_weights(iteration, reason=f"no recognised keys in {list(raw.keys())}")

    # ── Fill missing with default ───────────────────────────────────────
    defaults = {"profit_weight": 0.50, "coverage_weight": 0.40, "cost_weight": 0.10}
    for k in defaults:
        v = weights[k]
        if v is None:
            weights[k] = defaults[k]
        elif not isinstance(v, (int, float)):
            logger.info(
                "coordinator_weight_validation",
                tag="AI_REJECTED",
                iteration=iteration,
                reason=f"non-numeric value for {k}: {type(v).__name__}",
                source=source,
            )
            return _fallback_weights(iteration, reason=f"non-numeric {k}={v!r}")

    # ── Clamp each weight individually ──────────────────────────────────
    clamped = {}
    for k in defaults:
        clamped[k] = max(MIN_WEIGHT, min(MAX_WEIGHT, weights[k]))

    # ── Normalise so sum = 1.0 while respecting MIN/MAX bounds ──────────
    # After clamping, the sum might be >1.0 or <1.0.  We need a
    # distribution that respects [MIN_WEIGHT, MAX_WEIGHT] and sums to 1.0.
    # Strategy: proportional rescale within bounds.
    total_clamped = sum(clamped.values())

    if abs(total_clamped - 1.0) < 1e-6:
        # Already sums to 1.0 within tolerance
        normalised = {k: round(v, 4) for k, v in clamped.items()}
    else:
        # Scale proportionally, then handle bound violations iteratively
        scale = 1.0 / total_clamped
        normalised = {k: v * scale for k, v in clamped.items()}

        # If any weight fell below MIN_WEIGHT after scaling, redistribute
        # Iterate up to 5 times (converges in practice after 1-2 passes)
        for _ in range(5):
            below = {k: v for k, v in normalised.items() if v < MIN_WEIGHT}
            above = {k: v for k, v in normalised.items() if v > MAX_WEIGHT}
            if not below and not above:
                break
            # Pin violators to their bound and redistribute surplus/deficit
            pinned_total = 0.0
            pinned_count = 0
            for k in normalised:
                if normalised[k] < MIN_WEIGHT:
                    pinned_total += MIN_WEIGHT - normalised[k]
                    normalised[k] = MIN_WEIGHT
                    pinned_count += 1
                elif normalised[k] > MAX_WEIGHT:
                    pinned_total += normalised[k] - MAX_WEIGHT
                    normalised[k] = MAX_WEIGHT
                    pinned_count += 1
            # Redistribute pinned surplus/deficit among unpinned weights
            unpinned = {k: v for k, v in normalised.items()
                        if MIN_WEIGHT <= v <= MAX_WEIGHT}
            if unpinned and abs(pinned_total) > 1e-8:
                adjust = pinned_total / len(unpinned)
                for k in unpinned:
                    normalised[k] += adjust

        normalised = {k: round(v, 4) for k, v in normalised.items()}

    # ── Final sanity: sum close to 1.0 ──────────────────────────────────
    final_sum = sum(normalised.values())
    if abs(final_sum - 1.0) > TOLERANCE:
        # Last-resort: hard-normalise (should rarely trigger)
        normalised = {k: round(v / final_sum, 4) for k, v in normalised.items()}

    logger.info(
        "coordinator_weight_validation",
        tag="AI_VALIDATED",
        iteration=iteration,
        source=source,
        raw_weights=weights,
        clamped_weights=clamped,
        normalised_weights=normalised,
    )

    return normalised


def _get(d: dict, key: str) -> Optional[float]:
    """Case-insensitive-ish key lookup for common weight keys.
    Returns None for non-numeric values so the caller can reject gracefully."""
    def _to_float(val):
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        return None

    if key in d:
        return _to_float(d[key])
    # Try without _weight suffix
    short = key.replace("_weight", "")
    for dk, dv in d.items():
        if dk.replace("_weight", "") == short:
            return _to_float(dv)
    return None


def _fallback_weights(iteration: int, reason: str = "") -> Dict[str, float]:
    """Return safe default weights with AI_FALLBACK log."""
    fallback = {
        "profit_weight":   0.50,
        "coverage_weight": 0.40,
        "cost_weight":     0.10,
    }
    logger.info(
        "coordinator_weight_validation",
        tag="AI_FALLBACK",
        iteration=iteration,
        reason=reason or "unknown",
        default_weights=fallback,
    )
    return fallback
