"""Tests for the provider router: failover, 429, timeout, invalid JSON, etc.

These tests do NOT use real network.  They inject stub providers that
return canned responses / errors.
"""
from __future__ import annotations

import pytest

from src.llm.providers import (
    ErrorType,
    LLMResponse,
    ProviderConfig,
    ProviderRegistry,
    ProviderRouter,
)
from tests.test_provider_system.conftest import StubProvider


def _ok(name: str, content: str = "ok") -> LLMResponse:
    return LLMResponse(
        content=content, provider=name, model=f"{name}-model",
        status="ok", request_id=f"rid-{name}",
    )


def _err(name: str, et: ErrorType, msg: str = "x") -> LLMResponse:
    return LLMResponse(
        content="", provider=name, model=f"{name}-model",
        status="error", error_type=et, error_message=msg, fallback=True,
    )


def _registry_with(*providers):
    reg = ProviderRegistry()
    for p in providers:
        reg.register(p)
    return reg


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_happy_path_first_provider(stub_provider_factory):
    p1 = stub_provider_factory("groq", script=[_ok("groq", "from-groq")])
    reg = _registry_with(p1)
    r = ProviderRouter(registry=reg, provider_order=["groq"])
    out = r.chat(role="coordinator", system="s", user_message="u")
    assert out.status == "ok"
    assert out.content == "from-groq"
    assert p1.call_count == 1


# ---------------------------------------------------------------------------
# 429 → fast failover, no retries within provider
# ---------------------------------------------------------------------------

def test_429_failover_immediate(stub_provider_factory):
    p1 = stub_provider_factory("groq", script=[
        _err("groq", ErrorType.HTTP_429, "rate limited"),
    ])
    p2 = stub_provider_factory("cerebras", script=[_ok("cerebras", "from-cerebras")])
    reg = _registry_with(p1, p2)
    r = ProviderRouter(registry=reg, provider_order=["groq", "cerebras"], cooldown_sec=0.001)
    out = r.chat(role="coordinator", system="s", user_message="u")
    assert out.status == "ok"
    assert out.provider == "cerebras"
    # p1 must NOT have retried — the policy for 429 is 0 retries
    assert p1.call_count == 1
    assert p2.call_count == 1
    assert r.provider_switches == 1


def test_429_opens_breaker(stub_provider_factory):
    """Two consecutive 429s open the breaker (threshold=2 in policy)."""
    p1 = stub_provider_factory("groq", script=[
        _err("groq", ErrorType.HTTP_429, "rl1"),
        _err("groq", ErrorType.HTTP_429, "rl2"),
        _ok("groq", "late"),
    ])
    p2 = stub_provider_factory("cerebras", script=[_ok("cerebras", "cerebras-ok")])
    reg = _registry_with(p1, p2)
    r = ProviderRouter(registry=reg, provider_order=["groq", "cerebras"], cooldown_sec=60.0)
    # First call: 429 → failover to cerebras (groq not yet at threshold).
    out1 = r.chat(role="coordinator", system="s", user_message="u-1")
    assert out1.provider == "cerebras"
    # Second call: groq hits 429 again (threshold=2) → breaker opens;
    # but in this call the retry policy is 0 retries within provider for
    # 429, so we move to cerebras again.
    out2 = r.chat(role="coordinator", system="s", user_message="u-2")
    assert out2.provider == "cerebras"
    # The breaker for groq should now be OPEN; subsequent calls skip groq.
    snap = r.get_breaker_snapshot()
    groq_state = list(snap.values())[0] if "groq" in str(snap) else None
    # The actual key is the (provider, model) tuple; iterate to find it.
    found = False
    for (_p, _m), b in r._breakers.items():
        if _p == "groq":
            found = True
            assert b.state.value == "open"
    assert found, "breaker for groq should exist"


# ---------------------------------------------------------------------------
# Timeout → bounded retry within provider, then failover
# ---------------------------------------------------------------------------

def test_timeout_retries_then_fails_over(stub_provider_factory):
    p1 = stub_provider_factory("groq", script=[
        _err("groq", ErrorType.TIMEOUT, "slow"),
        _err("groq", ErrorType.TIMEOUT, "slow again"),
    ])
    p2 = stub_provider_factory("cerebras", script=[_ok("cerebras", "ok")])
    reg = _registry_with(p1, p2)
    r = ProviderRouter(registry=reg, provider_order=["groq", "cerebras"])
    out = r.chat(role="coordinator", system="s", user_message="u")
    assert out.provider == "cerebras"
    # max_retries_within is 1 for the stub (set in conftest) → p1 called 2x
    assert p1.call_count == 2


