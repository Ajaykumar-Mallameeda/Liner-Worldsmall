"""Phase 4 — Live provider abstraction.

Live maritime providers share the same contract as the existing
:class:`maritime.ingestion.base.BaseIngestionProvider`, with three
additions:

* :meth:`health_check` — a fast, bounded liveness probe.
* :meth:`fetch_snapshot` — returns a :class:`LiveFetchResult` that
  carries both the raw body and the per-attempt diagnostics.
* :meth:`source_status` — the provider's own view of its health,
  independent of the snapshot store.

The provider is the single place where a live source is consumed.
It is network-capable by construction; everything outside the live
package remains network-free.
"""

from __future__ import annotations

import abc
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from ..ingestion.base import IngestionError, IngestionResult
from ..schemas.intelligence import SourceStatus
from .http_client import BoundedHttpClient, HttpConfig, HttpErrorKind, HttpResult


# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    return raw if raw is not None and raw.strip() != "" else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


# --------------------------------------------------------------------
# Provider configuration
# --------------------------------------------------------------------


@dataclass(frozen=True)
class LiveProviderConfig:
    """Common live-provider configuration."""

    name: str
    source_label: str
    license: str
    attribution: str
    max_age_seconds: int
    enabled: bool
    user_agent: str
    extra_headers: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls, *, name: str, source_label: str,
                 license_str: str, attribution: str) -> "LiveProviderConfig":
        return cls(
            name=name,
            source_label=source_label,
            license=license_str,
            attribution=attribution,
            max_age_seconds=_env_int("MARITIME_LIVE_MAX_AGE_SECONDS", 600),
            enabled=_env_bool("MARITIME_LIVE_ENABLED", False),
            user_agent=_env_str(
                "MARITIME_LIVE_USER_AGENT",
                "ai-vessel-routing-optimizer/maritime-phase4",
            ),
            extra_headers={
                k[len("MARITIME_LIVE_HEADER_"):]: v
                for k, v in os.environ.items()
                if k.startswith("MARITIME_LIVE_HEADER_")
            },
        )


# --------------------------------------------------------------------
# Fetch result
# --------------------------------------------------------------------


@dataclass(frozen=True)
class LiveFetchResult:
    """Outcome of a single live fetch attempt.

    This is the boundary between the network layer and the rest of the
    system. The body is provided as parsed JSON when ``ok`` is True.
    """

    ok: bool
    provider: str
    url: str
    retrieved_at: str
    http: HttpResult
    payload: Optional[Any] = None
    error_kind: Optional[str] = None
    error: Optional[str] = None
    freshness_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "provider": self.provider,
            "url": self.url,
            "retrieved_at": self.retrieved_at,
            "http": self.http.to_dict(),
            "payload": self.payload,
            "error_kind": self.error_kind,
            "error": self.error,
            "freshness_seconds": self.freshness_seconds,
        }


# --------------------------------------------------------------------
# Abstract base
# --------------------------------------------------------------------


class BaseLiveProvider(abc.ABC):
    """Abstract live maritime provider.

    The contract is identical in spirit to
    :class:`maritime.ingestion.base.BaseIngestionProvider`, with
    additional diagnostics and a ``health_check`` entry point.
    """

    source: str = "LIVE_ABSTRACT"

    def __init__(
        self,
        config: LiveProviderConfig,
        *,
        http: Optional[BoundedHttpClient] = None,
        http_config: Optional[HttpConfig] = None,
    ) -> None:
        self._config = config
        self._http = http or BoundedHttpClient(http_config or HttpConfig.from_env())

    @property
    def config(self) -> LiveProviderConfig:
        return self._config

    @property
    def http(self) -> BoundedHttpClient:
        return self._http

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def endpoint_url(self) -> str:
        """Return the URL the provider fetches."""

    def headers(self) -> Dict[str, str]:
        """Return the per-request headers (excluding User-Agent and Accept-Encoding)."""
        return dict(self._config.extra_headers)

    @abc.abstractmethod
    def parse(self, payload: Any) -> List[Dict[str, Any]]:
        """Convert the provider's payload to a list of normalized records.

        Normalized records follow the canonical live-vessel-position
        contract (see :mod:`maritime.live.normalizer`).
        """

    def health_check(self) -> LiveFetchResult:
        """Bounded liveness probe. Same transport path as the full fetch.

        Default implementation performs a GET of ``endpoint_url()`` and
        reports the result. Providers may override to use a cheaper
        endpoint when one exists.
        """
        http_result = self._http.get_json(self.endpoint_url(), extra_headers=self.headers())
        if http_result.ok:
            try:
                payload = self._http.parse_json(http_result.body or b"")
            except Exception:
                payload = None
            return LiveFetchResult(
                ok=True,
                provider=self._config.name,
                url=self.endpoint_url(),
                retrieved_at=datetime.now(tz=timezone.utc).isoformat(),
                http=http_result,
                payload=(payload[1] if payload[0] else None),
            )
        return LiveFetchResult(
            ok=False,
            provider=self._config.name,
            url=self.endpoint_url(),
            retrieved_at=datetime.now(tz=timezone.utc).isoformat(),
            http=http_result,
            error_kind=http_result.kind,
            error=http_result.error,
        )

    def fetch_snapshot(self) -> LiveFetchResult:
        """Fetch the live snapshot for the configured endpoint."""
        return self._fetch()

    def source_status(self) -> SourceStatus:
        """Return the provider's own source-status hint.

        The default is conservative: when health_check fails, we return
        OFFLINE; when it succeeds, we return AVAILABLE. Subclasses may
        override to factor in freshness / schema mismatches.
        """
        check = self.health_check()
        return SourceStatus.AVAILABLE if check.ok else SourceStatus.OFFLINE

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fetch(self) -> LiveFetchResult:
        url = self.endpoint_url()
        retrieved_at = datetime.now(tz=timezone.utc).isoformat()
        http_result = self._http.get_json(url, extra_headers=self.headers())
        if not http_result.ok:
            return LiveFetchResult(
                ok=False,
                provider=self._config.name,
                url=url,
                retrieved_at=retrieved_at,
                http=http_result,
                error_kind=http_result.kind,
                error=http_result.error,
            )
        ok, payload, err = self._http.parse_json(http_result.body or b"")
        if not ok:
            return LiveFetchResult(
                ok=False,
                provider=self._config.name,
                url=url,
                retrieved_at=retrieved_at,
                http=http_result,
                error_kind=HttpErrorKind.MALFORMED_JSON,
                error=err,
            )
        return LiveFetchResult(
            ok=True,
            provider=self._config.name,
            url=url,
            retrieved_at=retrieved_at,
            http=http_result,
            payload=payload,
        )


__all__ = [
    "BaseLiveProvider",
    "LiveProviderConfig",
    "LiveFetchResult",
    "HttpConfig",
    "HttpErrorKind",
    "HttpResult",
    "BoundedHttpClient",
]
