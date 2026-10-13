# Integration Boundaries

**Phase:** 0 (Architecture Lock & Regression Baseline) · **Date:** 2026-08-26 · **Baseline:** `a44b987`

This document defines the ONLY places where future maritime intelligence may touch the
optimizer. It formalizes the integration points (IP-1/2/3/5) defined in
`MARITIME_INTELLIGENCE_INTEGRATION_BLUEPRINT.md` §12 and locks them against the verified
source of record in [`PROTECTED_COMPONENTS.md`](PROTECTED_COMPONENTS.md).

**Phase 0 status: none of these hooks exist yet. Nothing below has been implemented.
This document is the contract future phases must satisfy.**

---

## Hard architectural rules (apply to every boundary)

1. **Network isolation.** The optimizer never performs network ingestion.
   Allowed direction:
   ```
   EXTERNAL SOURCE → INGESTION PROCESS (separate daemon/offline)
     → NORMALIZATION → VALIDATION → SNAPSHOT STORE (data/maritime/*)
     → FEATURE ADAPTER → OPTIMIZER (reads local snapshot only)
   ```
   Forbidden: `OPTIMIZER → HTTP → EXTERNAL API`. Verified Phase 0 state: zero direct
   network imports anywhere under `src/`; the only outbound-capable code is the LLM
   provider layer (`src/llm/providers/*` via OpenAI SDK), which is existing sanctioned
   behavior and is NOT a maritime data path. Enforced by `tests/architecture/test_network_isolation.py`.
2. **Flags OFF ⇒ baseline.** With all maritime flags off/unset, behavior must be
   indistinguishable from the Phase 0 baseline (same schema, same selection authority,
   same math). Golden test: `tests/architecture/test_output_contract.py`.
3. **Failure ⇒ deterministic baseline.** Source failure / stale data / invalid data /
   network failure during ingestion must never surface inside the optimizer: the adapter
   ships `None`/absent features, and each consumer falls back to its exact pre-maritime code path.
4. **No new dependencies.** Ingestion tooling may not add imports to any module the
   optimizer imports.
5. **Additive output only.** One new optional payload key (`maritime_intelligence`, IP-5).
   Existing keys frozen per PIPELINE_OUTPUT_CONTRACT.json.

---

## IP-1 — Pre-loop feature attach (gateway hook)

| Aspect | Specification |
|---|---|
| **Exact location** | `src/agents/orchestrator_agent.py` → `OrchestratorAgent.process()`, immediately after the objective-weight application block (~:430–436), before demand capture (~:449) and the iteration loop |
| **Current behavior** | No attribute exists; `Problem` carries only ports/services/demands/distance_matrix/weights |
| **Future intended behavior** | `if MARITIME_INTELLIGENCE_ENABLED: problem.maritime_features = FeatureAdapter.snapshot(problem_ports)` — one read-only attribute attach per run; `snapshot()` reads **local store only**, wall-clock budget-capped (≤5 s) |
| **Flag required** | `MARITIME_INTELLIGENCE_ENABLED` (master; default false). Sub-flags gate downstream consumption individually |
| **Failure behavior** | Adapter exception or budget breach ⇒ attach skipped/partial + `MARITIME_BUDGET_EXCEEDED` telemetry; pipeline continues with absent attribute = exact baseline path |
| **Rollback mechanism** | Flag off (Level 1); remove attach block (Level 2); revert PR (Level 3) |
| **Regression test requirement** | Flags-off golden equality (schema + selection fields identical); flags-on attach produces attribute exactly once per run |

## IP-2 — Dynamic bunker price & weather speed factor (fuel path)

| Aspect | Specification |
|---|---|
| **Exact location** | `src/utils/fuel_cost.py::calculate_weekly_fuel_cost` (:115–162); default constant `BUNKER_PRICE_PER_TON = 600.0` (:62) remains the fallback; caller forwarding at `service_ga.py:224–229` |
| **Current behavior** | Fuel cost computed from consumption table × cycle time × constant 600 $/ton |
| **Future intended behavior** | Optional kwargs `bunker_price_per_ton: float | None = None`, `weather_speed_factor: float | None = None`; forwarded from `problem.maritime_features` only when present; GA fitness cache key gains a feature-set hash while active so cached values can't leak across world-states |
| **Flag required** | `MARITIME_WEATHER_ENABLED` / bunker-price sub-flag under master |
| **Failure behavior** | Missing/invalid feature ⇒ kwarg stays `None` ⇒ constant-600 path, bit-identical math |
| **Rollback mechanism** | Flag off ⇒ defaults restore baseline numerics; kwargs are additive so removal is trivial |
| **Regression test requirement** | `None` kwargs reproduce legacy fuel numbers to float equality; GA structure/operators/caps untouched |

## IP-3 — Congestion-aware MILP port capacity override