# ---------------------------------------------------------------------------
# Connection error → same as timeout
# ---------------------------------------------------------------------------

def test_connection_error_failover(stub_provider_factory):
    p1 = stub_provider_factory("groq", script=[
        _err("groq", ErrorType.CONNECTION, "dns"),
        _err("groq", ErrorType.CONNECTION, "dns"),
    ])
    p2 = stub_provider_factory("cerebras", script=[_ok("cerebras", "ok")])
    reg = _registry_with(p1, p2)
    r = ProviderRouter(registry=reg, provider_order=["groq", "cerebras"])
    out = r.chat(role="coordinator", system="s", user_message="u")
    assert out.provider == "cerebras"


# ---------------------------------------------------------------------------
# Auth error → provider disabled for run
# ---------------------------------------------------------------------------

def test_auth_error_skips_provider(stub_provider_factory):
    p1 = stub_provider_factory("groq", script=[
        _err("groq", ErrorType.AUTH, "bad key"),
    ])
    p2 = stub_provider_factory("cerebras", script=[_ok("cerebras", "ok")])
    reg = _registry_with(p1, p2)
    r = ProviderRouter(registry=reg, provider_order=["groq", "cerebras"])
    out = r.chat(role="coordinator", system="s", user_message="u")
    assert out.provider == "cerebras"
    # auth failure opens the breaker (threshold=1) → p1 not retried
    assert p1.call_count == 1


# ---------------------------------------------------------------------------
# Invalid model → provider disabled
# ---------------------------------------------------------------------------

def test_invalid_model_failover(stub_provider_factory):
    p1 = stub_provider_factory("groq", script=[
        _err("groq", ErrorType.INVALID_MODEL, "404 model"),
    ])
    p2 = stub_provider_factory("cerebras", script=[_ok("cerebras", "ok")])
    reg = _registry_with(p1, p2)
    r = ProviderRouter(registry=reg, provider_order=["groq", "cerebras"])
    out = r.chat(role="coordinator", system="s", user_message="u")
    assert out.provider == "cerebras"


# ---------------------------------------------------------------------------
# Invalid JSON → bounded retry, then failover
# ---------------------------------------------------------------------------

def test_invalid_json_retry_then_failover(stub_provider_factory):
    p1 = stub_provider_factory("groq", script=[
        _err("groq", ErrorType.INVALID_JSON, "no json"),
        _err("groq", ErrorType.INVALID_JSON, "no json"),
    ])
    p2 = stub_provider_factory("cerebras", script=[_ok("cerebras", "json-ok")])
    reg = _registry_with(p1, p2)
    r = ProviderRouter(registry=reg, provider_order=["groq", "cerebras"])
    out = r.chat(role="coordinator", system="s", user_message="u")
    assert out.provider == "cerebras"


# ---------------------------------------------------------------------------
# All providers fail → deterministic fallback
# ---------------------------------------------------------------------------

def test_all_fail_returns_fallback(stub_provider_factory):
    p1 = stub_provider_factory("groq", script=[_err("groq", ErrorType.HTTP_429, "rl")])
    p2 = stub_provider_factory("cerebras", script=[_err("cerebras", ErrorType.HTTP_429, "rl")])
    p3 = stub_provider_factory("google", script=[_err("google", ErrorType.HTTP_429, "rl")])
    reg = _registry_with(p1, p2, p3)
    r = ProviderRouter(registry=reg, provider_order=["groq", "cerebras", "google"])
    out = r.chat(role="coordinator", system="s", user_message="u")
    assert out.status == "fallback"
    assert "Service temporarily unavailable" in out.content
    assert out.fallback is True


def test_no_providers_returns_fallback():
    reg = ProviderRegistry()
    r = ProviderRouter(registry=reg, provider_order=[])
    out = r.chat(role="coordinator", system="s", user_message="u")
    assert out.status == "fallback"


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def test_cache_returns_same_response(stub_provider_factory):
    p1 = stub_provider_factory("groq", script=[_ok("groq", "cached")])
    reg = _registry_with(p1)
    r = ProviderRouter(registry=reg, provider_order=["groq"], cache_enabled=True)
    a = r.chat(role="coordinator", system="s", user_message="u")
    b = r.chat(role="coordinator", system="s", user_message="u")
    assert a.status == "ok"
    assert b.status == "cache_hit"
    assert b.cache_hit is True
    # Provider was only called once.
    assert p1.call_count == 1
    assert r.cache_hits == 1


