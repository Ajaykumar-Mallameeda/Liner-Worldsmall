"""Read-only maritime feature adapter.

This is the SINGLE boundary through which future consumers (optimizer IP-1,
dashboard, etc.) may access maritime intelligence. It reads the local
snapshot store only. It does NOT make network calls and does NOT depend on
any ingestor module at runtime — it is a pure read adapter.

API (all methods are read-only):

    get_snapshot_metadata()        -> dict (or None)
    get_traffic_snapshot()         -> list[TrafficFeature] | []
    get_density_at(lat, lon)       -> dict[feature_type, normalized_intensity] | {}
    get_route_density(waypoints)   -> dict[feature_type, aggregate_intensity] | {}
    get_hotspots(limit=10)         -> list[TrafficHotspot] | []
    get_source_health()            -> SourceHealth | None

All methods are safe to call when no snapshot exists: they return ``None``
or empty collections, never raise.

Feature flags (read once at import time via env, no re-polling):

    MARITIME_INTELLIGENCE_ENABLED  (default: 0)
    MARITIME_TRAFFIC_ENABLED       (default: 0)

When the master flag is OFF, the adapter still works (it just returns
empty results); this lets callers wire it up before they are ready to
turn it on. When the master flag is ON and no snapshot exists, the
adapter also returns empty results — the fallback path is the
optimizer's existing pre-maritime behavior.
"""

from __future__ import annotations

import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .schemas.intelligence import (
    TrafficHotspot,
    TrafficIntelligenceSnapshot,
    SourceHealth,
    SourceStatus,
    QualityStatus,
)
from .schemas.traffic_density import TrafficDensityRecord, VesselClass
from .storage.snapshots import (
    DEFAULT_SNAPSHOT_BASE,
    SnapshotStore,
    SnapshotPaths,
)


# --------------------------------------------------------------------
# Feature flags
# --------------------------------------------------------------------


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def maritime_intelligence_enabled() -> bool:
    """Master flag; when OFF the adapter returns empty data."""
    return _flag("MARITIME_INTELLIGENCE_ENABLED", default=False)


def maritime_traffic_enabled() -> bool:
    """Traffic-feature sub-flag; when OFF, traffic features are empty."""
    return _flag("MARITIME_TRAFFIC_ENABLED", default=False) and maritime_intelligence_enabled()


# --------------------------------------------------------------------
# Adapter
# --------------------------------------------------------------------