| Aspect | Specification |
|---|---|
| **Exact location** | `src/optimization/hub_milp.py::_port_capacity_map` (:68–73, synthetic `50000 + 0.1×demand`), consumed by capacity constraints (:342–343) |
| **Current behavior** | Synthetic per-port throughput caps derived from port demand share |
| **Future intended behavior** | Optional constructor param `port_capacity_override: dict[str,float] | None = None`; when provided (only for ports whose congestion confidence ≥ floor): `cap = base_cap × (1 − κ·score)`, κ = `MARITIME_CONGESTION_CAP_KAPPA` (default 0.3); objective/constraint STRUCTURE (:279–294, :299–310) untouched |
| **Flag required** | `MARITIME_CONGESTION_ENABLED` (+ master); confidence floor `MARITIME_CONGESTION_MIN_CONFIDENCE` (default 0.6) |
| **Failure behavior** | Absent override ⇒ synthetic formula unchanged; non-"Optimal" MILP status continues to zero out that cluster's result exactly as today |
| **Rollback mechanism** | Flag off ⇒ param `None` ⇒ byte-equivalent constraint set |
| **Regression test requirement** | Override `None` ⇒ identical model file/variable set; solver time limit untouched |

### IP-4 — Regional-agent pass-through (passive, no signature change)

`src/agents/regional_agent.py` merely forwards the same `Problem` object into
HierarchicalGA construction (~:199–210) and hub-cluster MILP calls (~:226–275);
constants `TRANSSHIP_COST_PER_TEU` / `ALPHA_UNSERVED` (:20–24) untouched. Attribute
absent ⇒ behavior identical. Documented here because the blueprint defines it;
no independent flag required beyond IP-1/IP-2/IP-3 sub-flags.

## IP-5 — Additive maritime_intelligence output boundary

| Aspect | Specification |
|---|---|
| **Exact location** | `src/agents/orchestrator_agent.py` return-dict assembly (:1196–1226) — add ONE optional key `"maritime_intelligence"` after selection completes |
| **Current behavior** | Payload contains exactly the 20 orchestrator keys (+`test_scorecard` from runner); unknown keys are inert to consumers (runtimeAdapter `??` chains — verified pattern; backend copies whole documents) |
| **Future intended behavior** | Freshness map, congestion table w/ confidences, weather-window summary, provenance/attribution strings, `synthetic` echo — post-selection decoration only |
| **Flag required** | Master `MARITIME_INTELLIGENCE_ENABLED`; key omitted entirely when off |
| **Failure behavior** | Any upstream failure ⇒ key omitted or carries explicit `degraded_reasons`; never fabricated fresh labels |
| **Rollback mechanism** | Flag off omits key; consumers unaffected either way |
| **Regression test requirement** | Contract test asserts frozen key set unchanged and treats `maritime_intelligence` as the single permitted extra |

---

## Flag strategy (documented now, introduced later)

```
MARITIME_INTELLIGENCE_ENABLED=false        # master — false ⇒ ALL IPs inert
MARITIME_TRAFFIC_ENABLED=false             # EMODnet/NOAA density features
MARITIME_PORT_INTELLIGENCE_ENABLED=false   # port calls / port intelligence
MARITIME_CONGESTION_ENABLED=false          # IP-3 overrides
MARITIME_WEATHER_ENABLED=false             # IP-2 speed factor
```

Expected semantics (all documented as future requirements — do not add env vars to
production config until a phase has a concrete consumer):

| Condition | Behavior |
|---|---|
| FLAGS OFF | Byte-comparable baseline optimizer behavior |
| FLAGS ON | Maritime intelligence becomes additive (fitness/capacity fidelity + payload block) |
| SOURCE FAILURE | Deterministic baseline behavior for affected features |
| STALE DATA | Deterministic baseline behavior (stale ⇒ not shipped as fresh) |
| INVALID DATA | Dropped at validation ⇒ deterministic baseline behavior |
| NETWORK FAILURE | Ingestion-side only; optimizer sees missing features ⇒ baseline |

## Rollback ladder

| Level | Action | Effect |
|---|---|---|
| 1 | Set flags OFF | Immediate return to baseline numerics & schema; no redeploy |
| 2 | Remove maritime adapter/modules | Optimizer tree returns to pre-maritime import graph (network-isolation test still passes) |
| 3 | Revert the integration PR | One focused PR per IP (blueprint §21 ordering); no entanglement with Tier-0 logic |
| 4 | Restore baseline commit `a44b987` (+ recorded uncommitted state, see PHASE_0_BASELINE.md) | Full restoration of Phase 0 state |

Design rule: **no future maritime feature may require destructive modification of
Tier-0 files.** If an implementation finds itself editing Tier-0 logic, the design is wrong — stop and re-plan at the boundaries above.
