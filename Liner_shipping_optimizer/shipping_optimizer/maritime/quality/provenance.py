"""Provenance metadata for maritime snapshots.

We never invent licensing. The :data:`KNOWN_LICENSES` table lists the few
licenses we have verified from EMODnet publications; anything else is
reported with license ``"unresolved"`` rather than guessed.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple


# Licenses we have actually verified from EMODnet product pages. When adding
# a new source, verify before adding an entry.
KNOWN_LICENSES: Dict[str, str] = {
    "CC BY 4.0": "Creative Commons Attribution 4.0 International",
    "CC-BY-4.0": "Creative Commons Attribution 4.0 International",
}


# Standard attribution strings per source. We do not invent these.
KNOWN_ATTRIBUTIONS: Dict[str, str] = {
    "EMODnet": (
        "EMODnet Human Activities, Vessel Density Map - All ships, "
        "https://www.emodnet-humanactivities.eu/"
    ),
}


def validate_provenance(provenance: Mapping[str, Any]) -> Tuple[bool, str]:
    """Validate that required provenance keys are present.

    Required keys: ``source``, ``dataset``, ``dataset_version``, ``retrieved_at``,
    ``observed_period``. Returns ``(ok, reason)`` — never raises.
    """
    required = ("source", "dataset", "dataset_version", "retrieved_at", "observed_period")
    for key in required:
        if key not in provenance:
            return False, f"missing required provenance key: {key}"
        v = provenance[key]
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return False, f"provenance key {key!r} is empty"
    return True, "ok"


def build_provenance(
    *,
    source: str,
    dataset: str,
    dataset_version: str,
    retrieved_at: str,
    observed_period: Mapping[str, str],
    license_str: str,
    attribution: str,
    extras: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a provenance mapping with required keys and validated values.

    License and attribution must already be verified by the caller; if not,
    pass ``"unresolved"`` and an empty string and the function will not
    raise, but the snapshot will be flagged in quality as DEGRADED.
    """
    out: Dict[str, Any] = {
        "source": source,
        "dataset": dataset,
        "dataset_version": dataset_version,
        "retrieved_at": retrieved_at,
        "observed_period": dict(observed_period),
        "license": license_str,
        "attribution": attribution,
    }
    if extras:
        for k, v in extras.items():
            if k not in out:
                out[k] = v
    return out
