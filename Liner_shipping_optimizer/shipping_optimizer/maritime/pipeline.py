"""End-to-end maritime intelligence pipeline.

This module ties together ingestion -> normalization -> quality -> storage
in a single deterministic function. It is the only function that knows
how to build a complete :class:`TrafficIntelligenceSnapshot` from an
:class:`IngestionResult`.

The pipeline is intentionally side-effect free apart from:

    * snapshot writes to disk (when ``store`` is provided)
    * telemetry events (always)

It NEVER makes network calls; the network is in the ingestion layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .ingestion.base import IngestionResult
from .normalization.coordinates import quantize_cell
from .normalization.timestamps import normalize_observation_window
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
    TrafficIntelligenceSnapshot,
)
from .schemas.traffic_density import TrafficDensityRecord, VesselClass, canonicalize_vessel_class
from .storage.snapshots import SnapshotStore, generate_snapshot_id
from .intelligence.traffic import compute_hotspots, compute_traffic_features
from . import telemetry
from . import source_health


# Default EMODnet dataset key used by the snapshot store and the adapter.
EMODNET_DATASET_KEY = "emodnet_vessel_density"


# --------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------


def build_snapshot(
    ingestion: IngestionResult,
    *,
    snapshot_id: Optional[str] = None,
    store: Optional[SnapshotStore] = None,
    stale_after_seconds: int = 60 * 60 * 24 * 30,
) -> TrafficIntelligenceSnapshot:
    """Build a :class:`TrafficIntelligenceSnapshot` from an ingestion result.

    Records are normalized, deduped, validated, and scored. Features and
    hotspots are derived. If ``store`` is provided the snapshot is also
    written to disk.
    """
    telemetry.record(
        "maritime_ingestion_started",
        source=ingestion.source,
        dataset=ingestion.dataset,
        snapshot_id=None,
        status="ok",
    )
    started = datetime.now(tz=timezone.utc)

    with telemetry.timed(
        "maritime_ingestion_completed",
        source=ingestion.source,
        dataset=ingestion.dataset,
        status="ok",
    ) as _payload:
        counters = RejectionCounters()
        accepted: List[TrafficDensityRecord] = []
        seen_keys: set = set()

        for raw in ingestion.records:
            counters.records_seen += 1
            try:
                record, key = _normalize_one(raw, ingestion)
            except _CoordError:
                counters.invalid_coordinates += 1
                counters.records_rejected += 1
                continue
            except _ValueError:
                counters.invalid_values += 1
                counters.records_rejected += 1
                continue
            except _TimestampError:
                counters.invalid_timestamps += 1
                counters.records_rejected += 1
                continue
            except _MissingError:
                counters.missing_required_fields += 1
                counters.records_rejected += 1
                continue
            except _VesselError:
                counters.invalid_vessel_class += 1
                counters.records_rejected += 1
                continue
            except Exception:  # noqa: BLE001
                counters.other_errors += 1
                counters.records_rejected += 1
                continue
            if key in seen_keys:
                counters.duplicates += 1
                counters.records_rejected += 1
                continue
            seen_keys.add(key)
            accepted.append(record)
            counters.records_accepted += 1

        completeness = compute_completeness_ratio(counters)
        avg_q = (
            sum(r.quality for r in accepted) / len(accepted) if accepted else None
        )
        quality_score = compute_quality_score(counters, avg_record_quality=avg_q)

        # Determine observed period from the records (earliest/latest observation).
        if accepted:
            obs_starts = sorted(r.observation_start for r in accepted)
            obs_ends = sorted(r.observation_end for r in accepted)
            observed_start = obs_starts[0]
            observed_end = obs_ends[-1]
        else:
            observed_start = ingestion.observed_period.get(
                "start", ingestion.retrieved_at
            )
            observed_end = ingestion.observed_period.get(
                "end", ingestion.retrieved_at
            )

        # Resolve license: mark unresolved rather than guess.
        license_str = ingestion.license if ingestion.license else "unresolved"
        attribution = ingestion.attribution or ""

        # Determine the quality status of the whole snapshot.
        quality_status = _classify_quality(counters, quality_score, license_str)

        # Source-health state machine.
        health = source_health.initial(ingestion.source)
        if not accepted:
            health = source_health.transition(health, event="snapshot_missing",
                                              success=False, notes="no accepted records")
        else:
            health = source_health.transition(health, event="snapshot_loaded",
                                              success=True, notes="snapshot built")
        freshness = compute_freshness(
            ingestion.retrieved_at, is_historical=True, stale_after_seconds=stale_after_seconds
        )
        if freshness.is_stale:
            health = source_health.transition(health, event="snapshot_stale",
                                              success=False, notes="snapshot older than threshold")
        source_status = health.status

        # Provenance
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

        # Features + hotspots
        features = compute_traffic_features(accepted) if maritime_traffic_enabled_default() else []
        hotspots = compute_hotspots(accepted) if maritime_traffic_enabled_default() else []

        sid = snapshot_id or generate_snapshot_id(dataset=EMODNET_DATASET_KEY, created_at=started)
        snap = TrafficIntelligenceSnapshot(
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
            quality_score=quality_score,
            completeness_ratio=completeness,
            freshness=freshness.created_at,
            source_status=source_status,
            quality_status=quality_status,
            source_health=health,
            provenance=provenance,
            records=accepted,
            features=features,
            hotspots=hotspots,
        )

        # Telemetry payload enrichment
        _payload["snapshot_id"] = snap.snapshot_id
        _payload["records_seen"] = counters.records_seen
        _payload["records_accepted"] = counters.records_accepted
        _payload["records_rejected"] = counters.records_rejected
        _payload["quality_score"] = round(quality_score, 4)

        if store is not None:
            try:
                store.write(snap, dataset_key=EMODNET_DATASET_KEY)
                telemetry.record(
                    "maritime_snapshot_loaded",
                    source=ingestion.source,
                    dataset=ingestion.dataset,
                    snapshot_id=snap.snapshot_id,
                    status="ok",
                )
            except Exception as e:  # noqa: BLE001
                telemetry.record(
                    "maritime_snapshot_invalid",
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


def maritime_traffic_enabled_default() -> bool:
    """Default: features are computed if the master flag is on. We do not
    require MARITIME_TRAFFIC_ENABLED to be set to *build* the snapshot —
    only to *expose* the features through the adapter. The build pipeline
    always runs derivation; gating happens at the consumer.
    """
    import os
    return os.environ.get("MARITIME_INTELLIGENCE_ENABLED", "0").lower() in ("1", "true", "yes", "on")


class _CoordError(Exception):
    pass


class _ValueError(Exception):
    pass


class _TimestampError(Exception):
    pass


class _MissingError(Exception):
    pass


class _VesselError(Exception):
    pass


def _normalize_one(raw: Mapping[str, Any], ingestion: IngestionResult) -> Tuple[TrafficDensityRecord, str]:
    """Build one record from a raw dict, returning the record + a dedup key."""
    if not isinstance(raw, Mapping):
        raise _ValueError("raw is not a mapping")
    # Coordinates
    try:
        lat = float(raw.get("latitude"))
        lon = float(raw.get("longitude"))
    except (TypeError, ValueError) as e:
        raise _CoordError(str(e)) from e
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
        raise _CoordError("coord out of range")
    # Spatial id: prefer explicit, fall back to quantized centroid.
    spatial_id = raw.get("spatial_id")
    if not spatial_id or not isinstance(spatial_id, str):
        try:
            spatial_id = quantize_cell(lat, lon, precision=3)
        except Exception as e:
            raise _CoordError(str(e)) from e
    # Vessel class
    raw_vc = raw.get("vessel_class")
    if raw_vc is None or (isinstance(raw_vc, str) and raw_vc.strip() == ""):
        raise _VesselError("missing vessel_class")
    vc = canonicalize_vessel_class(raw_vc)
    # Intensity
    try:
        intensity = float(raw.get("intensity"))
    except (TypeError, ValueError) as e:
        raise _ValueError(str(e)) from e
    if intensity < 0 or intensity != intensity:
        raise _ValueError("intensity invalid")
    # Observation window
    try:
        obs_start = raw.get("observation_start") or raw.get("obs_start") or raw.get("start")
        obs_end = raw.get("observation_end") or raw.get("obs_end") or raw.get("end")
        if obs_start is None or obs_end is None:
            # Allow a single 'timestamp' / 'observed_at' field.
            single = raw.get("timestamp") or raw.get("observed_at")
            if single is not None:
                obs_start = obs_end = single
        if obs_start is None or obs_end is None:
            raise _TimestampError("missing observation window")
        obs_start, obs_end = normalize_observation_window(obs_start, obs_end)
    except Exception as e:
        raise _TimestampError(str(e)) from e
    # observed_at: prefer explicit, else max(obs_start, obs_end)
    observed_at = raw.get("observed_at") or obs_end
    # Quality: default to 1.0 if missing, else clamp
    try:
        quality = float(raw.get("quality", 1.0))
    except (TypeError, ValueError) as e:
        raise _ValueError(str(e)) from e
    if not (0.0 <= quality <= 1.0):
        raise _ValueError("quality out of range")
    # Metadata
    source = raw.get("source") or ingestion.source
    dataset = raw.get("dataset") or ingestion.dataset
    dataset_version = raw.get("dataset_version") or ingestion.dataset_version
    license_str = raw.get("license") or ingestion.license or "unresolved"
    attribution = raw.get("attribution") or ingestion.attribution or ""
    snapshot_id = raw.get("snapshot_id") or "pending"
    if not isinstance(source, str) or not source:
        raise _MissingError("source")
    if not isinstance(dataset, str) or not dataset:
        raise _MissingError("dataset")
    if not isinstance(dataset_version, str) or not dataset_version:
        raise _MissingError("dataset_version")
    if not isinstance(license_str, str):
        raise _MissingError("license")
    if not isinstance(attribution, str):
        raise _MissingError("attribution")

    # Build via the canonical schema so the same validators apply.
    rec = TrafficDensityRecord.from_dict({
        "spatial_id": spatial_id,
        "latitude": lat,
        "longitude": lon,
        "vessel_class": vc.value,
        "intensity": intensity,
        "observation_start": obs_start,
        "observation_end": obs_end,
        "source": source,
        "dataset": dataset,
        "dataset_version": dataset_version,
        "observed_at": observed_at,
        "ingested_at": datetime.now(tz=timezone.utc).isoformat(),
        "snapshot_id": snapshot_id,
        "quality": quality,
        "provenance": {
            "source": ingestion.source,
            "dataset": ingestion.dataset,
            "dataset_version": ingestion.dataset_version,
            "retrieved_at": ingestion.retrieved_at,
            "observed_period": {"start": obs_start, "end": obs_end},
            "license": license_str,
            "attribution": attribution,
        },
        "license": license_str,
        "attribution": attribution,
        "extra": dict(raw.get("extra") or {}),
    })
    # Dedup key: spatial + class + observation_start
    dedup_key = f"{rec.spatial_id}|{rec.vessel_class.value}|{rec.observation_start}"
    return rec, dedup_key


def _classify_quality(
    counters: RejectionCounters, quality_score: float, license_str: str
) -> QualityStatus:
    if counters.records_seen == 0 or counters.records_accepted == 0:
        return QualityStatus.INVALID
    if license_str == "unresolved":
        return QualityStatus.DEGRADED
    if quality_score < 0.5:
        return QualityStatus.DEGRADED
    return QualityStatus.HEALTHY
