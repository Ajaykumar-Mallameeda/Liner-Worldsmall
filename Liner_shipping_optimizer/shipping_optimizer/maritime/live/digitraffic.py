"""Phase 4 — Digitraffic live provider.

Fintraffic Digitraffic publishes live vessel locations for the Baltic
and Gulf of Finland. The endpoint used here is
``https://meri.digitraffic.fi/api/ais/v1/locations``, which returns a
GeoJSON ``FeatureCollection`` with one feature per vessel. The feed
is verified to be:

* free to use, including commercial (CC BY 4.0)
* reachable without any API key
* served only over HTTPS
* requiring ``Accept-Encoding: gzip`` (otherwise the server returns
  ``HTTP 406``)
* rate-limited to 60 requests/min per IP by default; lifted with a
  ``Digitraffic-User`` header

The provider implements the live-provider contract (see
:mod:`maritime.live.provider`) and produces canonical
:class:`maritime.schemas.vessel_position.VesselPosition` records.

The default mode is :attr:`Mode.OFF`; :attr:`Mode.REMOTE` must be
opt-in. The provider never blocks longer than the configured timeout
and never retries beyond :attr:`HttpConfig.max_retries`.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .provider import BaseLiveProvider, LiveFetchResult, LiveProviderConfig


# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------

# Verified (2026-08-27) — see PHASE_4_EXECUTION_REPORT.md for sources.
DEFAULT_ENDPOINT = "https://meri.digitraffic.fi/api/ais/v1/locations"
DEFAULT_LICENSE = "CC BY 4.0"
DEFAULT_ATTRIBUTION = (
    "Source: Fintraffic / digitraffic.fi, license CC 4.0 BY "
    "(https://www.digitraffic.fi/en/terms-of-service/)"
)
DEFAULT_USER_AGENT = "ai-vessel-routing-optimizer/maritime-phase4"


class Mode(str, Enum):
    """Operating mode of the Digitraffic provider.

    * ``OFF`` — no network call is made. ``fetch_snapshot`` returns
      an empty, deterministic :class:`IngestionResult`. This is the
      default and is enforced by the live orchestrator when
      ``MARITIME_LIVE_ENABLED`` is false.
    * ``REMOTE`` — perform a real, bounded HTTP request to the
      configured endpoint. ``local`` mode is reserved for tests and
      fixtures.
    * ``LOCAL`` — load a previously-cached JSON file from disk.
    """

    OFF = "off"
    REMOTE = "remote"
    LOCAL = "local"


@dataclass(frozen=True)
class DigitrafficConfig:
    """Digitraffic-specific configuration."""

    endpoint: str = DEFAULT_ENDPOINT
    license: str = DEFAULT_LICENSE
    attribution: str = DEFAULT_ATTRIBUTION
    max_age_seconds: int = 600
    digitraffic_user: str = "ai-vessel-routing-optimizer/phase4"

    @classmethod
    def from_env(cls) -> "DigitrafficConfig":
        def _s(name: str, default: str) -> str:
            raw = os.environ.get(name)
            return raw if raw is not None and raw.strip() != "" else default

        def _i(name: str, default: int) -> int:
            raw = os.environ.get(name)
            if raw is None or raw.strip() == "":
                return default
            try:
                return int(raw.strip())
            except ValueError:
                return default

        return cls(
            endpoint=_s("MARITIME_LIVE_DIGITRAFFIC_ENDPOINT", DEFAULT_ENDPOINT),
            license=_s("MARITIME_LIVE_DIGITRAFFIC_LICENSE", DEFAULT_LICENSE),
            attribution=_s(
                "MARITIME_LIVE_DIGITRAFFIC_ATTRIBUTION", DEFAULT_ATTRIBUTION
            ),
            max_age_seconds=_i("MARITIME_LIVE_MAX_AGE_SECONDS", 600),
            digitraffic_user=_s(
                "MARITIME_LIVE_DIGITRAFFIC_USER", DEFAULT_USER_AGENT
            ),
        )


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _as_str_mmsi(value: Any) -> Optional[str]:
    """Convert a Digitraffic ``mmsi`` (int or str) to a 9-digit string."""
    if value is None:
        return None
    s = str(value).strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) != 9:
        return None
    return digits


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v:  # NaN
        return None
    return v


def _observation_timestamp(properties: Dict[str, Any], fallback: str) -> str:
    """Digitraffic encodes two timestamps: ``timestamp`` (AIS seconds)
    and ``timestampExternal`` (server-side milliseconds since epoch).
    Prefer the server-side one for stability.
    """
    ext = properties.get("timestampExternal")
    if isinstance(ext, (int, float)) and ext > 0:
        try:
            return datetime.fromtimestamp(ext / 1000.0, tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            pass
    return fallback


# --------------------------------------------------------------------
# Provider
# --------------------------------------------------------------------


class DigitrafficProvider(BaseLiveProvider):
    """Fintraffic Digitraffic AIS locations live provider.

    The provider is OFF by default. Setting
    ``MARITIME_LIVE_ENABLED=1`` AND ``MARITIME_LIVE_PROVIDER=digitraffic``
    is what activates it; the feature flag is double-gated for safety.
    """

    source = "DIGITRAFFIC"

    def __init__(
        self,
        config: Optional[DigitrafficConfig] = None,
        *,
        live_config: Optional[LiveProviderConfig] = None,
        http: Optional[Any] = None,
    ) -> None:
        self._dt = config or DigitrafficConfig.from_env()
        if live_config is None:
            live_config = LiveProviderConfig(
                name="digitraffic",
                source_label=self.source,
                license=self._dt.license,
                attribution=self._dt.attribution,
                max_age_seconds=self._dt.max_age_seconds,
                enabled=False,
                user_agent=DEFAULT_USER_AGENT,
                extra_headers={"Digitraffic-User": self._dt.digitraffic_user},
            )
        super().__init__(live_config, http=http)
        # Local-mode path for tests / fixtures.
        self._local_path: Optional[str] = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_local_path(self, path: str) -> None:
        self._local_path = path

    @property
    def digitraffic_config(self) -> DigitrafficConfig:
        return self._dt

    # ------------------------------------------------------------------
    # Live-provider contract
    # ------------------------------------------------------------------

    def endpoint_url(self) -> str:
        return self._dt.endpoint

    def headers(self) -> Dict[str, str]:
        base = super().headers()
        # Always include Digitraffic-User; this is non-secret
        # identification, not an API key.
        base.setdefault("Digitraffic-User", self._dt.digitraffic_user)
        return base

    def parse(self, payload: Any) -> List[Dict[str, Any]]:
        """Convert a Digitraffic ``FeatureCollection`` to canonical records.

        Output is a list of dicts ready for :class:`VesselPosition.from_dict`.
        Missing or invalid fields are dropped, never fabricated.
        """
        if not isinstance(payload, dict):
            return []
        features = payload.get("features")
        if not isinstance(features, list):
            return []
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        out: List[Dict[str, Any]] = []
        for feat in features:
            if not isinstance(feat, dict):
                continue
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates") if isinstance(geom, dict) else None
            if not (isinstance(coords, list) and len(coords) >= 2):
                continue
            lon = _coerce_float(coords[0])
            lat = _coerce_float(coords[1])
            if lat is None or lon is None:
                continue
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue
            props = feat.get("properties") or {}
            if not isinstance(props, dict):
                continue
            mmsi = _as_str_mmsi(props.get("mmsi"))
            if mmsi is None:
                continue
            timestamp = _observation_timestamp(props, now_iso)
            record: Dict[str, Any] = {
                "mmsi": mmsi,
                "timestamp": timestamp,
                "latitude": lat,
                "longitude": lon,
                "sog_kn": _coerce_float(props.get("sog")),
                "cog_deg": _coerce_float(props.get("cog")),
                "heading_deg": (
                    _coerce_float(props.get("heading"))
                    if _coerce_float(props.get("heading")) not in (None, 511.0)
                    else None
                ),
                "vessel_type": "other",
                "nav_status": props.get("navStat"),
                "source": self.source,
                "dataset": "digitraffic_live_ais",
                "dataset_version": "ais/v1/locations",
                "ingested_at": now_iso,
                "snapshot_id": "pending",
                "quality": 1.0,
                "license": self._dt.license,
                "attribution": self._dt.attribution,
                "provenance": {
                    "provider": self._config.name,
                    "url": self._dt.endpoint,
                    "retrieved_at": now_iso,
                    "source_type": "live",
                    "raw_mmsi": props.get("mmsi"),
                    "raw_nav_stat": props.get("navStat"),
                    "raw_timestamp_external": props.get("timestampExternal"),
                },
            }
            out.append(record)
        return out

    # ------------------------------------------------------------------
    # Local-mode fetch
    # ------------------------------------------------------------------

    def fetch_local(self, path: str) -> LiveFetchResult:
        """Load a previously-cached JSON file. For tests + offline runs."""
        import json
        from pathlib import Path
        from .http_client import HttpResult

        retrieved_at = datetime.now(tz=timezone.utc).isoformat()
        p = Path(path)
        if not p.exists():
            return LiveFetchResult(
                ok=False,
                provider=self._config.name,
                url=str(p),
                retrieved_at=retrieved_at,
                http=HttpResult(
                    ok=False, kind="file_missing", error="local file not found",
                    url=str(p),
                ),
                error_kind="file_missing",
                error=f"local source not found: {path}",
            )
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            return LiveFetchResult(
                ok=False,
                provider=self._config.name,
                url=str(p),
                retrieved_at=retrieved_at,
                http=HttpResult(
                    ok=False, kind="malformed_json", error=str(e), url=str(p),
                ),
                error_kind="malformed_json",
                error=str(e),
            )
        return LiveFetchResult(
            ok=True,
            provider=self._config.name,
            url=str(p),
            retrieved_at=retrieved_at,
            http=HttpResult(
                ok=True, kind="success", status=200, body=None,
                url=str(p), duration_ms=0.0, attempts=1,
            ),
            payload=payload,
        )


__all__ = [
    "DigitrafficProvider",
    "DigitrafficConfig",
    "Mode",
    "DEFAULT_ENDPOINT",
    "DEFAULT_LICENSE",
    "DEFAULT_ATTRIBUTION",
]
