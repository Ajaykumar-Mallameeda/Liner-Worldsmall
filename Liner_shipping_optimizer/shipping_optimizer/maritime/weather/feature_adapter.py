"""Phase 5 — Read-only weather feature adapter.

The adapter is the single way the rest of the system (dashboards,
analyses, future optimizer work) reads weather data. It is strictly
read-only and never makes a network call. The only place weather
data enters the system is :mod:`maritime.weather.orchestrator`, and
the only place the adapter reads from is a materialized local
snapshot on disk.

Queries:

* :meth:`latest_snapshot` — most recent snapshot for the dataset.
* :meth:`at_coord` — observations nearest a given coordinate.
* :meth:`along_route` — observations along a polyline.
* :meth:`forecast_window` — observations in a future window
  (``valid_at`` between ``start`` and ``end``).
* :meth:`source_status` — health and freshness of the latest
  snapshot.
* :meth:`commercial_safe` — whether the latest snapshot's records
  are licensed for commercial use.
* :meth:`quality_summary` — counts and average quality.

The adapter never fabricates a record and never lies about license.
If the snapshot is missing or empty, the corresponding query returns
an empty result.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ..storage.snapshots import DEFAULT_SNAPSHOT_BASE, SnapshotStore
from .orchestrator import WEATHER_DATASET_KEY


# Default maximum great-circle distance (km) for ``at_coord``.
DEFAULT_NEAREST_RADIUS_KM = 250.0

# Records file name as written by the orchestrator. The snapshot
# store's ``SnapshotPaths.records`` property is hardcoded to
# ``traffic_density.jsonl`` (Phase 1/2/3) and cannot be overridden
# without changing the store API. We use a small custom reader that
# resolves the file under the snapshot root directly.
WEATHER_RECORDS_FILENAME = "weather_observations.jsonl"


# --------------------------------------------------------------------
# Result type
# --------------------------------------------------------------------


@dataclass(frozen=True)
class WeatherQueryResult:
    """A serializable view of a single adapter query."""

    ok: bool
    source: str
    snapshot_id: Optional[str]
    retrieved_at: Optional[str]
    commercial_safe: bool
    freshness_state: str
    source_health: str
    quality: float
    records: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "source": self.source,
            "snapshot_id": self.snapshot_id,
            "retrieved_at": self.retrieved_at,
            "commercial_safe": self.commercial_safe,
            "freshness_state": self.freshness_state,
            "source_health": self.source_health,
            "quality": round(self.quality, 3),
            "records": self.records,
            "count": len(self.records),
            "error": self.error,
        }


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _parse_iso(ts: str) -> Optional[datetime]:
    if not isinstance(ts, str):
        return None
    s = ts.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read a JSONL file defensively; never raises."""
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                out.append(rec)
    return out


# --------------------------------------------------------------------
# Adapter
# --------------------------------------------------------------------


