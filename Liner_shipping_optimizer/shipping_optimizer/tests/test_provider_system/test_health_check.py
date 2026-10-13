"""Health-check tests using stub providers."""
from __future__ import annotations

from src.llm.providers import HealthStatus
from tests.test_provider_system.conftest import StubProvider


def test_health_check_ok_for_configured_model():
    p = StubProvider("groq", configured_models=["m1"])
    h = p.health_check(model="m1")
    assert h.status == "ok"
    assert h.model_valid is True
    assert h.structured_output_supported is True


def test_health_check_invalid_model():
    p = StubProvider("groq", configured_models=["m1"])
    h = p.health_check(model="missing")
    assert h.status == "invalid_model"
    assert h.model_valid is False
