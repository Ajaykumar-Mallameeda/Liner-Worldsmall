"""Freshness classification.

EMODnet publishes historical vessel-density products (typically yearly
aggregates). The freshness module therefore reports a *historical* product
as ``AVAILABLE / HEALTHY`` rather than ``LIVE``. A snapshot is considered
``STALE`` only after the cache age exceeds a configured threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Optional


_DEFAULT_STALE_AFTER_SECONDS = 60 * 60 * 24 * 30  # 30 days


@dataclass(frozen=True)
class Freshness:
    """Freshness classification result.

    Attributes:
        age_seconds: how old the snapshot is at evaluation time
        is_historical: True for cached/historical products (i.e. not live)
        is_stale: True when age exceeds ``stale_after_seconds``
        created_at: ISO-8601 UTC of the snapshot's creation
        evaluated_at: ISO-8601 UTC of the freshness evaluation
    """
    age_seconds: float
    is_historical: bool
    is_stale: bool
    created_at: str
    evaluated_at: str

    def to_dict(self) -> dict:
        return {
            "age_seconds": self.age_seconds,
            "is_historical": self.is_historical,
            "is_stale": self.is_stale,
            "created_at": self.created_at,
            "evaluated_at": self.evaluated_at,
        }


def compute_freshness(
    snapshot_created_at: str,
    *,
    is_historical: bool = True,
    stale_after_seconds: int = _DEFAULT_STALE_AFTER_SECONDS,
    now: Optional[datetime] = None,
) -> Freshness:
    """Compute freshness for a snapshot given its creation timestamp.

    EMODnet data is a historical density product, so ``is_historical`` defaults
    to ``True`` and downstream consumers should not label it as LIVE.
    """
    dt = datetime.fromisoformat(snapshot_created_at.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    eval_at = now or datetime.now(tz=timezone.utc)
    age = (eval_at - dt).total_seconds()
    return Freshness(
        age_seconds=max(0.0, age),
        is_historical=is_historical,
        is_stale=age > stale_after_seconds,
        created_at=dt.isoformat(),
        evaluated_at=eval_at.isoformat(),
    )


def is_stale(snapshot_created_at: str, *, stale_after_seconds: int = _DEFAULT_STALE_AFTER_SECONDS) -> bool:
    """Convenience wrapper returning only the staleness flag."""
    return compute_freshness(
        snapshot_created_at, stale_after_seconds=stale_after_seconds
    ).is_stale
