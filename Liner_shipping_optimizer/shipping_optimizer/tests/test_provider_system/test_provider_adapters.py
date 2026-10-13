"""Adapter-level smoke tests for Groq, Cerebras, Google.

These tests confirm the adapter modules import and instantiate cleanly.  They
do NOT make real network calls; we use the adapter's ``_send_request``
hook, which is overridden in subclasses.
"""
from __future__ import annotations

from src.llm.providers import (
    CerebrasProvider,
    GoogleProvider,
    GroqProvider,
    LLMResponse,
    ProviderConfig,
)


def _cfg(name: str) -> ProviderConfig:
    return ProviderConfig(
        name=name, api_key="x", base_url=f"https://{name}",
        orchestrator_model="m1", coordinator_model="m2",
        regional_model="m3", service_generator_model="m4",
        iteration_selector_model="m5",
    )


def test_groq_adapter_chat_returns_ok_response():
    p = GroqProvider(_cfg("groq"))
    # Replace _send_request with a stub.
    def _stub(model, system, user_message, temperature, max_tokens, timeout_sec):
        return LLMResponse(content="hello", provider="groq", model=model, status="ok")
    p._send_request = _stub  # type: ignore[method-assign]
    r = p.chat(model="m1", system="s", user_message="u")
    assert r.status == "ok"
    assert r.content == "hello"
    assert r.provider == "groq"


def test_cerebras_adapter_chat_returns_ok_response():
    p = CerebrasProvider(_cfg("cerebras"))
    def _stub(model, system, user_message, temperature, max_tokens, timeout_sec):
        return LLMResponse(content="hello", provider="cerebras", model=model, status="ok")
    p._send_request = _stub  # type: ignore[method-assign]
    r = p.chat(model="m1", system="s", user_message="u")
    assert r.status == "ok"
    assert r.provider == "cerebras"


def test_google_adapter_chat_returns_ok_response():
    p = GoogleProvider(_cfg("google"))
    def _stub(model, system, user_message, temperature, max_tokens, timeout_sec):
        return LLMResponse(content="hello", provider="google", model=model, status="ok")
    p._send_request = _stub  # type: ignore[method-assign]
    r = p.chat(model="m1", system="s", user_message="u")
    assert r.status == "ok"
    assert r.provider == "google"


def test_missing_api_key_returns_auth_error():
    p = GroqProvider(ProviderConfig(name="groq", api_key="", base_url="https://api.groq.com/openai/v1"))
    r = p.chat(model="m1", system="s", user_message="u")
    assert r.status == "error"
    assert r.error_type.value == "auth"
