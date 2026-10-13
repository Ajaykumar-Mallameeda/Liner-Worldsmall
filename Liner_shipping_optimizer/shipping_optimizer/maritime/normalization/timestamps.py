"""Timestamp + observation-window normalization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Tuple


def _parse(value: Any) -> str:
    """Coerce to ISO-8601 UTC string; raises ``ValueError`` on failure."""
    if value is None:
        raise ValueError("timestamp value is None")
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    if isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
        return dt.isoformat()
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            raise ValueError("timestamp is empty")
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"invalid ISO-8601 timestamp: {value!r}") from e
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    raise ValueError(f"unsupported timestamp type: {type(value).__name__}")


def parse_period(raw: Mapping[str, Any]) -> Tuple[str, str]:
    """Return (start, end) ISO strings for a raw period mapping.

    Accepts ``start/end`` or ``observation_start/observation_end`` keys, or
    single ``timestamp`` for instantaneous observations (start == end).
    """
    if not isinstance(raw, Mapping):
        raise ValueError("period must be a mapping")
    if "start" in raw and "end" in raw:
        return _parse(raw["start"]), _parse(raw["end"])
    if "observation_start" in raw and "observation_end" in raw:
        return _parse(raw["observation_start"]), _parse(raw["observation_end"])
    if "timestamp" in raw:
        ts = _parse(raw["timestamp"])
        return ts, ts
    raise ValueError("period mapping must contain start/end or timestamp")


def normalize_observation_window(
    start: Any, end: Any, *, max_window_seconds: int = 60 * 60 * 24 * 366
) -> Tuple[str, str]:
    """Validate that ``start <= end`` and within max window; return ISO strings.

    EMODnet yearly products are <12 months; we cap defensively at 1y+1d.
    """
    s = _parse(start)
    e = _parse(end)
    dt_s = datetime.fromisoformat(s.replace("Z", "+00:00"))
    dt_e = datetime.fromisoformat(e.replace("Z", "+00:00"))
    if dt_e < dt_s:
        raise ValueError(f"observation window end < start: {s} < {e}")
    delta = (dt_e - dt_s).total_seconds()
    if delta > max_window_seconds:
        raise ValueError(f"observation window too large: {delta}s > {max_window_seconds}s")
    return s, e