def test_cache_disabled_does_not_reuse(stub_provider_factory):
    p1 = stub_provider_factory("groq", script=[_ok("groq", "x"), _ok("groq", "y")])
    reg = _registry_with(p1)
    r = ProviderRouter(registry=reg, provider_order=["groq"], cache_enabled=False)
    a = r.chat(role="coordinator", system="s", user_message="u")
    b = r.chat(role="coordinator", system="s", user_message="u")
    assert p1.call_count == 2
    assert a.status == "ok"
    assert b.status == "ok"


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------

def test_telemetry_records_provider_switches(stub_provider_factory):
    p1 = stub_provider_factory("groq", script=[_err("groq", ErrorType.HTTP_429, "rl")])
    p2 = stub_provider_factory("cerebras", script=[_ok("cerebras", "ok")])
    reg = _registry_with(p1, p2)
    r = ProviderRouter(registry=reg, provider_order=["groq", "cerebras"], cooldown_sec=0.001)
    r.chat(role="coordinator", system="s", user_message="u")
    t = r.telemetry()
    assert t["attempts"] == 2
    assert t["failures"] == 1
    assert t["successes"] == 1
    assert t["provider_switches"] == 1
    assert t["error_type_counts"].get("http_429") == 1


# ---------------------------------------------------------------------------
# Half-open probe
# ---------------------------------------------------------------------------

def test_breaker_half_open_probe_succeeds(stub_provider_factory):
    """The breaker opens after 2 consecutive HTTP_429s, then a probe call
    (after the cooldown) succeeds and the breaker closes.

    The router's HTTP_429 policy is "0 within-provider retries, fail over
    immediately", so 2 consecutive 429s must come from 2 separate chat()
    calls (not one).  After the breaker is OPEN and the cooldown elapses,
    the next chat() must trigger a HALF_OPEN probe that is allowed to call
    the provider again and — if it returns ok — close the breaker.
    """
    import time

    p1 = stub_provider_factory("groq", script=[
        _err("groq", ErrorType.HTTP_429, "rl1"),
        _err("groq", ErrorType.HTTP_429, "rl2"),
        _ok("groq", "recovered"),
    ])
    reg = _registry_with(p1)
    r = ProviderRouter(registry=reg, provider_order=["groq"], cooldown_sec=0.001)

    # First 429 — only provider, hard fallback returned; failure_count=1 (still CLOSED).
    r.chat(role="coordinator", system="s", user_message="a")
    # Second 429 — failure_count=2 >= threshold; breaker opens.
    r.chat(role="coordinator", system="s", user_message="b")
    # Verify breaker is OPEN before we probe.
    found_open = False
    for (_p, _m), b in r._breakers.items():
        if _p == "groq":
            assert b.state.value == "open", f"expected open, got {b.state.value}"
            found_open = True
    assert found_open, "groq breaker should be open after 2 429s"

    # Cooldown is 0.001s; sleep so the breaker can transition to HALF_OPEN.
    time.sleep(0.05)

    # Third call: half-open probe.  Only one provider in the order, so the
    # probe must be the call that returns; if the router skipped the probe
    # the response would be hard_fallback, not ok.
    out = r.chat(role="coordinator", system="s", user_message="c")
    assert out.status == "ok", f"expected ok, got {out.status} (err={out.error_type})"
    assert out.provider == "groq"
    assert out.content == "recovered"


# ---------------------------------------------------------------------------
# No indefinite retries
# ---------------------------------------------------------------------------

def test_no_indefinite_retries(stub_provider_factory):
    p1 = stub_provider_factory("groq", script=[_err("groq", ErrorType.UNKNOWN, "x")] * 100)
    p2 = stub_provider_factory("cerebras", script=[_err("cerebras", ErrorType.UNKNOWN, "y")] * 100)
    p3 = stub_provider_factory("google", script=[_err("google", ErrorType.UNKNOWN, "z")] * 100)
    reg = _registry_with(p1, p2, p3)
    r = ProviderRouter(registry=reg, provider_order=["groq", "cerebras", "google"])
    out = r.chat(role="coordinator", system="s", user_message="u")
    assert out.status == "fallback"
    # Each provider at most 2 calls (initial + 1 retry) per the policy.
    assert p1.call_count <= 2
    assert p2.call_count <= 2
    assert p3.call_count <= 2
    # And total attempts bounded.
    t = r.telemetry()
    assert t["attempts"] <= 6
