# Protected Component Registry

**Phase:** 0 (Architecture Lock & Regression Baseline)
**Baseline commit:** `a44b987` (`main`, synced with `origin/main`)
**Date:** 2026-08-26
**Evidence standard:** every classification below was verified against working-tree source during Phase 0. Line numbers refer to the Phase 0 working tree and are re-checkable via the anchors given.

This registry classifies system components into four protection tiers. It is the
authoritative reference for what future phases (maritime intelligence et al.) may
and may not modify. Companion documents:
[`INTEGRATION_BOUNDARIES.md`](INTEGRATION_BOUNDARIES.md) (where extension is allowed),
[`CHANGE_CONTROL.md`](CHANGE_CONTROL.md) (process for any change),
[`PHASE_0_BASELINE.md`](PHASE_0_BASELINE.md) (measured baseline).

---

## Tier definitions

| Tier | Meaning | Change rule |
|---|---|---|
| **TIER 0** | Absolutely protected. System integrity depends on it. | **No modification by feature work — ever.** Changes require explicit product-owner approval + full recertification + dedicated migration note. |
| **TIER 1** | Controlled extension. Behavior-defining defaults and tuned policies. | Extend only additively with recalibration evidence; never silently retune existing values. |
| **TIER 2** | Safe extension. Established patterns exist; additive change is low-risk. | Follow the established pattern; contract tests must still pass. |
| **TIER 3** | Future / deferred. Not yet implemented; reserved space only. | Nothing to protect yet; creation is governed by INTEGRATION_BOUNDARIES.md. |

---

## TIER 0 — ABSOLUTELY PROTECTED

### T0-1 · Iteration selection policy — `src/pipeline/iteration_selection.py`
The system's integrity guarantee: *the best candidate wins, and the LLM can never overrule the math.*
- `DEFAULT_SCORING_WEIGHTS` (:72–76): `weekly_profit 0.60 / global_demand_weighted_coverage 0.25 / operating_cost 0.15`.
- `OBJECTIVE_DIRECTIONS` (:43–57), `PARETO_OBJECTIVES` (:61–70, 7 objectives; `services_deployed` deliberately excluded).
- `deterministic_select()` (:318+) — Pareto dominance + weighted score + tie-breakers.
- **Authority block in `select()` (:530–545):** deterministic winner is unconditionally authoritative; LLM contributes reasoning/confidence only when it agrees.
- Override rejection (:562–602 area): LLM disagreement → `iteration_selection_llm_override_rejected` log, override ignored, audited in reasoning.
- `_validate_llm_selection()` (:390+), ledger record (:608+).
Guarded by `tests/test_iteration_selection.py` (30 tests incl. live-artifact consistency checks).

### T0-2 · Iteration budget & snapshot machinery — `src/agents/orchestrator_agent.py`
- `MAX_ITERATIONS = 3`, `MIN_ITERATIONS = 3` (:27–28). Early convergence suppressed until budget met.
- Snapshot builder (:88–183): deep-copied immutable per-iteration candidates (`status/regional_results/selected_services/metrics/weights_used/...`).
- Selection glue + `best_snapshot` restore (:859–924): final network rebuilt from the **selected** snapshot, never "latest".
- Canonical coverage override (:936–945): `summary_metrics.coverage == global_demand_weighted_coverage`.
- Payload assembly (:1196–1226): top-level output contract keys (see PIPELINE_OUTPUT_CONTRACT.json).

### T0-3 · Canonical coverage definition — `src/agents/coordinator_agent.py`
- `global_demand_weighted_coverage = total_satisfied / (total_satisfied + total_unserved) × 100` (:294–300).
Cross-layer invariant asserted by the certification suite.

### T0-4 · MILP objective & constraint structure — `src/optimization/hub_milp.py`
- Objective :279–294 (`profit_expr + coverage_reward`; known caveat: reported profit includes coverage bonus).
- Constraints: per-demand conservation (:313–322), service capacity (:327–340), fleet count (:299–310), solver `PULP_CBC_CMD(msg=0, timeLimit=self.time_limit)` (:345).
- **Only exception:** the numeric capacity map INPUT (`_port_capacity_map`, :68–73 synthetic `50000 + 0.1×demand`) may be overridden behind a flag — see IP-3. Structure itself is untouched.

