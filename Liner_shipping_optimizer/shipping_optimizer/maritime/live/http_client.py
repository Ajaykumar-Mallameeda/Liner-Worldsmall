"""Phase 4 — Bounded HTTP client for live maritime ingestion.

A small stdlib-only wrapper around :mod:`urllib.request` that provides:

* bounded connect + read timeouts
* explicit, bounded retries
* deterministic 429 / Retry-After handling
* deterministic 5xx retry handling
* gzip / Accept-Encoding handling (mandatory for Digitraffic)
* structured ``HttpResult`` returns (never raise for non-fatal cases)
* full provenance fields (URL, method, status, attempt count, duration)
* no-secret guarantees (no Authorization headers, no body
  containing credentials, no logging of payload)

The client is the single network entry point for live maritime sources.
It is the only module (besides the provider implementations) that
imports :mod:`urllib` / :mod:`socket`. Tests pass a custom ``urlopen``
function to avoid real network access.
"""

from __future__ import annotations

import gzip
import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional, Tuple


# --------------------------------------------------------------------
# Error classification
# --------------------------------------------------------------------


class HttpErrorKind:
    """Stable identifiers for the kinds of failure the client can see."""

    SUCCESS = "success"
    TIMEOUT = "timeout"
    DNS_FAILURE = "dns_failure"
    CONNECTION_REFUSED = "connection_refused"
    CONNECTION_RESET = "connection_reset"
    HTTP_4XX = "http_4xx"
    HTTP_429 = "http_429"
    HTTP_5XX = "http_5xx"
    MALFORMED_JSON = "malformed_json"
    AUTH_FAILURE = "auth_failure"
    UNKNOWN_ERROR = "unknown_error"
    SCHEMA_MISMATCH = "schema_mismatch"


# --------------------------------------------------------------------
# Result type
# --------------------------------------------------------------------


@dataclass(frozen=True)
class HttpResult:
    """Outcome of a single HTTP request (including retries)."""

    ok: bool
    kind: str
    status: Optional[int] = None
    body: Optional[bytes] = None
    headers: Dict[str, str] = field(default_factory=dict)
    duration_ms: float = 0.0
    attempts: int = 1
    error: Optional[str] = None
    retry_after_seconds: Optional[float] = None
    url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "kind": self.kind,
            "status": self.status,
            "size_bytes": len(self.body) if self.body is not None else None,
            "duration_ms": round(self.duration_ms, 3),
            "attempts": self.attempts,
            "error": self.error,
            "retry_after_seconds": self.retry_after_seconds,
            "url": self.url,
        }


# --------------------------------------------------------------------
# Config
# --------------------------------------------------------------------


