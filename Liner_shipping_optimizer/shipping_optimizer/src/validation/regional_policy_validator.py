"""
Regional Policy Validator 

Validates, clamps, and normalises regional policy parameters produced by
the RegionalAgent (LLM or rule-based) before they reach process().

Required log tags:
  AI_GENERATED  — raw policy from the LLM
  AI_VALIDATED  — policy that passed validation
  AI_REJECTED   — policy that failed validation
  AI_FALLBACK   — fallback policy used when source was invalid
"""

from typing import Any, Dict, List, Optional, Set, Union
from src.utils.logger import logger


# ── Bounds ─────────────────────────────────────────────────────────────
COVERAGE_PRIORITY_MIN = 0.0
COVERAGE_PRIORITY_MAX = 1.0
PROFIT_PRIORITY_MIN   = 0.0
PROFIT_PRIORITY_MAX   = 1.0
MIN_SERVICE_MARGIN_MIN = 0.0
MIN_SERVICE_MARGIN_MAX = 0.30

VALID_VESSEL_BIASES = {"small", "balanced", "large"}
VALID_VESSEL_BIASES_LIST = ["small", "balanced", "large"]

# ── Default policy — safe, neutral values ─────────────────────────────
DEFAULT_REGIONAL_POLICY: Dict[str, Any] = {
    "coverage_priority":  0.50,
    "profit_priority":    0.50,
    "min_service_margin": 0.05,
    "vessel_bias":       "balanced",
    "hub_focus":          [],
    "corridor_focus":     [],
    "notes":              "",
}

# ── Expected keys for logging ─────────────────────────────────────────
POLICY_KEYS = [
    "coverage_priority",
    "profit_priority",
    "min_service_margin",
    "vessel_bias",
    "hub_focus",
    "corridor_focus",
    "notes",
]


def _to_bool(val: Any) -> Optional[bool]:
    """Loose boolean coercion for optional fields."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    if isinstance(val, (int, float)):
        return val != 0
    return None


def _get_float(d: dict, key: str, default: Optional[float] = None) -> Optional[float]:
    """Case-insensitivity helper for float fields.
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
    # Try short forms (e.g. "coverage" for "coverage_priority")
    short = key.replace("_priority", "").replace("_margin", "").replace("service_", "")
    for dk, dv in d.items():
        dk_normalised = dk.replace("_priority", "").replace("_margin", "").replace("service_", "")
        if dk_normalised == short:
            return _to_float(dv)
    return None


def _any_key_present(d: dict, keys: list) -> bool:
    """Check whether at least one expected key exists in d."""
    for key in keys:
        if key in d:
            return True
    return False


def _port_id_str(pid: Any) -> str:
    """Normalise a port ID to string for set membership checks."""
    return str(pid)


def _validate_corridor_focus(raw: Any) -> List[List[str]]:
    """Validate and normalise corridor_focus to list of [origin, destination] pairs."""
    if not isinstance(raw, list):
        return []
    validated = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            o, d = item
            # Accept int or str port IDs, normalise to str
            validated.append([str(o), str(d)])
        elif isinstance(item, dict) and "origin" in item and "destination" in item:
            validated.append([str(item["origin"]), str(item["destination"])])
        # Skip invalid entries
    return validated


def _fallback_regional_policy(reason: str = "") -> Dict[str, Any]:
    """Return safe default regional policy with AI_FALLBACK log."""
    fallback = dict(DEFAULT_REGIONAL_POLICY)
    logger.info(
        "regional_policy_validation",
        tag="AI_FALLBACK",
        reason=reason or "unknown",
        default_policy=fallback,
    )
    return fallback


