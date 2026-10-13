"""NOAA MarineCadastre historical AIS adapter.

NOAA MarineCadastre publishes bulk daily/monthly zips of historical US
AIS-derived vessel positions. License: CC0 (verified from
``catalog.data.gov`` / MarineCadastre). The corpus is large (multi-GB
per day in CSV form, zstd from 2025) and **out of scope** for this
project to ingest at scale; the adapter exists so that small curated
JSONL subsets can be loaded deterministically, just like the EMODnet
fixture.

The adapter accepts two layouts:

* JSONL  — one canonical vessel-position dict per line. The simplest
  fixture format; used for tests and demos.
* JSON   — ``{"records": [...]}`` envelope (same shape as the EMODnet
  fixture, for symmetry with ``BaseIngestionProvider.load_local``).

For both layouts, fields are interpreted as follows (with sensible
default fallbacks):

    MMSI / mmsi           -> mmsi
    BaseDateTime / ts / timestamp -> timestamp (ISO-8601 UTC)
    LAT / lat / latitude  -> latitude
    LON / lon / longitude -> longitude
    SOG / sog / sog_kn    -> sog_kn
    COG / cog / cog_deg   -> cog_deg
    Heading / heading     -> heading_deg
    VesselType / vessel_type / type -> vessel_type
    NavigationalStatus / nav_status -> nav_status

The adapter never makes a network call; it is purely a deterministic
loader, just like the EMODnet local-mode provider. The maritime
ingestion boundary is the only place that may make HTTP calls, and
the NOAA remote ingestion layer (not built in Phase 2) would live in
its own module to keep the provider tightly scoped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .base import BaseIngestionProvider, IngestionError, IngestionResult


# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------


@dataclass
class NoaaConfig:
    """NOAA MarineCadastre configuration.

    Defaults match the verified CC0 catalog entry; ``mode=local`` is
    the only supported mode for Phase 2 because raw NOAA archives are
    out of scope for this project. ``remote_url`` is reserved for a
    later phase and not exercised in tests.
    """

    dataset: str = "marinecadastre_ais"
    dataset_version: str = "2024.01"
    source_url: str = (
        "https://marinecadastre.gov/data/"
        "AIS/AIS_2024_01_Zone10.zip"
    )
    mode: str = "local"
    local_path: Optional[str] = None
    license: str = "CC0"
    attribution: str = (
        "NOAA MarineCadastre, AIS data (synthetic fixture for "
        "AI Vessel Routing System maritime intelligence layer)"
    )
    timeout_seconds: float = 30.0
    user_agent: str = "ai-vessel-routing-optimizer/maritime-phase2"

    def is_remote(self) -> bool:
        return self.mode.lower() == "remote"


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _first(d: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def _coerce_float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v:  # NaN
        return None
    return v


# --------------------------------------------------------------------
# Provider
# --------------------------------------------------------------------


class NoaaProvider(BaseIngestionProvider):
    """NOAA MarineCadastre AIS adapter (Phase 2: local-mode only)."""

    source = "MARINE_CADASTRE"

    def __init__(self, config: Optional[NoaaConfig] = None, *, timeout_seconds: Optional[float] = None) -> None:
        cfg = config or NoaaConfig()
        super().__init__(timeout_seconds=timeout_seconds if timeout_seconds is not None else cfg.timeout_seconds)
        self._config = cfg

    @property
    def config(self) -> NoaaConfig:
        return self._config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self) -> IngestionResult:
        """Load the configured NOAA local source.

        Local sources are JSONL or JSON; the format is auto-detected.
        Raises :class:`IngestionError` on missing file, bad format, or
        no records.
        """
        if self._config.is_remote():
            raise IngestionError(
                "NOAA remote ingestion is out of scope for Phase 2; "
                "use mode='local' with a curated fixture."
            )
        if not self._config.local_path:
            raise IngestionError(
                "NOAA provider is in LOCAL mode but no local_path is configured"
            )
        return self._fetch_local(self._config.local_path)

    def load_local(self, path: str) -> IngestionResult:  # type: ignore[override]
        return self._fetch_local(path)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fetch_local(self, path: str) -> IngestionResult:
        p = Path(path)
        if not p.exists():
            raise IngestionError(f"NOAA local source not found: {path}")
        # Detect JSONL vs JSON by the file extension / first non-blank char.
        records, envelope = self._read_file(p)
        if not records:
            raise IngestionError("NOAA local source has no records")
        period = self._extract_period(envelope, records)
        license_str = (
            envelope.get("license", self._config.license)
            if isinstance(envelope, dict) else self._config.license
        )
        attribution = (
            envelope.get("attribution", self._config.attribution)
            if isinstance(envelope, dict) else self._config.attribution
        )
        return IngestionResult(
            source=self.source,
            dataset=envelope.get("dataset", self._config.dataset)
                    if isinstance(envelope, dict) else self._config.dataset,
            dataset_version=envelope.get("dataset_version", self._config.dataset_version)
                            if isinstance(envelope, dict) else self._config.dataset_version,
            records=records,
            license=str(license_str) if license_str else "unresolved",
            attribution=str(attribution) if attribution else "",
            retrieved_at=envelope.get(
                "retrieved_at", datetime.now(tz=timezone.utc).isoformat()
            ) if isinstance(envelope, dict) else datetime.now(tz=timezone.utc).isoformat(),
            observed_period=period,
            source_url=str(path),
            notes="local-fixture",
        )

    def _read_file(self, p: Path) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Read the fixture file. Returns ``(records, envelope)``."""
        suffix = p.suffix.lower()
        text = p.read_text(encoding="utf-8")
        if suffix == ".jsonl":
            records = [self._normalize_line(json.loads(line))
                       for line in text.splitlines() if line.strip()]
            return records, {}
        # Default: JSON envelope.
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise IngestionError(f"NOAA local source is not valid JSON: {e}") from e
        if isinstance(data, list):
            return [self._normalize_line(r) for r in data if isinstance(r, dict)], {}
        if isinstance(data, dict):
            raw = data.get("records") or data.get("positions") or data.get("data") or []
            return [self._normalize_line(r) for r in raw if isinstance(r, dict)], data
        raise IngestionError("NOAA local source must be JSONL or a JSON object")

    def _normalize_line(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Map NOAA field names to the canonical vessel-position schema.

        Output is always a dict with the canonical keys (mmsi,
        timestamp, latitude, longitude, ...). Missing fields are left
        as ``None``; the schema layer rejects bad values downstream.
        """
        out: Dict[str, Any] = {}
        out["mmsi"] = _first(raw, "MMSI", "mmsi")
        ts = _first(
            raw,
            "BaseDateTime", "TIMESTAMP", "timestamp", "ts", "datetime", "observation_time",
        )
        out["timestamp"] = ts
        out["latitude"] = _first(raw, "LAT", "lat", "latitude")
        out["longitude"] = _first(raw, "LON", "lon", "longitude")
        out["sog_kn"] = _coerce_float_or_none(_first(raw, "SOG", "sog", "sog_kn", "SOG_kn"))
        out["cog_deg"] = _coerce_float_or_none(_first(raw, "COG", "cog", "cog_deg", "COG_deg"))
        out["heading_deg"] = _coerce_float_or_none(
            _first(raw, "Heading", "heading", "heading_deg", "TrueHeading")
        )
        out["vessel_type"] = _first(raw, "VesselType", "vessel_type", "type", "ship_type")
        out["nav_status"] = _first(raw, "NavigationalStatus", "nav_status", "NavStatus")
        # Provenance defaults filled in by the caller / downstream.
        out["source"] = _first(raw, "source", self.source, default=self.source)
        out["dataset"] = _first(raw, "dataset", default=self._config.dataset)
        out["dataset_version"] = _first(raw, "dataset_version", default=self._config.dataset_version)
        out["snapshot_id"] = _first(raw, "snapshot_id", default="pending")
        out["license"] = _first(raw, "license", default=self._config.license)
        out["attribution"] = _first(raw, "attribution", default=self._config.attribution)
        out["quality"] = _first(raw, "quality", default=1.0)
        # Pass through any extra fields unchanged.
        for k, v in raw.items():
            if k not in out:
                out.setdefault("extra", {})[k] = v
        return out

    @staticmethod
    def _extract_period(
        envelope: Any, records: Iterable[Dict[str, Any]]
    ) -> Dict[str, str]:
        if isinstance(envelope, dict):
            period = envelope.get("observed_period")
            if isinstance(period, dict) and "start" in period and "end" in period:
                return {"start": str(period["start"]), "end": str(period["end"])}
        timestamps = [r.get("timestamp") for r in records if r.get("timestamp")]
        if timestamps:
            ts_sorted = sorted(t for t in timestamps if isinstance(t, str))
            if ts_sorted:
                return {"start": ts_sorted[0], "end": ts_sorted[-1]}
        now = datetime.now(tz=timezone.utc).isoformat()
        return {"start": now, "end": now}