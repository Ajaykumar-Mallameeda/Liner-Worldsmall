"""
Archetype Parameter Validator — Phase B of Coordinator Activation Sprint.

Validates, clamps, and normalises archetype parameters produced by
the ServiceGeneratorAgent (LLM or rule-based) before they reach
generate_services().

Required log tags (Phase 2):
  AI_GENERATED  — raw parameters from the LLM
  AI_VALIDATED  — parameters that passed validation
  AI_REJECTED   — parameters that failed validation
  AI_FALLBACK   — fallback parameters used when source was invalid
"""

from typing import Any, Dict, Optional, Set
from src.utils.logger import logger


# ── Bounds ─────────────────────────────────────────────────────────────
RATIO_MIN = 0.05       # no ratio below 5%
RATIO_MAX = 0.80       # no ratio above 80%

VALID_VESSEL_BIASES = {"small", "balanced", "large"}

DEFAULT_ARCHETYPE_PARAMS: Dict[str, Any] = {
    "archetype_mix": {
        "direct_ratio":   0.60,
        "hub_loop_ratio": 0.15,
        "feeder_ratio":   0.20,
        "trunk_ratio":    0.05,
    },
    "vessel_bias": "balanced",
    "hub_focus": [],
    "notes": "",
}

DEFAULT_MIX = DEFAULT_ARCHETYPE_PARAMS["archetype_mix"]

# ── Key order for deterministic normalisation ──────────────────────────
MIX_KEYS = ["direct_ratio", "hub_loop_ratio", "feeder_ratio", "trunk_ratio"]


