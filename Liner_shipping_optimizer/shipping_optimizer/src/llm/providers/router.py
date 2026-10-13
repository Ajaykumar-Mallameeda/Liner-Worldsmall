"""Provider router with provider-aware circuit breaker and per-error-type policy.

The router is the single point of LLM call entry.  Callers ask for a
``role`` (e.g. ``coordinator``) and the router:

  1. Walks the configured provider order.
  2. For each provider/model pair, checks the circuit breaker — if OPEN
     and the cooldown has not elapsed, skip without a network call.
  3. Calls the provider.
  4. Maps the response to a policy outcome:
        HTTP_429       -> immediate failover, open cooldown
        TIMEOUT        -> bounded retry within provider, then failover
        CONNECTION     -> bounded retry within provider, then failover
        AUTH           -> provider/model disabled for the run
        INVALID_MODEL  -> provider/model disabled, continue to next
        INVALID_JSON   -> bounded retry within provider, then failover
        SCHEMA         -> retry-with-reformulation or failover
        QUALITY        -> bounded retry, then failover
        UNKNOWN        -> bounded retry, then failover
  5. Caches successful responses by a stable hash of (model, system, user).
  6. When all providers fail, returns a hard-fallback string so the
     existing agent-level fallbacks still trigger.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .types import (
    CircuitBreakerRecord,
    CircuitState,
    ErrorType,
    LLMResponse,
)
from .registry import ProviderRegistry, default_registry
from .base import LLMProvider


logger = logging.getLogger("llm.router")


# Per-error-type policy: how many retries within a single provider before
# the router gives up on that provider and moves to the next one.
_POLICY = {
    ErrorType.HTTP_429:      {"retries_within_provider": 0, "cooldown_sec": 60.0, "open_breaker": True},
    ErrorType.TIMEOUT:       {"retries_within_provider": 1, "cooldown_sec": 30.0, "open_breaker": False},
    ErrorType.CONNECTION:    {"retries_within_provider": 1, "cooldown_sec": 30.0, "open_breaker": False},
    ErrorType.AUTH:          {"retries_within_provider": 0, "cooldown_sec": 600.0, "open_breaker": True},
    ErrorType.INVALID_MODEL: {"retries_within_provider": 0, "cooldown_sec": 600.0, "open_breaker": True},
    ErrorType.INVALID_JSON:  {"retries_within_provider": 1, "cooldown_sec": 0.0,  "open_breaker": False},
    ErrorType.SCHEMA:        {"retries_within_provider": 1, "cooldown_sec": 0.0,  "open_breaker": False},
    ErrorType.QUALITY:       {"retries_within_provider": 1, "cooldown_sec": 0.0,  "open_breaker": False},
    ErrorType.UNKNOWN:       {"retries_within_provider": 1, "cooldown_sec": 30.0, "open_breaker": False},
    ErrorType.NONE:          {"retries_within_provider": 0, "cooldown_sec": 0.0,  "open_breaker": False},
}


# Per-error-type breach threshold for opening the circuit breaker.
# The breaker opens when the failure_count reaches this many in a row
# for the same (provider, model).
_BREAKER_THRESHOLD = {
    ErrorType.HTTP_429: 2,
    ErrorType.AUTH: 1,
    ErrorType.INVALID_MODEL: 1,
    ErrorType.TIMEOUT: 3,
    ErrorType.CONNECTION: 3,
    ErrorType.INVALID_JSON: 3,
    ErrorType.SCHEMA: 3,
    ErrorType.QUALITY: 3,
    ErrorType.UNKNOWN: 3,
    ErrorType.NONE: 99,
}


# Fallback constants (kept identical to the legacy client to preserve the
# agent-level detection that wraps every call).
_HARD_FALLBACK_TEXT = "Service temporarily unavailable. Using default optimization parameters."


class ProviderRouter:
    """Routes LLM calls across providers with failover + circuit breaker.

    The router is also the cache layer so the caller's surface is identical
    to the previous ``LLMClient.chat`` method.
    """

    def __init__(
        self,
        registry: Optional[ProviderRegistry] = None,
        provider_order: Optional[List[str]] = None,
        cache_enabled: Optional[bool] = None,
        cooldown_sec: Optional[float] = None,
        deterministic_fallback: str = _HARD_FALLBACK_TEXT,
    ):
        self.registry = registry or default_registry()
        if provider_order is None:
            order_env = os.getenv("LLM_PROVIDER_ORDER", "")
            if order_env:
                provider_order = [p.strip().lower() for p in order_env.split(",") if p.strip()]
            else:
                provider_order = self.registry.all_names()
        self.provider_order: List[str] = [
            n for n in provider_order if self.registry.get(n) is not None
        ]
        # Per-(provider, model) breaker state.
        self._breakers: Dict[Tuple[str, str], CircuitBreakerRecord] = {}
        self._lock = threading.Lock()

        # Global config (overrideable per-call via .chat parameters).
        self.cache_enabled = (
            cache_enabled if cache_enabled is not None
            else os.getenv("LLM_CACHE_ENABLED", "true").lower() not in ("0", "false", "no")
        )
        self.cooldown_sec = (
            cooldown_sec if cooldown_sec is not None
            else float(os.getenv("LLM_429_COOLDOWN_SEC", "60"))
        )
        # Track whether the caller explicitly set the cooldown; the breaker
        # failure path uses this to honour explicit overrides.
        self._explicit_cooldown_sec = cooldown_sec
        self.deterministic_fallback = deterministic_fallback

        # Counters for telemetry.
        self.attempts = 0
        self.successes = 0
        self.failures = 0
        self.fallback_uses = 0
        self.cache_hits = 0
        self.provider_switches = 0
        self.circuit_breaker_events = 0
        self.error_type_counts: Dict[str, int] = {}
        self.provider_call_counts: Dict[str, int] = {}
        self.model_call_counts: Dict[str, int] = {}
        # Cache.
        self._cache: Dict[str, LLMResponse] = {}

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------
    def chat(
        self,
        role: str,
        system: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        timeout_sec: Optional[float] = None,
    ) -> LLMResponse:
        """Provider-routed LLM call.

        ``role`` resolves to a per-provider model name via the provider's
        ``ProviderConfig.model_for``.  When ``model`` is given, it is used
        verbatim (with the first available provider in the order).
        """
        if not self.provider_order:
            # No providers configured at all — return hard fallback.
            return self._hard_fallback(role=role, reason="no providers configured")

        # Build the candidate plan: [(provider, model), ...]
        plan = self._build_plan(role, model)
        if not plan:
            return self._hard_fallback(role=role, reason="no model configured for role")

        # Cache check (keyed on (model, system, user_message)).
        cache_key = self._cache_key(plan[0][1], system, user_message, temperature, max_tokens)
        if self.cache_enabled:
            cached = self._cache_lookup(cache_key)
            if cached is not None:
                self.cache_hits += 1
                # Re-annotate so the caller can tell it was a cache hit.
                out = LLMResponse(
                    content=cached.content,
                    provider=cached.provider,
                    model=cached.model,
                    status="cache_hit",
                    request_id=cached.request_id,
                    role=role,
                    cache_hit=True,
                )
                logger.info(
                    "llm_cache_hit provider=%s model=%s role=%s",
                    cached.provider, cached.model, role,
                )
                return out

        last_error_type = ErrorType.NONE
        last_error_msg = ""
        last_provider = ""
        last_model = ""
        switches_this_call = 0

        for idx, (provider_name, model_name) in enumerate(plan):
            provider = self.registry.get(provider_name)
            if provider is None:
                continue
            self.provider_call_counts[provider_name] = (
                self.provider_call_counts.get(provider_name, 0) + 1
            )
            self.model_call_counts[model_name] = (
                self.model_call_counts.get(model_name, 0) + 1
            )
            if idx > 0:
                self.provider_switches += 1
                switches_this_call += 1
                logger.info(
                    "llm_provider_switch from=%s to=%s role=%s reason=%s",
                    last_provider, provider_name, role, last_error_type.value,
                )

            # Check breaker.
            if not self._breaker_allows(provider_name, model_name):
                logger.info('llm_circuit_breaker_open | provider=%s model=%s role=%s', provider_name, model_name, role)
                self.circuit_breaker_events += 1
                last_error_type = ErrorType.HTTP_429
                last_error_msg = "circuit_breaker_open"
                last_provider, last_model = provider_name, model_name
                continue

            # Call (with bounded retry inside the provider, per the policy).
            policy = dict(_POLICY[ErrorType.HTTP_429])  # default
            attempts = 0
            response: Optional[LLMResponse] = None
            while attempts <= self._max_retries_within(provider_name, model_name):
                self.attempts += 1
                attempts += 1
                response = provider.chat(
                    model=model_name,
                    system=system,
                    user_message=user_message,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout_sec=timeout_sec,
                )
                if response.status == "ok" and response.error_type == ErrorType.NONE:
                    # Success.
                    self.successes += 1
                    self._breaker_success(provider_name, model_name)
                    if idx > 0:
                        self.fallback_uses += 1
                    response.role = role
                    # Cache.
                    if self.cache_enabled:
                        self._cache_store(cache_key, response)
                    return response

                # Failure path.
                err_t = response.error_type
                self.failures += 1
                self.error_type_counts[err_t.value] = self.error_type_counts.get(err_t.value, 0) + 1
                self._breaker_failure(provider_name, model_name, err_t)
                last_error_type = err_t
                last_error_msg = response.error_message
                last_provider, last_model = provider_name, model_name

                if not self._should_retry_within(err_t, attempts, provider_name, model_name):
                    break
                # Bounded retry inside provider.
                time.sleep(0.1)

            # Provider gave us a non-ok response; the loop continues to the
            # next provider in the order.

        # All providers failed.
        return self._hard_fallback(
            role=role,
            reason=last_error_msg or "all_providers_failed",
            provider=last_provider,
            model=last_model,
            error_type=last_error_type,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _build_plan(self, role: str, model_override: Optional[str]) -> List[Tuple[str, str]]:
        plan: List[Tuple[str, str]] = []
        for name in self.provider_order:
            p = self.registry.get(name)
            if p is None:
                continue
            cfg = p.config
            chosen = model_override or cfg.model_for(role) or cfg.orchestrator_model
            if not chosen:
                continue
            plan.append((name, chosen))
        return plan

    def _max_retries_within(self, provider: str, model: str) -> int:
        p = self.registry.get(provider)
        if p is None:
            return 0
        return max(0, int(p.config.max_retries or 0))

    def _should_retry_within(
        self, err_t: ErrorType, attempts: int, provider: str, model: str
    ) -> bool:
        cap = _POLICY.get(err_t, {}).get("retries_within_provider", 0)
        return attempts <= cap

    # ---- Circuit breaker -----------------------------------------------
    def _breaker_key(self, provider: str, model: str) -> Tuple[str, str]:
        return (provider, model)

    def _get_breaker(self, provider: str, model: str) -> CircuitBreakerRecord:
        k = self._breaker_key(provider, model)
        with self._lock:
            b = self._breakers.get(k)
            if b is None:
                b = CircuitBreakerRecord(provider=provider, model=model)
                self._breakers[k] = b
            return b

    def _breaker_allows(self, provider: str, model: str) -> bool:
        b = self._get_breaker(provider, model)
        now = time.time()
        with self._lock:
            if b.state == CircuitState.OPEN:
                if now >= b.cooldown_until:
                    b.state = CircuitState.HALF_OPEN
                    b.half_open_probe_in_flight = True
                    return True
                return False
            if b.state == CircuitState.HALF_OPEN:
                # Only one probe at a time.
                if b.half_open_probe_in_flight:
                    return False
                b.half_open_probe_in_flight = True
                return True
            return True

    def _breaker_success(self, provider: str, model: str) -> None:
        b = self._get_breaker(provider, model)
        now = time.time()
        with self._lock:
            b.success_count += 1
            b.failure_count = 0
            b.half_open_probe_in_flight = False
            b.state = CircuitState.CLOSED

    def _breaker_failure(self, provider: str, model: str, err_t: ErrorType) -> None:
        b = self._get_breaker(provider, model)
        threshold = _BREAKER_THRESHOLD.get(err_t, 3)
        # Cooldown comes from the per-error-type policy.  When the router was
        # explicitly constructed with a non-default ``cooldown_sec`` (e.g. for
        # tests or tighter ops windows), honor it as an upper bound so
        # operators can dial it down.
        policy_cooldown = _POLICY.get(err_t, {}).get("cooldown_sec", 0.0)
        explicit = getattr(self, "_explicit_cooldown_sec", None)
        if explicit is not None:
            cooldown = min(policy_cooldown, explicit)
        else:
            cooldown = policy_cooldown
        open_breaker = _POLICY.get(err_t, {}).get("open_breaker", False)
        with self._lock:
            b.failure_count += 1
            b.last_failure_ts = time.time()
            b.last_error_type = err_t
            b.half_open_probe_in_flight = False
            if open_breaker and b.failure_count >= threshold:
                b.state = CircuitState.OPEN
                b.cooldown_until = time.time() + cooldown
                self.circuit_breaker_events += 1
                logger.warning(
                    "llm_circuit_breaker_open provider=%s model=%s error_type=%s cooldown_sec=%s",
                    provider, model, err_t.value, cooldown,
                )

    def get_breaker_snapshot(self) -> Dict[str, Dict[str, Any]]:
        snap: Dict[str, Dict[str, Any]] = {}
        with self._lock:
            for (p, m), b in self._breakers.items():
                snap[f"{p}/{m}"] = {
                    "state": b.state.value,
                    "failure_count": b.failure_count,
                    "success_count": b.success_count,
                    "cooldown_until": b.cooldown_until,
                    "last_error_type": b.last_error_type.value,
                }
        return snap

    # ---- Cache ---------------------------------------------------------
    @staticmethod
    def _cache_key(model: str, system: str, user_message: str, temperature: float, max_tokens: int) -> str:
        h = hashlib.md5(
            f"{model}|{temperature}|{max_tokens}|{system}|{user_message}".encode()
        ).hexdigest()
        return h

    def _cache_lookup(self, key: str) -> Optional[LLMResponse]:
        return self._cache.get(key)

    def _cache_store(self, key: str, response: LLMResponse) -> None:
        self._cache[key] = response

    # ---- Hard fallback -------------------------------------------------
    def _hard_fallback(
        self,
        role: str,
        reason: str,
        provider: str = "",
        model: str = "",
        error_type: ErrorType = ErrorType.UNKNOWN,
    ) -> LLMResponse:
        self.fallback_uses += 1
        logger.error(
            "llm_all_providers_failed role=%s reason=%s last_provider=%s last_model=%s last_error_type=%s",
            role, reason, provider, model, error_type.value,
        )
        return LLMResponse(
            content=self.deterministic_fallback,
            provider=provider,
            model=model,
            status="fallback",
            error_type=error_type,
            error_message=reason,
            fallback=True,
            role=role,
        )

    # ---- Telemetry ----------------------------------------------------
    def telemetry(self) -> Dict[str, Any]:
        return {
            "attempts": self.attempts,
            "successes": self.successes,
            "failures": self.failures,
            "fallback_uses": self.fallback_uses,
            "cache_hits": self.cache_hits,
            "provider_switches": self.provider_switches,
            "circuit_breaker_events": self.circuit_breaker_events,
            "error_type_counts": dict(self.error_type_counts),
            "provider_call_counts": dict(self.provider_call_counts),
            "model_call_counts": dict(self.model_call_counts),
            "provider_order": list(self.provider_order),
            "cache_size": len(self._cache),
            "breakers": self.get_breaker_snapshot(),
        }
