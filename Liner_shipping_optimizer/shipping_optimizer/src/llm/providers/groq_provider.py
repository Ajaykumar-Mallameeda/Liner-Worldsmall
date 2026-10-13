"""Groq provider adapter.

Groq exposes an OpenAI-compatible endpoint at ``https://api.groq.com/openai/v1``
with very fast inference.  See https://console.groq.com/docs/openai for the
API contract.  Free-tier limits are per-model and per-account; the actual
availability of any specific model MUST be validated against the API key at
health-check time — the provider itself does not pre-bake model names.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from .base import LLMProvider
from .types import ErrorType, LLMResponse


logger = logging.getLogger("llm.provider.groq")


class GroqProvider(LLMProvider):
    name = "groq"

    def _send_request(
        self,
        model: str,
        system: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
        timeout_sec: float,
    ) -> LLMResponse:
        from openai import OpenAI  # local import to keep module import-time light

        if not self.config.api_key:
            return LLMResponse(
                content="",
                provider=self.name,
                model=model,
                status="error",
                error_type=ErrorType.AUTH,
                error_message="GROQ_API_KEY is not set",
                fallback=True,
            )

        client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url or "https://api.groq.com/openai/v1",
        )
        import time as _t
        t0 = _t.perf_counter()
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout_sec,
            )
        except Exception as e:                                  # noqa: BLE001
            latency_ms = (_t.perf_counter() - t0) * 1000
            # Re-raise so the base.chat() handler can map to ErrorType; but
            # tag the error message with provider context.
            from .base import _classify_exception
            err_type = _classify_exception(e)
            return LLMResponse(
                content="",
                provider=self.name,
                model=model,
                latency_ms=round(latency_ms, 1),
                status="error",
                error_type=err_type,
                error_message=f"groq: {e!s}"[:200],
                fallback=True,
            )

        latency_ms = (_t.perf_counter() - t0) * 1000
        request_id = getattr(resp, "id", "") or ""
        try:
            msg = resp.choices[0].message
            content = (getattr(msg, "content", None) or "")
            if not content and getattr(msg, "reasoning_content", None):
                # Reasoning-only — same as the legacy client: signal as
                # INVALID_JSON so the router retries with a fallback model.
                return LLMResponse(
                    content="",
                    provider=self.name,
                    model=model,
                    latency_ms=round(latency_ms, 1),
                    status="error",
                    error_type=ErrorType.INVALID_JSON,
                    error_message="reasoning_only",
                    request_id=request_id,
                )
            return LLMResponse(
                content=content,
                provider=self.name,
                model=model,
                latency_ms=round(latency_ms, 1),
                status="ok",
                request_id=request_id,
            )
        except Exception as e:                                  # noqa: BLE001
            return LLMResponse(
                content="",
                provider=self.name,
                model=model,
                latency_ms=round(latency_ms, 1),
                status="error",
                error_type=ErrorType.UNKNOWN,
                error_message=f"response parse: {e!s}"[:200],
                request_id=request_id,
            )
