"""Tests for the provider registry."""
from __future__ import annotations

from src.llm.providers import ProviderConfig, ProviderRegistry
from src.llm.providers.groq_provider import GroqProvider
from src.llm.providers.cerebras_provider import CerebrasProvider
from src.llm.providers.google_provider import GoogleProvider


def _make_cfg(name: str, key: str = "x") -> ProviderConfig:
    return ProviderConfig(
        name=name, api_key=key, base_url=f"https://{name}",
        orchestrator_model=f"{name}-orch",
        coordinator_model=f"{name}-coord",
        regional_model=f"{name}-regional",
        service_generator_model=f"{name}-svc",
        iteration_selector_model=f"{name}-iter",
    )


def test_registry_register_and_lookup():
    reg = ProviderRegistry()
    p = GroqProvider(_make_cfg("groq"))
    reg.register(p)
    assert reg.get("groq") is p
    assert reg.is_available("groq") is True
    assert reg.is_available("missing") is False


def test_registry_all_names_order():
    reg = ProviderRegistry()
    reg.register(GroqProvider(_make_cfg("groq")))
    reg.register(CerebrasProvider(_make_cfg("cerebras")))
    reg.register(GoogleProvider(_make_cfg("google")))
    assert reg.all_names() == ["groq", "cerebras", "google"]


def test_registry_config_for():
    reg = ProviderRegistry()
    cfg = _make_cfg("cerebras")
    reg.register(CerebrasProvider(cfg))
    got = reg.config_for("cerebras")
    assert got is cfg


def test_registry_rejects_duplicate_name():
    reg = ProviderRegistry()
    reg.register(GroqProvider(_make_cfg("groq")))
    reg.register(GroqProvider(_make_cfg("groq")))  # overwrites
    assert len(reg.all()) == 1