class FeatureAdapter:
    """Read-only adapter over the local snapshot store."""

    def __init__(self, store: Optional[SnapshotStore] = None) -> None:
        self._store = store or SnapshotStore()
        self._cache: Optional[TrafficIntelligenceSnapshot] = None

    @property
    def store(self) -> SnapshotStore:
        return self._store

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_cached_snapshot(self) -> Optional[TrafficIntelligenceSnapshot]:
        """Load + cache the most recent snapshot for the configured dataset.

        Returns ``None`` when no snapshot exists, when the master flag is
        OFF, or when the manifest is unreadable. Never raises.
        """
        if not maritime_intelligence_enabled():
            return None
        if self._cache is not None:
            return self._cache
        # We read the most-recent snapshot under the EMODnet dataset name.
        try:
            paths = self._store.latest("emodnet_vessel_density")
        except Exception:
            return None
        if paths is None:
            return None
        try:
            snap = load_snapshot_from_paths(paths)
        except Exception:
            return None
        self._cache = snap
        return snap

    def invalidate_cache(self) -> None:
        self._cache = None

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    def get_snapshot_metadata(self) -> Optional[Dict[str, Any]]:
        """Return snapshot metadata, or ``None`` if no snapshot is available."""
        snap = self._load_cached_snapshot()
        if snap is None:
            return None
        meta = snap.to_metadata_dict()
        meta["flags"] = {
            "MARITIME_INTELLIGENCE_ENABLED": maritime_intelligence_enabled(),
            "MARITIME_TRAFFIC_ENABLED": maritime_traffic_enabled(),
        }
        return meta

    def get_traffic_snapshot(self) -> List[Dict[str, Any]]:
        """Return all traffic features as a list of dicts (read-only)."""
        if not maritime_traffic_enabled():
            return []
        snap = self._load_cached_snapshot()
        if snap is None:
            return []
        return [f.to_dict() for f in snap.features]

    def get_density_at(self, latitude: float, longitude: float, *, radius_deg: float = 1.0) -> Dict[str, float]:
        """Return a ``{feature_type: normalized_intensity}`` mapping for the
        nearest cell(s) to the given coordinates. Returns empty when no
        traffic features are available.
        """
        if not maritime_traffic_enabled():
            return {}
        snap = self._load_cached_snapshot()
        if snap is None:
            return {}
        return _aggregate_features_at(snap.features, latitude, longitude, radius_deg=radius_deg)

    def get_route_density(
        self, waypoints: Sequence[Tuple[float, float]], *, radius_deg: float = 1.0
    ) -> Dict[str, float]:
        """Aggregate density along a list of (lat, lon) waypoints.

        Returns a ``{feature_type: aggregate_intensity}`` mapping where
        ``aggregate_intensity`` is the mean of ``get_density_at`` results
        across the waypoints. Returns empty when no traffic features.
        """
        if not maritime_traffic_enabled():
            return {}
        if not waypoints:
            return {}
        snap = self._load_cached_snapshot()
        if snap is None:
            return {}
        per_wp = [
            _aggregate_features_at(snap.features, lat, lon, radius_deg=radius_deg)
            for lat, lon in waypoints
        ]
        if not per_wp:
            return {}
        keys: set = set()
        for d in per_wp:
            keys.update(d.keys())
        out: Dict[str, float] = {}
        for k in keys:
            vals = [d.get(k, 0.0) for d in per_wp]
            out[k] = sum(vals) / len(vals) if vals else 0.0
        return out

    def get_hotspots(self, *, limit: int = 10) -> List[Dict[str, Any]]:
        """Return up to ``limit`` traffic hotspots as dicts."""
        if not maritime_traffic_enabled():
            return []
        snap = self._load_cached_snapshot()
        if snap is None:
            return []
        return [h.to_dict() for h in snap.hotspots[:limit]]

    def get_source_health(self) -> Optional[Dict[str, Any]]:
        """Return source-health as a dict, or ``None`` if no snapshot."""
        snap = self._load_cached_snapshot()
        if snap is None:
            return None
        d = snap.source_health.to_dict()
        d["source_status"] = snap.source_status.value
        d["quality_status"] = snap.quality_status.value
        return d

    # ------------------------------------------------------------------
    # Phase 2: Port-intelligence delegated methods.
    # These forward to a lazily-created PortFeatureAdapter so callers
    # can use a single FeatureAdapter for both traffic and port data.
    # They are safe to call when no port snapshot exists.
    # ------------------------------------------------------------------

    def _port_adapter(self) -> "PortFeatureAdapter":
        # Local import to avoid a circular dependency at module load.
        from .port_adapter import PortFeatureAdapter
        if not hasattr(self, "_port_adapter_cache"):
            self._port_adapter_cache = PortFeatureAdapter(store=self._store)
        return self._port_adapter_cache  # type: ignore[attr-defined]

    def get_port_snapshot_metadata(self) -> Optional[Dict[str, Any]]:
        from .port_adapter import maritime_port_enabled
        if not maritime_port_enabled():
            return None
        return self._port_adapter().get_port_snapshot_metadata()

    def get_ports(self) -> List[Dict[str, Any]]:
        from .port_adapter import maritime_port_enabled
        if not maritime_port_enabled():
            return []
        return self._port_adapter().get_port_list()

    def get_port_calls(self, *, limit: Optional[int] = None,
                       port_id: Optional[str] = None) -> List[Dict[str, Any]]:
        from .port_adapter import maritime_port_enabled
        if not maritime_port_enabled():
            return []
        return self._port_adapter().get_port_calls(limit=limit, port_id=port_id)

    def get_port_activity(self) -> List[Dict[str, Any]]:
        from .port_adapter import maritime_port_enabled
        if not maritime_port_enabled():
            return []
        return self._port_adapter().get_port_activity()

    def get_port_vessel_type_mix(self) -> List[Dict[str, Any]]:
        from .port_adapter import maritime_port_enabled
        if not maritime_port_enabled():
            return []
        return self._port_adapter().get_port_vessel_type_mix()

    def get_port_call_timeline(
        self, *, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        from .port_adapter import maritime_port_enabled
        if not maritime_port_enabled():
            return []
        return self._port_adapter().get_port_call_timeline(limit=limit)

    def get_port_call_count(self) -> int:
        from .port_adapter import maritime_port_enabled
        if not maritime_port_enabled():
            return 0
        return self._port_adapter().get_port_call_count()

    def get_port_source_health(self) -> Optional[Dict[str, Any]]:
        from .port_adapter import maritime_port_enabled
        if not maritime_port_enabled():
            return None
        return self._port_adapter().get_source_health()

    def get_vessel_history(self, mmsi: str, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        from .port_adapter import maritime_port_enabled
        if not maritime_port_enabled():
            return []
        return self._port_adapter().get_vessel_history(mmsi, limit=limit)


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _aggregate_features_at(
    features: Sequence, latitude: float, longitude: float, *, radius_deg: float
) -> Dict[str, float]:
    """Mean normalized_intensity of features whose cell is within the radius."""
    if not features:
        return {}
    selected = []
    for f in features:
        dlat = abs(f.latitude - latitude)
        dlon = abs(f.longitude - longitude)
        if dlat <= radius_deg and dlon <= radius_deg:
            selected.append(f)
    if not selected:
        return {}
    by_type: Dict[str, List[float]] = {}
    for f in selected:
        by_type.setdefault(f.feature_type, []).append(float(f.normalized_intensity))
    return {k: sum(v) / len(v) for k, v in by_type.items()}


def load_snapshot_from_paths(paths: SnapshotPaths) -> TrafficIntelligenceSnapshot:
    """Rebuild a :class:`TrafficIntelligenceSnapshot` from on-disk files.

    This is a small convenience for the adapter; it is also used by tests.
    """
    import json
    meta = json.loads(paths.metadata.read_text(encoding="utf-8"))
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    from .storage.jsonl_store import read_jsonl
    records_raw = list(read_jsonl(paths.records)) if paths.records.exists() else []
    records = [_record_from_dict(r) for r in records_raw]
    from .schemas.intelligence import TrafficFeature, TrafficHotspot
    from .schemas.intelligence import SourceHealth, SourceStatus, QualityStatus
    features = [
        TrafficFeature(**_drop_extra(f, TrafficFeature.__dataclass_fields__.keys()))
        for f in manifest.get("features", [])
    ]
    hotspots = [
        TrafficHotspot(**_drop_extra(h, TrafficHotspot.__dataclass_fields__.keys()))
        for h in manifest.get("hotspots", [])
    ]
    sh = meta.get("source_health", {})
    health = SourceHealth(
        source=sh.get("source", meta.get("source", "EMODNET")),
        status=SourceStatus(sh.get("status", "unknown")),
        last_check_at=sh.get("last_check_at", meta.get("created_at", datetime.now(tz=timezone.utc).isoformat())),
        last_success_at=sh.get("last_success_at"),
        last_failure_at=sh.get("last_failure_at"),
        consecutive_failures=int(sh.get("consecutive_failures", 0)),
        notes=sh.get("notes", ""),
    )
    # Use the manifest as the authoritative view; metadata is a subset.
    return TrafficIntelligenceSnapshot(
        snapshot_id=meta["snapshot_id"],
        source=meta["source"],
        dataset=meta["dataset"],
        dataset_version=meta["dataset_version"],
        license=meta["license"],
        attribution=meta["attribution"],
        created_at=meta["created_at"],
        observed_start=meta["observed_start"],
        observed_end=meta["observed_end"],
        record_count=int(meta["record_count"]),
        accepted_records=int(meta["accepted_records"]),
        rejected_records=int(meta["rejected_records"]),
        duplicate_records=int(meta.get("duplicate_records", 0)),
        quality_score=float(meta["quality_score"]),
        completeness_ratio=float(meta["completeness_ratio"]),
        freshness=meta.get("freshness", meta["created_at"]),
        source_status=SourceStatus(meta.get("source_status", "unknown")),
        quality_status=QualityStatus(meta.get("quality_status", "unknown")),
        source_health=health,
        provenance=meta.get("provenance", {}),
        records=records,
        features=features,
        hotspots=hotspots,
        schema_version=meta.get("schema_version", "1.0.0"),
    )


def _record_from_dict(d: Mapping[str, Any]) -> TrafficDensityRecord:
    return TrafficDensityRecord.from_dict(d)


def _drop_extra(d: Mapping[str, Any], allowed: Iterable[str]) -> Dict[str, Any]:
    allowed_set = set(allowed)
    return {k: v for k, v in d.items() if k in allowed_set}
