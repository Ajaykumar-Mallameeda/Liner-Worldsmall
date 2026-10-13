"""EMODnet Human Activities — vessel-density provider.

This is the first (and only, in Phase 1) source-specific adapter. The
adapter is intentionally narrow: it downloads the configured EMODnet
product (or loads a previously-cached file) and emits a list of raw
records. License + attribution are pinned to the verified values for
EMODnet Human Activities — we do not invent them.

Modes
-----
LOCAL:    read a previously downloaded file from disk. This is the default
          and is required for tests, demos, and offline operation.
REMOTE:   fetch the configured URL with a single bounded HTTP request.

The REMOTE path uses :mod:`urllib` from the standard library only. No new
dependencies. A failure during remote fetch raises :class:`IngestionError`;
callers are expected to fall back to a cached snapshot.

We make at most one network request per call. There are no retries. The
timeout is enforced via :mod:`socket` (set before the request) so the call
cannot block indefinitely.
"""

from __future__ import annotations

import json
import socket
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import BaseIngestionProvider, IngestionError, IngestionResult


# --------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------


@dataclass
class EmodnetConfig:
    """EMODnet-specific configuration.

    The default URL is the documented EMODnet Human Activities WMS/WFS
    endpoint. We default to ``mode=LOCAL`` for safety; users opt into
    remote ingestion explicitly.
    """
    dataset: str = "vessel_density_all_ships"
    dataset_version: str = "2023"
    source_url: str = "https://ows.emodnet-humanactivities.eu/wms"
    mode: str = "local"  # one of: "local", "remote"
    local_path: Optional[str] = None
    license: str = "CC BY 4.0"
    attribution: str = (
        "EMODnet Human Activities, Vessel Density Map - All ships, "
        "https://www.emodnet-humanactivities.eu/"
    )
    timeout_seconds: float = 30.0
    user_agent: str = "ai-vessel-routing-optimizer/maritime-phase1"

    def is_remote(self) -> bool:
        return self.mode.lower() == "remote"


# --------------------------------------------------------------------
# Provider
# --------------------------------------------------------------------


class EmodnetProvider(BaseIngestionProvider):
    """EMODnet Human Activities vessel-density adapter."""

    source = "EMODNET"

    def __init__(self, config: Optional[EmodnetConfig] = None, *, timeout_seconds: Optional[float] = None) -> None:
        cfg = config or EmodnetConfig()
        super().__init__(timeout_seconds=timeout_seconds if timeout_seconds is not None else cfg.timeout_seconds)
        self._config = cfg

    @property
    def config(self) -> EmodnetConfig:
        return self._config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch(self) -> IngestionResult:
        """Fetch from EMODnet.

        - LOCAL mode: read the configured local_path, or fail.
        - REMOTE mode: one HTTP request, with timeout, no retries.

        Raises :class:`IngestionError` for unrecoverable failures.
        """
        if not self._config.is_remote():
            if not self._config.local_path:
                raise IngestionError(
                    "EMODnet provider is in LOCAL mode but no local_path is configured"
                )
            return self._fetch_local(self._config.local_path)

        return self._fetch_remote()

    def load_local(self, path: str) -> IngestionResult:  # type: ignore[override]
        """Explicit local load (always uses the given path, not config)."""
        return self._fetch_local(path)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fetch_local(self, path: str) -> IngestionResult:
        from pathlib import Path
        p = Path(path)
        if not p.exists():
            raise IngestionError(f"EMODnet local source not found: {path}")
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise IngestionError(f"EMODnet local source is not valid JSON: {e}") from e
        records = self._extract_records(raw)
        period = self._extract_period(raw)
        return IngestionResult(
            source=self.source,
            dataset=raw.get("dataset", self._config.dataset) if isinstance(raw, dict) else self._config.dataset,
            dataset_version=raw.get("dataset_version", self._config.dataset_version) if isinstance(raw, dict) else self._config.dataset_version,
            records=records,
            license=raw.get("license", self._config.license) if isinstance(raw, dict) else self._config.license,
            attribution=raw.get("attribution", self._config.attribution) if isinstance(raw, dict) else self._config.attribution,
            retrieved_at=raw.get("retrieved_at", datetime.now(tz=timezone.utc).isoformat()) if isinstance(raw, dict) else datetime.now(tz=timezone.utc).isoformat(),
            observed_period=period,
            source_url=str(path),
            notes="local-fixture",
        )

    def _fetch_remote(self) -> IngestionResult:
        url = self._config.source_url
        if not url:
            raise IngestionError("EMODnet remote source_url is empty")
        # Enforce timeout at the socket layer. Single request, no retries.
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(self.timeout_seconds)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self._config.user_agent, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                status = getattr(resp, "status", 200)
                if status >= 400:
                    raise IngestionError(f"EMODnet remote returned HTTP {status}")
                body = resp.read()
        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            raise IngestionError(f"EMODnet remote fetch failed: {e}") from e
        except IngestionError:
            raise
        finally:
            socket.setdefaulttimeout(old_timeout)
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            raise IngestionError(f"EMODnet remote body is not valid JSON: {e}") from e
        records = self._extract_records(data)
        period = self._extract_period(data)
        return IngestionResult(
            source=self.source,
            dataset=data.get("dataset", self._config.dataset) if isinstance(data, dict) else self._config.dataset,
            dataset_version=data.get("dataset_version", self._config.dataset_version) if isinstance(data, dict) else self._config.dataset_version,
            records=records,
            license=data.get("license", self._config.license) if isinstance(data, dict) else self._config.license,
            attribution=data.get("attribution", self._config.attribution) if isinstance(data, dict) else self._config.attribution,
            retrieved_at=datetime.now(tz=timezone.utc).isoformat(),
            observed_period=period,
            source_url=url,
            notes="remote-fetch",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_records(raw: Any) -> List[Dict[str, Any]]:
        if isinstance(raw, list):
            return [r for r in raw if isinstance(r, dict)]
        if isinstance(raw, dict):
            recs = raw.get("records") or raw.get("features") or raw.get("data")
            if isinstance(recs, list):
                return [r for r in recs if isinstance(r, dict)]
        return []

    @staticmethod
    def _extract_period(raw: Any) -> Dict[str, str]:
        now = datetime.now(tz=timezone.utc).isoformat()
        if isinstance(raw, dict):
            period = raw.get("observed_period")
            if isinstance(period, dict) and "start" in period and "end" in period:
                return {"start": str(period["start"]), "end": str(period["end"])}
        return {"start": now, "end": now}