def validate_regional_policy(
    raw: Any,
    valid_port_ids: Optional[Set[str]] = None,
    source: str = "llm",
) -> Dict[str, Any]:
    """
    Validate, clamp, and normalise a regional policy dict.

    Accepts any input shape (None, {}, {"coverage_priority": ...}) and returns
    a guaranteed-valid dict matching DEFAULT_REGIONAL_POLICY structure.

    Guarantees:
      - coverage_priority in [0.0, 1.0]
      - profit_priority in [0.0, 1.0]
      - min_service_margin in [0.0, 0.30]
      - vessel_bias is one of {"small", "balanced", "large"}
      - hub_focus is a list (filtered to valid_port_ids when set is provided)
      - corridor_focus is a list of [origin, destination] pairs

    Logging tags used:
      AI_GENERATED  — raw input printed (only on first structural presence)
      AI_VALIDATED  — policy passed structural checks
      AI_REJECTED   — policy structurally invalid
      AI_FALLBACK   — fell back to default policy
    """

    # ── Structure check ─────────────────────────────────────────────────
    if not isinstance(raw, dict):
        logger.info(
            "regional_policy_validation",
            tag="AI_REJECTED",
            reason=f"expected dict, got {type(raw).__name__}",
            source=source,
        )
        return _fallback_regional_policy(reason=f"not a dict: {type(raw).__name__}")

    if not raw:
        logger.info(
            "regional_policy_validation",
            tag="AI_REJECTED",
            reason="empty dict",
            source=source,
        )
        return _fallback_regional_policy(reason="empty dict")

    # ── AI_GENERATED log (raw policy received from LLM) ────────────────
    logger.info(
        "regional_policy_validation",
        tag="AI_GENERATED",
        source=source,
        raw_keys=list(raw.keys()),
        raw_sample={k: raw[k] for k in list(raw.keys())[:6]},
    )

    # ── coverage_priority ─────────────────────────────────────────────
    cov_raw = _get_float(raw, "coverage_priority", None)
    if cov_raw is None:
        logger.info(
            "regional_policy_validation",
            tag="AI_REJECTED",
            reason="coverage_priority missing or non-numeric",
            source=source,
        )
        coverage_priority = DEFAULT_REGIONAL_POLICY["coverage_priority"]
    else:
        coverage_priority = max(COVERAGE_PRIORITY_MIN, min(COVERAGE_PRIORITY_MAX, cov_raw))

    # ── profit_priority ───────────────────────────────────────────────
    prof_raw = _get_float(raw, "profit_priority", None)
    if prof_raw is None:
        logger.info(
            "regional_policy_validation",
            tag="AI_REJECTED",
            reason="profit_priority missing or non-numeric",
            source=source,
        )
        profit_priority = DEFAULT_REGIONAL_POLICY["profit_priority"]
    else:
        profit_priority = max(PROFIT_PRIORITY_MIN, min(PROFIT_PRIORITY_MAX, prof_raw))

    # ── min_service_margin ────────────────────────────────────────────
    margin_raw = _get_float(raw, "min_service_margin", None)
    if margin_raw is None:
        # Not critical — use default silently
        min_service_margin = DEFAULT_REGIONAL_POLICY["min_service_margin"]
    else:
        min_service_margin = max(MIN_SERVICE_MARGIN_MIN, min(MIN_SERVICE_MARGIN_MAX, margin_raw))

    # ── vessel_bias ────────────────────────────────────────────────────
    vb = raw.get("vessel_bias", DEFAULT_REGIONAL_POLICY["vessel_bias"])
    if isinstance(vb, str) and vb.lower() in VALID_VESSEL_BIASES:
        vessel_bias = vb.lower()
    else:
        logger.info(
            "regional_policy_validation",
            tag="AI_REJECTED",
            reason=f"invalid vessel_bias: {vb!r}",
            source=source,
            valid_biases=VALID_VESSEL_BIASES_LIST,
        )
        vessel_bias = DEFAULT_REGIONAL_POLICY["vessel_bias"]

    # ── hub_focus ──────────────────────────────────────────────────────
    hf = raw.get("hub_focus", [])
    if isinstance(hf, list):
        # Normalise to strings for set comparison
        if valid_port_ids is not None:
            hf = [_port_id_str(p) for p in hf if _port_id_str(p) in valid_port_ids]
        else:
            hf = [_port_id_str(p) for p in hf]
    else:
        hf = []

    # ── corridor_focus ─────────────────────────────────────────────────
    cf = raw.get("corridor_focus", [])
    corridor_focus = _validate_corridor_focus(cf)

    # ── notes ──────────────────────────────────────────────────────────
    notes = raw.get("notes", "")
    notes = str(notes) if notes else ""

    # ── Assemble result ────────────────────────────────────────────────
    result: Dict[str, Any] = {
        "coverage_priority":  round(coverage_priority, 4),
        "profit_priority":    round(profit_priority, 4),
        "min_service_margin": round(min_service_margin, 4),
        "vessel_bias":        vessel_bias,
        "hub_focus":          hf,
        "corridor_focus":     corridor_focus,
        "notes":              notes,
    }

    logger.info(
        "regional_policy_validation",
        tag="AI_VALIDATED",
        source=source,
        policy=result,
    )

    return result
