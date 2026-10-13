"""Phase 3 — Deterministic fallback resolver.

Implements the strict fallback hierarchy requested by Phase 3 §8:

    1. fresh valid snapshot
    2. latest valid cached snapshot within allowed stale window
    3. known-good historical snapshot
    4. deterministic empty/neutral result
    5. safe failure state

The resolver is a pure function over its inputs. It does NOT call
the network, does NOT invoke an LLM, and does NOT mutate disk state.
The hierarchy is deterministic so that two consumers with the same
inputs always reach the same conclusion.

Two helpers are exposed:

* :func:`resolve_snapshot_fallback` — picks the best snapshot from a
  list of candidate snapshot directories given a freshness policy.
* :func:`empty_feature_dict` — returns the deterministic empty
  safe-default payload used by the dashboard / API / optimizer.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .freshness_policy import (
    FreshnessConfig,
    FreshnessEvaluation,
    FreshnessState,
    evaluate,
)
from .schema_registry import SchemaRegistry
from .snapshot_verifier import VerificationResult, verify_snapshot_directory


# --------------------------------------------------------------------
# Fallback tier
# --------------------------------------------------------------------


class FallbackTier(str, Enum):
    FRESH = "fresh"
    STALE_WITHIN_WINDOW = "stale_within_window"
    KNOWN_GOOD_HISTORICAL = "known_good_historical"
    EMPTY = "empty"
    FAILURE = "failure"


@dataclass(frozen=True)
class FallbackDecision:
    tier: FallbackTier
    snapshot_dir: Optional[Path]
    freshness: Optional[FreshnessEvaluation]
    verification: Optional[VerificationResult]
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.value,
            "snapshot_dir": str(self.snapshot_dir) if self.snapshot_dir else None,
            "freshness": self.freshness.to_dict() if self.freshness else None,
            "verification": self.verification.to_dict() if self.verification else None,
            "notes": self.notes,
        }


# --------------------------------------------------------------------
# Empty safe-default payload
# --------------------------------------------------------------------


EMPTY_FEATURE_PAYLOAD: Dict[str, Any] = {
    "enabled": False,
    "fresh": False,
    "state": FreshnessState.OFFLINE.value,
    "tier": FallbackTier.EMPTY.value,
    "source": None,
    "snapshot_id": None,
    "created_at": None,
    "record_count": 0,
    "quality_score": None,
    "freshness_label": None,
    "degraded_reasons": ["no_snapshot"],
    "checksum": None,
    "schema_version": None,
}


def empty_feature_dict(notes: Optional[str] = None) -> Dict[str, Any]:
    """Return the deterministic empty safe-default payload."""
    out = dict(EMPTY_FEATURE_PAYLOAD)
    if notes:
        out["degraded_reasons"] = [notes]
    return out


# --------------------------------------------------------------------
# Resolver
# --------------------------------------------------------------------


def _manifest_for(snapshot_dir: Path) -> Optional[Mapping[str, Any]]:
    p = snapshot_dir / "manifest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _metadata_for(snapshot_dir: Path) -> Optional[Mapping[str, Any]]:
    p = snapshot_dir / "metadata.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _verdict_for(
    snapshot_dir: Path,
    dataset: str,
    registry: SchemaRegistry,
    config: FreshnessConfig,
    now: Optional[datetime] = None,
) -> tuple[Optional[VerificationResult], Optional[FreshnessEvaluation]]:
    verification = verify_snapshot_directory(
        snapshot_dir,
        compatible_schema_versions=registry.compatible_versions(dataset),
    )
    meta = _metadata_for(snapshot_dir)
    created_at = meta.get("created_at") if meta else None
    quality = meta.get("quality_score") if meta else None
    freshness = evaluate(
        snapshot_created_at=created_at,
        quality_score=quality,
        verification_ok=verification.ok,
        config=config,
        now=now,
    )
    return verification, freshness


def resolve_snapshot_fallback(
    *,
    dataset: str,
    snapshot_root: Path,
    registry: Optional[SchemaRegistry] = None,
    config: Optional[FreshnessConfig] = None,
    allow_stale_window_seconds: int = 60 * 60 * 24 * 7,
    now: Optional[datetime] = None,
) -> FallbackDecision:
    """Pick the best snapshot from a snapshot root, falling back deterministically.

    The resolver scans the dataset directory in lex order (most recent
    first by name) and picks the first snapshot that matches the
    fallback hierarchy.

    ``now`` is an optional reference time for deterministic testing.
    Production code should omit it (the default is ``datetime.now()``).
    """
    cfg = config or FreshnessConfig()
    reg = registry or SchemaRegistry.with_defaults()

    candidates: List[Path] = []
    base = snapshot_root / dataset
    if base.is_dir():
        for child in sorted(base.iterdir(), reverse=True):
            if child.is_dir() and (child / "manifest.json").exists():
                candidates.append(child)

    if not candidates:
        return FallbackDecision(
            tier=FallbackTier.EMPTY,
            snapshot_dir=None,
            freshness=None,
            verification=None,
            notes="no_candidates",
        )

    # Tier 1: fresh valid snapshot.
    for cand in candidates:
        verification, freshness = _verdict_for(cand, dataset, reg, cfg, now=now)
        if freshness.state == FreshnessState.AVAILABLE:
            return FallbackDecision(
                tier=FallbackTier.FRESH,
                snapshot_dir=cand,
                freshness=freshness,
                verification=verification,
                notes="tier1_fresh",
            )

    # Tier 2: stale-but-valid within allowed stale window.
    for cand in candidates:
        verification, freshness = _verdict_for(cand, dataset, reg, cfg, now=now)
        if (
            freshness.state in (FreshnessState.STALE, FreshnessState.DEGRADED)
            and freshness.age_seconds <= cfg.stale_after_seconds + allow_stale_window_seconds
        ):
            return FallbackDecision(
                tier=FallbackTier.STALE_WITHIN_WINDOW,
                snapshot_dir=cand,
                freshness=freshness,
                verification=verification,
                notes="tier2_stale_within_window",
            )

    # Tier 3: known-good historical (any verified, even if stale past window).
    for cand in candidates:
        verification, freshness = _verdict_for(cand, dataset, reg, cfg, now=now)
        if verification.ok and freshness.state in (
            FreshnessState.AVAILABLE,
            FreshnessState.DEGRADED,
            FreshnessState.STALE,
        ):
            return FallbackDecision(
                tier=FallbackTier.KNOWN_GOOD_HISTORICAL,
                snapshot_dir=cand,
                freshness=freshness,
                verification=verification,
                notes="tier3_known_good_historical",
            )

    # Tier 4: deterministic empty (no verified snapshot).
    return FallbackDecision(
        tier=FallbackTier.EMPTY,
        snapshot_dir=None,
        freshness=None,
        verification=None,
        notes="no_verified_snapshot",
    )


# --------------------------------------------------------------------
# Tier 5 — safe failure
# --------------------------------------------------------------------


def safe_failure_payload(reason: str = "unreachable") -> Dict[str, Any]:
    """Tier-5 safe-failure payload. Distinct from the empty payload."""
    return {
        **empty_feature_dict(reason),
        "tier": FallbackTier.FAILURE.value,
        "degraded_reasons": [reason, "safe_failure"],
    }