def validate_archetype_params(
    raw: Any,
    valid_port_ids: Optional[Set[str]] = None,
    source: str = "llm",
) -> Dict[str, Any]:
    """
    Validate, clamp, and normalise archetype parameters.

    Accepts any input shape (None, {}, {"direct_ratio": ...}) and returns
    a guaranteed-valid dict matching DEFAULT_ARCHETYPE_PARAMS structure.

    Guarantees:
      - All four ratios in [RATIO_MIN, RATIO_MAX]
      - Sum of all four ratios is exactly 1.0
      - vessel_bias is one of {"small", "balanced", "large"}
      - hub_focus entries are filtered to valid port IDs (when set is provided)

    Logging tags used:
      AI_GENERATED  — raw input printed (only on first structural presence)
      AI_VALIDATED  — parameters passed structural checks
      AI_REJECTED   — parameters structurally invalid
      AI_FALLBACK   — fell back to default parameters
    """

    # ── Structure check ─────────────────────────────────────────────────
    if not isinstance(raw, dict):
        logger.info(
            "archetype_param_validation",
            tag="AI_REJECTED",
            reason=f"expected dict, got {type(raw).__name__}",
            source=source,
        )
        return _fallback_archetype_params(reason=f"not a dict: {type(raw).__name__}")

    if not raw:
        logger.info(
            "archetype_param_validation",
            tag="AI_REJECTED",
            reason="empty dict",
            source=source,
        )
        return _fallback_archetype_params(reason="empty dict")

    # ── Extract archetype_mix ──────────────────────────────────────────
    mix = raw.get("archetype_mix", {})
    mix_valid = isinstance(mix, dict)
    if not mix_valid:
        logger.info(
            "archetype_param_validation",
            tag="AI_REJECTED",
            reason="archetype_mix not a dict",
            source=source,
            mix_type=type(mix).__name__,
        )
        # Fall through: use default ratios but keep validating other fields

    # Extract known ratio keys (returns None for missing keys)
    ratios = {}
    for key in MIX_KEYS:
        ratios[key] = _get_ratio(mix if mix_valid else {}, key, None)

    # If no ratio keys found, use default mix but continue validation
    effective_mix = mix if mix_valid else {}
    if not _any_key_present(effective_mix, MIX_KEYS):
        logger.info(
            "archetype_param_validation",
            tag="AI_REJECTED",
            reason="no recognised ratio keys found in archetype_mix",
            source=source,
            keys=list(effective_mix.keys()),
        )
        ratios = dict(DEFAULT_MIX)

    # ── Fill missing with default ───────────────────────────────────────
    for k in MIX_KEYS:
        v = ratios[k]
        if v is None:
            ratios[k] = DEFAULT_MIX[k]
        elif not isinstance(v, (int, float)):
            logger.info(
                "archetype_param_validation",
                tag="AI_REJECTED",
                reason=f"non-numeric value for {k}: {type(v).__name__}",
                source=source,
            )
            return _fallback_archetype_params(reason=f"non-numeric {k}={v!r}")

    # ── Clamp each ratio individually ──────────────────────────────────
    clamped = {}
    for k in MIX_KEYS:
        clamped[k] = max(RATIO_MIN, min(RATIO_MAX, ratios[k]))

    # ── Normalise so sum = 1.0 while respecting MIN/MAX bounds ─────────
    total_clamped = sum(clamped.values())

    if abs(total_clamped - 1.0) < 1e-6:
        # Already sums to 1.0 within tolerance
        normalised = {k: round(v, 4) for k, v in clamped.items()}
    else:
        # Scale proportionally, then handle bound violations iteratively
        scale = 1.0 / total_clamped
        normalised = {k: v * scale for k, v in clamped.items()}

        # Iterate up to 5 times (converges in practice after 1-2 passes)
        for _ in range(5):
            below = {k: v for k, v in normalised.items() if v < RATIO_MIN}
            above = {k: v for k, v in normalised.items() if v > RATIO_MAX}
            if not below and not above:
                break
            # Pin violators to their bound and redistribute surplus/deficit
            pinned_total = 0.0
            for k in list(normalised.keys()):
                if normalised[k] < RATIO_MIN:
                    pinned_total += RATIO_MIN - normalised[k]
                    normalised[k] = RATIO_MIN
                elif normalised[k] > RATIO_MAX:
                    pinned_total += normalised[k] - RATIO_MAX
                    normalised[k] = RATIO_MAX
            # Redistribute pinned surplus/deficit among unpinned weights
            unpinned = {k: v for k, v in normalised.items()
                        if RATIO_MIN <= v <= RATIO_MAX}
            if unpinned and abs(pinned_total) > 1e-8:
                adjust = pinned_total / len(unpinned)
                for k in unpinned:
                    normalised[k] += adjust

        # Round to 4 decimal places; last bucket absorbs remainder
        rounded = {}
        remaining = 1.0
        for i, k in enumerate(MIX_KEYS):
            if i == len(MIX_KEYS) - 1:
                rounded[k] = round(remaining, 4)
            else:
                val = round(normalised[k], 4)
                rounded[k] = val
                remaining -= val
        normalised = rounded

    # ── Final sanity: sum close to 1.0 ─────────────────────────────────
    final_sum = sum(normalised.values())
    if abs(final_sum - 1.0) > 0.02:
        # Last-resort: hard-normalise (should rarely trigger)
        normalised = {k: round(v / final_sum, 4) for k, v in normalised.items()}

    # ── vessel_bias ────────────────────────────────────────────────────
    vb = raw.get("vessel_bias", DEFAULT_ARCHETYPE_PARAMS["vessel_bias"])
    if isinstance(vb, str) and vb.lower() in VALID_VESSEL_BIASES:
        vessel_bias = vb.lower()
    else:
        logger.info(
            "archetype_param_validation",
            tag="AI_REJECTED",
            reason=f"invalid vessel_bias: {vb!r}",
            source=source,
            valid_biases=sorted(VALID_VESSEL_BIASES),
        )
        vessel_bias = DEFAULT_ARCHETYPE_PARAMS["vessel_bias"]

    # ── hub_focus ──────────────────────────────────────────────────────
    hf = raw.get("hub_focus", [])
    if isinstance(hf, list) and valid_port_ids is not None:
        hf = [p for p in hf if p in valid_port_ids]
    elif not isinstance(hf, list):
        hf = []

    # ── notes ──────────────────────────────────────────────────────────
    notes = raw.get("notes", "")
    notes = str(notes) if notes else ""

    result = {
        "archetype_mix": normalised,
        "vessel_bias": vessel_bias,
        "hub_focus": hf,
        "notes": notes,
    }

    logger.info(
        "archetype_param_validation",
        tag="AI_VALIDATED",
        source=source,
        raw_ratios=ratios,
        clamped_ratios=clamped,
        normalised_mix=normalised,
        vessel_bias=vessel_bias,
        hub_focus_count=len(hf),
    )

    return result


def _get_ratio(d: dict, key: str, default: float) -> Optional[float]:
    """Case-insensitive-ish key lookup for ratio keys.
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
    # Try without _ratio suffix
    short = key.replace("_ratio", "")
    for dk, dv in d.items():
        if dk.replace("_ratio", "") == short:
            return _to_float(dv)
    return None


def _any_key_present(d: dict, keys: list) -> bool:
    """Check whether at least one expected key exists in d (exact or short-form)."""
    for key in keys:
        if key in d:
            return True
        short = key.replace("_ratio", "")
        for dk in d:
            if dk.replace("_ratio", "") == short:
                return True
    return False


def _fallback_archetype_params(reason: str = "") -> Dict[str, Any]:
    """Return safe default archetype parameters with AI_FALLBACK log."""
    fallback = {
        "archetype_mix": {k: DEFAULT_MIX[k] for k in MIX_KEYS},
        "vessel_bias": DEFAULT_ARCHETYPE_PARAMS["vessel_bias"],
        "hub_focus": [],
        "notes": "",
    }
    logger.info(
        "archetype_param_validation",
        tag="AI_FALLBACK",
        reason=reason or "unknown",
        default_params=fallback,
    )
    return fallback
