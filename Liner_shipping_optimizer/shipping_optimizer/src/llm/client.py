"""Provider-independent LLM client.

The previous client was a single-OpenCode implementation.  This module is
backward-compatible: ``llm_client.chat(model, system, user_message, ...)``
still returns a string, and ``llm_client`` still exposes the same methods
that the rest of the codebase uses (``chat``, ``_get_hard_fallback_response``,
``_strip_model``, ``total_calls``, ``cache_hits``, ``fallback_uses``,
``failure_count``).

Internally, every call is routed through ``ProviderRouter`` which
implements the failover / circuit-breaker / cache behaviour.  The role is
inferred from the model name (legacy behaviour) so existing agent code
works unchanged.  New code may pass an explicit ``role=`` to ``chat``.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any, Dict, List, Optional

from src.utils.logger import logger
from src.utils.config import Config
from src.llm.providers import (
    ProviderRouter,
    ProviderRegistry,
    default_registry,
    LLMResponse,
)


_MODEL_TO_ROLE = {
    # legacy aliases — most calls in the codebase use a free-form model
    # string. We default them to "orchestrator" because the orchestrator
    # model is what the previous architecture routed everything through.
}


def _infer_role(model: str) -> str:
    m = (model or "").lower()
    if "coordinator" in m:
        return "coordinator"
    if "regional" in m:
        return "regional"
    if "service" in m or "svc_gen" in m or "svcgen" in m:
        return "service_generator"
    if "iteration" in m or "selector" in m:
        return "iteration_selector"
    if "orchestrator" in m:
        return "orchestrator"
    return "orchestrator"


class LLMClient:
    """Provider-routed LLM client with the legacy surface preserved.

    The previous single-OpenCode client was modified only at the network
    boundary; the rest of the codebase (``BaseAgent.call_llm``,
    ``CoordinatorAgent``, ``RegionalAgent``, ``ServiceGeneratorAgent``,
    ``IterationSelector``) still calls ``llm_client.chat(model, system,
    user_message)`` and expects a string back.
    """

    def __init__(self):
        self._router: Optional[ProviderRouter] = None
        self._init_router()

        # Last router response — agents can read this after a chat() to
        # extract provider / model / latency metadata for telemetry.
        self.last_response: Optional[LLMResponse] = None

        # Legacy counters / state — kept so anything that reads them still
        # works.  They mirror the router's telemetry.
        self.total_calls = 0
        self.cache_hits = 0
        self.fallback_uses = 0
        self.failure_count = 0
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 60
        self.max_retries = 1
        self.retry_delay = 1.0

        # Legacy cache (mirrors the router's cache so the existing
        # ``test_cache`` and other tests that read ``self.cache`` still
        # work).
        self.cache: Dict[str, str] = {}

        # Legacy fallback model list — used only by ``_strip_model``.
        self.fallback_models: List[str] = []

    # ---------------------------------------------------------------
    # Router wiring
    # ---------------------------------------------------------------
    def _init_router(self) -> None:
        reg: ProviderRegistry = default_registry()
        self._router = ProviderRouter(
            registry=reg,
            provider_order=None,         # use the registry's order / LLM_PROVIDER_ORDER
            cache_enabled=Config.LLM_CACHE_ENABLED,
            cooldown_sec=Config.LLM_429_COOLDOWN_SEC,
        )

    def _ensure_router(self) -> ProviderRouter:
        if self._router is None:
            self._init_router()
        assert self._router is not None
        return self._router

    # ---------------------------------------------------------------
    # Legacy surface — chat() returns a string (the content field of
    # LLMResponse).  The router's metadata is exposed via telemetry().
    # ---------------------------------------------------------------
    def chat(
        self,
        model: str,
        system: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        role: Optional[str] = None,
    ) -> str:
        self.total_calls += 1
        r = self._ensure_router()
        resolved_role = role or _infer_role(model)
        # Do NOT pass the legacy ``model`` string verbatim to the router —
        # the router resolves per-provider models from the registry, and
        # passing the legacy model would force every provider to use it.
        # We only forward the model if ``role`` was explicitly given AND
        # the caller truly wants to override; in the new architecture
        # per-role models live in the registry.
        router_model = None
        if resolved_role and resolved_role != _infer_role(model):
            # Caller explicitly named a role that overrides the legacy model
            # inference — let the router resolve per-provider models.
            router_model = None
        resp: LLMResponse = r.chat(
            role=resolved_role,
            system=system,
            user_message=user_message,
            model=router_model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_sec=Config.LLM_REQUEST_TIMEOUT_SEC,
        )
        self.last_response = resp

        # Mirror the router's state to the legacy fields.
        if resp.cache_hit:
            self.cache_hits += 1
        if resp.fallback:
            self.fallback_uses += 1
        if resp.status == "error":
            self.failure_count += 1

        # Mirror the cache so legacy ``self.cache`` lookups still work.
        cache_key = self._legacy_cache_key(model, system, user_message)
        if resp.status == "ok" and not resp.cache_hit:
            self.cache[cache_key] = resp.content
        elif resp.cache_hit and cache_key not in self.cache:
            # Cache hit reported by router but legacy cache empty; backfill.
            self.cache[cache_key] = resp.content

        return resp.content

    @staticmethod
    def _legacy_cache_key(model: str, system: str, user_message: str) -> str:
        return hashlib.md5(
            f"{model}|{system}|{user_message}".encode()
        ).hexdigest()

    # ---------------------------------------------------------------
    # Legacy helpers
    # ---------------------------------------------------------------
    @staticmethod
    def _strip_model(model: str) -> str:
        return model.split("/", 1)[-1] if "/" in model else model

    def _get_hard_fallback_response(self) -> str:
        return "Service temporarily unavailable. Using default optimization parameters."

    # ---------------------------------------------------------------
    # Legacy stubs — kept so any old direct calls don't blow up.
    # ---------------------------------------------------------------
    def _is_circuit_open(self) -> bool:                        # noqa: D401
        return False

    @staticmethod
    def _extract_response_content(response) -> str:
        if response and getattr(response, "choices", None):
            try:
                msg = response.choices[0].message
                return (getattr(msg, "content", None) or "")
            except Exception:
                return ""
        return ""

    def _try_call(self, *args, **kwargs):                      # noqa: D401
        raise NotImplementedError(
            "_try_call is a legacy method; use chat() with the new router."
        )

    # ---------------------------------------------------------------
    # New telemetry surface
    # ---------------------------------------------------------------
    def telemetry(self) -> Dict[str, Any]:
        r = self._ensure_router()
        return r.telemetry()

    def health_report(self) -> List[Dict[str, Any]]:
        """Run a one-shot health probe for every configured (provider, model).

        Returns a list of dicts (HealthStatus.to_dict).  Never raises.
        """
        from src.llm.providers import HealthStatus
        reg = default_registry()
        results: List[Dict[str, Any]] = []
        for p in reg.all():
            cfg = p.config
            for role in ("orchestrator", "coordinator", "regional",
                         "service_generator", "iteration_selector"):
                model = cfg.model_for(role)
                if not model:
                    continue
                h: HealthStatus = p.health_check(model=model, timeout_sec=10)
                h.role = role  # type: ignore[attr-defined]
                d = h.to_dict()
                d["role"] = role
                results.append(d)
        return results


# Singleton — preserved.
llm_client = LLMClient()
