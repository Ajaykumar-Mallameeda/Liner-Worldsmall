"""Phase Q — synthetic provider-failover test.

Simulates three failure scenarios against the live provider router using
stub providers, and verifies that the deterministic fallback still
triggers when ALL providers fail.

Scenarios:
  1. All providers healthy        -> first provider serves the call.
  2. First provider returns 429   -> failover to second provider.
  3. All providers return 429     -> deterministic fallback triggers.
  4. All providers timeout/connect-> deterministic fallback triggers.

Writes ``RUNTIME_FAILOVER_TEST_REPORT.json``.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _ok(name: str, content: str):
    from src.llm.providers import LLMResponse
    return LLMResponse(
        content=content, provider=name, model=f"{name}-model",
        status="ok", request_id=f"rid-{name}",
    )


def _err(name: str, et, msg: str = "x"):
    from src.llm.providers import LLMResponse
    return LLMResponse(
        content="", provider=name, model=f"{name}-model",
        status="error", error_type=et, error_message=msg, fallback=True,
    )


def _build_stub_providers():
    from tests.test_provider_system.conftest import StubProvider
    p1 = StubProvider("groq")
    p2 = StubProvider("openrouter")
    p3 = StubProvider("google")
    return p1, p2, p3


def _run_scenario(name: str, scripts: dict, expected_provider: str | None, expected_status: str):
    from src.llm.providers import (
        ErrorType,
        ProviderRegistry,
        ProviderRouter,
    )
    p1, p2, p3 = _build_stub_providers()
    p1.script = scripts["groq"]
    p2.script = scripts["openrouter"]
    p3.script = scripts["google"]
    reg = ProviderRegistry()
    reg.register(p1); reg.register(p2); reg.register(p3)
    router = ProviderRouter(
        registry=reg,
        provider_order=["groq", "openrouter", "google"],
        cooldown_sec=0.001,
    )
    t0 = time.perf_counter()
    out = router.chat(role="coordinator", system="s", user_message="u")
    dur = round((time.perf_counter() - t0) * 1000, 1)
    passed = (
        (expected_provider is None or out.provider == expected_provider)
        and out.status == expected_status
    )
    return {
        "scenario": name,
        "passed": passed,
        "duration_ms": dur,
        "actual_provider": out.provider,
        "actual_status": out.status,
        "attempts": router.attempts,
        "provider_switches": router.provider_switches,
        "circuit_breaker_events": router.circuit_breaker_events,
    }


def run() -> int:
    from src.llm.providers import ErrorType

    scenarios = [
        (
            "all_healthy",
            {
                "groq":     [_ok("groq", "from-groq")],
                "openrouter": [_ok("openrouter", "from-or")],
                "google":   [_ok("google", "from-google")],
            },
            "groq", "ok",
        ),
        (
            "groq_429_failover",
            {
                "groq":     [_err("groq", ErrorType.HTTP_429, "rl")],
                "openrouter": [_ok("openrouter", "from-or")],
                "google":   [_ok("google", "from-google")],
            },
            "openrouter", "ok",
        ),
        (
            "all_429_fallback",
            {
                "groq":     [_err("groq", ErrorType.HTTP_429, "rl")],
                "openrouter": [_err("openrouter", ErrorType.HTTP_429, "rl")],
                "google":   [_err("google", ErrorType.HTTP_429, "rl")],
            },
            None, "fallback",
        ),
        (
            "all_timeout_fallback",
            {
                "groq":     [_err("groq", ErrorType.TIMEOUT, "slow")] * 5,
                "openrouter": [_err("openrouter", ErrorType.TIMEOUT, "slow")] * 5,
                "google":   [_err("google", ErrorType.TIMEOUT, "slow")] * 5,
            },
            None, "fallback",
        ),
        (
            "groq_invalid_model_failover",
            {
                "groq":     [_err("groq", ErrorType.INVALID_MODEL, "404")],
                "openrouter": [_ok("openrouter", "ok")],
                "google":   [_ok("google", "ok")],
            },
            "openrouter", "ok",
        ),
        (
            "groq_auth_failover",
            {
                "groq":     [_err("groq", ErrorType.AUTH, "bad-key")],
                "openrouter": [_ok("openrouter", "ok")],
                "google":   [_ok("google", "ok")],
            },
            "openrouter", "ok",
        ),
    ]

    results = []
    t0 = time.perf_counter()
    for name, scripts, expected_p, expected_s in scenarios:
        results.append(_run_scenario(name, scripts, expected_p, expected_s))
    total_sec = round(time.perf_counter() - t0, 2)

    passed = sum(1 for r in results if r["passed"])
    out = {
        "scenarios_total": len(results),
        "scenarios_passed": passed,
        "scenarios_failed": len(results) - passed,
        "total_sec": total_sec,
        "results": results,
    }
    out_path = PROJECT_ROOT / "RUNTIME_FAILOVER_TEST_REPORT.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"[failover-test] Wrote {out_path}")
    print(json.dumps(out, indent=2))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(run())
