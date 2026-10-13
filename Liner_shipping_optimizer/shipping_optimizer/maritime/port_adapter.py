"""Read-only port-intelligence adapter + snapshot loader.

Phase 2 adds a parallel adapter for NOAA MarineCadastre port-call
intelligence. It mirrors :class:`maritime.FeatureAdapter` but reads
the ``noaa_ais_port_intelligence`` snapshot directory. The two
adapters are independent: traffic and port intelligence are stored
in separate snapshot trees and surfaced through separate methods.

Public API (read-only):

    get_port_snapshot_metadata() -> dict | None
    get_port_list()              -> list[Port]
    get_port_calls(limit=...)    -> list[PortCall]
    get_port_activity()          -> list[PortActivityFeature]
    get_port_vessel_type_mix()   -> list[PortVesselTypeMixFeature]
    get_port_call_timeline(limit=...) -> list[PortCallTimelineFeature]
    get_port_call_count()        -> int
    get_source_health()          -> dict | None
    get_vessel_history(mmsi)     -> list[VesselPosition]

The loader (:func:`load_port_snapshot_from_paths`) reconstructs a
:class:`PortIntelligenceSnapshot` from the on-disk files. It is also
used by tests.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set

from .feature_adapter import maritime_intelligence_enabled, _flag
from .schemas.intelligence import (
    QualityStatus,
    SourceHealth,
    SourceStatus,
)
from .schemas.port import Port, PortCall, PortCallStatus
from .schemas.port_intelligence import PortIntelligenceSnapshot
from .schemas.vessel_position import NavStatus, VesselPosition
from .storage.jsonl_store import read_jsonl
from .storage.snapshots import (
    DEFAULT_SNAPSHOT_BASE,
    SnapshotPaths,
    SnapshotStore,
)
from .intelligence.port_activity import (
    PortActivityFeature,
    PortCallTimelineFeature,
    PortVesselTypeMixFeature,
)


NOAA_DATASET_KEY = "noaa_ais_port_intelligence"


def maritime_port_enabled() -> bool:
    """Feature flag for port intelligence. Defaults to the master flag."""
    return _flag("MARITIME_PORT_INTELLIGENCE_ENABLED", default=False) \
        and maritime_intelligence_enabled()


# --------------------------------------------------------------------
# Snapshot loader
# --------------------------------------------------------------------


def load_port_snapshot_from_paths(paths: SnapshotPaths) -> PortIntelligenceSnapshot:
    """Rebuild a :class:`PortIntelligenceSnapshot` from on-disk files."""
    meta = json.loads(paths.metadata.read_text(encoding="utf-8"))
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))

    positions_path = paths.root / "vessel_positions.jsonl"
    calls_path = paths.root / "port_calls.jsonl"
    positions_raw = list(read_jsonl(positions_path)) if positions_path.exists() else []
    calls_raw = list(read_jsonl(calls_path)) if calls_path.exists() else []

    positions = [_position_from_dict(r) for r in positions_raw]
    port_calls = [_port_call_from_dict(r) for r in calls_raw]

    ports_raw = manifest.get("ports", [])
    ports = [Port.from_dict(p) for p in ports_raw]

    activity = [
        PortActivityFeature(**_keep(f, PortActivityFeature))
        for f in manifest.get("port_activity_features", [])
    ]
    mix = [
        PortVesselTypeMixFeature(**_keep(f, PortVesselTypeMixFeature))
        for f in manifest.get("port_vessel_mix_features", [])
    ]
    timeline = [
        PortCallTimelineFeature(**_keep(f, PortCallTimelineFeature))
        for f in manifest.get("port_timeline_features", [])
    ]

    sh = meta.get("source_health", {})
    health = SourceHealth(
        source=sh.get("source", meta.get("source", "MARINE_CADASTRE")),
        status=SourceStatus(sh.get("status", "unknown")),
        last_check_at=sh.get("last_check_at", meta.get("created_at", _utcnow_iso())),
        last_success_at=sh.get("last_success_at"),
        last_failure_at=sh.get("last_failure_at"),
        consecutive_failures=int(sh.get("consecutive_failures", 0)),
        notes=sh.get("notes", ""),
    )

    return PortIntelligenceSnapshot(
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
        port_count=int(meta.get("port_count", len(ports))),
        call_count=int(meta.get("call_count", len(port_calls))),
        quality_score=float(meta["quality_score"]),
        completeness_ratio=float(meta["completeness_ratio"]),
        freshness=meta.get("freshness", meta["created_at"]),
        source_status=SourceStatus(meta.get("source_status", "unknown")),
        quality_status=QualityStatus(meta.get("quality_status", "unknown")),
        source_health=health,
        provenance=meta.get("provenance", {}),
        ports=ports,
        positions=positions,
        port_calls=port_calls,
        port_activity_features=activity,
        port_vessel_mix_features=mix,
        port_timeline_features=timeline,
        schema_version=meta.get("schema_version", "1.0.0"),
    )


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _position_from_dict(d: Mapping[str, Any]) -> VesselPosition:
    return VesselPosition.from_dict(d)


def _port_call_from_dict(d: Mapping[str, Any]) -> PortCall:
    return PortCall.from_dict(d)


def _keep(d: Mapping[str, Any], cls: type) -> Dict[str, Any]:
    fields = set(cls.__dataclass_fields__.keys())
    return {k: v for k, v in d.items() if k in fields}


# --------------------------------------------------------------------
# Adapter
# --------------------------------------------------------------------


class PortFeatureAdapter:
    """Read-only adapter over the local port-intelligence snapshot store."""

    def __init__(self, store: Optional[SnapshotStore] = None) -> None:
        self._store = store or SnapshotStore()
        self._cache: Optional[PortIntelligenceSnapshot] = None

    @property
    def store(self) -> SnapshotStore:
        return self._store

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_cached_snapshot(self) -> Optional[PortIntelligenceSnapshot]:
        if not maritime_intelligence_enabled():
            return None
        if self._cache is not None:
            return self._cache
        try:
            paths = self._store.latest(NOAA_DATASET_KEY)
        except Exception:
            return None
        if paths is None:
            return None
        try:
            snap = load_port_snapshot_from_paths(paths)
        except Exception:
            return None
        self._cache = snap
        return snap

    def invalidate_cache(self) -> None:
        self._cache = None

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    def get_port_snapshot_metadata(self) -> Optional[Dict[str, Any]]:
        snap = self._load_cached_snapshot()
        if snap is None:
            return None
        meta = snap.to_metadata_dict()
        meta["flags"] = {
            "MARITIME_INTELLIGENCE_ENABLED": maritime_intelligence_enabled(),
            "MARITIME_PORT_INTELLIGENCE_ENABLED": maritime_port_enabled(),
        }
        return meta

    def get_port_list(self) -> List[Dict[str, Any]]:
        if not maritime_port_enabled():
            return []
        snap = self._load_cached_snapshot()
        if snap is None:
            return []
        return [p.to_dict() for p in snap.ports]

    def get_ports(self) -> List[Dict[str, Any]]:
        """Alias for :meth:`get_port_list` for API symmetry."""
        return self.get_port_list()

    def get_port_calls(self, *, limit: Optional[int] = None,
                       port_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not maritime_port_enabled():
            return []
        snap = self._load_cached_snapshot()
        if snap is None:
            return []
        calls = snap.port_calls
        if port_id is not None:
            calls = [c for c in calls if c.port_id == port_id]
        if limit is not None:
            calls = calls[:limit]
        return [c.to_dict() for c in calls]

    def get_port_activity(self) -> List[Dict[str, Any]]:
        if not maritime_port_enabled():
            return []
        snap = self._load_cached_snapshot()
        if snap is None:
            return []
        return [f.to_dict() for f in snap.port_activity_features]

    def get_port_vessel_type_mix(self) -> List[Dict[str, Any]]:
        if not maritime_port_enabled():
            return []
        snap = self._load_cached_snapshot()
        if snap is None:
            return []
        return [f.to_dict() for f in snap.port_vessel_mix_features]

    def get_port_call_timeline(
        self, *, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        if not maritime_port_enabled():
            return []
        snap = self._load_cached_snapshot()
        if snap is None:
            return []
        feats = snap.port_timeline_features
        if limit is not None:
            feats = feats[:limit]
        return [f.to_dict() for f in feats]

    def get_port_call_count(self) -> int:
        if not maritime_port_enabled():
            return 0
        snap = self._load_cached_snapshot()
        if snap is None:
            return 0
        return len(snap.port_calls)

    def get_source_health(self) -> Optional[Dict[str, Any]]:
        snap = self._load_cached_snapshot()
        if snap is None:
            return None
        d = snap.source_health.to_dict()
        d["source_status"] = snap.source_status.value
        d["quality_status"] = snap.quality_status.value
        return d

    def get_vessel_history(self, mmsi: str, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not maritime_port_enabled():
            return []
        snap = self._load_cached_snapshot()
        if snap is None:
            return []
        positions = [p.to_dict() for p in snap.positions if p.mmsi == mmsi]
        positions.sort(key=lambda p: p["timestamp"])
        if limit is not None:
            positions = positions[:limit]
        return positions