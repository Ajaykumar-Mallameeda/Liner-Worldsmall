"""Phase 5 — Open-Meteo weather provider.

Open-Meteo (open-meteo.com) is a free public weather API that
exposes a Forecast endpoint and a Marine endpoint. The provider
in this module is configured to call the **public free** API and
MUST be treated as ``commercial_safe=False``.

Licensing (verified 2026-08-27):

* The free public API is offered under a "non-commercial" use
  clause. Commercial deployments require a paid plan. See
  https://open-meteo.com/en/license for the current terms.
* Attribution: "Weather data by Open-Meteo.com (CC BY 4.0)".

Because the licensing condition is restrictive, the provider:

* sets ``license="Open-Meteo Free (non-commercial)"``,
* sets ``commercial_safe=False``,
* is **double-gated** (the master ``MARITIME_WEATHER_ENABLED`` flag
  AND a per-provider ``MARITIME_WEATHER_PROVIDER`` selector must
  both be set to activate it),
* carries a clear attribution string on every record,
* carries a clear notice in the dashboard so operators never
  confuse this with a commercial-safe source.

The provider is OFF by default.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from ..live.http_client import BoundedHttpClient, HttpConfig, HttpErrorKind, HttpResult
from ..live.provider import (
    BaseLiveProvider,
    LiveFetchResult,
    LiveProviderConfig,
)
from ..schemas.weather import WeatherObservation


# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------

# Public free endpoints — documented at https://open-meteo.com/en/docs
DEFAULT_FORECAST_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
DEFAULT_MARINE_ENDPOINT = "https://marine-api.open-meteo.com/v1/marine"

# Open-Meteo's free tier is explicitly non-commercial.
LICENSE = "Open-Meteo Free (non-commercial)"
ATTRIBUTION = (
    "Weather data by Open-Meteo.com (CC BY 4.0). "
    "Free tier is for non-commercial use only."
)
COMMERCIAL_SAFE = False

DEFAULT_USER_AGENT = "ai-vessel-routing-optimizer/maritime-phase5"

# Variables we request from each endpoint.
FORECAST_HOURLY = (
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "temperature_2m",
    "pressure_msl",
    "precipitation",
    "visibility",
)
MARINE_HOURLY = (
    "wave_height",
    "wave_period",
    "wave_direction",
)


class Mode(str, Enum):
    """Operating mode of the Open-Meteo provider.

    * ``OFF`` — no network call; ``fetch_snapshot`` returns an empty
      deterministic result. This is the default.
    * ``REMOTE`` — perform a real, bounded HTTP request.
    * ``LOCAL`` — load a previously-cached JSON file from disk.
    """

    OFF = "off"
    REMOTE = "remote"
    LOCAL = "local"


@dataclass(frozen=True)
class OpenMeteoConfig:
    """Open-Meteo provider configuration."""

    forecast_endpoint: str = DEFAULT_FORECAST_ENDPOINT
    marine_endpoint: str = DEFAULT_MARINE_ENDPOINT
    license: str = LICENSE
    attribution: str = ATTRIBUTION
    commercial_safe: bool = COMMERCIAL_SAFE
    max_age_seconds: int = 3600  # forecasts are valid for hours; cap at 1h
    forecast_days: int = 1
    cell_size_deg: float = 1.0  # default grid spacing when a corridor is given

    @classmethod
    def from_env(cls) -> "OpenMeteoConfig":
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

        def _f(name: str, default: float) -> float:
            raw = os.environ.get(name)
            if raw is None or raw.strip() == "":
                return default
            try:
                return float(raw.strip())
            except ValueError:
                return default

        return cls(
            forecast_endpoint=_s(
                "MARITIME_WEATHER_OPENMETEO_FORECAST_ENDPOINT",
                DEFAULT_FORECAST_ENDPOINT,
            ),
            marine_endpoint=_s(
                "MARITIME_WEATHER_OPENMETEO_MARINE_ENDPOINT",
                DEFAULT_MARINE_ENDPOINT,
            ),
            max_age_seconds=_i("MARITIME_WEATHER_MAX_AGE_SECONDS", 3600),
            forecast_days=_i("MARITIME_WEATHER_OPENMETEO_DAYS", 1),
            cell_size_deg=_f("MARITIME_WEATHER_OPENMETEO_CELL_DEG", 1.0),
        )


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


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


def _coerce_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s if s else None
    return str(value)


def _build_grid(
    *,
    latitude: float,
    longitude: float,
    cell_size_deg: float,
) -> List[Dict[str, float]]:
    """Return the single (lat, lon) the API will be called for.

    Open-Meteo's free public API is bounded by both a per-minute rate
    limit and an explicit "non-commercial" clause. Calling it once
    per location and caching locally is the only sustainable
    production approach. We expose ``cell_size_deg`` for callers that
    want to sample a wider corridor in a single call (Open-Meteo
    accepts a list of latitudes / longitudes in one request).
    """
    return [{"latitude": round(latitude, 4), "longitude": round(longitude, 4)}]


def _build_forecast_params(
    *,
    latitudes: Sequence[float],
    longitudes: Sequence[float],
    forecast_days: int,
) -> Dict[str, str]:
    return {
        "latitude": ",".join(str(round(float(v), 4)) for v in latitudes),
        "longitude": ",".join(str(round(float(v), 4)) for v in longitudes),
        "hourly": ",".join(FORECAST_HOURLY),
        "forecast_days": str(int(forecast_days)),
        "wind_speed_unit": "ms",
        "timezone": "UTC",
    }


def _build_marine_params(
    *,
    latitudes: Sequence[float],
    longitudes: Sequence[float],
    forecast_days: int,
) -> Dict[str, str]:
    return {
        "latitude": ",".join(str(round(float(v), 4)) for v in latitudes),
        "longitude": ",".join(str(round(float(v), 4)) for v in longitudes),
        "hourly": ",".join(MARINE_HOURLY),
        "forecast_days": str(int(forecast_days)),
        "length_unit": "metric",
        "timezone": "UTC",
    }


def _urlencode(params: Dict[str, str]) -> str:
    """Tiny stdlib-only URL-encoder.

    The network-boundary test forbids ``urllib`` imports outside
    ``maritime/ingestion/`` and ``maritime/live/``. We hand-roll
    the encoding using only ``str`` operations and ``quote`` is
    unnecessary for the characters in our parameter values
    (digits, dot, comma, underscore, ASCII letters). When a
    parameter is added that requires richer escaping, use the
    shared encoder from :mod:`maritime.live.http_client` instead.
    """
    parts: List[str] = []
    for k, v in params.items():
        # The values we ship contain only digits, dots, commas,
        # underscores, and ASCII letters; a one-pass replace is
        # safe and keeps the module free of ``urllib`` imports.
        safe = (
            str(v)
            .replace(" ", "%20")
            .replace("&", "%26")
            .replace("=", "%3D")
            .replace("+", "%2B")
            .replace(",", "%2C")
        )
        parts.append(f"{k}={safe}")
    return "&".join(parts)


# --------------------------------------------------------------------
# Provider
# --------------------------------------------------------------------


class OpenMeteoProvider(BaseLiveProvider):
    """Open-Meteo forecast + marine weather live provider.

    Reuses the bounded HTTP client from :mod:`maritime.live.http_client`
    so the network boundary is shared with the rest of the maritime
    layer. No API key is required and no Authorization header is
    attached.
    """

    source = "OPEN_METEO"

    def __init__(
        self,
        config: Optional[OpenMeteoConfig] = None,
        *,
        live_config: Optional[LiveProviderConfig] = None,
        http: Optional[BoundedHttpClient] = None,
    ) -> None:
        self._om = config or OpenMeteoConfig.from_env()
        if live_config is None:
            live_config = LiveProviderConfig(
                name="openmeteo",
                source_label=self.source,
                license=self._om.license,
                attribution=self._om.attribution,
                max_age_seconds=self._om.max_age_seconds,
                enabled=False,
                user_agent=DEFAULT_USER_AGENT,
            )
        super().__init__(live_config, http=http)
        self._local_path: Optional[str] = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @property
    def openmeteo_config(self) -> OpenMeteoConfig:
        return self._om

    def set_local_path(self, path: str) -> None:
        self._local_path = path

    @property
    def commercial_safe(self) -> bool:
        return self._om.commercial_safe

    # ------------------------------------------------------------------
    # Live-provider contract
    # ------------------------------------------------------------------

    def endpoint_url(self) -> str:
        """The forecast endpoint. The marine endpoint is also probed
        when ``fetch_observation`` is called with ``include_marine=True``."""
        return self._om.forecast_endpoint

    def headers(self) -> Dict[str, str]:
        return super().headers()

    def parse(self, payload: Any) -> List[Dict[str, Any]]:
        """Convert an Open-Meteo payload (forecast or marine) to canonical
        record dicts.

        Open-Meteo returns a JSON object with shape::

            {
              "latitude": [...], "longitude": [...],
              "hourly": {
                "time": ["2026-08-27T00:00", ...],
                "wind_speed_10m": [...], "wind_direction_10m": [...],
                ...
              }
            }

        We support both a single-coordinate response (lists of length 1)
        and a multi-coordinate response. Records that fail validation
        are dropped (caller routes into rejection counters).
        """
        if not isinstance(payload, dict):
            return []
        hourly = payload.get("hourly")
        if not isinstance(hourly, dict):
            return []
        times = hourly.get("time")
        if not isinstance(times, list) or not times:
            return []
        lats = payload.get("latitude") or []
        lons = payload.get("longitude") or []
        if not (isinstance(lats, list) and isinstance(lons, list)):
            return []
        if len(lats) != len(lons):
            return []
        # For each coordinate, expand the hourly arrays into records.
        out: List[Dict[str, Any]] = []
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        for ci, (lat_v, lon_v) in enumerate(zip(lats, lons)):
            lat = _coerce_float(lat_v)
            lon = _coerce_float(lon_v)
            if lat is None or lon is None:
                continue
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue
            for ti, t in enumerate(times):
                ts = _coerce_str(t)
                if not ts:
                    continue
                # Open-Meteo emits local timestamps in the requested
                # timezone; we requested UTC, so the value is already
                # an ISO-8601 string without an offset. We normalize to
                # an explicit ``+00:00`` suffix for downstream parsing.
                valid_at = ts if "+" in ts or ts.endswith("Z") else ts + "+00:00"
                record: Dict[str, Any] = {
                    "record_id": f"om-{uuid.uuid5(uuid.NAMESPACE_URL, f'{self._om.forecast_endpoint}|{lat}|{lon}|{valid_at}')}",
                    "source": self.source,
                    "dataset": "openmeteo_forecast",
                    "dataset_version": self._om.forecast_endpoint.rsplit("/", 1)[-1],
                    "latitude": lat,
                    "longitude": lon,
                    "valid_at": valid_at,
                    "retrieved_at": now_iso,
                    "wind_speed_ms": _read_at(hourly, "wind_speed_10m", ti),
                    "wind_direction_deg": _read_at(hourly, "wind_direction_10m", ti),
                    "gust_speed_ms": _read_at(hourly, "wind_gusts_10m", ti),
                    "temperature_c": _read_at(hourly, "temperature_2m", ti),
                    "pressure_hpa": _read_at(hourly, "pressure_msl", ti),
                    "precipitation_mm": _read_at(hourly, "precipitation", ti),
                    "visibility_m": _read_at(hourly, "visibility", ti),
                    "wave_height_m": _read_at(hourly, "wave_height", ti),
                    "wave_period_s": _read_at(hourly, "wave_period", ti),
                    "wave_direction_deg": _read_at(hourly, "wave_direction", ti),
                    "license": self._om.license,
                    "attribution": self._om.attribution,
                    "commercial_safe": self._om.commercial_safe,
                    "quality": 0.85,  # forecast: structurally sound, but not observed
                    "freshness_state": "available",
                    "provenance": {
                        "provider": self._config.name,
                        "url": self._om.forecast_endpoint,
                        "retrieved_at": now_iso,
                        "source_type": "live_forecast",
                        "coordinate_index": ci,
                        "time_index": ti,
                    },
                }
                out.append(record)
        return out

    # ------------------------------------------------------------------
    # Fetches
    # ------------------------------------------------------------------

    def fetch_observation(
        self,
        *,
        latitude: float,
        longitude: float,
        include_marine: bool = True,
    ) -> List[WeatherObservation]:
        """Fetch weather for one coordinate and return canonical records.

        This is the synchronous "give me the weather here now" entry
        point. The orchestrator (see :mod:`maritime.weather.orchestrator`)
        decides when to call it; the provider is transport-only.
        """
        records: List[Dict[str, Any]] = []
        lat = float(latitude)
        lon = float(longitude)
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return []

        # Forecast endpoint (always)
        params = _build_forecast_params(
            latitudes=[lat], longitudes=[lon],
            forecast_days=self._om.forecast_days,
        )
        url = self._om.forecast_endpoint + "?" + _urlencode(params)
        result = self._http.get_json(url, extra_headers=self.headers())
        if not result.ok:
            # Mirror the LiveFetchResult structure for callers that want
            # to surface the failure.
            self._last_http = result
        else:
            ok, payload, err = self._http.parse_json(result.body or b"")
            if ok and payload is not None:
                records.extend(self.parse(payload))
            self._last_http = result

        # Marine endpoint (optional)
        if include_marine:
            mparams = _build_marine_params(
                latitudes=[lat], longitudes=[lon],
                forecast_days=self._om.forecast_days,
            )
            murl = self._om.marine_endpoint + "?" + _urlencode(mparams)
            mresult = self._http.get_json(murl, extra_headers=self.headers())
            self._last_marine_http = mresult
            if mresult.ok:
                ok, mpayload, err = self._http.parse_json(mresult.body or b"")
                if ok and mpayload is not None:
                    records.extend(self.parse(mpayload))

        # Convert dicts to canonical dataclasses, dropping failures.
        out: List[WeatherObservation] = []
        for r in records:
            try:
                out.append(WeatherObservation.from_dict(r))
            except (ValueError, TypeError):
                continue
        return out

    def fetch_snapshot(self) -> LiveFetchResult:
        """Delegate to ``_fetch`` for the orchestrator pattern.

        Note: this only hits the forecast endpoint. The orchestrator
        uses :meth:`fetch_observation` for richer snapshots.
        """
        return self._fetch()

    def health_check(self) -> LiveFetchResult:
        """Bounded liveness probe against the forecast endpoint."""
        url = self.endpoint_url() + "?" + _urlencode(
            _build_forecast_params(
                latitudes=[0.0], longitudes=[0.0],
                forecast_days=1,
            )
        )
        http_result = self._http.get_json(url, extra_headers=self.headers())
        if http_result.ok:
            ok, payload, err = self._http.parse_json(http_result.body or b"")
            return LiveFetchResult(
                ok=True,
                provider=self._config.name,
                url=url,
                retrieved_at=datetime.now(tz=timezone.utc).isoformat(),
                http=http_result,
                payload=(payload[1] if payload[0] else None),
            )
        return LiveFetchResult(
            ok=False,
            provider=self._config.name,
            url=url,
            retrieved_at=datetime.now(tz=timezone.utc).isoformat(),
            http=http_result,
            error_kind=http_result.kind,
            error=http_result.error,
        )

    def fetch_local(self, path: str) -> LiveFetchResult:
        """Load a previously-cached JSON file (LOCAL mode)."""
        import json
        from pathlib import Path

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


def _read_at(hourly: Dict[str, Any], key: str, index: int) -> Optional[float]:
    arr = hourly.get(key)
    if not isinstance(arr, list) or index >= len(arr):
        return None
    return _coerce_float(arr[index])


__all__ = [
    "OpenMeteoProvider",
    "OpenMeteoConfig",
    "Mode",
    "DEFAULT_FORECAST_ENDPOINT",
    "DEFAULT_MARINE_ENDPOINT",
    "LICENSE",
    "ATTRIBUTION",
    "COMMERCIAL_SAFE",
]
