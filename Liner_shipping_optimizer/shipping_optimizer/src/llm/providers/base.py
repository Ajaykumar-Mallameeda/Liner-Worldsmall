"""Abstract ``LLMProvider`` base class.

Concrete providers (Groq, Cerebras, Google) subclass this.  The contract is
narrow:

  * ``chat()`` returns an ``LLMResponse`` (never raises on network errors —
    those are mapped to ``error_type`` and ``status="fallback"``).
  * ``health_check()`` is a one-shot probe that returns a ``HealthStatus``.
  * ``validate_model()`` confirms a model name is actually usable against
    the configured API key (best-effort; provider-dependent).

The router and circuit breaker are provider-agnostic; they only rely on
``LLMResponse.error_type`` to decide whether to fail over.
"""

from __future__ import annotations

import json
import re
import time
import logging
from typing import Any, Dict, Optional

from .types import (
    ErrorType,
    LLMResponse,
    ProviderConfig,
    HealthStatus,
)


logger = logging.getLogger("llm.provider")


def _classify_exception(err: Exception) -> ErrorType:
    """Map a network/HTTP exception to a categorical error type.

    The mapping is intentionally lightweight — we look for substrings in the
    error string that are well-known for the providers we support.
    """
    msg = (str(err) or "").lower()
    if "429" in msg or "rate limit" in msg or "freeusagelimit" in msg or "quota" in msg:
        return ErrorType.HTTP_429
    if "timeout" in msg or "timed out" in msg:
        return ErrorType.TIMEOUT
    if "connect" in msg or "connection" in msg or "resolve" in msg:
        return ErrorType.CONNECTION
    if "401" in msg or "403" in msg or "unauthorized" in msg or "forbidden" in msg:
        return ErrorType.AUTH
    if "404" in msg and "model" in msg:
        return ErrorType.INVALID_MODEL
    if "400" in msg and ("model" in msg or "not found" in msg or "invalid" in msg):
        return ErrorType.INVALID_MODEL
    return ErrorType.UNKNOWN


class LLMProvider:
    """Base class for a provider adapter.

    Subclasses must set ``name`` and override ``_send_request()``.
    """

    name: str = ""

    def __init__(self, config: ProviderConfig):
        self.config = config

    # ---------------------------------------------------------------
    # Health / model discovery
    # ---------------------------------------------------------------
    def health_check(self, model: str, timeout_sec: float = 15.0) -> HealthStatus:
        """Probe the provider with a tiny structured-output request.

        Returns a ``HealthStatus``.  Never raises.
        """
        h = HealthStatus(
            provider=self.name,
            model=model,
            configured=bool(self.config.api_key),
            authentication=bool(self.config.api_key),
        )
        if not self.config.api_key:
            h.status = "auth_failed"
            h.error = "missing API key"
            return h

        probe_prompt = (
            "Respond with ONLY this JSON object and nothing else: "
            '{"ok": true}'
        )
        t0 = time.perf_counter()
        try:
            resp = self._send_request(
                model=model,
                system="You are a JSON emitter.",
                user_message=probe_prompt,
                temperature=0.0,
                max_tokens=20,
                timeout_sec=timeout_sec,
            )
        except Exception as e:                                  # noqa: BLE001
            h.reachable = False
            h.error = str(e)[:200]
            et = _classify_exception(e)
            h.status = {
                ErrorType.HTTP_429: "rate_limited",
                ErrorType.TIMEOUT:  "unreachable",
                ErrorType.CONNECTION: "unreachable",
                ErrorType.AUTH:     "auth_failed",
                ErrorType.INVALID_MODEL: "invalid_model",
            }.get(et, "unreachable")
            h.latency_ms = round((time.perf_counter() - t0) * 1000, 1)
            return h

        h.latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        h.reachable = True
        # Auth is "ok" if we got any HTTP response (even a 4xx is past auth)
        h.authentication = True

        if resp.error_type in (ErrorType.AUTH, ErrorType.INVALID_MODEL):
            h.model_valid = False
            h.status = "invalid_model" if resp.error_type == ErrorType.INVALID_MODEL else "auth_failed"
            h.error = resp.error_message[:200]
            return h

        # Validate structured output
        text = resp.content or ""
        h.model_valid = bool(text)
        if h.model_valid:
            # The probe expects JSON.  Try to parse; if the model is chatty
            # it may wrap the JSON in prose.  Be tolerant.
            parsed = self._try_parse_json(text)
            h.structured_output_supported = parsed.get("ok") is True
            if h.structured_output_supported:
                h.status = "ok"
            else:
                h.status = "structured_unsupported"
                h.error = "model did not return expected JSON shape"
        else:
            h.status = "invalid_model"
            h.error = "empty response"
        return h

    @staticmethod
    def _try_parse_json(text: str) -> Dict[str, Any]:
        if not text:
            return {}
        text = text.strip()
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        try:
            v = json.loads(text)
            return v if isinstance(v, dict) else {}
        except Exception:
            pass
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                v = json.loads(m.group())
                return v if isinstance(v, dict) else {}
            except Exception:
                return {}
        return {}

    # ---------------------------------------------------------------
    # Chat
    # ---------------------------------------------------------------
    def chat(
        self,
        model: str,
        system: str,
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        timeout_sec: Optional[float] = None,
    ) -> LLMResponse:
        """Public chat entrypoint.

        Returns ``LLMResponse(status="ok"|"fallback"|"error")``.  Never
        raises — all error handling is mapped to ``error_type``.
        """
        timeout = timeout_sec if timeout_sec is not None else self.config.timeout_sec
        t0 = time.perf_counter()
        try:
            return self._send_request(
                model=model,
                system=system,
                user_message=user_message,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout_sec=timeout,
            )
        except Exception as e:                                  # noqa: BLE001
            latency_ms = (time.perf_counter() - t0) * 1000
            err_type = _classify_exception(e)
            logger.warning(
                "llm_provider_error provider=%s model=%s error_type=%s error=%s",
                self.name, model, err_type.value, str(e)[:200],
            )
            return LLMResponse(
                content="",
                provider=self.name,
                model=model,
                latency_ms=round(latency_ms, 1),
                status="error",
                error_type=err_type,
                error_message=str(e)[:200],
                fallback=True,
            )

    # ---------------------------------------------------------------
    # Subclass hook
    # ---------------------------------------------------------------
    def _send_request(
        self,
        model: str,
        system: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
        timeout_sec: float,
    ) -> LLMResponse:
        raise NotImplementedError
