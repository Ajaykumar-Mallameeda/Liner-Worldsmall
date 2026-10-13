"""Structured maritime telemetry.

We never use the existing logger for maritime events because we want the
events to be namespaced, deterministic, and machine-readable. The
telemetry module records events in-memory and exposes them through
``get_events()`` for tests and the dashboard. It does NOT call the
network and does NOT depend on the optimizer's structlog instance.

The schema is intentionally simple and matches the prompt's required
fields:

    timestamp
    source
    dataset
    snapshot_id
    duration_ms
    records_seen
    records_accepted
    records_rejected
    quality_score
    status
    event (e.g. maritime_ingestion_started)

No event here collides with existing ``/ws/pipeline`` event names (those
are ``initial_state`` / ``pipeline_started`` / ``stage_*`` / ``region_update``
/ ``pipeline_completed`` / ``pipeline_error``); maritime events use the
``maritime_*`` prefix.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional


@dataclass
class TelemetryEvent:
    timestamp: str
    event: str
    source: Optional[str] = None
    dataset: Optional[str] = None
    snapshot_id: Optional[str] = None
    duration_ms: Optional[float] = None
    records_seen: Optional[int] = None
    records_accepted: Optional[int] = None
    records_rejected: Optional[int] = None
    quality_score: Optional[float] = None
    status: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # ``extras`` are flattened into the top-level dict for ergonomics.
        extras = d.pop("extras") or {}
        d.update(extras)
        return d


# --------------------------------------------------------------------
# Singleton recorder (process-local; safe to use from anywhere)
# --------------------------------------------------------------------


class _Recorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: List[TelemetryEvent] = []

    def record(self, event: TelemetryEvent) -> None:
        with self._lock:
            self._events.append(event)

    def get_events(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._events]

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


_recorder = _Recorder()


def get_events() -> List[Dict[str, Any]]:
    return _recorder.get_events()


def reset_events() -> None:
    _recorder.reset()


@contextmanager
def timed(event_name: str, **fields: Any) -> Iterator[Dict[str, Any]]:
    """Context manager that records ``event_name`` with timing on exit."""
    started = time.perf_counter()
    payload: Dict[str, Any] = dict(fields)
    payload.setdefault("status", "ok")
    payload.setdefault("timestamp", datetime.now(tz=timezone.utc).isoformat())
    payload.setdefault("event", event_name)
    try:
        yield payload
    except Exception as e:  # noqa: BLE001
        payload["status"] = "error"
        payload["error"] = repr(e)
        raise
    finally:
        payload["duration_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
        _recorder.record(TelemetryEvent(**payload))


def record(event: str, **fields: Any) -> None:
    """Record a single telemetry event without timing."""
    payload: Dict[str, Any] = {"event": event, "timestamp": datetime.now(tz=timezone.utc).isoformat()}
    payload.update(fields)
    _recorder.record(TelemetryEvent(**payload))