### T0-5 · GA mathematics — `src/optimization/service_ga.py`, `frequency_ga.py`, `hierarchical_ga.py`
- ServiceGA: binary mask encoding, fitness `evaluate()` (:162–373), elitism top-10, hard cap `MAX_RUNTIME = 90`s (:16), cached fitness.
- FrequencyGA: ints 0..3, fleet >300 ⇒ fitness −1e9 reject (:123–130 region). Known pre-existing quirks (fuel omitted from L2 objective) are documented but NOT to be "fixed" casually — any fix moves every certified number.
- HierarchicalGA orchestration + fleet prune to 300.
- Population/generations defaults live in Tier-1 config (`GA_POPULATION_SIZE=80`, `GA_GENERATIONS=120`) — the algorithm structure here is Tier 0.

### T0-6 · Router policy tables — `src/llm/providers/router.py`
- `_POLICY` (:49–61) per-error retry/cooldown/breaker matrix and `_BREAKER_THRESHOLD` (:66–79); breaker state machine CLOSED→OPEN→HALF_OPEN.
- Mirrored exactly by 15+ stub tests in `tests/test_provider_system/test_router_failover.py`.

### T0-7 · Consensus engine formulas — `src/validation/consensus_engine.py`
- Voter weights `COORDINATOR 0.40 / REGIONAL 0.40 / SERVICE_GENERATOR 0.20` (:54–56) (+ previous-consensus bonus), confidence penalties `CONFIDENCE_PER_CONFLICT 0.15` / `CONFIDENCE_UNRESOLVED_PENALTY 0.25` (:66–67), rejection floor `CONSENSUS_REJECTED_MAX 0.30` (:71).

### T0-8 · Validator clamp ranges
- `src/validation/weight_validator.py`: `MIN_WEIGHT=0.05`, `MAX_WEIGHT=0.90` (:20–21).
- `src/validation/archetype_validator.py`: `RATIO_MIN=0.05`, `RATIO_MAX=0.80` (:20–21).
These are the guardrails that make every LLM contribution safe.

### T0-9 · Output contract — field names of `pipeline_output.json`
21 top-level keys and their nested shapes consumed by `runtimeAdapter.js`, `backend/server.py`, and the certification suite. Canonical description: [`PIPELINE_OUTPUT_CONTRACT.json`](PIPELINE_OUTPUT_CONTRACT.json). Additive keys allowed (IP-5 pattern); renames/removals forbidden.

### T0-10 · Backend WS event names/shapes — `backend/server.py`
`initial_state`, `pong`, `pipeline_started`, `stage_started`, `stage_progress`, `stage_completed`, `region_update`, `pipeline_completed`, `pipeline_error` on `/ws/pipeline` (:211–605). Consumed by `frontend/src/hooks/useOptimizationState.js`. New channels are fine; existing ones are frozen.

### T0-11 · Certification assertions & calibration scalars — `tests/test_orchestrator.py`
- Exactly-3-iterations (:1075–1084), exactly-one `selected_as_final` (:1100–1107), coverage consistency (:1117–1121).
- `DEMAND_SCALE = 6` (:129); loader cost multipliers ×2.0 (`src/data/network_loader.py:44–48`).
These define what "working" means; loosening them invalidates every freeze claim.

### T0-12 · Demand pipeline semantics
Demand loading path used by production (`tests/test_orchestrator.load_problem` :103–140 → `Port/Demand` dataclasses, JSON seed `data/datasets/large_shipping_problem.json`, distance matrix from `data/raw/distance_dense.csv` via `NetworkLoader.load_distance_matrix`), scaling (×6), normalization, scenario interpretation. No maritime phase may alter demand values or scaling.

### T0-13 · Production runner identity — `tests/test_orchestrator.__main__` (:4059+)
The de-facto production entry point (documented `python -m src.pipeline.optimization_pipeline` is an empty phantom module). Its artifact-writing behavior (`<repo_root>/pipeline_output.json`, save-even-on-failure) is part of the contract until a sanctioned CLI replaces it.

---

## TIER 1 — CONTROLLED EXTENSION

