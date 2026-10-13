# Phase 0 Dependency Baseline

**Date:** 2026-08-26 · **Baseline commit:** `a44b987` · **Rule: NO new packages during Phase 0. None were installed.**

This record makes future dependency changes explicit. Any phase that adds a dependency
must update this file with a justification row and pass CHANGE_CONTROL review.

## Runtime environment

| Item | Value |
|---|---|
| Python (runtime venv) | **3.11.9** (`venv/Scripts/python.exe`) |
| Package manager | pip against `requirements.txt` (no lock file anywhere) |
| Node | frontend toolchain via `frontend/package.json` (vite 4.5 era) |
| OS (baseline machine) | Windows 11 |

⚠️ Known environment trap: system Python on this machine is 3.14 and lacks project
dependencies — all test/run commands MUST use `venv/Scripts/python.exe`.

## Python — root `requirements.txt` (the optimizer's declared set)

| Package | Pinned | Actually used by | Criticality |
|---|---|---|---|
| openai | 1.40.6 | all provider adapters (`src/llm/providers/*`) as OpenAI-compatible client | Core (LLM mode; keyless deterministic boot works without network) |
| numpy | 1.26.3 | GA/MILP/clustering numerics | Core |
| scipy | 1.12.0 | transitive via scikit-learn | Redundant-as-declared |
| pulp | 2.7.0 | `hub_milp.py` (bundled CBC solver) | Core |
| scikit-learn | 1.4.2 | `port_clustering.py` KMeans | Core |
| torch | 2.1.0 | nothing (0 imports) | Dead weight — removal candidate, NOT removed in Phase 0 |
| gymnasium | 0.29.1 | nothing (0 imports) | Dead weight |
| fastapi | 0.109.0 | backend servers | Core (backend) |
| uvicorn | 0.27.0 | ASGI server | Core (backend) |
| pydantic | 2.5.3 | event schemas (superseded backend path only) | Optional-leaning-core |
| python-dotenv | 1.0.0 | `utils/config.py` import-time `.env` load | Core |
| structlog | 24.1.0 | JSON logging (`utils/logger.py`) | Core |
| pytest | 7.4.4 | tests | Dev |

**Unpinned but imported:** pandas (used by `src/data/network_loader.py`; installed in venv,
absent from root requirements.txt — pre-existing gap, documented not fixed).

**Conflicting second constraint set:** `backend/requirements.txt`
(fastapi==0.104.1, uvicorn[standard]==0.24.0, websockets==12.0, pydantic==2.5.0,
python-multipart==0.0.6, aiofiles==23.2.1). Pre-existing duplication; do not "reconcile"
during feature phases.

## External services (existing, sanctioned)

| Service | Purpose | Failure behavior |
|---|---|---|
| Groq API (primary), OpenRouter (secondary), Google GenAI (tertiary) — OpenAI-compatible endpoints | LLM coordination/advisory calls | Router failover → breaker → hard deterministic fallback string; pipeline proceeds keyless |
| Cerebras API | Supported adapter, unconfigured (dormant) | n/a |
| jsDelivr CDN (world-atlas TopoJSON) | Dashboard map geography | Map loses outlines offline; markers remain |

## Environment variables consumed today (from `.env.example`; values never recorded here)

- Per-provider ×3(+Cerebras dormant): `{PROVIDER}_API_KEY`, `_BASE_URL`, `_ORCHESTRATOR_MODEL`, `_COORDINATOR_MODEL`, `_REGIONAL_MODEL`, `_SERVICE_GENERATOR_MODEL`, `_ITERATION_SELECTOR_MODEL`, `_TIMEOUT_SEC`, `_MAX_RETRIES`
- Routing/cache: `LLM_PROVIDER_ORDER` (default `groq,openrouter,google`), `LLM_CACHE_ENABLED`, `LLM_429_COOLDOWN_SEC`, `LLM_REQUEST_TIMEOUT_SEC`
- Optimization knobs: `GA_POPULATION_SIZE` (80), `GA_GENERATIONS` (120), `MILP_TIME_LIMIT` (120)
- Declared-but-dead knobs (read by nobody): `LLM_PROVIDER_FAILURE_THRESHOLD`, `LLM_ENABLE_PROVIDER_FAILOVER`, `LLM_ENABLE_DETERMINISTIC_FALLBACK`

## Maritime flag namespace (RESERVED — not added to config in Phase 0)

`MARITIME_INTELLIGENCE_ENABLED`, `MARITIME_TRAFFIC_ENABLED`,
`MARITIME_PORT_INTELLIGENCE_ENABLED`, `MARITIME_CONGESTION_ENABLED`,
`MARITIME_WEATHER_ENABLED` (+ documented sub-knobs in INTEGRATION_BOUNDARIES.md).
These names are reserved for future phases; introducing any of them requires a
CHANGE_CONTROL entry naming its first consumer.

## Change procedure for any future dependency

1. Justify in the phase PR: what it does, why stdlib/existing deps are insufficient.
2. Confirm it is NOT imported by any module under `src/optimization/`, `src/pipeline/`,
   `src/utils/`, `src/validation/`, `src/services/`, `src/decomposition/`, `src/data/`
   unless the change is a sanctioned Tier-2 pattern extension.
3. Network-capable libraries are permitted ONLY inside ingestion tooling / providers layer,
   never in optimizer modules (enforced by `tests/architecture/test_network_isolation.py`).
4. Update this file; re-run full regression suite + golden run; attach both results.
