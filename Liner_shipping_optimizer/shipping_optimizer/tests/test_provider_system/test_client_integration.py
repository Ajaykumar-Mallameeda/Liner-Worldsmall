"""Integration tests for the legacy ``llm_client`` surface after the
refactor.

These tests confirm that the public surface of the previous client — in
particular ``llm_client.chat()`` returning a string and the
``_get_hard_fallback_response`` / ``_strip_model`` helpers — still works.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.llm.client import llm_client, LLMClient                    # noqa: E402


def test_legacy_strip_model():
    assert llm_client._strip_model("groq/llama-3.3-70b") == "llama-3.3-70b"
    assert llm_client._strip_model("llama-3.3-70b") == "llama-3.3-70b"


def test_legacy_hard_fallback_string():
    s = llm_client._get_hard_fallback_response()
    assert "Service temporarily unavailable" in s


def test_chat_returns_string_with_no_providers(monkeypatch):
    """When no provider is configured, the client returns the hard-fallback string."""
    # Force a registry with no providers
    from src.llm.providers import ProviderRegistry, ProviderRouter
    reg = ProviderRegistry()
    monkeypatch.setattr(llm_client, "_router", ProviderRouter(registry=reg, provider_order=[]))
    out = llm_client.chat(
        model="m1", system="s", user_message="u", role="orchestrator",
    )
    assert isinstance(out, str)
    assert "Service temporarily unavailable" in out


def test_telemetry_exposes_router():
    t = llm_client.telemetry()
    assert "attempts" in t
    assert "provider_switches" in t