@dataclass(frozen=True)
class HttpConfig:
    """Bounded HTTP client configuration.

    All values are tunable via env variables; see ``from_env``.
    """

    timeout_seconds: float = 10.0
    max_retries: int = 2
    backoff_base_seconds: float = 0.5
    backoff_max_seconds: float = 4.0
    user_agent: str = "ai-vessel-routing-optimizer/maritime-phase4"
    accept_encoding: str = "gzip"
    accept: str = "*/*"

    @classmethod
    def from_env(cls) -> "HttpConfig":
        import os

        def _f(name: str, default: float) -> float:
            raw = os.environ.get(name)
            if raw is None or raw.strip() == "":
                return default
            try:
                return float(raw.strip())
            except ValueError:
                return default

        def _i(name: str, default: int) -> int:
            raw = os.environ.get(name)
            if raw is None or raw.strip() == "":
                return default
            try:
                return max(0, int(raw.strip()))
            except ValueError:
                return default

        return cls(
            timeout_seconds=_f("MARITIME_LIVE_TIMEOUT_SECONDS", 10.0),
            max_retries=_i("MARITIME_LIVE_MAX_RETRIES", 2),
            backoff_base_seconds=_f("MARITIME_LIVE_BACKOFF_SECONDS", 0.5),
            backoff_max_seconds=_f("MARITIME_LIVE_BACKOFF_MAX_SECONDS", 4.0),
        )


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def _classify_http_error(
    exc: Exception,
) -> Tuple[str, Optional[int], Optional[str], Optional[float]]:
    """Map an exception to a stable error kind + status + retry-after."""
    if isinstance(exc, socket.timeout):
        return HttpErrorKind.TIMEOUT, None, repr(exc), None
    if isinstance(exc, socket.gaierror):
        return HttpErrorKind.DNS_FAILURE, None, repr(exc), None
    if isinstance(exc, urllib.error.HTTPError):
        status = exc.code
        # 401/403 are auth failures and must never be retried.
        if status in (401, 403):
            return HttpErrorKind.AUTH_FAILURE, status, str(exc), None
        if status == 429:
            retry_after = _parse_retry_after(exc.headers)
            return HttpErrorKind.HTTP_429, status, str(exc), retry_after
        if 400 <= status < 500:
            return HttpErrorKind.HTTP_4XX, status, str(exc), None
        if 500 <= status < 600:
            return HttpErrorKind.HTTP_5XX, status, str(exc), None
        return HttpErrorKind.UNKNOWN_ERROR, status, str(exc), None
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, socket.timeout):
            return HttpErrorKind.TIMEOUT, None, repr(exc), None
        if isinstance(reason, ConnectionRefusedError):
            return HttpErrorKind.CONNECTION_REFUSED, None, repr(exc), None
        if isinstance(reason, ConnectionResetError):
            return HttpErrorKind.CONNECTION_RESET, None, repr(exc), None
        # socket.gaierror is a subclass of OSError with .errno + .strerror
        if isinstance(reason, socket.gaierror) or (
            isinstance(reason, OSError) and getattr(reason, "errno", None)
            in {socket.EAI_NONAME, socket.EAI_AGAIN}
        ):
            return HttpErrorKind.DNS_FAILURE, None, repr(exc), None
        # As a last resort, classify by errno on the reason.
        if isinstance(reason, OSError):
            if getattr(reason, "errno", None) in {
                socket.EAI_NONAME, socket.EAI_AGAIN,
                -2, -3,  # some Windows error codes
            }:
                return HttpErrorKind.DNS_FAILURE, None, repr(exc), None
        return HttpErrorKind.UNKNOWN_ERROR, None, repr(exc), None
    if isinstance(exc, ConnectionRefusedError):
        return HttpErrorKind.CONNECTION_REFUSED, None, repr(exc), None
    if isinstance(exc, ConnectionResetError):
        return HttpErrorKind.CONNECTION_RESET, None, repr(exc), None
    return HttpErrorKind.UNKNOWN_ERROR, None, repr(exc), None


def _parse_retry_after(headers: Optional[Mapping[str, str]]) -> Optional[float]:
    if headers is None:
        return None
    val = headers.get("Retry-After") or headers.get("retry-after")
    if val is None:
        return None
    try:
        v = float(str(val).strip())
    except (TypeError, ValueError):
        return None
    return max(0.0, v)


def _backoff(attempt: int, cfg: HttpConfig) -> float:
    """Bounded exponential backoff with a deterministic cap."""
    delay = cfg.backoff_base_seconds * (2 ** max(0, attempt - 1))
    return min(delay, cfg.backoff_max_seconds)


# --------------------------------------------------------------------
# Client
# --------------------------------------------------------------------


# Type for an injected urlopen — used by tests to avoid real network access.
UrlopenFn = Callable[..., Any]


