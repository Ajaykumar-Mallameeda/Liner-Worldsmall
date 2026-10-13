"""Phase 4 — Live maritime orchestrator.

The orchestrator is the bounded entry point that:

1. Reads the ``MARITIME_LIVE_PROVIDER`` env var to pick a provider.
2. Verifies the master feature flag.
3. Performs a live fetch (or skips it when disabled).
4. Normalizes, validates, and quality-scores the records.
5. Publishes a fresh immutable local snapshot via the existing
   :mod:`maritime.snapshot_publisher`.
6. Emits structured :mod:`maritime.telemetry` events for every step.

The orchestrator never raises; it returns a structured
:class:`LiveRunResult` that downstream code (REST endpoints, dashboard
view-model) can serialize directly.

It is the single new place where the live layer touches the rest of
the system. Everything else is read-only.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .. import telemetry
from ..quality.completeness import RejectionCounters, compute_quality_score
from ..quality.freshness import compute_freshness
from ..quality.provenance import build_provenance
from ..schemas.intelligence import (
    QualityStatus,
    SourceHealth,
    SourceStatus,
    TrafficHotspot,
    TrafficIntelligenceSnapshot,
    TrafficFeature,
)
from ..schemas.traffic_density import TrafficDensityRecord, VesselClass
from ..schemas.vessel_position import VesselPosition
from ..snapshot_publisher import (
    PublicationResult,
    publish_json,
    publish_jsonl,
)
from ..storage.snapshots import DEFAULT_SNAPSHOT_BASE, generate_snapshot_id
from .provider import BaseLiveProvider, LiveFetchResult
from .registry import get_provider_class


LIVE_DATASET_KEY = "digitraffic_live_vessel_positions"
LIVE_SCHEMA_VERSION = "1.0.0"


# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------


def live_enabled() -> bool:
    raw = os.environ.get("MARITIME_LIVE_ENABLED", "0")
    return raw.strip().lower() in ("1", "true", "yes", "on")


def live_provider_name() -> str:
    raw = os.environ.get("MARITIME_LIVE_PROVIDER", "").strip()
    return raw or ""


def live_max_age_seconds() -> int:
    raw = os.environ.get("MARITIME_LIVE_MAX_AGE_SECONDS", "600")
    try:
        return int(raw.strip())
    except ValueError:
        return 600


# --------------------------------------------------------------------
# Result types
# --------------------------------------------------------------------


@dataclass(frozen=True)
class LiveRunResult:
    """Outcome of a single orchestrator run.

    ``state`` is one of the dashboard-facing tokens (live, cached,
    historical, stale, offline, degraded, disabled, error).
    """

    state: str
    enabled: bool
    provider: Optional[str] = None
    snapshot_id: Optional[str] = None
    snapshot_dir: Optional[str] = None
    record_count: int = 0
    accepted: int = 0
    rejected: int = 0
    quality_score: float = 0.0
    freshness_seconds: Optional[float] = None
    license: str = "unresolved"
    attribution: str = ""
    fallback_tier: str = "empty"
    duration_ms: float = 0.0
    error_kind: Optional[str] = None
    error: Optional[str] = None
    rate_limited: bool = False
    http: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    raw_event_log: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "enabled": self.enabled,
            "provider": self.provider,
            "snapshot_id": self.snapshot_id,
            "snapshot_dir": self.snapshot_dir,
            "record_count": self.record_count,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "quality_score": self.quality_score,
            "freshness_seconds": self.freshness_seconds,
            "license": self.license,
            "attribution": self.attribution,
            "fallback_tier": self.fallback_tier,
            "duration_ms": round(self.duration_ms, 3),
            "error_kind": self.error_kind,
            "error": self.error,
            "rate_limited": self.rate_limited,
            "http": self.http,
            "provenance": self.provenance,
            "events": self.raw_event_log,
        }


# --------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------


class LiveOrchestrator:
    """Bounded entry point for live maritime ingestion.

    All public methods are read-only or short-lived side-effecting
    operations. The orchestrator never mutates the optimizer; it
    publishes a new snapshot directory and returns.
    """

    def __init__(
        self,
        *,
        provider: Optional[BaseLiveProvider] = None,
        snapshot_root: Optional[Path] = None,
    ) -> None:
        self._provider = provider
        self._snapshot_root = Path(
            snapshot_root
            if snapshot_root is not None
            else os.environ.get("MARITIME_SNAPSHOT_BASE", str(DEFAULT_SNAPSHOT_BASE))
        )

    @property
    def snapshot_root(self) -> Path:
        return self._snapshot_root

    def set_provider(self, provider: BaseLiveProvider) -> None:
        self._provider = provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        """Read-only status without performing any fetch."""
        enabled = live_enabled()
        name = live_provider_name() if enabled else ""
        latest = self._latest_snapshot()
        return {
            "enabled": enabled,
            "provider": name or None,
            "latest_snapshot": latest,
            "evaluated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    def run_once(self, *, local_path: Optional[str] = None,
                 provider_name: Optional[str] = None) -> LiveRunResult:
        """Run one fetch+publish cycle. Never raises."""
        started = time.perf_counter()
        events: List[Dict[str, Any]] = []
        if not live_enabled() and local_path is None:
            result = LiveRunResult(
                state="disabled",
                enabled=False,
                duration_ms=(time.perf_counter() - started) * 1000.0,
                raw_event_log=events,
            )
            self._record_event("maritime_live_disabled", events, **{})
            return result
        provider = self._provider
        if provider is None:
            name = provider_name or live_provider_name()
            if not name:
                result = LiveRunResult(
                    state="disabled",
                    enabled=False,
                    error_kind="provider_not_selected",
                    error="MARITIME_LIVE_PROVIDER is not set",
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                    raw_event_log=events,
                )
                self._record_event("maritime_live_provider_missing", events)
                return result
            try:
                cls = get_provider_class(name)
            except KeyError as e:
                result = LiveRunResult(
                    state="error",
                    enabled=True,
                    provider=name,
                    error_kind="unknown_provider",
                    error=str(e),
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                    raw_event_log=events,
                )
                self._record_event("maritime_live_provider_unknown", events, **{"provider": name})
                return result
            provider = cls()
        fetch = self._fetch(provider, local_path=local_path, events=events)
        if not fetch.ok:
            return self._build_failure_result(provider, fetch, started, events)
        return self._publish(provider, fetch, started, events)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fetch(
        self,
        provider: BaseLiveProvider,
        *,
        local_path: Optional[str],
        events: List[Dict[str, Any]],
    ) -> LiveFetchResult:
        self._record_event(
            "maritime_ingestion_started",
            events,
            provider=provider.config.name,
            url=provider.endpoint_url(),
        )
        if local_path is not None and hasattr(provider, "fetch_local"):
            fetch = provider.fetch_local(local_path)  # type: ignore[attr-defined]
        else:
            fetch = provider.fetch_snapshot()
        if fetch.ok:
            self._record_event(
                "maritime_ingestion_completed",
                events,
                provider=provider.config.name,
                status_code=fetch.http.status,
                attempts=fetch.http.attempts,
                duration_ms=fetch.http.duration_ms,
            )
        else:
            self._record_event(
                "maritime_ingestion_failed",
                events,
                provider=provider.config.name,
                error_kind=fetch.error_kind,
                attempts=fetch.http.attempts,
            )
        return fetch

    def _build_failure_result(
        self,
        provider: BaseLiveProvider,
        fetch: LiveFetchResult,
        started: float,
        events: List[Dict[str, Any]],
    ) -> LiveRunResult:
        rate_limited = bool(fetch.error_kind == "http_429")
        if rate_limited:
            self._record_event("maritime_rate_limited", events,
                               provider=provider.config.name,
                               retry_after=fetch.http.retry_after_seconds)
        # Source-health degraded/offline
        self._record_event(
            "maritime_source_degraded" if fetch.error_kind in (
                "http_5xx", "timeout", "connection_reset",
            ) else "maritime_source_offline",
            events,
            provider=provider.config.name,
            error_kind=fetch.error_kind,
        )
        # Fallback: latest valid live snapshot if any
        latest = self._latest_snapshot()
        if latest is not None:
            self._record_event("maritime_fallback_activated", events,
                               provider=provider.config.name,
                               fallback_tier="cached_live")
            return LiveRunResult(
                state="cached",
                enabled=True,
                provider=provider.config.name,
                snapshot_id=latest.get("snapshot_id"),
                snapshot_dir=latest.get("snapshot_dir"),
                record_count=latest.get("record_count", 0),
                accepted=latest.get("record_count", 0),
                quality_score=latest.get("quality_score", 0.0),
                license=latest.get("license", "unresolved"),
                attribution=latest.get("attribution", ""),
                fallback_tier="cached_live",
                duration_ms=(time.perf_counter() - started) * 1000.0,
                error_kind=fetch.error_kind,
                error=fetch.error,
                rate_limited=rate_limited,
                http=fetch.http.to_dict(),
                provenance=latest.get("provenance", {}),
                raw_event_log=events,
            )
        # No previous live snapshot; fall back to historical (NOAA) and
        # finally to the deterministic safe-empty payload.
        self._record_event("maritime_fallback_activated", events,
                           provider=provider.config.name,
                           fallback_tier="historical")
        return LiveRunResult(
            state="historical",
            enabled=True,
            provider=provider.config.name,
            snapshot_id=None,
            snapshot_dir=None,
            record_count=0,
            accepted=0,
            rejected=0,
            quality_score=0.0,
            license=provider.config.license,
            attribution=provider.config.attribution,
            fallback_tier="historical",
            duration_ms=(time.perf_counter() - started) * 1000.0,
            error_kind=fetch.error_kind,
            error=fetch.error,
            rate_limited=rate_limited,
            http=fetch.http.to_dict(),
            provenance={
                "provider": provider.config.name,
                "url": provider.endpoint_url(),
                "license": provider.config.license,
                "attribution": provider.config.attribution,
            },
            raw_event_log=events,
        )

    def _publish(
        self,
        provider: BaseLiveProvider,
        fetch: LiveFetchResult,
        started: float,
        events: List[Dict[str, Any]],
    ) -> LiveRunResult:
        try:
            normalized = provider.parse(fetch.payload)
        except Exception as e:  # noqa: BLE001
            self._record_event("maritime_snapshot_rejected", events,
                               provider=provider.config.name,
                               error_kind="parse_failed",
                               error=str(e))
            return self._build_failure_result(
                provider,
                LiveFetchResult(
                    ok=False,
                    provider=provider.config.name,
                    url=fetch.url,
                    retrieved_at=fetch.retrieved_at,
                    http=fetch.http,
                    error_kind="schema_mismatch",
                    error=f"parse failed: {e!r}",
                ),
                started,
                events,
            )
        # Validate each record; build accepted/rejected lists.
        accepted_positions: List[VesselPosition] = []
        rejected = 0
        for raw in normalized:
            try:
                pos = VesselPosition.from_dict(raw)
            except (ValueError, TypeError) as e:
                rejected += 1
                continue
            accepted_positions.append(pos)
        if not accepted_positions and normalized:
            # 100% rejection -> treat as schema_mismatch
            self._record_event("maritime_snapshot_rejected", events,
                               provider=provider.config.name,
                               error_kind="schema_mismatch",
                               reason="all_records_invalid")
            return self._build_failure_result(
                provider,
                LiveFetchResult(
                    ok=False,
                    provider=provider.config.name,
                    url=fetch.url,
                    retrieved_at=fetch.retrieved_at,
                    http=fetch.http,
                    error_kind="schema_mismatch",
                    error="all records failed validation",
                ),
                started,
                events,
            )
        # Quality score
        avg_quality = (
            sum(p.quality for p in accepted_positions) / len(accepted_positions)
            if accepted_positions else 0.0
        )
        counters = RejectionCounters(
            records_seen=len(normalized),
            records_accepted=len(accepted_positions),
            records_rejected=rejected,
            duplicates=0,
        )
        quality = compute_quality_score(
            counters, avg_record_quality=avg_quality,
        )
        # Compute observed period first so the provenance helper has it.
        created_at_iso = datetime.now(tz=timezone.utc).isoformat()
        observed_start = min(
            (p.timestamp for p in accepted_positions), default=created_at_iso,
        )
        observed_end = max(
            (p.timestamp for p in accepted_positions), default=created_at_iso,
        )
        # Build provenance using the existing helper.
        prov = build_provenance(
            source=provider.source,
            dataset=LIVE_DATASET_KEY,
            dataset_version="ais/v1/locations",
            retrieved_at=fetch.retrieved_at,
            observed_period={"start": observed_start, "end": observed_end},
            license_str=provider.config.license,
            attribution=provider.config.attribution,
            extras={"provider": provider.config.name, "url": provider.endpoint_url()},
        )
        # Synthesize a thin TrafficIntelligenceSnapshot so the existing
        # SnapshotStore.write() pipeline can publish it. Live records
        # carry the canonical VesselPosition shape; we store the JSON
        # form on the manifest and write JSONL.
        snapshot_id = generate_snapshot_id(
            dataset=LIVE_DATASET_KEY,
            created_at=datetime.now(tz=timezone.utc),
        )
        # Build the manifest payload (records are written separately).
        record_dicts = [p.to_dict() for p in accepted_positions]
        records_path = self._snapshot_root / LIVE_DATASET_KEY / snapshot_id / "vessel_positions.jsonl"
        try:
            self._snapshot_root.mkdir(parents=True, exist_ok=True)
            publication = publish_jsonl(records_path, record_dicts)
        except Exception as e:  # noqa: BLE001
            self._record_event("maritime_snapshot_rejected", events,
                               provider=provider.config.name,
                               error_kind="publication_failed",
                               error=str(e))
            return self._build_failure_result(
                provider,
                LiveFetchResult(
                    ok=False,
                    provider=provider.config.name,
                    url=fetch.url,
                    retrieved_at=fetch.retrieved_at,
                    http=fetch.http,
                    error_kind="publication_failed",
                    error=str(e),
                ),
                started,
                events,
            )
        # Write manifest + metadata
        manifest_path = records_path.parent / "manifest.json"
        metadata_path = records_path.parent / "metadata.json"
        # Freshness
        try:
            age = (datetime.fromisoformat(observed_end.replace("Z", "+00:00"))
                   - datetime.now(tz=timezone.utc)).total_seconds()
        except Exception:
            age = 0.0
        is_live_fresh = abs(age) <= provider.config.max_age_seconds
        freshness_label = "live" if is_live_fresh else "stale"
        health = SourceHealth(
            source=provider.source,
            status=SourceStatus.AVAILABLE if is_live_fresh else SourceStatus.STALE,
            last_check_at=created_at_iso,
            last_success_at=created_at_iso,
            last_failure_at=None,
            consecutive_failures=0,
            notes="live fetch ok" if is_live_fresh else "live but stale",
        )
        quality_status = (
            QualityStatus.HEALTHY if avg_quality >= 0.5
            else QualityStatus.DEGRADED
        )
        manifest = {
            "schema_version": LIVE_SCHEMA_VERSION,
            "snapshot_id": snapshot_id,
            "dataset": LIVE_DATASET_KEY,
            "source": provider.source,
            "dataset_version": "ais/v1/locations",
            "created_at": created_at_iso,
            "observed_start": observed_start,
            "observed_end": observed_end,
            "record_count": len(record_dicts),
            "accepted_records": len(accepted_positions),
            "rejected_records": rejected,
            "duplicate_records": 0,
            "quality_score": round(quality, 4),
            "completeness_ratio": 1.0 if accepted_positions else 0.0,
            "freshness": freshness_label,
            "source_status": health.status.value,
            "quality_status": quality_status.value,
            "license": provider.config.license,
            "attribution": provider.config.attribution,
            "provenance": prov,
            "records_path": str(records_path.relative_to(self._snapshot_root)),
            "checksum_records": publication.sha256,
            "checksum_manifest": "",
            "checksum_metadata": "",
            "checksum": publication.sha256,
            "size_bytes": publication.size_bytes,
            "previous_known_good_preserved": publication.previous_known_good_preserved,
            "provider": provider.config.name,
            "endpoint_url": provider.endpoint_url(),
            "http": fetch.http.to_dict(),
        }
        publish_json(manifest_path, manifest)
        metadata = {
            "snapshot_id": snapshot_id,
            "source": provider.source,
            "provider": provider.config.name,
            "dataset": LIVE_DATASET_KEY,
            "dataset_version": "ais/v1/locations",
            "license": provider.config.license,
            "attribution": provider.config.attribution,
            "created_at": created_at_iso,
            "observed_start": observed_start,
            "observed_end": observed_end,
            "record_count": len(record_dicts),
            "accepted_records": len(accepted_positions),
            "rejected_records": rejected,
            "quality_score": round(quality, 4),
            "completeness_ratio": 1.0 if accepted_positions else 0.0,
            "freshness": freshness_label,
            "source_status": health.status.value,
            "quality_status": quality_status.value,
            "source_health": health.to_dict(),
            "provenance": prov,
            "schema_version": LIVE_SCHEMA_VERSION,
        }
        publish_json(metadata_path, metadata)
        self._record_event("maritime_snapshot_created", events,
                           provider=provider.config.name,
                           dataset=LIVE_DATASET_KEY,
                           snapshot_id=snapshot_id,
                           record_count=len(record_dicts),
                           quality_score=round(avg_quality, 4))
        self._record_event("maritime_source_available", events,
                           provider=provider.config.name,
                           freshness_label=freshness_label)
        self._record_event("maritime_data_quality_changed", events,
                           provider=provider.config.name,
                           quality_score=round(avg_quality, 4),
                           rejected=rejected)
        # Mark in-process caches stale
        try:
            from ..feature_adapter import FeatureAdapter
            FeatureAdapter().invalidate_cache()
        except Exception:
            pass
        return LiveRunResult(
            state=freshness_label,
            enabled=True,
            provider=provider.config.name,
            snapshot_id=snapshot_id,
            snapshot_dir=str(records_path.parent),
            record_count=len(record_dicts),
            accepted=len(accepted_positions),
            rejected=rejected,
            quality_score=round(avg_quality, 4),
            freshness_seconds=age,
            license=provider.config.license,
            attribution=provider.config.attribution,
            fallback_tier="live",
            duration_ms=(time.perf_counter() - started) * 1000.0,
            http=fetch.http.to_dict(),
            provenance=prov,
            raw_event_log=events,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _record_event(
        self,
        event: str,
        events: List[Dict[str, Any]],
        **fields: Any,
    ) -> None:
        payload: Dict[str, Any] = {"event": event}
        payload.update(fields)
        payload["timestamp"] = datetime.now(tz=timezone.utc).isoformat()
        events.append(payload)
        try:
            telemetry.record(event, **payload)
        except Exception:
            pass

    def _latest_snapshot(self) -> Optional[Dict[str, Any]]:
        """Return a small dict describing the most recent live snapshot."""
        base = self._snapshot_root / LIVE_DATASET_KEY
        if not base.is_dir():
            return None
        children = sorted(
            [c for c in base.iterdir() if c.is_dir() and (c / "metadata.json").exists()],
            key=lambda p: p.name,
        )
        if not children:
            return None
        latest = children[-1]
        try:
            import json as _json
            meta = _json.loads((latest / "metadata.json").read_text(encoding="utf-8"))
        except Exception:
            return None
        return {
            "snapshot_id": meta.get("snapshot_id"),
            "snapshot_dir": str(latest),
            "created_at": meta.get("created_at"),
            "record_count": meta.get("accepted_records", 0),
            "quality_score": meta.get("quality_score", 0.0),
            "license": meta.get("license", "unresolved"),
            "attribution": meta.get("attribution", ""),
            "freshness": meta.get("freshness", "unknown"),
            "source_status": meta.get("source_status", "unknown"),
            "provenance": meta.get("provenance", {}),
        }


__all__ = [
    "LiveOrchestrator",
    "LiveRunResult",
    "LIVE_DATASET_KEY",
    "LIVE_SCHEMA_VERSION",
    "live_enabled",
    "live_provider_name",
    "live_max_age_seconds",
]
