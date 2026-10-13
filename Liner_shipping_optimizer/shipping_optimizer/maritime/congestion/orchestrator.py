"""Phase 6 — Congestion orchestrator.

The orchestrator is the single entry point that produces congestion
records. It does so by:

1. Reading already-materialized local snapshots from the
   existing maritime layers (Phases 1–5).
2. Assembling a :class:`CongestionSignals` object per
   geographic entity.
3. Running :func:`maritime.congestion.model.evaluate_congestion`
   to produce a bounded, explainable score.
4. Publishing the resulting records to an immutable local
   snapshot via :mod:`maritime.snapshot_publisher`.

The orchestrator NEVER opens a network connection. It is a
read-only aggregator over local snapshots, plus a writer to the
local snapshot store. It is double-gated by
``MARITIME_CONGESTION_ENABLED`` and is OFF by default.

It also has a ``synthesize_demo`` mode that produces a small
deterministic set of records from bundled synthetic fixtures.
This is the safe-empty default when no upstream data is
available; the resulting records carry ``synthetic=True`` so the
dashboard can label them clearly.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .. import telemetry
from ..schemas.congestion import CongestionRecord
from ..snapshot_publisher import PublicationResult, publish_json, publish_jsonl
from ..storage.snapshots import DEFAULT_SNAPSHOT_BASE, generate_snapshot_id
from .model import (
    CongestionModelConfig,
    CongestionSignals,
    build_record,
)


# --------------------------------------------------------------------
# Dataset key + version
# --------------------------------------------------------------------


CONGESTION_DATASET_KEY = "maritime_congestion"
CONGESTION_SCHEMA_VERSION = "1.0.0"
CONGESTION_RECORDS_FILENAME = "congestion_records.jsonl"
CONGESTION_COMPUTATION_VERSION = "1.0.0"


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


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class CongestionOrchestratorConfig:
    """Orchestrator configuration."""

    enabled: bool = False
    snapshot_base: str = DEFAULT_SNAPSHOT_BASE
    dataset_key: str = CONGESTION_DATASET_KEY
    schema_version: str = CONGESTION_SCHEMA_VERSION
    synthetic_when_empty: bool = True
    max_age_seconds: int = 7 * 24 * 3600
    model_config: CongestionModelConfig = field(
        default_factory=CongestionModelConfig
    )

    @classmethod
    def from_env(cls) -> "CongestionOrchestratorConfig":
        try:
            max_age = int(os.environ.get(
                "MARITIME_CONGESTION_MAX_AGE_SECONDS", str(7 * 24 * 3600)
            ))
        except (TypeError, ValueError):
            max_age = 7 * 24 * 3600
        return cls(
            enabled=_env_bool("MARITIME_CONGESTION_ENABLED", False),
            snapshot_base=_env_str(
                "MARITIME_CONGESTION_SNAPSHOT_BASE", DEFAULT_SNAPSHOT_BASE
            ),
            synthetic_when_empty=_env_bool(
                "MARITIME_CONGESTION_SYNTHETIC_WHEN_EMPTY", True
            ),
            max_age_seconds=max_age,
            model_config=CongestionModelConfig.from_env(),
        )


# --------------------------------------------------------------------
# Result type
# --------------------------------------------------------------------


@dataclass(frozen=True)
class CongestionRunResult:
    """Outcome of a single orchestrator run. Never raises."""

    ok: bool
    enabled: bool
    dataset_key: str
    schema_version: str
    snapshot_id: str
    retrieved_at: str
    source_health: str
    freshness_state: str
    quality: float
    records_seen: int = 0
    records_accepted: int = 0
    records_rejected: int = 0
    snapshot_path: Optional[str] = None
    manifest_path: Optional[str] = None
    error_kind: Optional[str] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    synthetic: bool = False
    inputs_used: tuple = ()
    inputs_missing: tuple = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "enabled": self.enabled,
            "dataset_key": self.dataset_key,
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "retrieved_at": self.retrieved_at,
            "source_health": self.source_health,
            "freshness_state": self.freshness_state,
            "quality": round(self.quality, 3),
            "records_seen": self.records_seen,
            "records_accepted": self.records_accepted,
            "records_rejected": self.records_rejected,
            "snapshot_path": self.snapshot_path,
            "manifest_path": self.manifest_path,
            "error_kind": self.error_kind,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 3),
            "synthetic": self.synthetic,
            "inputs_used": list(self.inputs_used),
            "inputs_missing": list(self.inputs_missing),
        }


# --------------------------------------------------------------------
# Local snapshot readers
# --------------------------------------------------------------------


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


def _read_meta(snapshot_root: Path, dataset_key: str) -> Optional[Dict[str, Any]]:
    base = snapshot_root / dataset_key
    if not base.is_dir():
        return None
    children = sorted(
        [c for c in base.iterdir() if c.is_dir() and (c / "metadata.json").exists()],
        key=lambda p: p.name,
    )
    if not children:
        return None
    try:
        return json.loads((children[-1] / "metadata.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _read_manifest(snapshot_root: Path, dataset_key: str,
                   snapshot_id: str) -> Optional[Dict[str, Any]]:
    p = snapshot_root / dataset_key / snapshot_id / "manifest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _collect_inputs(snapshot_root: Path) -> Dict[str, Dict[str, Any]]:
    """Discover available local snapshots (read-only)."""
    inputs: Dict[str, Dict[str, Any]] = {}
    candidates = {
        "traffic": "emodnet_vessel_density",
        "port": "noaa_ais_port_intelligence",
        "live": "digitraffic_live_vessel_positions",
        "weather": "maritime_weather_observations",
    }
    for label, key in candidates.items():
        meta = _read_meta(snapshot_root, key)
        if meta is not None:
            snap_id = meta.get("snapshot_id")
            inputs[label] = {
                "meta": meta,
                "snapshot_id": snap_id,
                "records": [],
            }
            if snap_id:
                base = snapshot_root / key / snap_id
                # The records file name differs by phase. Try a small
                # well-known set.
                for fname in (
                    "traffic_density.jsonl",
                    "vessel_positions.jsonl",
                    "weather_observations.jsonl",
                ):
                    p = base / fname
                    if p.exists():
                        inputs[label]["records"] = _read_jsonl(p)
                        inputs[label]["records_filename"] = fname
                        break
                manifest = _read_manifest(snapshot_root, key, snap_id)
                if manifest is not None:
                    inputs[label]["manifest"] = manifest
        else:
            inputs[label] = None
    return inputs


# --------------------------------------------------------------------
# Signal assembly from local snapshots
# --------------------------------------------------------------------


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# A small grid of canonical locations. When the orchestrator cannot
# find any port entities, it falls back to these so the dashboard
# always has something to render — with the synthetic flag set.
DEFAULT_SYNTHETIC_LOCATIONS: List[Tuple[str, float, float]] = [
    ("norfolk",   36.85, -76.29),
    ("rotterdam", 51.95,   4.14),
    ("shanghai",  31.20, 121.50),
    ("santos",   -23.95, -46.33),
    ("hamburg",   53.55,   9.99),
]


def _nearest_traffic(
    inputs: Mapping[str, Any], lat: float, lon: float, radius_km: float = 150.0
) -> Tuple[List[Dict[str, Any]], Optional[float]]:
    if not inputs or not inputs.get("traffic"):
        return [], None
    records = inputs["traffic"].get("records") or []
    picked: List[Dict[str, Any]] = []
    for r in records:
        rlat = r.get("latitude")
        rlon = r.get("longitude")
        if not (isinstance(rlat, (int, float)) and isinstance(rlon, (int, float))):
            continue
        d = _haversine_km(lat, lon, float(rlat), float(rlon))
        if d <= radius_km:
            picked.append(r)
    avg_intensity: Optional[float] = None
    if picked:
        vals: List[float] = []
        for r in picked:
            intensity = r.get("normalized_intensity")
            if intensity is None:
                intensity = r.get("intensity")
            if isinstance(intensity, (int, float)):
                vals.append(float(intensity))
        if vals:
            # Normalize: treat max=1.0 over this slice.
            mx = max(vals)
            if mx > 0:
                avg_intensity = sum(min(1.0, v / mx) for v in vals) / len(vals)
    return picked, avg_intensity


def _nearest_port_calls(
    inputs: Mapping[str, Any], lat: float, lon: float, radius_km: float = 60.0
) -> Tuple[int, Optional[float], Optional[float]]:
    if not inputs or not inputs.get("port"):
        return 0, None, None
    records = inputs["port"].get("records") or []
    nearby = 0
    util_vals: List[float] = []
    dwell_vals: List[float] = []
    # First: the port_calls.jsonl (if present)
    for r in records:
        if r.get("record_type") and r.get("record_type") != "port_call":
            continue
        plat = r.get("port_latitude")
        plon = r.get("port_longitude")
        if not (isinstance(plat, (int, float)) and isinstance(plon, (int, float))):
            continue
        d = _haversine_km(lat, lon, float(plat), float(plon))
        if d <= radius_km:
            nearby += 1
            u = r.get("utilization_proxy")
            if isinstance(u, (int, float)):
                util_vals.append(float(u))
            dwell = r.get("average_dwell_hours")
            if isinstance(dwell, (int, float)):
                dwell_vals.append(float(dwell))
    if nearby == 0:
        return 0, None, None
    util = sum(util_vals) / len(util_vals) if util_vals else None
    dwell = sum(dwell_vals) / len(dwell_vals) if dwell_vals else None
    return nearby, util, dwell


def _nearest_weather(
    inputs: Mapping[str, Any], lat: float, lon: float, radius_km: float = 250.0
) -> Tuple[Optional[Dict[str, Any]], bool]:
    if not inputs or not inputs.get("weather"):
        return None, False
    records = inputs["weather"].get("records") or []
    best: Optional[Tuple[float, Dict[str, Any]]] = None
    for r in records:
        rlat = r.get("latitude")
        rlon = r.get("longitude")
        if not (isinstance(rlat, (int, float)) and isinstance(rlon, (int, float))):
            continue
        d = _haversine_km(lat, lon, float(rlat), float(rlon))
        if d <= radius_km:
            if best is None or d < best[0]:
                best = (d, r)
    if best is None:
        return None, False
    return best[1], True


def _weather_risk_from_observation(obs: Mapping[str, Any]) -> float:
    """Convert a single weather observation into a bounded risk factor in [0, 1].

    The risk is computed from wind, gust, and wave height. Pure
    clear-sky conditions yield ~0.0; storm conditions yield ~1.0.
    The mapping is documented and deterministic.
    """
    if not isinstance(obs, Mapping):
        return 0.0
    parts: List[float] = []
    wind = obs.get("wind_speed_ms")
    if isinstance(wind, (int, float)):
        # Reference: 18 m/s ~ gale-force, 25 m/s ~ storm
        parts.append(min(1.0, max(0.0, float(wind) / 25.0)))
    gust = obs.get("gust_speed_ms")
    if isinstance(gust, (int, float)):
        parts.append(min(1.0, max(0.0, float(gust) / 35.0)))
    wave = obs.get("wave_height_m")
    if isinstance(wave, (int, float)):
        parts.append(min(1.0, max(0.0, float(wave) / 6.0)))
    if not parts:
        return 0.0
    return min(1.0, sum(parts) / len(parts))


# --------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------


class CongestionOrchestrator:
    """The bounded entry point for congestion intelligence."""

    def __init__(self, config: Optional[CongestionOrchestratorConfig] = None,
                 *, snapshot_root: Optional[Path] = None) -> None:
        self._config = config or CongestionOrchestratorConfig.from_env()
        self._snapshot_root = (
            Path(snapshot_root) if snapshot_root is not None
            else Path(self._config.snapshot_base)
        )

    @property
    def config(self) -> CongestionOrchestratorConfig:
        return self._config

    def run(self) -> CongestionRunResult:
        started = time.perf_counter()
        retrieved_at = datetime.now(tz=timezone.utc).isoformat()
        snapshot_id = generate_snapshot_id(dataset=self._config.dataset_key)
        dataset_key = self._config.dataset_key
        schema_version = self._config.schema_version

        if not self._config.enabled:
            telemetry.record(
                "maritime_congestion_run_skipped",
                source="derived",
                status="disabled",
                extras={"reason": "MARITIME_CONGESTION_ENABLED is false"},
            )
            return CongestionRunResult(
                ok=False,
                enabled=False,
                dataset_key=dataset_key,
                schema_version=schema_version,
                snapshot_id=snapshot_id,
                retrieved_at=retrieved_at,
                source_health="offline",
                freshness_state="unknown",
                quality=0.0,
                error_kind="disabled",
                error="MARITIME_CONGESTION_ENABLED is false",
                duration_ms=(time.perf_counter() - started) * 1000.0,
            )

        # Discover local inputs (read-only).
        inputs = _collect_inputs(self._snapshot_root)
        inputs_present = tuple(k for k, v in inputs.items() if v)
        inputs_missing = tuple(k for k, v in inputs.items() if not v)

        # Build entity list:
        # 1) Use the port snapshot's port definitions when available
        #    (they carry coordinates and IDs).
        # 2) Otherwise fall back to the synthetic grid.
        entities: List[Tuple[str, float, float, bool]] = []  # (id, lat, lon, is_synthetic)
        port_meta = (inputs.get("port") or {}).get("meta") if inputs.get("port") else None
        port_manifest = (inputs.get("port") or {}).get("manifest") if inputs.get("port") else None
        if port_manifest is not None:
            for p in port_manifest.get("ports", []) or []:
                pid = p.get("port_id")
                plat = p.get("latitude")
                plon = p.get("longitude")
                if (
                    isinstance(pid, str) and pid.strip() != ""
                    and isinstance(plat, (int, float))
                    and isinstance(plon, (int, float))
                ):
                    entities.append((pid, float(plat), float(plon), False))
        if not entities and self._config.synthetic_when_empty:
            for name, lat, lon in DEFAULT_SYNTHETIC_LOCATIONS:
                entities.append((name, lat, lon, True))

        if not entities:
            telemetry.record(
                "maritime_congestion_run_skipped",
                source="derived",
                status="no_entities",
                extras={"reason": "no port entities and synthetic disabled"},
            )
            return CongestionRunResult(
                ok=False,
                enabled=True,
                dataset_key=dataset_key,
                schema_version=schema_version,
                snapshot_id=snapshot_id,
                retrieved_at=retrieved_at,
                source_health="offline",
                freshness_state="offline",
                quality=0.0,
                error_kind="no_entities",
                error="no port entities available",
                duration_ms=(time.perf_counter() - started) * 1000.0,
                synthetic=False,
                inputs_used=inputs_present,
                inputs_missing=inputs_missing,
            )

        # For each entity: gather signals → evaluate → build record.
        all_records: List[CongestionRecord] = []
        records_rejected = 0
        # Aggregate quality inputs (used for source-health rollup)
        quality_inputs: List[float] = []
        freshness_inputs: List[str] = []

        for entity_id, lat, lon, is_synthetic in entities:
            # Traffic
            traffic_records, traffic_density = _nearest_traffic(inputs, lat, lon)
            cargo_density: Optional[float] = None
            tanker_density: Optional[float] = None
            passenger_density: Optional[float] = None
            if traffic_records:
                # Split by vessel_class when present
                buckets: Dict[str, List[float]] = {}
                for r in traffic_records:
                    cls = str(r.get("vessel_class", "other")).lower()
                    intensity = r.get("normalized_intensity")
                    if intensity is None:
                        intensity = r.get("intensity")
                    if isinstance(intensity, (int, float)):
                        buckets.setdefault(cls, []).append(float(intensity))
                if buckets:
                    mx = max(
                        (max(v) for v in buckets.values() if v),
                        default=1.0,
                    ) or 1.0
                    for cls, vals in buckets.items():
                        avg = sum(vals) / len(vals)
                        normalized = min(1.0, avg / mx)
                        if cls in ("cargo",):
                            cargo_density = normalized
                        elif cls in ("tanker",):
                            tanker_density = normalized
                        elif cls in ("passenger",):
                            passenger_density = normalized

            # Port
            call_count, utilization, dwell = _nearest_port_calls(inputs, lat, lon)

            # Weather
            weather_obs, weather_available = _nearest_weather(inputs, lat, lon)
            weather_risk = (
                _weather_risk_from_observation(weather_obs)
                if weather_available else None
            )
            weather_quality: Optional[float] = None
            if weather_available and isinstance(weather_obs, Mapping):
                q = weather_obs.get("quality")
                if isinstance(q, (int, float)):
                    weather_quality = float(q)

            # Roll up source quality + freshness from inputs that fed us.
            source_quality = 0.0
            source_count = 0
            freshness_state = "unknown"
            for label, info in inputs.items():
                if not info:
                    continue
                meta = info.get("meta") or {}
                q = meta.get("quality_score")
                if q is None:
                    q = meta.get("completeness_ratio")
                if isinstance(q, (int, float)):
                    source_quality += float(q)
                    source_count += 1
                fs = meta.get("freshness_state") or meta.get("source_status")
                if isinstance(fs, str) and fs:
                    freshness_inputs.append(fs)
            if source_count > 0:
                source_quality = source_quality / source_count
            else:
                source_quality = 0.5
            # Determine freshness from inputs
            if freshness_inputs:
                # Worst wins (so a stale weather record ages the whole picture)
                ranking = {
                    "available": 0, "checking": 1, "degraded": 2,
                    "stale": 3, "offline": 4, "invalid": 4, "unknown": 1,
                }
                freshness_state = max(
                    freshness_inputs, key=lambda s: ranking.get(s, 1)
                )
            else:
                freshness_state = "unknown"

            observed_at = retrieved_at
            prov: Dict[str, Any] = {
                "computation_version": CONGESTION_COMPUTATION_VERSION,
                "schema_version": schema_version,
                "inputs_present": list(inputs_present),
                "inputs_missing": list(inputs_missing),
            }
            if is_synthetic:
                prov["synthetic_label"] = "synthetic"
            signals = CongestionSignals(
                entity_type="port",
                latitude=lat,
                longitude=lon,
                observed_at=observed_at,
                traffic_density=traffic_density,
                cargo_density=cargo_density,
                tanker_density=tanker_density,
                passenger_density=passenger_density,
                port_call_count=call_count,
                utilization_proxy=utilization,
                average_dwell_hours=dwell,
                arrival_rate_per_day=(
                    (float(call_count) / 7.0) if call_count else None
                ),
                weather_available=weather_available,
                weather_quality=weather_quality,
                weather_risk_factor=weather_risk,
                source_quality=source_quality,
                freshness_state=freshness_state,
                source="derived",
                dataset_version=schema_version,
                license="derived",
                attribution=(
                    "Derived from EMODnet, NOAA MarineCadastre, NOAA NWS, "
                    "and Digitraffic (see provenance chain)."
                ),
                commercial_safe=True,  # derived: no upstream license
                provenance=prov,
                synthetic=is_synthetic,
            )
            try:
                rec = build_record(
                    signals,
                    config=self._config.model_config,
                    entity_id=entity_id,
                )
            except (ValueError, TypeError) as e:
                records_rejected += 1
                telemetry.record(
                    "maritime_congestion_sample_rejected",
                    source="derived",
                    status="error",
                    extras={"entity_id": entity_id, "error": repr(e)},
                )
                continue
            all_records.append(rec)

        if not all_records:
            return CongestionRunResult(
                ok=False,
                enabled=True,
                dataset_key=dataset_key,
                schema_version=schema_version,
                snapshot_id=snapshot_id,
                retrieved_at=retrieved_at,
                source_health="offline",
                freshness_state=freshness_state,
                quality=0.0,
                records_rejected=records_rejected,
                error_kind="no_records_accepted",
                error="no congestion records produced",
                duration_ms=(time.perf_counter() - started) * 1000.0,
                synthetic=any(e[3] for e in entities),
                inputs_used=inputs_present,
                inputs_missing=inputs_missing,
            )

        # Aggregate quality
        avg_quality = sum(r.confidence for r in all_records) / len(all_records)
        if freshness_state in ("offline", "invalid"):
            source_health = "offline"
        elif freshness_state == "stale":
            source_health = "stale"
        elif avg_quality < 0.5:
            source_health = "degraded"
        else:
            source_health = "available"

        ok = True
        snapshot_path: Optional[str] = None
        manifest_path: Optional[str] = None
        checksum_records: Optional[str] = None
        records_path = (
            self._snapshot_root / dataset_key / snapshot_id
            / CONGESTION_RECORDS_FILENAME
        )
        manifest_path_obj = records_path.parent / "manifest.json"
        metadata_path_obj = records_path.parent / "metadata.json"

        try:
            self._snapshot_root.mkdir(parents=True, exist_ok=True)
            payload = [r.to_dict() for r in all_records]
            pub = publish_jsonl(records_path, payload)
            snapshot_path = str(records_path)
            checksum_records = pub.sha256
        except Exception as e:  # noqa: BLE001
            ok = False
            source_health = "offline"
            telemetry.record(
                "maritime_congestion_run_failed",
                source="derived",
                status="snapshot_publish_failed",
                extras={"error": repr(e)},
            )
            return CongestionRunResult(
                ok=False,
                enabled=True,
                dataset_key=dataset_key,
                schema_version=schema_version,
                snapshot_id=snapshot_id,
                retrieved_at=retrieved_at,
                source_health="offline",
                freshness_state=freshness_state,
                quality=avg_quality,
                records_seen=len(all_records) + records_rejected,
                records_accepted=0,
                records_rejected=records_rejected,
                error_kind="snapshot_publish_failed",
                error=repr(e),
                duration_ms=(time.perf_counter() - started) * 1000.0,
                synthetic=any(e[3] for e in entities),
                inputs_used=inputs_present,
                inputs_missing=inputs_missing,
            )

        manifest_doc = {
            "snapshot_id": snapshot_id,
            "dataset_key": dataset_key,
            "schema_version": schema_version,
            "computation_version": CONGESTION_COMPUTATION_VERSION,
            "retrieved_at": retrieved_at,
            "source": "derived",
            "source_health": source_health,
            "freshness_state": freshness_state,
            "quality": round(avg_quality, 3),
            "checksum_records": checksum_records or "",
            "inputs_present": list(inputs_present),
            "inputs_missing": list(inputs_missing),
            "synthetic": any(e[3] for e in entities),
            "record_count": len(all_records),
            "provenance": {
                "source": "derived",
                "dataset": dataset_key,
                "dataset_version": schema_version,
                "retrieved_at": retrieved_at,
                "license": "derived",
                "attribution": (
                    "Derived from EMODnet, NOAA MarineCadastre, NOAA NWS, "
                    "and Digitraffic (see provenance chain)."
                ),
            },
        }
        if ok:
            try:
                pub_m = publish_json(manifest_path_obj, manifest_doc)
                manifest_path = str(manifest_path_obj)
                _ = pub_m
            except Exception as e:  # noqa: BLE001
                ok = False
                source_health = "offline"
                telemetry.record(
                    "maritime_congestion_run_failed",
                    source="derived",
                    status="manifest_publish_failed",
                    extras={"error": repr(e)},
                )
        if ok:
            try:
                meta_doc = dict(manifest_doc)
                meta_doc["records_path"] = str(
                    records_path.relative_to(self._snapshot_root)
                )
                meta_doc["records_accepted"] = len(all_records)
                meta_doc["records_rejected"] = records_rejected
                publish_json(metadata_path_obj, meta_doc)
            except Exception:  # noqa: BLE001
                pass

        telemetry.record(
            "maritime_congestion_run_completed",
            source="derived",
            status="ok" if ok else "degraded",
            records_seen=len(all_records) + records_rejected,
            records_accepted=len(all_records),
            records_rejected=records_rejected,
            quality_score=round(avg_quality, 3),
            snapshot_id=snapshot_id,
            extras={
                "inputs_present": list(inputs_present),
                "inputs_missing": list(inputs_missing),
                "source_health": source_health,
            },
        )

        return CongestionRunResult(
            ok=ok,
            enabled=True,
            dataset_key=dataset_key,
            schema_version=schema_version,
            snapshot_id=snapshot_id,
            retrieved_at=retrieved_at,
            source_health=source_health,
            freshness_state=freshness_state,
            quality=avg_quality,
            records_seen=len(all_records) + records_rejected,
            records_accepted=len(all_records),
            records_rejected=records_rejected,
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            synthetic=any(e[3] for e in entities),
            inputs_used=inputs_present,
            inputs_missing=inputs_missing,
        )


__all__ = [
    "CongestionOrchestrator",
    "CongestionOrchestratorConfig",
    "CongestionRunResult",
    "CONGESTION_DATASET_KEY",
    "CONGESTION_SCHEMA_VERSION",
    "CONGESTION_RECORDS_FILENAME",
    "CONGESTION_COMPUTATION_VERSION",
]
