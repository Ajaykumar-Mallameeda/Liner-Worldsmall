"""Provider registry — maps provider name -> configured ``LLMProvider``.

The registry is the only place where the provider roster lives.  Adding a new
provider means writing a ``LLMProvider`` subclass and registering it in
``_PROVIDER_CLASSES``.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from .base import LLMProvider
from .types import ProviderConfig


logger = logging.getLogger("llm.registry")


_PROVIDER_CLASSES = {
    "groq": "GroqProvider",
    "cerebras": "CerebrasProvider",
    "google": "GoogleProvider",
    "openrouter": "OpenRouterProvider",
}


def _load_class(name: str):
    """Late import so a missing optional dep doesn't kill the module."""
    if name == "GroqProvider":
        from .groq_provider import GroqProvider
        return GroqProvider
    if name == "CerebrasProvider":
        from .cerebras_provider import CerebrasProvider
        return CerebrasProvider
    if name == "GoogleProvider":
        from .google_provider import GoogleProvider
        return GoogleProvider
    if name == "OpenRouterProvider":
        from .openrouter_provider import OpenRouterProvider
        return OpenRouterProvider
    raise KeyError(name)


def _provider_config_from_env(name: str) -> ProviderConfig:
    """Read per-provider configuration from environment.

    The schema (set in the new ``.env.example``) is:

        GROQ_API_KEY, GROQ_BASE_URL (optional override),
        GROQ_ORCHESTRATOR_MODEL, GROQ_COORDINATOR_MODEL, ...

    Same shape for ``CEREBRAS_*`` and ``GOOGLE_*``.
    """
    base = name.upper()
    api_key = os.getenv(f"{base}_API_KEY")
    base_url = os.getenv(f"{base}_BASE_URL", "")
    if not base_url:
        base_url = {
            "GROQ":       "https://api.groq.com/openai/v1",
            "CEREBRAS":   "https://api.cerebras.ai/v1",
            "GOOGLE":     "https://generativelanguage.googleapis.com/v1beta/openai/",
            "OPENROUTER": "https://openrouter.ai/api/v1",
        }.get(base, "")
    return ProviderConfig(
        name=name,
        api_key=api_key,
        base_url=base_url,
        orchestrator_model=os.getenv(f"{base}_ORCHESTRATOR_MODEL", ""),
        coordinator_model=os.getenv(f"{base}_COORDINATOR_MODEL", ""),
        regional_model=os.getenv(f"{base}_REGIONAL_MODEL", ""),
        service_generator_model=os.getenv(f"{base}_SERVICE_GENERATOR_MODEL", ""),
        iteration_selector_model=os.getenv(f"{base}_ITERATION_SELECTOR_MODEL", ""),
        timeout_sec=float(os.getenv(f"{base}_TIMEOUT_SEC", "30")),
        max_retries=int(os.getenv(f"{base}_MAX_RETRIES", "1")),
        fallback_models=[
            m.strip() for m in os.getenv(f"{base}_FALLBACK_MODELS", "").split(",") if m.strip()
        ],
    )


class ProviderRegistry:
    """Stores provider name -> ``LLMProvider`` mapping."""

    def __init__(self):
        self._providers: Dict[str, LLMProvider] = {}
        self._configs: Dict[str, ProviderConfig] = {}

    def register(self, provider: LLMProvider) -> None:
        if not provider.name:
            raise ValueError("provider must set .name")
        self._providers[provider.name] = provider
        self._configs[provider.name] = provider.config
        logger.info(
            "provider_registered name=%s base_url=%s has_key=%s",
            provider.name, provider.config.base_url, bool(provider.config.api_key),
        )

    def get(self, name: str) -> Optional[LLMProvider]:
        return self._providers.get(name)

    def all(self) -> List[LLMProvider]:
        return list(self._providers.values())

    def all_names(self) -> List[str]:
        return list(self._providers.keys())

    def config_for(self, name: str) -> Optional[ProviderConfig]:
        return self._configs.get(name)

    def is_available(self, name: str) -> bool:
        p = self._providers.get(name)
        return bool(p and p.config.api_key)


def build_default_registry() -> ProviderRegistry:
    """Build a registry from environment.

    The order of providers follows ``LLM_PROVIDER_ORDER`` (csv).  When unset,
    the order is ``groq,cerebras,google`` so Groq is tried first.
    """
    order = os.getenv("LLM_PROVIDER_ORDER", "groq,openrouter,google")
    order = [p.strip().lower() for p in order.split(",") if p.strip()]

    reg = ProviderRegistry()
    for name in order:
        if name not in _PROVIDER_CLASSES:
            logger.warning("provider_unknown name=%s", name)
            continue
        cfg = _provider_config_from_env(name)
        cls = _load_class(_PROVIDER_CLASSES[name])
        try:
            reg.register(cls(cfg))
        except Exception as e:                                  # noqa: BLE001
            logger.error("provider_register_failed name=%s error=%s", name, e)
    return reg


# Module-level default registry.  Initialised lazily.
_default_registry: Optional[ProviderRegistry] = None


def default_registry() -> ProviderRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = build_default_registry()
    return _default_registry
