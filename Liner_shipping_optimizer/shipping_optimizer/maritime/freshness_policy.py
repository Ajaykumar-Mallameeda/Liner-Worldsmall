"""Phase 3 — Freshness policy.

Deterministic, configurable freshness policy. Resolves a snapshot's
freshness state to one of the seven canonical states:

    UNKNOWN     -> no information yet
    CHECKING    -> a check is in flight (transient)
    AVAILABLE   -> fresh and valid
    DEGRADED    -> fresh but low quality / partial data
    STALE       -> older than the freshness window
    OFFLINE     -> no snapshot / source unreachable
    INVALID     -> snapshot on disk is corrupted or schema-incompatible

The policy is the single source of truth for "is this safe to ship as
fresh?" and is consulted by the fallback resolver.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class FreshnessState(str, Enum):
    UNKNOWN = "unknown"
    CHECKING = "checking"
    AVAILABLE = "available"
    DEGRADED = "degraded"
    STALE = "stale"
    OFFLINE = "offline"
    INVALID = "invalid"


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _parse_iso(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------


@dataclass(frozen=True)
class FreshnessConfig:
    """Freshness thresholds.

    All values are tunable via env variables. Defaults are documented
    and conservative.

    * ``fresh_after_seconds`` (default 7 days) — snapshots younger than
      this are considered fresh. Older snapshots are checked against
      ``stale_after_seconds``.
    * ``stale_after_seconds`` (default 30 days) — snapshots older than
      this are explicitly STALE.
    * ``degraded_quality_floor`` (default 0.5) — quality below this
      promotes the state to DEGRADED even when fresh.
    """
    fresh_after_seconds: int = 60 * 60 * 24 * 7
    stale_after_seconds: int = 60 * 60 * 24 * 30
    degraded_quality_floor: float = 0.5
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "FreshnessConfig":
        return cls(
            fresh_after_seconds=_env_int("MARITIME_FRESH_AFTER_SECONDS", 60 * 60 * 24 * 7),
            stale_after_seconds=_env_int("MARITIME_STALE_AFTER_SECONDS", 60 * 60 * 24 * 30),
            degraded_quality_floor=_env_float("MARITIME_DEGRADED_QUALITY_FLOOR", 0.5),
            enabled=_env_bool("MARITIME_INTELLIGENCE_ENABLED", False),
        )


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# --------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------


@dataclass(frozen=True)
class FreshnessEvaluation:
    state: FreshnessState
    age_seconds: float
    is_fresh: bool
    is_stale: bool
    is_degraded_quality: bool
    notes: str

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "age_seconds": round(self.age_seconds, 3),
            "is_fresh": self.is_fresh,
            "is_stale": self.is_stale,
            "is_degraded_quality": self.is_degraded_quality,
            "notes": self.notes,
        }


def evaluate(
    *,
    snapshot_created_at: Optional[str],
    quality_score: Optional[float],
    verification_ok: bool,
    config: Optional[FreshnessConfig] = None,
    now: Optional[datetime] = None,
) -> FreshnessEvaluation:
    """Evaluate the freshness state of a snapshot."""
    cfg = config or FreshnessConfig()
    eval_at = now or _utcnow()

    if not verification_ok:
        return FreshnessEvaluation(
            state=FreshnessState.INVALID,
            age_seconds=0.0,
            is_fresh=False,
            is_stale=False,
            is_degraded_quality=False,
            notes="verification_failed",
        )

    if not snapshot_created_at:
        return FreshnessEvaluation(
            state=FreshnessState.OFFLINE,
            age_seconds=0.0,
            is_fresh=False,
            is_stale=False,
            is_degraded_quality=False,
            notes="missing_created_at",
        )

    created = _parse_iso(snapshot_created_at)
    if created is None:
        return FreshnessEvaluation(
            state=FreshnessState.INVALID,
            age_seconds=0.0,
            is_fresh=False,
            is_stale=False,
            is_degraded_quality=False,
            notes="unparseable_created_at",
        )

    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    age = (eval_at - created).total_seconds()
    if age < 0:
        # Future timestamp: treat as INVALID rather than pretend it's fresh.
        return FreshnessEvaluation(
            state=FreshnessState.INVALID,
            age_seconds=float(age),
            is_fresh=False,
            is_stale=False,
            is_degraded_quality=False,
            notes="future_created_at",
        )

    is_degraded = (
        quality_score is not None and quality_score < cfg.degraded_quality_floor
    )
    is_stale = age > cfg.stale_after_seconds
    is_fresh = age <= cfg.fresh_after_seconds

    if is_stale:
        return FreshnessEvaluation(
            state=FreshnessState.STALE,
            age_seconds=age,
            is_fresh=False,
            is_stale=True,
            is_degraded_quality=is_degraded,
            notes="age_exceeds_stale_threshold",
        )
    if is_fresh and not is_degraded:
        return FreshnessEvaluation(
            state=FreshnessState.AVAILABLE,
            age_seconds=age,
            is_fresh=True,
            is_stale=False,
            is_degraded_quality=False,
            notes="fresh",
        )
    if is_fresh and is_degraded:
        return FreshnessEvaluation(
            state=FreshnessState.DEGRADED,
            age_seconds=age,
            is_fresh=True,
            is_stale=False,
            is_degraded_quality=True,
            notes="fresh_but_low_quality",
        )
    # Between fresh and stale window: still ship as DEGRADED rather than STALE.
    return FreshnessEvaluation(
        state=FreshnessState.DEGRADED,
        age_seconds=age,
        is_fresh=False,
        is_stale=False,
        is_degraded_quality=is_degraded,
        notes="between_fresh_and_stale",
    )
