"""Source-health state machine for maritime data sources.

Implemented as a pure state-transition function so the same logic can be
replayed deterministically in tests. The states are:

    UNKNOWN -> CHECKING -> AVAILABLE
                       -> STALE
                       -> OFFLINE
                       -> DEGRADED (remote failed but cached snapshot is valid)

NEVER ``LIVE`` for historical products. ``AVAILABLE / HEALTHY`` is the
correct label for a freshly-cached historical dataset.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .schemas.intelligence import SourceHealth, SourceStatus


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def transition(
    current: SourceHealth,
    *,
    event: str,
    success: bool,
    last_check_at: Optional[str] = None,
    notes: Optional[str] = None,
) -> SourceHealth:
    """Apply a state-machine transition.

    Events:
        "check_start"  -> CHECKING
        "check_ok"     -> AVAILABLE (consecutive_failures=0)
        "check_failed" -> increments consecutive_failures; may move to DEGRADED / OFFLINE
        "snapshot_loaded" -> AVAILABLE if a fresh valid snapshot is on disk
        "snapshot_missing" -> OFFLINE if nothing is available
        "snapshot_stale"   -> STALE
    """
    check_at = last_check_at or _utcnow()
    note = notes or current.notes
    if event == "check_start":
        return SourceHealth(
            source=current.source,
            status=SourceStatus.CHECKING,
            last_check_at=check_at,
            last_success_at=current.last_success_at,
            last_failure_at=current.last_failure_at,
            consecutive_failures=current.consecutive_failures,
            notes=note,
        )
    if event == "check_ok" and success:
        return SourceHealth(
            source=current.source,
            status=SourceStatus.AVAILABLE,
            last_check_at=check_at,
            last_success_at=check_at,
            last_failure_at=current.last_failure_at,
            consecutive_failures=0,
            notes=note,
        )
    if event == "check_failed" or (event == "check_ok" and not success):
        failures = current.consecutive_failures + 1
        # 1 failure => DEGRADED; 3+ => OFFLINE.
        if failures >= 3:
            new_status = SourceStatus.OFFLINE
        else:
            new_status = SourceStatus.DEGRADED
        return SourceHealth(
            source=current.source,
            status=new_status,
            last_check_at=check_at,
            last_success_at=current.last_success_at,
            last_failure_at=check_at,
            consecutive_failures=failures,
            notes=note,
        )
    if event == "snapshot_loaded":
        return SourceHealth(
            source=current.source,
            status=SourceStatus.AVAILABLE,
            last_check_at=check_at,
            last_success_at=check_at,
            last_failure_at=current.last_failure_at,
            consecutive_failures=0,
            notes=note or "snapshot loaded",
        )
    if event == "snapshot_stale":
        return SourceHealth(
            source=current.source,
            status=SourceStatus.STALE,
            last_check_at=check_at,
            last_success_at=current.last_success_at,
            last_failure_at=current.last_failure_at,
            consecutive_failures=current.consecutive_failures,
            notes=note or "snapshot is stale",
        )
    if event == "snapshot_missing":
        return SourceHealth(
            source=current.source,
            status=SourceStatus.OFFLINE,
            last_check_at=check_at,
            last_success_at=current.last_success_at,
            last_failure_at=check_at,
            consecutive_failures=max(1, current.consecutive_failures),
            notes=note or "no snapshot available",
        )
    # Default: leave state as-is, update last_check_at.
    return SourceHealth(
        source=current.source,
        status=current.status,
        last_check_at=check_at,
        last_success_at=current.last_success_at,
        last_failure_at=current.last_failure_at,
        consecutive_failures=current.consecutive_failures,
        notes=note,
    )


def initial(source: str) -> SourceHealth:
    return SourceHealth.initial(source)