class WeatherFeatureAdapter:
    """Read-only adapter over materialized weather snapshots.

    The adapter does not depend on any network or live code. It is
    safe to call from any thread. It is also safe to call when the
    weather layer is disabled — the relevant queries simply return
    empty results with a clear ``error`` message.
    """

    def __init__(
        self,
        store: Optional[SnapshotStore] = None,
        *,
        dataset_key: str = WEATHER_DATASET_KEY,
    ) -> None:
        self._store = store or SnapshotStore(base_dir=Path(DEFAULT_SNAPSHOT_BASE))
        self._dataset_key = dataset_key

    @property
    def store(self) -> SnapshotStore:
        return self._store

    @property
    def dataset_key(self) -> str:
        return self._dataset_key

    # ------------------------------------------------------------------
    # Snapshot introspection
    # ------------------------------------------------------------------

    def latest_snapshot(self) -> Optional[Dict[str, Any]]:
        """Return the manifest of the most recent snapshot, or None."""
        paths = self._store.latest(self._dataset_key)
        if paths is None:
            return None
        try:
            return self._store.load_manifest(paths)
        except Exception:  # noqa: BLE001
            return None

    def list_snapshots(self) -> List[Any]:
        return self._store.list_snapshots(self._dataset_key)

    def source_status(self) -> WeatherQueryResult:
        """Return the source-health of the latest snapshot, if any."""
        manifest = self.latest_snapshot()
        if manifest is None:
            return WeatherQueryResult(
                ok=False,
                source="",
                snapshot_id=None,
                retrieved_at=None,
                commercial_safe=False,
                freshness_state="unknown",
                source_health="offline",
                quality=0.0,
                error="no weather snapshot available",
            )
        return WeatherQueryResult(
            ok=True,
            source=str(manifest.get("provider_source") or manifest.get("provider", "")),
            snapshot_id=str(manifest.get("snapshot_id", "")),
            retrieved_at=manifest.get("retrieved_at"),
            commercial_safe=bool(manifest.get("commercial_safe", False)),
            freshness_state=str(manifest.get("freshness_state", "unknown")),
            source_health=str(manifest.get("source_health", "offline")),
            quality=float(manifest.get("quality", 0.0) or 0.0),
        )

    def commercial_safe(self) -> bool:
        return self.source_status().commercial_safe

    # ------------------------------------------------------------------
    # Records
    # ------------------------------------------------------------------

    def _load_records(self) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        paths = self._store.latest(self._dataset_key)
        if paths is None:
            return [], None
        try:
            manifest = self._store.load_manifest(paths)
        except Exception:  # noqa: BLE001
            manifest = None
        records_path = paths.root / WEATHER_RECORDS_FILENAME
        records = _read_jsonl(records_path)
        return records, manifest if isinstance(manifest, dict) else None

    def quality_summary(self) -> WeatherQueryResult:
        records, manifest = self._load_records()
        if not records:
            return self.source_status()
        avg_q = 0.0
        commercial_safe = False
        if manifest is not None:
            commercial_safe = bool(manifest.get("commercial_safe", False))
        qs: List[float] = []
        for r in records:
            q = r.get("quality")
            if isinstance(q, (int, float)):
                qs.append(float(q))
            if not commercial_safe and r.get("commercial_safe"):
                commercial_safe = True
        if qs:
            avg_q = sum(qs) / float(len(qs))
        return WeatherQueryResult(
            ok=True,
            source=str(manifest.get("provider", "")) if manifest else "",
            snapshot_id=str(manifest.get("snapshot_id", "")) if manifest else None,
            retrieved_at=manifest.get("retrieved_at") if manifest else None,
            commercial_safe=commercial_safe,
            freshness_state=str(manifest.get("freshness_state", "unknown"))
            if manifest else "unknown",
            source_health=str(manifest.get("source_health", "offline"))
            if manifest else "offline",
            quality=avg_q,
            records=[],
        )

    def at_coord(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_km: float = DEFAULT_NEAREST_RADIUS_KM,
        limit: int = 8,
    ) -> WeatherQueryResult:
        records, manifest = self._load_records()
        if not records:
            return self.source_status()
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for r in records:
            lat = r.get("latitude")
            lon = r.get("longitude")
            if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
                continue
            d = _haversine_km(float(latitude), float(longitude), float(lat), float(lon))
            if d <= radius_km:
                scored.append((d, r))
        scored.sort(key=lambda t: t[0])
        picked = [r for _, r in scored[: max(1, int(limit))]]
        return WeatherQueryResult(
            ok=True,
            source=str(manifest.get("provider", "")) if manifest else "",
            snapshot_id=str(manifest.get("snapshot_id", "")) if manifest else None,
            retrieved_at=manifest.get("retrieved_at") if manifest else None,
            commercial_safe=bool(manifest.get("commercial_safe", False)) if manifest else False,
            freshness_state=str(manifest.get("freshness_state", "unknown"))
            if manifest else "unknown",
            source_health=str(manifest.get("source_health", "offline"))
            if manifest else "offline",
            quality=float(manifest.get("quality", 0.0) or 0.0) if manifest else 0.0,
            records=picked,
        )

    def along_route(
        self,
        *,
        waypoints: Sequence[Tuple[float, float]],
        radius_km: float = 150.0,
    ) -> WeatherQueryResult:
        records, manifest = self._load_records()
        if not records or not waypoints:
            return self.source_status()
        # For each waypoint, keep the nearest record within radius_km.
        picked: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        for lat, lon in waypoints:
            for r in records:
                rlat = r.get("latitude")
                rlon = r.get("longitude")
                if not (isinstance(rlat, (int, float)) and isinstance(rlon, (int, float))):
                    continue
                d = _haversine_km(float(lat), float(lon), float(rlat), float(rlon))
                if d > radius_km:
                    continue
                key = str(r.get("record_id", ""))
                cur = picked.get(key)
                if cur is None or d < cur[0]:
                    picked[key] = (d, r)
        out = [r for _, r in picked.values()]
        out.sort(key=lambda r: r.get("valid_at", ""))
        return WeatherQueryResult(
            ok=True,
            source=str(manifest.get("provider", "")) if manifest else "",
            snapshot_id=str(manifest.get("snapshot_id", "")) if manifest else None,
            retrieved_at=manifest.get("retrieved_at") if manifest else None,
            commercial_safe=bool(manifest.get("commercial_safe", False)) if manifest else False,
            freshness_state=str(manifest.get("freshness_state", "unknown"))
            if manifest else "unknown",
            source_health=str(manifest.get("source_health", "offline"))
            if manifest else "offline",
            quality=float(manifest.get("quality", 0.0) or 0.0) if manifest else 0.0,
            records=out,
        )

    def forecast_window(
        self,
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 64,
    ) -> WeatherQueryResult:
        records, manifest = self._load_records()
        if not records:
            return self.source_status()
        # Parse and normalize the date window at the boundary. A
        # malformed input is reported honestly rather than being
        # silently dropped, so the caller can distinguish an invalid
        # request from an empty result.
        sdt: Optional[datetime] = None
        if start:
            sdt = _parse_iso(start)
            if sdt is None:
                return WeatherQueryResult(
                    ok=False,
                    source=str(manifest.get("provider", "")) if manifest else "",
                    snapshot_id=str(manifest.get("snapshot_id", "")) if manifest else None,
                    retrieved_at=manifest.get("retrieved_at") if manifest else None,
                    commercial_safe=bool(manifest.get("commercial_safe", False)) if manifest else False,
                    freshness_state=str(manifest.get("freshness_state", "unknown"))
                    if manifest else "unknown",
                    source_health=str(manifest.get("source_health", "offline"))
                    if manifest else "offline",
                    quality=float(manifest.get("quality", 0.0) or 0.0) if manifest else 0.0,
                    error=f"invalid datetime: {start!r}",
                )
        edt: Optional[datetime] = None
        if end:
            edt = _parse_iso(end)
            if edt is None:
                return WeatherQueryResult(
                    ok=False,
                    source=str(manifest.get("provider", "")) if manifest else "",
                    snapshot_id=str(manifest.get("snapshot_id", "")) if manifest else None,
                    retrieved_at=manifest.get("retrieved_at") if manifest else None,
                    commercial_safe=bool(manifest.get("commercial_safe", False)) if manifest else False,
                    freshness_state=str(manifest.get("freshness_state", "unknown"))
                    if manifest else "unknown",
                    source_health=str(manifest.get("source_health", "offline"))
                    if manifest else "offline",
                    quality=float(manifest.get("quality", 0.0) or 0.0) if manifest else 0.0,
                    error=f"invalid datetime: {end!r}",
                )
        # Force tz-aware for comparison: both sides must agree. The
        # API accepts ISO-8601 with or without an explicit offset; a
        # naive value is interpreted as UTC, matching the storage
        # convention used for the snapshot's valid_at timestamps.
        if sdt is not None and sdt.tzinfo is None:
            sdt = sdt.replace(tzinfo=timezone.utc)
        if edt is not None and edt.tzinfo is None:
            edt = edt.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        out: List[Dict[str, Any]] = []
        for r in records:
            v = _parse_iso(str(r.get("valid_at", "")))
            if v is None:
                continue
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            if sdt is not None and v < sdt:
                continue
            if edt is not None and v > edt:
                continue
            out.append(r)
        # If no window given, default to the next 24 hours.
        if sdt is None and edt is None:
            horizon = now.replace(microsecond=0)
            out = [r for r in out if (
                _parse_iso(str(r.get("valid_at", ""))) or now
            ) >= horizon]
        out.sort(key=lambda r: r.get("valid_at", ""))
        if limit > 0:
            out = out[: int(limit)]
        return WeatherQueryResult(
            ok=True,
            source=str(manifest.get("provider", "")) if manifest else "",
            snapshot_id=str(manifest.get("snapshot_id", "")) if manifest else None,
            retrieved_at=manifest.get("retrieved_at") if manifest else None,
            commercial_safe=bool(manifest.get("commercial_safe", False)) if manifest else False,
            freshness_state=str(manifest.get("freshness_state", "unknown"))
            if manifest else "unknown",
            source_health=str(manifest.get("source_health", "offline"))
            if manifest else "offline",
            quality=float(manifest.get("quality", 0.0) or 0.0) if manifest else 0.0,
            records=out,
        )


__all__ = [
    "WeatherFeatureAdapter",
    "WeatherQueryResult",
    "DEFAULT_NEAREST_RADIUS_KM",
    "WEATHER_RECORDS_FILENAME",
]
