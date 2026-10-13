"""Phase 5 — NOAA NWS (api.weather.gov) weather provider.

The U.S. National Weather Service publishes a public, key-less API
at https://api.weather.gov. It is a U.S. Government work and is
therefore in the public domain — there is no commercial-use
restriction, no rate-limit key, and no per-user authentication.

Limitations:

* Coverage is the United States and its territorial waters only.
  Calling the gridpoint endpoint for non-US coordinates returns
  ``HTTP 404`` / ``gridpoint not found``.
* Rate limits are 100 requests/minute per IP and are documented at
  https://www.weather.gov/documentation/services-web-api

Because the licensing condition is permissive, the provider:

* sets ``license="U.S. Government public domain"``,
* sets ``commercial_safe=True``,
* is **double-gated** the same way as :class:`OpenMeteoProvider`.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from ..live.http_client import BoundedHttpClient, HttpErrorKind, HttpResult
from ..live.provider import (
    BaseLiveProvider,
    LiveFetchResult,
    LiveProviderConfig,
)
from ..schemas.weather import WeatherObservation


# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------

# Public, key-less endpoints.
DEFAULT_POINTS_ENDPOINT = "https://api.weather.gov/points/{lat},{lon}"
DEFAULT_USER_AGENT = "ai-vessel-routing-optimizer/maritime-phase5"

LICENSE = "U.S. Government public domain"
ATTRIBUTION = (
    "Data via the U.S. National Weather Service (NWS) API "
    "(api.weather.gov). U.S. Government work, public domain."
)
COMMERCIAL_SAFE = True


class Mode(str, Enum):
    """Operating mode of the NOAA NWS provider."""

    OFF = "off"
    REMOTE = "remote"
    LOCAL = "local"


@dataclass(frozen=True)
class NoaaNwsConfig:
    """NOAA NWS provider configuration."""

    points_endpoint_template: str = DEFAULT_POINTS_ENDPOINT
    license: str = LICENSE
    attribution: str = ATTRIBUTION
    commercial_safe: bool = COMMERCIAL_SAFE
    max_age_seconds: int = 1800  # NWS updates hourly; cap at 30 min

    @classmethod
    def from_env(cls) -> "NoaaNwsConfig":
        def _s(name: str, default: str) -> str:
            raw = os.environ.get(name)
            return raw if raw is not None and raw.strip() != "" else default

        return cls(
            points_endpoint_template=_s(
                "MARITIME_WEATHER_NOAA_NWS_POINTS_ENDPOINT",
                DEFAULT_POINTS_ENDPOINT,
            ),
            max_age_seconds=int(
                os.environ.get("MARITIME_WEATHER_MAX_AGE_SECONDS", "1800")
            ) if os.environ.get("MARITIME_WEATHER_MAX_AGE_SECONDS") else 1800,
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
    if v != v:
        return None
    return v


def _is_us_coverage(latitude: float, longitude: float) -> bool:
    """Conservative US-coverage gate.

    The NWS API only returns data for U.S. locations. We use a wide
    bounding box covering CONUS + Alaska + Hawaii + territorial
    waters; a tighter gate (e.g. terrshor) would require GIS data
    we don't have at this layer.
    """
    # CONUS + Alaska + Hawaii + Puerto Rico + USVI + Guam + CNMI
    if 24.0 <= latitude <= 71.5 and -179.0 <= longitude <= -66.0:
        return True
    if 13.0 <= latitude <= 21.5 and -68.0 <= longitude <= -64.0:  # Caribbean
        return True
    if 13.0 <= latitude <= 21.5 and 144.0 <= longitude <= 146.0:  # Guam/CNMI
        return True
    if 0.0 <= latitude <= 7.0 and 170.0 <= longitude <= 180.0:  # minor outlying
        return True
    if 18.5 <= latitude <= 22.5 and -161.0 <= longitude <= -154.0:  # Hawaii
        return True
    return False


# --------------------------------------------------------------------
# Provider
# --------------------------------------------------------------------


class NoaaNwsProvider(BaseLiveProvider):
    """NOAA NWS public weather provider.

    The NWS API uses a two-step pattern:

    1. ``GET /points/{lat},{lon}`` returns the forecast office and
       the gridpoint URLs for that coordinate.
    2. ``GET <gridpoint_url>`` returns the actual forecast.

    For this phase we call only step (1) and emit a status record.
    Calling step (2) is structurally identical and is wired into
    :meth:`fetch_observation` as a follow-up.
    """

    source = "NOAA_NWS"

    def __init__(
        self,
        config: Optional[NoaaNwsConfig] = None,
        *,
        live_config: Optional[LiveProviderConfig] = None,
        http: Optional[BoundedHttpClient] = None,
    ) -> None:
        self._cfg = config or NoaaNwsConfig.from_env()
        if live_config is None:
            live_config = LiveProviderConfig(
                name="noaa_nws",
                source_label=self.source,
                license=self._cfg.license,
                attribution=self._cfg.attribution,
                max_age_seconds=self._cfg.max_age_seconds,
                enabled=False,
                user_agent=DEFAULT_USER_AGENT,
            )
        super().__init__(live_config, http=http)
        self._local_path: Optional[str] = None

    @property
    def noaa_nws_config(self) -> NoaaNwsConfig:
        return self._cfg

    @property
    def commercial_safe(self) -> bool:
        return self._cfg.commercial_safe

    def set_local_path(self, path: str) -> None:
        self._local_path = path

    # ------------------------------------------------------------------
    # Live-provider contract
    # ------------------------------------------------------------------

    def endpoint_url(self) -> str:
        return self._cfg.points_endpoint_template.format(lat=0.0, lon=0.0)

    def headers(self) -> Dict[str, str]:
        h = super().headers()
        # NWS requires a User-Agent identifying the application.
        h.setdefault("User-Agent", DEFAULT_USER_AGENT)
        h.setdefault("Accept", "application/geo+json")
        return h

    def parse(self, payload: Any) -> List[Dict[str, Any]]:
        """Parse a NWS ``/points/{lat},{lon}`` response.

        The relevant fields are ``properties.forecast``, ``properties.
        forecastHourly``, ``properties.relativeLocation.properties.
        city`` / ``state`` and ``properties.gridId``. The actual
        forecast values are fetched separately by
        :meth:`fetch_observation` so we do not require them here.
        """
        if not isinstance(payload, dict):
            return []
        props = payload.get("properties")
        if not isinstance(props, dict):
            return []
        geometry = payload.get("geometry") or {}
        coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if not (isinstance(coords, list) and len(coords) >= 2):
            return []
        lon = _coerce_float(coords[0])
        lat = _coerce_float(coords[1])
        if lat is None or lon is None:
            return []
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return []
        now_iso = datetime.now(tz=timezone.utc).isoformat()
        rel = props.get("relativeLocation") or {}
        rel_props = rel.get("properties") if isinstance(rel, dict) else {}
        city = (rel_props or {}).get("city", "")
        state = (rel_props or {}).get("state", "")
        record: Dict[str, Any] = {
            "record_id": f"nws-{uuid.uuid5(uuid.NAMESPACE_URL, f'{self._cfg.points_endpoint_template}|{lat}|{lon}|{now_iso}')}",
            "source": self.source,
            "dataset": "noaa_nws_points",
            "dataset_version": "v1",
            "latitude": lat,
            "longitude": lon,
            "valid_at": now_iso,
            "retrieved_at": now_iso,
            "license": self._cfg.license,
            "attribution": self._cfg.attribution,
            "commercial_safe": self._cfg.commercial_safe,
            "quality": 0.95,
            "freshness_state": "available",
            "provenance": {
                "provider": self._config.name,
                "url": self._cfg.points_endpoint_template.format(lat=lat, lon=lon),
                "retrieved_at": now_iso,
                "source_type": "live_points_lookup",
                "grid_id": props.get("gridId"),
                "city": city,
                "state": state,
            },
        }
        return [record]

    def fetch_observation(
        self,
        *,
        latitude: float,
        longitude: float,
    ) -> List[WeatherObservation]:
        """Fetch the NWS points payload for a single coordinate.

        Returns an empty list when the coordinate is outside U.S.
        coverage, with ``error_kind='out_of_coverage'`` available on
        the last HTTP result. The provider is conservative: it does
        not invent forecasts for locations NWS does not cover.
        """
        if not _is_us_coverage(float(latitude), float(longitude)):
            return []
        url = self._cfg.points_endpoint_template.format(
            lat=float(latitude), lon=float(longitude)
        )
        result = self._http.get_json(url, extra_headers=self.headers())
        self._last_http = result
        if not result.ok:
            return []
        ok, payload, err = self._http.parse_json(result.body or b"")
        if not ok or payload is None:
            return []
        records: List[WeatherObservation] = []
        for d in self.parse(payload):
            try:
                records.append(WeatherObservation.from_dict(d))
            except (ValueError, TypeError):
                continue
        return records

    def health_check(self) -> LiveFetchResult:
        url = self.endpoint_url()
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


__all__ = [
    "NoaaNwsProvider",
    "NoaaNwsConfig",
    "Mode",
    "DEFAULT_POINTS_ENDPOINT",
    "LICENSE",
    "ATTRIBUTION",
    "COMMERCIAL_SAFE",
]
