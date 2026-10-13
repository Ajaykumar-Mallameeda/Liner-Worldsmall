"""Phase 5 — Weather orchestrator.

The orchestrator is the single entry point that the rest of the
system (REST endpoints, dashboard, FeatureAdapter) talks to. It:

1. Reads ``MARITIME_WEATHER_PROVIDER`` to pick a provider.
2. Verifies the master feature flag ``MARITIME_WEATHER_ENABLED``.
3. Performs a bounded fetch through the chosen provider.
4. Normalizes, validates, quality-scores, and freshness-stamps
   every record.
5. Publishes a fresh, immutable local snapshot via
   :mod:`maritime.snapshot_publisher`.
6. Emits structured telemetry events for every step.

Like its Phase 4 sibling, the orchestrator never raises. It returns
a structured :class:`WeatherRunResult` that downstream code can
serialize directly.

The orchestrator is the only place where live weather data enters
the rest of the system. Everything else is read-only and
network-free.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .. import telemetry
from ..quality.completeness import RejectionCounters, compute_quality_score
from ..quality.freshness import compute_freshness
from ..quality.provenance import build_provenance
from ..schemas.weather import WeatherObservation
from ..snapshot_publisher import PublicationResult, publish_json, publish_jsonl
from ..storage.snapshots import DEFAULT_SNAPSHOT_BASE, generate_snapshot_id


WEATHER_DATASET_KEY = "maritime_weather_observations"
WEATHER_SCHEMA_VERSION = "1.0.0"


# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    return raw if raw is not None and raw.strip() != "" else default


def _env_list(name: str, default: Sequence[float]) -> List[float]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return list(default)
    out: List[float] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        try:
            out.append(float(tok))
        except ValueError:
            continue
    return out or list(default)


# Default sampling locations: a representative global grid.
# All are over open ocean, deliberately international.
DEFAULT_GLOBAL_SAMPLES: List[Tuple[float, float]] = [
    (53.55, 9.99),    # North Sea approaches (open water near Hamburg)
    (36.85, -76.29),  # US East Coast (Norfolk approaches)
    (1.30, 103.85),   # Strait of Malacca approaches
    (33.95, -118.40), # US West Coast approaches
    (-23.95, -46.33), # Santos approaches
    (35.45, 139.95),  # Tokyo Bay approaches
    (31.20, 121.50),  # Shanghai approaches
    (-33.95, 18.42),  # Cape Town approaches
    (60.15, 24.95),   # Baltic approaches (Helsinki)
    (25.65, -80.10),  # Miami approaches
]


@dataclass(frozen=True)
class WeatherOrchestratorConfig:
    """Orchestrator configuration."""

    enabled: bool = False
    provider_name: str = "openmeteo"
    snapshot_base: str = DEFAULT_SNAPSHOT_BASE
    dataset_key: str = WEATHER_DATASET_KEY
    schema_version: str = WEATHER_SCHEMA_VERSION
    commercial_check: bool = True
    samples: List[Tuple[float, float]] = field(
        default_factory=lambda: list(DEFAULT_GLOBAL_SAMPLES)
    )

    @classmethod
    def from_env(cls) -> "WeatherOrchestratorConfig":
        samples_env = os.environ.get("MARITIME_WEATHER_SAMPLES")
        samples: List[Tuple[float, float]] = []
        if samples_env and samples_env.strip():
            for tok in samples_env.split(";"):
                tok = tok.strip()
                if not tok or "," not in tok:
                    continue
                a, _, b = tok.partition(",")
                try:
                    samples.append((float(a.strip()), float(b.strip())))
                except ValueError:
                    continue
        if not samples:
            samples = list(DEFAULT_GLOBAL_SAMPLES)
        return cls(
            enabled=_env_bool("MARITIME_WEATHER_ENABLED", False),
            provider_name=_env_str("MARITIME_WEATHER_PROVIDER", "openmeteo"),
            snapshot_base=_env_str(
                "MARITIME_WEATHER_SNAPSHOT_BASE", DEFAULT_SNAPSHOT_BASE
            ),
            commercial_check=_env_bool(
                "MARITIME_WEATHER_REQUIRE_COMMERCIAL_SAFE", True
            ),
            samples=samples,
        )


# --------------------------------------------------------------------
# Result type
# --------------------------------------------------------------------


@dataclass(frozen=True)
class WeatherRunResult:
    """Outcome of a single orchestrator run."""

    ok: bool
    enabled: bool
    provider: str
    retrieved_at: str
    snapshot_id: str
    dataset_key: str
    schema_version: str
    commercial_safe: bool
    source_health: str
    records_seen: int = 0
    records_accepted: int = 0
    records_rejected: int = 0
    snapshot_path: Optional[str] = None
    manifest_path: Optional[str] = None
    error_kind: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    samples_attempted: int = 0
    samples_succeeded: int = 0
    quality: float = 0.0
    freshness_state: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "enabled": self.enabled,
            "provider": self.provider,
            "retrieved_at": self.retrieved_at,
            "snapshot_id": self.snapshot_id,
            "dataset_key": self.dataset_key,
            "schema_version": self.schema_version,
            "commercial_safe": self.commercial_safe,
            "source_health": self.source_health,
            "records_seen": self.records_seen,
            "records_accepted": self.records_accepted,
            "records_rejected": self.records_rejected,
            "snapshot_path": self.snapshot_path,
            "manifest_path": self.manifest_path,
            "error_kind": self.error_kind,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 3),
            "samples_attempted": self.samples_attempted,
            "samples_succeeded": self.samples_succeeded,
            "quality": round(self.quality, 3),
            "freshness_state": self.freshness_state,
        }


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _is_commercial_safe(provider: Any) -> bool:
    cs = getattr(provider, "commercial_safe", None)
    if isinstance(cs, bool):
        return cs
    # Fall back to config inspection.
    cfg = getattr(provider, "openmeteo_config", None) or getattr(
        provider, "noaa_nws_config", None
    )
    if cfg is not None:
        return bool(getattr(cfg, "commercial_safe", False))
    return False


def _compute_health(
    *,
    ok: bool,
    counters: RejectionCounters,
    quality: float,
) -> str:
    if not ok:
        return "offline"
    if counters.records_accepted == 0:
        return "offline"
    if quality < 0.5:
        return "degraded"
    return "available"


# --------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------


class WeatherOrchestrator:
    """The bounded entry point for live weather data.

    The orchestrator is the only place outside ``maritime/live/`` and
    ``maritime/weather/`` that may invoke a network operation; the
    invocation is funnelled through the provider's bounded HTTP
    client, which is shared with the rest of the maritime layer.
    """

    def __init__(self, config: Optional[WeatherOrchestratorConfig] = None) -> None:
        self._config = config or WeatherOrchestratorConfig.from_env()
        self._provider = self._load_provider(self._config.provider_name)
        # Disable the provider by default; the orchestrator's enabled
        # flag is the master switch.
        if self._provider is not None:
            try:
                self._provider._config.enabled = False  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def config(self) -> WeatherOrchestratorConfig:
        return self._config

    @property
    def provider(self) -> Any:
        return self._provider

    def list_providers(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "openmeteo",
                "label": "Open-Meteo",
                "license": "Open-Meteo Free (non-commercial)",
                "commercial_safe": False,
                "endpoint": "https://api.open-meteo.com/v1/forecast",
            },
            {
                "name": "noaa_nws",
                "label": "NOAA NWS (api.weather.gov)",
                "license": "U.S. Government public domain",
                "commercial_safe": True,
                "endpoint": "https://api.weather.gov/points/{lat},{lon}",
            },
        ]

    def run(self) -> WeatherRunResult:
        """Execute one orchestrator pass. Never raises."""
        started = time.perf_counter()
        retrieved_at = datetime.now(tz=timezone.utc).isoformat()
        snapshot_id = generate_snapshot_id(dataset=self._config.dataset_key)
        provider_name = self._config.provider_name

        if not self._config.enabled:
            telemetry.record(
                "maritime_weather_run_skipped",
                source=provider_name,
                status="disabled",
                extras={"reason": "MARITIME_WEATHER_ENABLED is false"},
            )
            return WeatherRunResult(
                ok=False,
                enabled=False,
                provider=provider_name,
                retrieved_at=retrieved_at,
                snapshot_id=snapshot_id,
                dataset_key=self._config.dataset_key,
                schema_version=self._config.schema_version,
                commercial_safe=_is_commercial_safe(self._provider)
                if self._provider else False,
                source_health="offline",
                error_kind="disabled",
                error="MARITIME_WEATHER_ENABLED is false",
                duration_ms=(time.perf_counter() - started) * 1000.0,
            )

        if self._provider is None:
            telemetry.record(
                "maritime_weather_run_failed",
                source=provider_name,
                status="invalid",
                extras={"reason": "unknown_provider"},
            )
            return WeatherRunResult(
                ok=False,
                enabled=True,
                provider=provider_name,
                retrieved_at=retrieved_at,
                snapshot_id=snapshot_id,
                dataset_key=self._config.dataset_key,
                schema_version=self._config.schema_version,
                commercial_safe=False,
                source_health="invalid",
                error_kind="unknown_provider",
                error=f"unknown provider: {provider_name}",
                duration_ms=(time.perf_counter() - started) * 1000.0,
            )

        commercial_safe = _is_commercial_safe(self._provider)
        if self._config.commercial_check and not commercial_safe:
            telemetry.record(
                "maritime_weather_run_blocked_commercial_unsafe",
                source=provider_name,
                status="blocked",
                extras={
                    "license": getattr(self._provider, "openmeteo_config", None)
                    and self._provider.openmeteo_config.license,
                },
            )
            return WeatherRunResult(
                ok=False,
                enabled=True,
                provider=provider_name,
                retrieved_at=retrieved_at,
                snapshot_id=snapshot_id,
                dataset_key=self._config.dataset_key,
                schema_version=self._config.schema_version,
                commercial_safe=False,
                source_health="offline",
                error_kind="commercial_unsafe",
                error=(
                    f"provider {provider_name!r} is not commercial-safe; "
                    "set MARITIME_WEATHER_REQUIRE_COMMERCIAL_SAFE=0 to override "
                    "explicitly."
                ),
                duration_ms=(time.perf_counter() - started) * 1000.0,
            )

        # Fetch weather for each configured sample location.
        counters = RejectionCounters()
        all_records: List[WeatherObservation] = []
        samples_attempted = 0
        samples_succeeded = 0
        last_error_kind: Optional[str] = None
        last_error: Optional[str] = None

        for lat, lon in self._config.samples:
            samples_attempted += 1
            try:
                fetched = self._provider.fetch_observation(
                    latitude=lat, longitude=lon
                )
            except Exception as e:  # noqa: BLE001
                counters.other_errors += 1
                last_error_kind = "provider_exception"
                last_error = repr(e)
                telemetry.record(
                    "maritime_weather_sample_failed",
                    source=provider_name,
                    status="error",
                    extras={"lat": lat, "lon": lon, "error": repr(e)},
                )
                continue
            if not fetched:
                counters.records_rejected += 1
                last_error_kind = "no_data"
                continue
            samples_succeeded += 1
            for obs in fetched:
                counters.records_seen += 1
                # Dedup by record_id (forecast slots are unique per
                # (source, dataset, lat, lon, valid_at)).
                if any(r.record_id == obs.record_id for r in all_records):
                    counters.duplicates += 1
                    continue
                all_records.append(obs)
                counters.records_accepted += 1

        ok = samples_succeeded > 0 and counters.records_accepted > 0
        quality = compute_quality_score(
            counters, avg_record_quality=_avg_quality(all_records)
        )
        source_health = _compute_health(
            ok=ok, counters=counters, quality=quality
        )

        # Build a deterministic list for snapshotting.
        snapshot_payload: List[Dict[str, Any]] = []
        for obs in all_records:
            try:
                snapshot_payload.append(obs.to_dict())
            except (ValueError, TypeError):
                counters.records_rejected += 1
                continue

        observed_start = min(
            (r.valid_at for r in all_records), default=retrieved_at
        )
        observed_end = max(
            (r.valid_at for r in all_records), default=retrieved_at
        )
        prov = build_provenance(
            source=provider_name,
            dataset=self._config.dataset_key,
            dataset_version=self._config.schema_version,
            retrieved_at=retrieved_at,
            observed_period={"start": observed_start, "end": observed_end},
            license_str=getattr(self._provider, "_config", None)
            and self._provider._config.license or "unresolved",
            attribution=getattr(self._provider, "_config", None)
            and self._provider._config.attribution or "",
            extras={
                "samples_attempted": samples_attempted,
                "samples_succeeded": samples_succeeded,
                "commercial_safe": commercial_safe,
            },
        )

        freshness = compute_freshness(
            retrieved_at,
            is_historical=False,
            stale_after_seconds=(
                self._provider._config.max_age_seconds
                if self._provider is not None else 3600
            ),
        )
        is_stale = bool(getattr(freshness, "is_stale", False))
        if not ok:
            freshness_state = "offline"
        elif is_stale:
            freshness_state = "stale"
        elif quality < 0.5:
            freshness_state = "degraded"
        else:
            freshness_state = "available"

        manifest_doc = {
            "snapshot_id": snapshot_id,
            "dataset_key": self._config.dataset_key,
            "schema_version": self._config.schema_version,
            "retrieved_at": retrieved_at,
            "provider": provider_name,
            "provider_source": str(getattr(self._provider, "source", provider_name)),
            "commercial_safe": commercial_safe,
            "source_health": source_health,
            "freshness_state": freshness_state,
            "quality": round(quality, 3),
            "provenance": prov,
            "counters": {
                "records_seen": counters.records_seen,
                "records_accepted": counters.records_accepted,
                "records_rejected": counters.records_rejected,
                "duplicates": counters.duplicates,
                "other_errors": counters.other_errors,
            },
        }

        snapshot_root = Path(self._config.snapshot_base)
        records_path = (
            snapshot_root
            / self._config.dataset_key
            / snapshot_id
            / "weather_observations.jsonl"
        )
        manifest_path_obj = records_path.parent / "manifest.json"
        metadata_path_obj = records_path.parent / "metadata.json"

        snapshot_path: Optional[str] = None
        manifest_path: Optional[str] = None
        checksum_records: Optional[str] = None
        if ok:
            try:
                snapshot_root.mkdir(parents=True, exist_ok=True)
                publication = publish_jsonl(records_path, snapshot_payload)
                snapshot_path = str(records_path)
                checksum_records = publication.sha256
            except Exception as e:  # noqa: BLE001
                ok = False
                source_health = "offline"
                last_error_kind = "snapshot_publish_failed"
                last_error = repr(e)
        if ok:
            try:
                pub_manifest = publish_json(manifest_path_obj, manifest_doc)
                manifest_path = str(manifest_path_obj)
            except Exception as e:  # noqa: BLE001
                ok = False
                source_health = "offline"
                last_error_kind = "manifest_publish_failed"
                last_error = repr(e)
        if ok:
            try:
                metadata_doc = dict(manifest_doc)
                metadata_doc["records_path"] = str(
                    records_path.relative_to(snapshot_root)
                )
                metadata_doc["checksum_records"] = checksum_records or ""
                metadata_doc["checksum"] = checksum_records or ""
                publish_json(metadata_path_obj, metadata_doc)
            except Exception as e:  # noqa: BLE001
                # Metadata is non-fatal; log and continue.
                last_error_kind = "metadata_publish_failed"
                last_error = repr(e)

        telemetry.record(
            "maritime_weather_run_completed",
            source=provider_name,
            status="ok" if ok else "degraded",
            records_seen=counters.records_seen,
            records_accepted=counters.records_accepted,
            records_rejected=counters.records_rejected,
            quality_score=round(quality, 3),
            snapshot_id=snapshot_id,
            extras={
                "samples_attempted": samples_attempted,
                "samples_succeeded": samples_succeeded,
                "source_health": source_health,
                "commercial_safe": commercial_safe,
            },
        )

        return WeatherRunResult(
            ok=ok,
            enabled=True,
            provider=provider_name,
            retrieved_at=retrieved_at,
            snapshot_id=snapshot_id,
            dataset_key=self._config.dataset_key,
            schema_version=self._config.schema_version,
            commercial_safe=commercial_safe,
            source_health=source_health,
            records_seen=counters.records_seen,
            records_accepted=counters.records_accepted,
            records_rejected=counters.records_rejected,
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
            error_kind=last_error_kind,
            error=last_error,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            samples_attempted=samples_attempted,
            samples_succeeded=samples_succeeded,
            quality=quality,
            freshness_state=freshness_state,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_provider(self, name: str) -> Any:
        """Load a provider class by name.

        The provider classes live in :mod:`maritime.weather`. We
        avoid registering them in the Phase 4 registry because the
        weather layer is a separate, downstream concern.
        """
        try:
            if name == "openmeteo":
                from .openmeteo import OpenMeteoProvider
                return OpenMeteoProvider()
            if name == "noaa_nws":
                from .noaa_nws import NoaaNwsProvider
                return NoaaNwsProvider()
        except Exception as e:  # noqa: BLE001
            telemetry.record(
                "maritime_weather_provider_load_failed",
                source=name,
                status="error",
                extras={"error": repr(e)},
            )
            return None
        return None


def _avg_quality(records: Sequence[WeatherObservation]) -> Optional[float]:
    if not records:
        return None
    vals = [r.quality for r in records if isinstance(r.quality, (int, float))]
    if not vals:
        return None
    return sum(vals) / float(len(vals))


__all__ = [
    "WeatherOrchestrator",
    "WeatherOrchestratorConfig",
    "WeatherRunResult",
    "WEATHER_DATASET_KEY",
    "WEATHER_SCHEMA_VERSION",
    "DEFAULT_GLOBAL_SAMPLES",
]