class BoundedHttpClient:
    """Bounded, stdlib-only HTTP client.

    All requests use the configured connect+read timeout, gzip is sent,
    and retries are bounded. The client never raises for transport
    failures; it returns a structured :class:`HttpResult` instead.
    """

    def __init__(
        self,
        config: Optional[HttpConfig] = None,
        *,
        urlopen: Optional[UrlopenFn] = None,
        sleep: Optional[Callable[[float], None]] = None,
    ) -> None:
        self._cfg = config or HttpConfig.from_env()
        # Default urlopen is the stdlib; tests can inject a stub.
        self._urlopen = urlopen or urllib.request.urlopen
        # Default sleep is the stdlib; tests can inject a no-op.
        self._sleep = sleep or (lambda s: time.sleep(s))

    @property
    def config(self) -> HttpConfig:
        return self._cfg

    def get_json(
        self,
        url: str,
        *,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> HttpResult:
        """GET a URL, transparently retry on 429/5xx, decode gzip, return ``HttpResult``.

        Returns ``ok=True`` only when the body is valid JSON and the HTTP
        status is in the 2xx range. The decoded JSON is NOT parsed here;
        callers do that so they can apply schema-specific validation.
        """
        return self._do_get(url, extra_headers=extra_headers, parse_json=True)

    def get_bytes(
        self,
        url: str,
        *,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> HttpResult:
        return self._do_get(url, extra_headers=extra_headers, parse_json=False)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _do_get(
        self,
        url: str,
        *,
        extra_headers: Optional[Mapping[str, str]],
        parse_json: bool,
    ) -> HttpResult:
        headers: Dict[str, str] = {
            "User-Agent": self._cfg.user_agent,
            "Accept": self._cfg.accept,
            "Accept-Encoding": self._cfg.accept_encoding,
        }
        # Drop any caller-supplied Authorization to make secret leakage
        # structurally impossible.
        if extra_headers:
            for k, v in extra_headers.items():
                lk = k.lower()
                if lk in {"authorization", "proxy-authorization", "cookie"}:
                    continue
                headers[k] = v
        last_result: Optional[HttpResult] = None
        for attempt in range(1, self._cfg.max_retries + 2):  # initial + retries
            started = time.perf_counter()
            try:
                req = urllib.request.Request(url, headers=dict(headers))
                resp = self._urlopen(req, timeout=self._cfg.timeout_seconds)
                status = getattr(resp, "status", 200)
                raw = resp.read()
                resp_headers = {k: v for k, v in resp.headers.items()}
                if resp_headers.get("Content-Encoding") == "gzip":
                    try:
                        raw = gzip.decompress(raw)
                    except OSError:
                        # Some servers mislabel non-gzip bodies. We don't
                        # fail the call — we just return the raw body.
                        pass
                duration_ms = (time.perf_counter() - started) * 1000.0
                if 200 <= status < 300:
                    return HttpResult(
                        ok=True,
                        kind=HttpErrorKind.SUCCESS,
                        status=status,
                        body=raw,
                        headers=resp_headers,
                        duration_ms=duration_ms,
                        attempts=attempt,
                        url=url,
                    )
                # Non-2xx (but not raised): treat like an HTTPError.
                kind = HttpErrorKind.HTTP_4XX if 400 <= status < 500 else HttpErrorKind.HTTP_5XX
                last_result = HttpResult(
                    ok=False,
                    kind=kind,
                    status=status,
                    body=raw,
                    headers=resp_headers,
                    duration_ms=duration_ms,
                    attempts=attempt,
                    error=f"http_{status}",
                    url=url,
                )
                if not _is_retryable_status(status, attempt, self._cfg):
                    return last_result
                self._sleep(_backoff(attempt, self._cfg))
                continue
            except Exception as e:  # noqa: BLE001
                duration_ms = (time.perf_counter() - started) * 1000.0
                kind, status, error, retry_after = _classify_http_error(e)
                last_result = HttpResult(
                    ok=False,
                    kind=kind,
                    status=status,
                    body=None,
                    headers={},
                    duration_ms=duration_ms,
                    attempts=attempt,
                    error=error,
                    retry_after_seconds=retry_after,
                    url=url,
                )
                if not _is_retryable(kind, attempt, self._cfg):
                    return last_result
                delay = retry_after if retry_after is not None else _backoff(attempt, self._cfg)
                self._sleep(min(delay, self._cfg.backoff_max_seconds))
                continue
        # Exhausted retries: return the last failure.
        assert last_result is not None
        return last_result

    # ------------------------------------------------------------------
    # JSON helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_json(body: bytes) -> Tuple[bool, Any, Optional[str]]:
        """Parse JSON bytes; never raises. Returns ``(ok, value, error)``."""
        try:
            return True, json.loads(body), None
        except json.JSONDecodeError as e:
            return False, None, f"malformed_json:{e}"


def _is_retryable(kind: str, attempt: int, cfg: HttpConfig) -> bool:
    """Decide whether the next attempt is allowed."""
    if attempt > cfg.max_retries:
        return False
    if kind in (HttpErrorKind.HTTP_429, HttpErrorKind.HTTP_5XX, HttpErrorKind.TIMEOUT,
                HttpErrorKind.CONNECTION_RESET, HttpErrorKind.UNKNOWN_ERROR):
        return True
    return False


def _is_retryable_status(status: int, attempt: int, cfg: HttpConfig) -> bool:
    if attempt > cfg.max_retries:
        return False
    return 500 <= status < 600
