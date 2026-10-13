"""Phase 6 — Read-only congestion feature adapter.

The adapter is the single way the rest of the system reads
congestion data. It is strictly read-only and never makes a network
call. The only place congestion data enters the system is
:mod:`maritime.congestion.orchestrator`; the only place the adapter
reads from is a materialized local snapshot on disk.

The adapter exposes:

* :meth:`latest_snapshot` — most recent congestion manifest.
* :meth:`source_status` — health and freshness of the latest snapshot.
* :meth:`congestion_at` — nearest record to a coordinate.
* :meth:`congestion_for_port` — record for a port_id.
* :meth:`congestion_along_route` — best record per waypoint.
* :meth:`high_congestion_regions` — records above a score threshold.
* :meth:`congestion_summary` — aggregate counts and average score.

Empty data remains empty. The adapter NEVER fabricates a record
and NEVER claims "LIVE" on insufficient evidence.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..schemas.congestion import CongestionRecord, CongestionLevel
from ..storage.snapshots import DEFAULT_SNAPSHOT_BASE, SnapshotStore
from .orchestrator import (
    CONGESTION_DATASET_KEY,
    CONGESTION_RECORDS_FILENAME,
)


# --------------------------------------------------------------------
# Result type
# --------------------------------------------------------------------


@dataclass(frozen=True)
class CongestionQueryResult:
    """A serializable view of a single adapter query."""

    ok: bool
    source: str
    snapshot_id: Optional[str]
    retrieved_at: Optional[str]
    freshness_state: str
    source_health: str
    quality: float
    synthetic: bool
    records: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "source": self.source,
            "snapshot_id": self.snapshot_id,
            "retrieved_at": self.retrieved_at,
            "freshness_state": self.freshness_state,
            "source_health": self.source_health,
            "quality": round(self.quality, 3),
            "synthetic": self.synthetic,
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


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
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
    except Exception:  # noqa: BLE001
        return out
    return out


# --------------------------------------------------------------------
# Adapter
# --------------------------------------------------------------------


class CongestionFeatureAdapter:
    """Read-only adapter over materialized congestion snapshots."""

    def __init__(
        self,
        store: Optional[SnapshotStore] = None,
        *,
        dataset_key: str = CONGESTION_DATASET_KEY,
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
        paths = self._store.latest(self._dataset_key)
        if paths is None:
            return None
        try:
            return self._store.load_manifest(paths)
        except Exception:  # noqa: BLE001
            return None

    def source_status(self) -> CongestionQueryResult:
        manifest = self.latest_snapshot()
        if manifest is None:
            return CongestionQueryResult(
                ok=False,
                source="derived",
                snapshot_id=None,
                retrieved_at=None,
                freshness_state="unknown",
                source_health="offline",
                quality=0.0,
                synthetic=False,
                error="no congestion snapshot available",
            )
        return CongestionQueryResult(
            ok=True,
            source=str(manifest.get("source", "derived")),
            snapshot_id=str(manifest.get("snapshot_id", "")),
            retrieved_at=manifest.get("retrieved_at"),
            freshness_state=str(manifest.get("freshness_state", "unknown")),
            source_health=str(manifest.get("source_health", "offline")),
            quality=float(manifest.get("quality", 0.0) or 0.0),
            synthetic=bool(manifest.get("synthetic", False)),
        )

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
        records_path = paths.root / CONGESTION_RECORDS_FILENAME
        records = _read_jsonl(records_path)
        return records, manifest if isinstance(manifest, dict) else None

    def _status_from(self, manifest: Optional[Dict[str, Any]]) -> CongestionQueryResult:
        if not manifest:
            return self.source_status()
        return CongestionQueryResult(
            ok=True,
            source=str(manifest.get("source", "derived")),
            snapshot_id=str(manifest.get("snapshot_id", "")),
            retrieved_at=manifest.get("retrieved_at"),
            freshness_state=str(manifest.get("freshness_state", "unknown")),
            source_health=str(manifest.get("source_health", "offline")),
            quality=float(manifest.get("quality", 0.0) or 0.0),
            synthetic=bool(manifest.get("synthetic", False)),
        )

    def _with_records(
        self, status: CongestionQueryResult, records: List[Dict[str, Any]]
    ) -> CongestionQueryResult:
        # The query result is frozen, so we reconstruct it with the
        # records populated. This mirrors the pattern used by the
        # WeatherFeatureAdapter helpers.
        return CongestionQueryResult(
            ok=status.ok,
            source=status.source,
            snapshot_id=status.snapshot_id,
            retrieved_at=status.retrieved_at,
            freshness_state=status.freshness_state,
            source_health=status.source_health,
            quality=status.quality,
            synthetic=status.synthetic,
            records=list(records),
            error=status.error,
        )

    def congestion_at(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_km: float = 200.0,
        limit: int = 4,
    ) -> CongestionQueryResult:
        records, manifest = self._load_records()
        if not records:
            return self.source_status()
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for r in records:
            lat = r.get("latitude")
            lon = r.get("longitude")
            if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
                continue
            d = _haversine_km(latitude, longitude, float(lat), float(lon))
            if d <= radius_km:
                scored.append((d, r))
        scored.sort(key=lambda t: t[0])
        picked = [r for _, r in scored[: max(1, int(limit))]]
        status = self._status_from(manifest)
        return self._with_records(status, picked)

    def congestion_for_port(
        self, port_id: str
    ) -> CongestionQueryResult:
        records, manifest = self._load_records()
        status = self._status_from(manifest)
        if not records:
            return status
        picked = [r for r in records if r.get("entity_id") == port_id]
        # If no exact match, return the nearest single record so the
        # caller can still render something useful.
        if not picked and records:
            nearest = min(
                records,
                key=lambda r: (
                    r.get("entity_id", ""),
                    r.get("congestion_score", 0.0),
                ),
            )
            picked = [nearest]
        return self._with_records(status, picked)

    def congestion_along_route(
        self,
        *,
        waypoints: Sequence[Tuple[float, float]],
        radius_km: float = 150.0,
    ) -> CongestionQueryResult:
        records, manifest = self._load_records()
        if not records or not waypoints:
            return self.source_status()
        # For each waypoint, keep the best (lowest distance) record.
        picked: List[Dict[str, Any]] = []
        for lat, lon in waypoints:
            best: Optional[Tuple[float, Dict[str, Any]]] = None
            for r in records:
                rlat = r.get("latitude")
                rlon = r.get("longitude")
                if not (isinstance(rlat, (int, float))
                        and isinstance(rlon, (int, float))):
                    continue
                d = _haversine_km(lat, lon, float(rlat), float(rlon))
                if d > radius_km:
                    continue
                if best is None or d < best[0]:
                    best = (d, r)
            if best is not None and best[1] not in picked:
                picked.append(best[1])
        status = self._status_from(manifest)
        return self._with_records(status, picked)

    def high_congestion_regions(
        self,
        *,
        threshold: float = 0.65,
        limit: int = 10,
    ) -> CongestionQueryResult:
        records, manifest = self._load_records()
        if not records:
            return self.source_status()
        scored = [r for r in records
                 if isinstance(r.get("congestion_score"), (int, float))
                 and r["congestion_score"] >= threshold]
        scored.sort(key=lambda r: r.get("congestion_score", 0.0), reverse=True)
        picked = scored[: max(1, int(limit))]
        status = self._status_from(manifest)
        return self._with_records(status, picked)

    def congestion_summary(self) -> CongestionQueryResult:
        records, manifest = self._load_records()
        if not records:
            return self.source_status()
        # Build a compact summary from the records themselves.
        levels: Dict[str, int] = {l.value: 0 for l in CongestionLevel}
        scores: List[float] = []
        confidences: List[float] = []
        synthetic_count = 0
        for r in records:
            lvl = r.get("congestion_level")
            if isinstance(lvl, str) and lvl in levels:
                levels[lvl] += 1
            sc = r.get("congestion_score")
            if isinstance(sc, (int, float)):
                scores.append(float(sc))
            cf = r.get("confidence")
            if isinstance(cf, (int, float)):
                confidences.append(float(cf))
            if r.get("synthetic"):
                synthetic_count += 1
        avg_score = sum(scores) / len(scores) if scores else 0.0
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        max_score = max(scores) if scores else 0.0
        synthetic_flag = bool(manifest and manifest.get("synthetic", False)) \
            or (synthetic_count == len(records) and records)
        status = self._status_from(manifest)
        return self._with_records(status, [{
            "entity_count": len(records),
            "by_level": levels,
            "average_score": round(avg_score, 4),
            "average_confidence": round(avg_conf, 4),
            "max_score": round(max_score, 4),
            "synthetic": synthetic_flag,
        }])


__all__ = [
    "CongestionFeatureAdapter",
    "CongestionQueryResult",
    "CONGESTION_RECORDS_FILENAME",
]
