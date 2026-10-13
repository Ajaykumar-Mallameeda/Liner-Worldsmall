"""Shared pytest fixtures for the multi-provider LLM tests.

These tests are offline (no real network).  They use stubbed providers and
the public router API to exercise:

  * Provider registry
  * Provider configuration
  * Provider health check (mocked)
  * Provider failover (mocked)
  * 429 handling
  * Timeout handling
  * Invalid model handling
  * Circuit breaker
  * Cache
  * JSON validation
  * Coordinator AI success / fallback
  * Iteration selector AI success / fallback
  * Service generator AI path
  * Deterministic fallback
  * Telemetry
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Ensure the project root is on sys.path so the test suite works regardless
# of where pytest is invoked from.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.llm.providers import (                                # noqa: E402
    CircuitState,
    ErrorType,
    HealthStatus,
    LLMResponse,
    ProviderConfig,
    ProviderRegistry,
    ProviderRouter,
)
from src.llm.providers.base import LLMProvider                # noqa: E402


# ---------------------------------------------------------------------------
# Stub provider
# ---------------------------------------------------------------------------

class StubProvider(LLMProvider):
    """Provider that returns canned responses or canned errors.

    Configure via the ``script`` attribute, which is a list of either:
      * ``LLMResponse`` objects (returned in order) or
      * ``Exception`` instances (raised then caught by ``_send_request``).

    After the script is exhausted, the last item is reused.
    """

    def __init__(self, name: str, api_key: str = "stub-key", base_url: str = "https://stub",
                 script: Optional[List[Any]] = None,
                 configured_models: Optional[List[str]] = None):
        cfg = ProviderConfig(
            name=name, api_key=api_key, base_url=base_url,
            orchestrator_model="stub-orchestrator",
            coordinator_model="stub-coordinator",
            regional_model="stub-regional",
            service_generator_model="stub-service",
            iteration_selector_model="stub-iter",
            timeout_sec=5.0, max_retries=1,
        )
        super().__init__(cfg)
        self.name = name
        self.script = script or [LLMResponse(
            content="ok", provider=name, model="stub",
            status="ok", request_id="rid-1",
        )]
        self.configured_models = configured_models or [
            "stub-orchestrator", "stub-coordinator", "stub-regional",
            "stub-service", "stub-iter",
        ]
        self.call_count = 0
        self.last_request: Dict[str, Any] = {}

    def _send_request(self, model, system, user_message, temperature, max_tokens, timeout_sec):
        idx = min(self.call_count, len(self.script) - 1)
        item = self.script[idx]
        self.call_count += 1
        self.last_request = {
            "model": model, "system": system, "user_message": user_message,
            "temperature": temperature, "max_tokens": max_tokens,
            "timeout_sec": timeout_sec,
        }
        if isinstance(item, Exception):
            raise item
        if isinstance(item, LLMResponse):
            # Make a copy with provider/model set.
            return LLMResponse(
                content=item.content,
                provider=item.provider or self.name,
                model=item.model or model,
                status=item.status,
                error_type=item.error_type,
                error_message=item.error_message,
                fallback=item.fallback,
                request_id=item.request_id or f"rid-{self.call_count}",
                role=item.role,
                latency_ms=item.latency_ms or 1.0,
            )
        raise RuntimeError(f"Unsupported script item: {item!r}")

    def health_check(self, model: str, timeout_sec: float = 5.0) -> HealthStatus:
        h = HealthStatus(
            provider=self.name, model=model,
            configured=True, authentication=True,
            reachable=True, model_valid=model in self.configured_models,
            structured_output_supported=True,
            latency_ms=2.0, status="ok",
        )
        if model not in self.configured_models:
            h.model_valid = False
            h.status = "invalid_model"
            h.error = "stub: model not in configured_models"
        return h


@pytest.fixture
def stub_provider_factory():
    """Factory for stub providers."""
    def _make(name: str, **kw):
        return StubProvider(name=name, **kw)
    return _make
