"""Phase 4 — Deterministic token-bucket rate limiter.

A simple, stdlib-only rate limiter. The bucket is a per-key state dict
holding ``(tokens, last_refill_at)``. ``acquire(key)`` returns ``True``
when the request is allowed under the configured rate and ``False``
when it is not — it never sleeps, never blocks, and never raises.

The limiter is thread-safe. It has no I/O, no globals, and no
dependency on the optimizer.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass(frozen=True)
class RateLimitConfig:
    """Rate-limiter configuration.

    ``rate_per_minute`` is the steady-state allowance; ``burst`` is the
    initial token capacity. Both are tunable.
    """

    rate_per_minute: float = 60.0
    burst: float = 1.0

    @classmethod
    def from_env(cls) -> "RateLimitConfig":
        import os

        def _f(name: str, default: float) -> float:
            raw = os.environ.get(name)
            if raw is None or raw.strip() == "":
                return default
            try:
                return float(raw.strip())
            except ValueError:
                return default

        return cls(
            rate_per_fm=_f("MARITIME_LIVE_RATE_PER_MINUTE", 60.0),
            burst=_f("MARITIME_LIVE_RATE_BURST", 1.0),
        ) if False else cls(  # explicit constructor for clarity
            rate_per_minute=_f("MARITIME_LIVE_RATE_PER_MINUTE", 60.0),
            burst=_f("MARITIME_LIVE_RATE_BURST", 1.0),
        )


class TokenBucket:
    """A single key's token bucket (not thread-safe on its own)."""

    __slots__ = ("tokens", "last_refill_at", "rate_per_second", "burst")

    def __init__(self, rate_per_minute: float, burst: float) -> None:
        self.rate_per_second = max(0.0, rate_per_minute) / 60.0
        self.burst = max(1.0, burst)
        self.tokens: float = self.burst
        self.last_refill_at: float = time.monotonic()

    def refill(self, now: float) -> None:
        elapsed = max(0.0, now - self.last_refill_at)
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate_per_second)
        self.last_refill_at = now

    def try_acquire(self, now: float) -> bool:
        self.refill(now)
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimiter:
    """Thread-safe rate limiter keyed by an arbitrary string.

    ``acquire(key)`` is non-blocking: it returns ``True`` if the request
    is allowed right now and ``False`` otherwise. Callers should treat
    ``False`` as a rate-limit signal and respect the configured policy
    (e.g. exponential backoff or 429 reporting).
    """

    def __init__(self, config: Optional[RateLimitConfig] = None) -> None:
        self._cfg = config or RateLimitConfig()
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    @property
    def config(self) -> RateLimitConfig:
        return self._cfg

    def acquire(self, key: str, *, now: Optional[float] = None) -> bool:
        t = now if now is not None else time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket(self._cfg.rate_per_minute, self._cfg.burst)
                self._buckets[key] = bucket
            return bucket.try_acquire(t)

    def snapshot(self) -> Dict[str, Tuple[float, float]]:
        """Inspect bucket state (for tests + dashboards)."""
        with self._lock:
            now = time.monotonic()
            return {k: (b.tokens, b.last_refill_at) for k, b in self._buckets.items()}

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()
