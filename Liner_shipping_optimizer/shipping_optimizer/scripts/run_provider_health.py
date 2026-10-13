"""Phase D — provider discovery and validation.

Runs a one-shot health probe against every configured (provider, role, model)
and writes the result to ``PROVIDER_HEALTH_REPORT.json``.  The script does
NOT call any expensive pipeline; a failed probe does NOT crash the run.

Usage::

    python -m scripts.run_provider_health

Output::

    PROVIDER_HEALTH_REPORT.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Best-effort: load the .env.example so a fresh checkout can run the probe
# without first hand-editing a .env.  Real keys are NOT in the template.
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", override=True)
example_env = PROJECT_ROOT / ".env.example"
if example_env.exists() and not os.getenv("GROQ_API_KEY"):
    load_dotenv(example_env, override=False)

from src.llm.providers import (
    ProviderRegistry,
    build_default_registry,
    HealthStatus,
)


ROLES = ("orchestrator", "coordinator", "regional",
         "service_generator", "iteration_selector")


def run() -> int:
    reg: ProviderRegistry = build_default_registry()
    results = []
    t0 = time.perf_counter()
    for p in reg.all():
        cfg = p.config
        for role in ROLES:
            model = cfg.model_for(role)
            if not model:
                continue
            try:
                h: HealthStatus = p.health_check(model=model, timeout_sec=10)
            except Exception as e:                              # noqa: BLE001
                h = HealthStatus(
                    provider=p.name, model=model,
                    configured=bool(cfg.api_key),
                    authentication=bool(cfg.api_key),
                    error=str(e)[:200],
                    status="unreachable",
                )
            entry = h.to_dict()
            entry["role"] = role
            entry["base_url"] = cfg.base_url
            entry["has_api_key"] = bool(cfg.api_key)
            results.append(entry)
    total_sec = round(time.perf_counter() - t0, 2)

    summary = {
        "total_probes":      len(results),
        "providers_queried": reg.all_names(),
        "ok_count":          sum(1 for r in results if r.get("status") == "ok"),
        "unreachable_count": sum(1 for r in results if r.get("status") == "unreachable"),
        "auth_failed_count": sum(1 for r in results if r.get("status") == "auth_failed"),
        "invalid_model_count": sum(1 for r in results if r.get("status") == "invalid_model"),
        "structured_unsupported_count": sum(1 for r in results if r.get("status") == "structured_unsupported"),
        "missing_key_count": sum(1 for r in results if not r.get("has_api_key")),
        "total_sec":         total_sec,
    }
    out = {
        "summary": summary,
        "results": results,
    }
    out_path = PROJECT_ROOT / "PROVIDER_HEALTH_REPORT.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {out_path}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
