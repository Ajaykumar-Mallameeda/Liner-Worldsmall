"""Tests for provider configuration resolution from environment."""
from __future__ import annotations

import os
import importlib
from src.llm.providers import registry as reg_module


def test_build_default_registry_reads_order(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "cerebras,groq,google")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("CEREBRAS_API_KEY", "y")
    monkeypatch.setenv("GOOGLE_API_KEY", "z")
    # Re-import to pick up the new env
    importlib.reload(reg_module)
    reg = reg_module.build_default_registry()
    assert reg.all_names() == ["cerebras", "groq", "google"]


def test_provider_config_uses_default_urls(monkeypatch):
    monkeypatch.delenv("GROQ_BASE_URL", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "x")
    importlib.reload(reg_module)
    reg = reg_module.build_default_registry()
    cfg = reg.config_for("groq")
    assert cfg.base_url == "https://api.groq.com/openai/v1"


def test_provider_config_per_role_models(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("GROQ_ORCHESTRATOR_MODEL", "m-orch")
    monkeypatch.setenv("GROQ_REGIONAL_MODEL", "m-reg")
    # Importing src.llm.client (any sibling test) loads .env into os.environ,
    # which pre-seeds these role models and defeats the orchestrator fallback
    # this test is about. Clear them so the test controls its own inputs.
    monkeypatch.delenv("GROQ_COORDINATOR_MODEL", raising=False)
    monkeypatch.delenv("GROQ_ITERATION_SELECTOR_MODEL", raising=False)
    monkeypatch.delenv("GROQ_SERVICE_GENERATOR_MODEL", raising=False)
    importlib.reload(reg_module)
    reg = reg_module.build_default_registry()
    cfg = reg.config_for("groq")
    assert cfg.model_for("orchestrator") == "m-orch"
    assert cfg.model_for("regional") == "m-reg"
    # Role-specific default falls back to orchestrator_model.
    assert cfg.model_for("coordinator") == "m-orch"
    assert cfg.model_for("iteration_selector") == "m-orch"