| ID | Component | Anchor | Rule |
|---|---|---|---|
| T1-1 | Fuel consumption table & bunker price default | `src/utils/fuel_cost.py:20–63`, `BUNKER_PRICE_PER_TON=600.0` :62 | Defaults changeable only with recalibration evidence; IP-2 adds optional kwargs without touching defaults. |
| T1-2 | Regional economics constants | `regional_agent.py:20–24` (`TRANSSHIP_COST_PER_TEU=80`, `ALPHA_UNSERVED=300`) | Same rule. |
| T1-3 | GA hyperparameters | `Config.GA_POPULATION_SIZE=80 / GA_GENERATIONS=120` (`utils/config.py:55–56`), env-tunable | Env knobs are operational; code defaults are calibrated. |
| T1-4 | MILP time limit | `hub_milp.time_limit` (env `MILP_TIME_LIMIT`, default 120 s) | Operational tuning allowed; structure not. |
| T1-5 | Provider registry order & models | `registry.py:117–124` (`LLM_PROVIDER_ORDER` default `groq,openrouter,google`), per-role model env vars | Adding a provider follows the established adapter+registry+env pattern (Tier-2 mechanics) but changing ORDER/priority is a policy decision. |
| T1-6 | Coverage target / margin gate | `optimizer_config.py` (`min_coverage_percent=70`, `min_margin_percent=0.05`) | Feedback triggers only — never selection disqualifiers (selector policy is T0-1). |

## TIER 2 — SAFE EXTENSION

| ID | Component | Pattern to follow |
|---|---|---|
| T2-1 | Provider adapters (`groq/openrouter/google/cerebras_provider.py`) | Thin OpenAI-compatible wrappers; register in `registry.py`; add env keys `{PROVIDER}_API_KEY/_BASE_URL/_{ROLE}_MODEL/_TIMEOUT_SEC/_MAX_RETRIES`. |
| T2-2 | Validator rules | Clamp philosophy welcomes additional bounded rules; ranges themselves are T0-8. |
| T2-3 | Scripts runners (`scripts/*.py`) | Offline tooling; extend freely, keep network use out of optimizer modules. |
| T2-4 | Frontend leaf components / new tabs | `navItems.js` entry + view component reading normalized state; `runtimeAdapter.js` passes unknown fields through. |
| T2-5 | Additive payload fields | IP-5 pattern: new top-level keys inert to all existing consumers (verified `??`-chain tolerance). |
| T2-6 | Backend REST additions beside existing block | `server.py` read-only local-file handlers; no synchronous ingestion in request paths. |

## TIER 3 — FUTURE / DEFERRED

| ID | Reserved for | Notes |
|---|---|---|
| T3-1 | Maritime ingestion daemon + stores (`data/maritime/*`) | Separate process; never imported by optimizer at runtime. See INTEGRATION_BOUNDARIES.md §Network Isolation. |
| T3-2 | Feature adapter (`maritime/feature_adapter.py`) | The only maritime→optimizer contact point (IP-1), flag-gated. |
| T3-3 | Maritime REST surface (`/api/maritime/*`, optional `/ws/maritime`) | Read-only, store-backed, degrade-don't-error. |
| T3-4 | Dashboard maritime overlays/views | Leaf components + one nav entry; layers default OFF. |

---

## Explicitly NOT integration points (mirror of blueprint §13)

Consensus weights · validator clamps · MIN/MAX_ITERATIONS · anything in
`iteration_selection.py` · coordinator gdwc formula · router `_POLICY`/breaker tables ·
WS event names/shapes · certification assertions · calibration scalars
(`DEMAND_SCALE=6`, loader ×2.0, `BUNKER_PRICE_PER_TON` default, TRANSSHIP/ALPHA constants) ·
existing `pipeline_output.json` field names.

## Dead / dormant strata (do not "resurrect" casually)

`backend/routes/*` (orphaned, mock-bearing), `backend/main.py`, `backend/unified_main.py`,
`PipelineStreamer` ×2, `PipelineService`, `OptimizationService`,
`real_orchestrator_integration.py`, `src/optimization/flow_optimizer.py`,
`src/agents/regional_metrics.py`, `regional_policy_mapping.py`, `src/data/preprocess.py`,
`graph_builder.py`, `validation/regional_policy_validator_v2.py` (test-only),
`src/utils/sample.py`. Removal/rework is out of scope for maritime phases and requires its own change-control entry.

---

*Registry verified 2026-08-26 against working tree @ `a44b987` + recorded uncommitted changes
(see PHASE_0_BASELINE.md §Repository state). No source file was modified to produce this document.*
