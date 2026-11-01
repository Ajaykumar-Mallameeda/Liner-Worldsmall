"""Provider-neutral data types.

These dataclasses are the only types that cross the provider boundary; the
``LLMResponse`` is what the rest of the codebase consumes.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class ErrorType(str, Enum):
    """Categorical error classification used by the router to choose a
    response policy.  See ``router._POLICY``.
    """

    NONE = "none"
    HTTP_429 = "http_429"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    AUTH = "auth"
    INVALID_MODEL = "invalid_model"
    INVALID_JSON = "invalid_json"
    SCHEMA = "schema"
    QUALITY = "quality"
    UNKNOWN = "unknown"


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ProviderConfig:
    """Configuration for one (provider, role) entry.

    Attributes
    ----------
    name:
        Logical provider name (groq, cerebras, google).
    api_key:
        Provider API key (env-supplied).
    base_url:
        OpenAI-compatible endpoint base URL.
    orchestrator_model, coordinator_model, regional_model,
    service_generator_model, iteration_selector_model:
        Per-role model names.  Each provider can have a different model for
        each role.  The agent asks for ``role=coordinator`` and the router
        looks up the right model.
    timeout_sec:
        HTTP request timeout per call.
    max_retries:
        Retries within a single provider (NOT across providers).
    fallback_models:
        Same-provider backup models, tried in order after the role model
        fails (e.g. per-model 429).  Each has its own breaker and quota.
    extra:
        Free-form provider-specific extra config (e.g. Gemini uses
        ``x-goog-api-key`` instead of bearer; base_url is suffixed with
        ``/v1beta/openai/`` for OpenAI-compat mode).
    """

    name: str
    api_key: Optional[str]
    base_url: str
    orchestrator_model: str = ""
    coordinator_model: str = ""
    regional_model: str = ""
    service_generator_model: str = ""
    iteration_selector_model: str = ""
    timeout_sec: float = 30.0
    max_retries: int = 1
    fallback_models: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def model_for(self, role: str) -> str:
        return getattr(self, f"{role}_model", "") or self.orchestrator_model or ""


@dataclass
class LLMResponse:
    """Uniform provider response.

    ``content`` is the (best-effort) extracted text.  When the provider
    fails, ``error_type`` is non-NONE and ``content`` is the safe fallback
    string.
    """

    content: str
    provider: str = ""
    model: str = ""
    attempt: int = 0
    latency_ms: float = 0.0
    status: str = "ok"               # "ok" | "fallback" | "error" | "cache_hit"
    error_type: ErrorType = ErrorType.NONE
    error_message: str = ""
    fallback: bool = False
    request_id: str = ""
    role: str = ""
    cache_hit: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["error_type"] = self.error_type.value
        return d


@dataclass
class HealthStatus:
    """Result of a one-shot health probe for a single (provider, model)."""

    provider: str
    model: str
    configured: bool = False
    authentication: bool = False
    reachable: bool = False
    model_valid: bool = False
    structured_output_supported: bool = False
    latency_ms: float = 0.0
    error: str = ""
    status: str = "unknown"          # "ok" | "unreachable" | "auth_failed" | "invalid_model" | "structured_unsupported"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CircuitBreakerRecord:
    """Per (provider, model) circuit-breaker state."""

    provider: str
    model: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_ts: float = 0.0
    last_error_type: ErrorType = ErrorType.NONE
    cooldown_until: float = 0.0
    success_count: int = 0
    half_open_probe_in_flight: bool = False

    def is_open(self, now: float) -> bool:
        if self.state == CircuitState.OPEN:
            return now < self.cooldown_until
        return False
