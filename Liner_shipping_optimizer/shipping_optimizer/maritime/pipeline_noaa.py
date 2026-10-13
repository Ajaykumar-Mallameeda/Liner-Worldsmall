"""NOAA port-intelligence pipeline.

End-to-end: ingestion -> normalization -> quality -> port-call
extraction -> derived features -> snapshot write.

Mirrors :mod:`maritime.pipeline` (Phase 1 EMODnet traffic pipeline) in
style and telemetry events. This is the only function that knows how
to build a :class:`PortIntelligenceSnapshot` from the raw NOAA inputs.

The pipeline is side-effect free apart from:

    * snapshot writes to disk (when ``store`` is provided)
    * telemetry events (always)

It NEVER makes network calls; the network is in the ingestion layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .ingestion.base import IngestionResult
from .ingestion.noaa import NoaaConfig, NoaaProvider
from .intelligence.port_activity import (
    compute_port_activity,
    compute_port_call_timeline,
    compute_port_vessel_type_mix,
)
from .port_call_extractor import extract_port_calls
from .quality.completeness import (
    RejectionCounters,
    compute_completeness_ratio,
    compute_quality_score,
)
from .quality.freshness import compute_freshness
from .quality.provenance import build_provenance, validate_provenance
from .schemas.intelligence import (
    QualityStatus,
    SourceHealth,
    SourceStatus,
)
from .schemas.port import Port, PortCall, PortCallStatus
from .schemas.port_intelligence import PortIntelligenceSnapshot
from .schemas.vessel_position import NavStatus, VesselPosition
from .storage.snapshots import (
    SnapshotPaths,
    SnapshotStore,
    _atomic_write_json,
    _hash_file,
    generate_snapshot_id,
)
from .storage.jsonl_store import write_jsonl
from . import source_health
from . import telemetry


# Default NOAA dataset key used by the snapshot store and the adapter.
NOAA_DATASET_KEY = "noaa_ais_port_intelligence"


# --------------------------------------------------------------------
# Pipeline entry point
# --------------------------------------------------------------------


def build_port_snapshot(
    *,
    ingestion: IngestionResult,
    ports: Sequence[Port],
    snapshot_id: Optional[str] = None,
    store: Optional[SnapshotStore] = None,
    min_dwell_minutes: float = 30.0,
    stale_after_seconds: int = 60 * 60 * 24 * 30,
) -> PortIntelligenceSnapshot:
    """Build a :class:`PortIntelligenceSnapshot` from a NOAA ingestion.

    Parameters
    ----------
    ingestion:
        Result from :class:`NoaaProvider.fetch()` (or hand-built for tests).
    ports:
        Canonical port geofences.
    snapshot_id, store, min_dwell_minutes, stale_after_seconds:
        See :mod:`maritime.pipeline` for the parallel Phase 1 contract.
    """
    telemetry.record(
        "maritime_noaa_ingestion_started",
        source=ingestion.source,
        dataset=ingestion.dataset,
        snapshot_id=None,
        status="ok",
    )
    started = datetime.now(tz=timezone.utc)

    with telemetry.timed(
        "maritime_noaa_ingestion_completed",
        source=ingestion.source,
        dataset=ingestion.dataset,
        status="ok",
    ) as _payload:
        positions, port_calls, counters = _process_records(ingestion, ports, started)

        # Map ports by id for downstream lookups
        ports_by_id = {p.port_id: p for p in ports}
        accepted_position_count = len(positions)

        completeness = compute_completeness_ratio(counters)
        avg_q = (
            sum(p.quality for p in positions) / len(positions)
            if positions else None
        )
        quality_score = compute_quality_score(counters, avg_record_quality=avg_q)

        # Determine observed period
        if positions:
            obs_starts = sorted(p.timestamp for p in positions)
            obs_ends = sorted(p.timestamp for p in positions)
            observed_start = obs_starts[0]
            observed_end = obs_ends[-1]
        else:
            observed_start = ingestion.observed_period.get("start", ingestion.retrieved_at)
            observed_end = ingestion.observed_period.get("end", ingestion.retrieved_at)

        license_str = ingestion.license if ingestion.license else "unresolved"
        attribution = ingestion.attribution or ""

        quality_status = _classify_port_quality(counters, quality_score, license_str, ports)
        health = source_health.initial(ingestion.source)
        if not positions:
            health = source_health.transition(
                health, event="snapshot_missing", success=False,
                notes="no accepted positions",
            )
        else:
            health = source_health.transition(
                health, event="snapshot_loaded", success=True,
                notes="port snapshot built",
            )
        freshness = compute_freshness(
            ingestion.retrieved_at, is_historical=True,
            stale_after_seconds=stale_after_seconds,
        )
        if freshness.is_stale:
            health = source_health.transition(
                health, event="snapshot_stale", success=False,
                notes="snapshot older than threshold",
            )
        source_status = health.status

        provenance = build_provenance(
            source=ingestion.source,
            dataset=ingestion.dataset,
            dataset_version=ingestion.dataset_version,
            retrieved_at=ingestion.retrieved_at,
            observed_period={"start": observed_start, "end": observed_end},
            license_str=license_str,
            attribution=attribution,
            extras={"source_url": ingestion.source_url, "notes": ingestion.notes},
        )
        if not validate_provenance(provenance)[0]:
            quality_status = QualityStatus.DEGRADED

        # Feature derivation (always on; the adapter gates visibility).
        port_activity = compute_port_activity(port_calls, ports_by_id)
        vessel_mix = compute_port_vessel_type_mix(port_calls, ports_by_id)
        timeline = compute_port_call_timeline(port_calls, ports_by_id)

        sid = snapshot_id or generate_snapshot_id(dataset=NOAA_DATASET_KEY, created_at=started)
        snap = PortIntelligenceSnapshot(
            snapshot_id=sid,
            source=ingestion.source,
            dataset=ingestion.dataset,
            dataset_version=ingestion.dataset_version,
            license=license_str,
            attribution=attribution,
            created_at=started.isoformat(),
            observed_start=observed_start,
            observed_end=observed_end,
            record_count=counters.records_seen,
            accepted_records=counters.records_accepted,
            rejected_records=counters.records_rejected,
            duplicate_records=counters.duplicates,
            port_count=len(ports),
            call_count=len(port_calls),
            quality_score=quality_score,
            completeness_ratio=completeness,
            freshness=freshness.created_at,
            source_status=source_status,
            quality_status=quality_status,
            source_health=health,
            provenance=provenance,
            ports=list(ports),
            positions=positions,
            port_calls=port_calls,
            port_activity_features=port_activity,
            port_vessel_mix_features=vessel_mix,
            port_timeline_features=timeline,
        )

        _payload["snapshot_id"] = snap.snapshot_id
        _payload["records_seen"] = counters.records_seen
        _payload["records_accepted"] = counters.records_accepted
        _payload["records_rejected"] = counters.records_rejected
        _payload["extras"] = {"port_calls": len(port_calls)}
        _payload["quality_score"] = round(quality_score, 4)

        if store is not None:
            try:
                _write_port_snapshot(store, snap)
                telemetry.record(
                    "maritime_noaa_snapshot_loaded",
                    source=ingestion.source,
                    dataset=ingestion.dataset,
                    snapshot_id=snap.snapshot_id,
                    status="ok",
                )
            except Exception as e:  # noqa: BLE001
                telemetry.record(
                    "maritime_noaa_snapshot_invalid",
                    source=ingestion.source,
                    dataset=ingestion.dataset,
                    snapshot_id=snap.snapshot_id,
                    status="error",
                    extras={"error": repr(e)},
                )

        return snap


# --------------------------------------------------------------------
# Internal helpers
# --------------------------------------------------------------------


def _process_records(
    ingestion: IngestionResult,
    ports: Sequence[Port],
    ingested_at: datetime,
) -> Tuple[List[VesselPosition], List[PortCall], RejectionCounters]:
    """Normalize raw NOAA records into positions + port-calls + counters."""
    counters = RejectionCounters()
    positions: List[VesselPosition] = []
    seen_keys: set = set()

    ingested_iso = ingested_at.isoformat()
    for raw in ingestion.records:
        counters.records_seen += 1
        try:
            pos, key = _normalize_one_position(raw, ingestion, ingested_iso)
        except _PosError as e:
            counters.invalid_values += 1
            counters.records_rejected += 1
            continue
        if key in seen_keys:
            counters.duplicates += 1
            counters.records_rejected += 1
            continue
        seen_keys.add(key)
        positions.append(pos)
        counters.records_accepted += 1

    port_calls = extract_port_calls(
        positions, ports,
        snapshot_id="pending",
        ingested_at=ingested_iso,
        min_dwell_minutes=30.0,
        dataset_version=ingestion.dataset_version,
        license=ingestion.license or "unresolved",
        attribution=ingestion.attribution or "",
    )
    return positions, port_calls, counters


def _normalize_one_position(
    raw: Mapping[str, Any],
    ingestion: IngestionResult,
    ingested_iso: str,
) -> Tuple[VesselPosition, str]:
    """Build a single canonical :class:`VesselPosition` from a raw dict.

    Returns the record + a dedup key. Raises ``_PosError`` for any
    invalid input; callers must catch and route into rejection
    counters.
    """
    if not isinstance(raw, Mapping):
        raise _PosError("raw is not a mapping")

    # Defensive: the NOAA adapter has already normalized key names but
    # we still apply strict validation here. Missing required fields
    # are caught by the schema validator and surfaced as _PosError.
    payload = dict(raw)
    payload.setdefault("source", ingestion.source)
    payload.setdefault("dataset", ingestion.dataset)
    payload.setdefault("dataset_version", ingestion.dataset_version)
    payload.setdefault("ingested_at", ingested_iso)
    payload.setdefault("snapshot_id", "pending")
    payload.setdefault("license", ingestion.license or "unresolved")
    payload.setdefault("attribution", ingestion.attribution or "")
    payload.setdefault("provenance", {
        "source": ingestion.source,
        "dataset": ingestion.dataset,
        "dataset_version": ingestion.dataset_version,
        "license": payload.get("license", "unresolved"),
        "attribution": payload.get("attribution", ""),
    })
    try:
        rec = VesselPosition.from_dict(payload)
    except (ValueError, KeyError) as e:
        raise _PosError(str(e)) from e

    # Dedup key: MMSI + timestamp
    key = f"{rec.mmsi}|{rec.timestamp}"
    return rec, key


def _classify_port_quality(
    counters: RejectionCounters,
    quality_score: float,
    license_str: str,
    ports: Sequence[Port],
) -> QualityStatus:
    if counters.records_seen == 0 or counters.records_accepted == 0:
        return QualityStatus.INVALID
    if not ports:
        return QualityStatus.DEGRADED
    if license_str == "unresolved":
        return QualityStatus.DEGRADED
    if quality_score < 0.5:
        return QualityStatus.DEGRADED
    return QualityStatus.HEALTHY


class _PosError(Exception):
    pass


# --------------------------------------------------------------------
# Snapshot writer (port-specific)
# --------------------------------------------------------------------


def _write_port_snapshot(
    store: SnapshotStore,
    snap: PortIntelligenceSnapshot,
    *,
    dataset_key: str = NOAA_DATASET_KEY,
) -> SnapshotPaths:
    """Write a :class:`PortIntelligenceSnapshot` to disk.

    Layout mirrors Phase 1: ``<base>/<dataset_key>/<snapshot_id>/`` with
    ``metadata.json``, ``manifest.json``, ``vessel_positions.jsonl``,
    and ``port_calls.jsonl``. Checksums cover the two JSONL files.
    """
    paths = SnapshotPaths(base=store.base_dir, dataset=dataset_key, snapshot_id=snap.snapshot_id)
    paths.ensure()

    # 1) Vessel positions JSONL
    pos_records = [p.to_dict() for p in snap.positions]
    positions_summary = write_jsonl(paths.root / "vessel_positions.jsonl", pos_records)

    # 2) Port-calls JSONL
    call_records = [c.to_dict() for c in snap.port_calls]
    calls_summary = write_jsonl(paths.root / "port_calls.jsonl", call_records)

    # 3) Manifest
    manifest = {
        "schema_version": snap.schema_version,
        "snapshot_id": snap.snapshot_id,
        "dataset": snap.dataset,
        "source": snap.source,
        "dataset_version": snap.dataset_version,
        "created_at": snap.created_at,
        "observed_start": snap.observed_start,
        "observed_end": snap.observed_end,
        "record_count": snap.record_count,
        "accepted_records": snap.accepted_records,
        "rejected_records": snap.rejected_records,
        "duplicate_records": snap.duplicate_records,
        "port_count": snap.port_count,
        "call_count": snap.call_count,
        "quality_score": snap.quality_score,
        "completeness_ratio": snap.completeness_ratio,
        "freshness": snap.freshness,
        "source_status": snap.source_status.value,
        "quality_status": snap.quality_status.value,
        "license": snap.license,
        "attribution": snap.attribution,
        "provenance": dict(snap.provenance),
        "ports": [p.to_dict() for p in snap.ports],
        "port_activity_features": [f.to_dict() for f in snap.port_activity_features],
        "port_vessel_mix_features": [f.to_dict() for f in snap.port_vessel_mix_features],
        "port_timeline_features": [f.to_dict() for f in snap.port_timeline_features],
        "checksum_vessel_positions": positions_summary["checksum"],
        "checksum_port_calls": calls_summary["checksum"],
        "checksum_manifest": "",
    }
    _atomic_write_json(paths.manifest, manifest)
    manifest["checksum_manifest"] = _hash_file(paths.manifest)
    _atomic_write_json(paths.manifest, manifest)

    # 4) Metadata
    metadata = snap.to_metadata_dict()
    metadata["files"] = {
        "vessel_positions": "vessel_positions.jsonl",
        "port_calls": "port_calls.jsonl",
        "manifest": "manifest.json",
    }
    _atomic_write_json(paths.metadata, metadata)

    return paths