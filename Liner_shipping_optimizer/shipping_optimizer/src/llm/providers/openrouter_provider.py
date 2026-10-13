"""OpenRouter provider adapter.

OpenRouter exposes an OpenAI-compatible endpoint at
``https://openrouter.ai/api/v1``. Free-tier models include several
options that are useful as a secondary provider when Groq or Google
are unavailable. The implementation does NOT pre-bake which free
model is available — model availability is verified at health-check
time via the configured API key.
"""

from __future__ import annotations

import logging
import time as _t

from .base import LLMProvider, _classify_exception
from .types import ErrorType, LLMResponse


logger = logging.getLogger("llm.provider.openrouter")


class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def _send_request(
        self,
        model: str,
        system: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
        timeout_sec: float,
    ) -> LLMResponse:
        from openai import OpenAI

        if not self.config.api_key:
            return LLMResponse(
                content="",
                provider=self.name,
                model=model,
                status="error",
                error_type=ErrorType.AUTH,
                error_message="OPENROUTER_API_KEY is not set",
                fallback=True,
            )

        client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url or "https://openrouter.ai/api/v1",
        )
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
            return LLMResponse(
                content="",
                provider=self.name,
                model=model,
                latency_ms=round(latency_ms, 1),
                status="error",
                error_type=_classify_exception(e),
                error_message=f"openrouter: {e!s}"[:200],
                fallback=True,
            )

        latency_ms = (_t.perf_counter() - t0) * 1000
        request_id = getattr(resp, "id", "") or ""
        try:
            msg = resp.choices[0].message
            content = (getattr(msg, "content", None) or "")
            if not content and getattr(msg, "reasoning_content", None):
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
