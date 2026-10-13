"""Tests for the LLM actuation ledger."""
from __future__ import annotations

from src.llm.actuation import actuation_ledger, LLMActuationLedger, ActuationRecord


def test_ledger_records_per_component():
    led = LLMActuationLedger()
    r = led.begin("coordinator")
    r.provider = "groq"
    r.attempts = 1
    r.successes = 1
    r.ai_generated = True
    assert led.get("coordinator") is r
    assert led.summary()["coordinator"]["provider"] == "groq"


def test_global_ledger_singleton_exists():
    assert actuation_ledger is not None
    a = actuation_ledger.begin("test_singleton")
    assert a.component == "test_singleton"
