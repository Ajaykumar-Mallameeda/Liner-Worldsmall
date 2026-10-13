"""Provider-independent multi-provider LLM layer.

This module replaces the previous single-OpenCode/DeepSeek architecture with a
provider-independent layer supporting Groq, Cerebras, and Google Gemini. The
key design principles:

  * Providers are pluggable.  New providers can be added by writing an
    ``LLMProvider`` subclass and registering it in the ``ProviderRegistry``.
  * Provider failover is automatic.  HTTP 429 (rate-limited) responses open a
    short cooldown on the affected provider/model and move on.  The pipeline
    never blocks on a single rate-limited provider.
  * A provider-aware circuit breaker is maintained per (provider, model)
    pair.  Failures trip the breaker; the next call after the cooldown
    performs a controlled probe.
  * The output (``LLMResponse``) is uniform across providers and includes
    ``provider``, ``model``, ``attempt``, ``latency_ms``, ``status``,
    ``error_type``, ``fallback``, and ``request_id`` metadata.
  * The deterministic fallback (a constant string) is preserved for the
    failure case so the existing agent-level fallbacks still trigger.

The new module is the ONLY network-touching code.  All call sites continue to
use ``src.llm.client.llm_client`` — the public surface is unchanged.
"""

from .types import (
    ErrorType,
    LLMResponse,
    ProviderConfig,
    CircuitState,
    HealthStatus,
)
from .registry import ProviderRegistry, default_registry, build_default_registry
from .router import ProviderRouter
from .base import LLMProvider
from .groq_provider import GroqProvider
from .cerebras_provider import CerebrasProvider
from .google_provider import GoogleProvider
from .openrouter_provider import OpenRouterProvider

__all__ = [
    "ErrorType",
    "LLMResponse",
    "ProviderConfig",
    "CircuitState",
    "HealthStatus",
    "ProviderRegistry",
    "default_registry",
    "build_default_registry",
    "ProviderRouter",
    "LLMProvider",
    "GroqProvider",
    "CerebrasProvider",
    "GoogleProvider",
    "OpenRouterProvider",
]
