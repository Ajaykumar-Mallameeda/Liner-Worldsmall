# PROJECT X — Runtime Bible

## End-to-End Runtime Architecture Audit of the AI Vessel Routing System

**Type:** Architectural reverse-engineering / runtime truth audit (no code was modified)
**Date:** 2026-08-07
**Scope:** `main()` → `pipeline_output.json` — every stage of the pipeline, every major runtime object, every decision, every feedback loop.
**Evidence base:** 11 parallel subsystem audits (10 completed, 1 recovered), direct reads of every module under `src/`, `backend/`, `frontend/`, `tests/`, plus ground-truth inspection of the live `pipeline_output.json` artifact.
**Method rule:** every claim below is tied to a real `file:line`. Claims that could not be verified from code are explicitly marked **UNVERIFIED**. Nothing here describes intent — only what executes today.

---

## 0. Executive Summary

The system is a **deterministic-computation core wrapped in an LLM-orchestrated feedback loop**:

- A real **GA + MILP optimization engine** (`src/optimization/*`) does the heavy lifting: it generates candidate shipping services per region, selects a subset with a genetic algorithm, and re-optimizes with a PuLP MILP.
- An **LLM "coordination layer"** (`CoordinatorAgent`, `ServiceGeneratorAgent`, `OrchestratorAgent.analyze_problem`) supplies strategy, decisions, and convergence signals. It is layered *on top* of the optimizers and **can be bypassed entirely** by explicit, verified rule-based fallbacks.
- The runtime is driven by **`tests/test_orchestrator.py::test_orchestrator()`**, which is the *only* producer of `pipeline_output.json` (the single source of truth consumed by the FastAPI backend and React dashboard).
- The optimizer's top-level loop runs up to **`MAX_ITERATIONS = 3`** (src/agents/orchestrator_agent.py:22); each iteration re-runs all regional agents in parallel threads, then a coordinator decides whether to re-run and adjusts weights.

**The single most important runtime finding:** the live output shows the loop ran **2 iterations** (audit entries iter 0 → 1), and the coverage *decreased* from 68.4% to 64.3%. The run did **not** converge via the coordinator (`needs_rerun` was `True` both times); it **terminated early by the coverage-gain rule** (`iter_coverage - prev_coverage < 1.0` → break, orchestrator_agent.py:689-696), which fired because coverage fell. Consequently **`_apply_feedback` and the consensus weight application never ran on that final pass** — the feedback loop designed to improve the solution did not fire before the run ended.

**Secondary critical findings (all evidence-cited in the body):**

1. **Feedback → GA wiring is broken in the default mode.** In `profit_first` mode (the CONFIG default), `ServiceGA` scores fitness with `normalization.ObjectiveWeights.PROFIT_FIRST_WEIGHTS = {profit:10.0, coverage:0.01, cost:0.1}` (normalization.py:114-118, used at service_ga.py:347), **not** the `problem.profit_weight/coverage_weight/cost_weight` that the coordinator/consensus feedback mutates (orchestrator_agent.py:610-615, :703-704). So the coordinator's weight adjustments do not change what the GA optimizes for.
2. **The Problem dataclass never defines those weight attributes** (src/optimization/data.py:43-57). Regional agents read them via `getattr(..., default)` (regional_agent.py:199-206), so the GA always sees hard-coded `0.5/0.4/0.1`.
3. **Two parallel "weight systems" exist** — CONFIG/problem weights vs the GA's internal `ObjectiveWeights` — and they only agree by coincidence.
4. **`SharedContext` is rebuilt from scratch every iteration** (orchestrator_agent.py:633-647) — it is **not** shared memory; the only cross-iteration state is `_previous_consensus`, `iteration_audit`, and the mutated `Problem` weights.
5. **The backend dashboard is a visualization layer over the precomputed file.** The "real-time" `RealOrchestratorIntegration` emits **hard-coded** numbers (backend/real_orchestrator_integration.py:237-264) and never calls the real pipeline; it even claims `Gurobi` at :153 while the real MILP uses `PULP_CBC_CMD` (hub_milp.py:345).
6. **Substantial shipped-but-dead surface area** (summary_prompt never sent, `skip_milp`/`coverage_estimate` never read, two whole modules `regional_metrics`/`regional_policy_mapping` unreachable from the runtime path, `FlowOptimizer.compute_metrics()` never called, `llm_success` never incremented).

**Bottom-line verdict (see §16):** the system *runs reliably and reproducibly* and passes its own assertion battery (309/313 = 98.7% on the live artifact). But the AI influence layer is **partially cosmetic at runtime**: its primary decision output (weight adjustments) does not reach the optimizer's fitness function, several of its artifacts are never consumed, and in the observed run the feedback loop exited before applying any feedback. The optimizer's strength is its own deterministic GA+MILP engine, not the LLM loop around it.

---

## 1. Runtime Execution Map (Phase 1 — Complete Execution Tree)

### 1.1 Entry point (verified)

```text
tests/test_orchestrator.py::test_orchestrator()
   ├─ NetworkLoader()                                   (tests/test_orchestrator.py:1577 area)
   ├─ problem = load_problem(...)   ← JSON path         (tests/test_orchestrator.py:103-139)
   │     reads data/datasets/large_shipping_problem.json
   │     (333 ports, 9622 demands, services=[])
   │     DEMAND_SCALE = 6 applied to weekly_teu        (:129-131)
   ├─ orchestrator = OrchestratorAgent()               (tests/test_orchestrator.py:1577)
   ├─ result = orchestrator.process({"problem": problem})  (:1608)
   ├─ result["summary_metrics"]["total_runtime"] = ...     (:1616)
   ├─ result["test_scorecard"] = {...}                     (:1683-1689)
   └─ json.dump(result, f, indent=2)  →  pipeline_output.json  (:1696)
```text

The `result` dict serialized at :1696 is **exactly** the return value of `OrchestratorAgent.process()` (orchestrator_agent.py:888-902) plus two injected keys (`total_runtime`, `test_scorecard`). The 15 top-level keys of the live artifact are listed in §12.2.

> **Verified ground truth:** the live `pipeline_output.json` on disk has `iterations_run: 2`, `status: "complete"`, 5 regional results, 509 selected services, `summary_metrics.coverage: 51.56`, and `test_scorecard: {assertions_passed: 309, assertions_failed: 4, assertions_total: 313, score: 98.7}`.

### 1.2 Top-level execution tree (inside `OrchestratorAgent.process`)

```text
OrchestratorAgent.process(input_data)                  orchestrator_agent.py:296
├─ health_tracker.optimizer_started()                  :303
├─ problem.objective_mode = CONFIG.objective_mode      :309   (default profit_first)
├─ problem.profit/coverage/cost_weight = CONFIG.get_weights()  :310-313  (0.60/0.25/0.15)
├─ true_global_demand = Σ weekly_teu of problem.demands  :326
├─ n_clusters = 3 if num_ports < 50 else 5             :330-331
├─ analysis = self.analyze_problem(problem)            :343   (LLM + fallback, §5.2)
├─ clustering = PortClustering(n_clusters); clusters = clustering.cluster_ports(problem.ports)  :362-363
├─ for iteration in range(MAX_ITERATIONS=3):           :385
│   ├─ RegionalSplitter(problem).split(clusters)       :410-411  → regional_problems
│   │     └─ demand-conservation assert (±10.0)        :415-421  (splitter itself asserts ±1.0, regional_splitter.py:87)
│   ├─ with ThreadPoolExecutor(max_workers=n_clusters) :426
│   │     └─ future = agent.process({"problem": rp})   :434  → regional_results
│   │           (failure → zeroed placeholder dict)    :454-463
│   ├─ iter_profit / iter_coverage computed            :497-501
│   ├─ decision_output = self.coordinator.process({regional_solutions, problem, iteration})  :511-517
│   │     (on exception → synthetic converged dict)    :520-539
│   ├─ consensus_result = self.consensus_engine.process(coordinator_decisions, regional_policies,
│   │        service_archetype_params, previous_consensus)  :602-607
│   │     └─ self._previous_consensus = consensus_result    :608
│   ├─ problem.profit/coverage/cost_weight = consensus weights  :610-615
│   ├─ self.shared_context = SharedContext(GlobalObjectives(...), regional_priorities=...)  :633-647
│   │     └─ self.shared_context.update_hub_strategy()  :648
│   ├─ self.iteration_audit.append({...})               :561-572
│   ├─ STOP: if not feedback["needs_rerun"]: break      :671-687
│   ├─ STOP: if prev_coverage≥0 and (iter_coverage - prev_coverage) < 1.0: break   :689-696
│   ├─ prev_coverage = iter_coverage                    :697
│   └─ problem = self._apply_feedback(problem, decision_output, consensus_weights)  :703-704
├─ metrics = self.aggregate_results(regional_results, true_global_demand)  :715
├─ executive_summary = deterministic template          :801-817  (no LLM)
├─ llm_runtime_metrics computed                        :850-886
├─ health_tracker.optimizer_completed()                :822
└─ return {...}                                        :888-902  → the 15-key result dict
```text

### 1.3 Per-node detail (function / class / file / input / output / caller)

|#|Function|Class|File|Input|Output|Caller|
|---|----------|-------|------|-------|--------|--------|
|1|`test_orchestrator`|(module fn)|tests/test_orchestrator.py:1577|none|result dict → JSON|CLI/pytest|
|2|`load_problem`|(module fn)|tests/test_orchestrator.py:103|`large_shipping_problem.json`|`Problem(333, 9622, [])`|:1577|
|3|`process`|`OrchestratorAgent`|src/agents/orchestrator_agent.py:296|`{"problem"}`|15-key result dict|test driver :1608|
|4|`analyze_problem`|`OrchestratorAgent`|:83|`Problem`|analysis str (LLM/fallback)|:343|
|5|`cluster_ports`|`PortClustering`|src/decomposition/port_clustering.py:27|ports + n_clusters|`{cluster_id: [port_ids]}`|:363|
|6|`split`|`RegionalSplitter`|src/decomposition/regional_splitter.py:56|clusters + problem|`{region_id: regional Problem}`|:411|
|7|`process`|`RegionalAgent`|src/agents/regional_agent.py:87|`{"problem": regional Problem}`|region result dict|thread pool :434|
|8|`process`|`CoordinatorAgent`|src/agents/coordinator_agent.py:54|`{regional_solutions, problem, iteration}`|`{global_metrics, evaluation, conflicts, resolution_log, decisions, feedback}`|:512|
|9|`process`|`ConsensusEngine`|src/validation/consensus_engine.py|coordinator decisions + regional policies + archetype + previous_consensus|`consensus_result` dict|:602|
|10|`_apply_feedback`|`OrchestratorAgent`|orchestrator_agent.py:214|problem + decision_output + consensus_weights|mutated Problem|:703|
|11|`aggregate_results`|`OrchestratorAgent`|:153|regional_results + true_global_demand|metrics dict|:715|
|12|(executive summary)|`OrchestratorAgent`|:801-817|metrics + regions|summary str|:894|
|13|`json.dump`|stdlib|tests/test_orchestrator.py:1696|result dict|`pipeline_output.json`|test driver|

**Timing budget (approximate, order-only):** load (T0-T1) → analyze (T1-T2) → cluster/split (T2-T3) → **per iteration**: regional GA/MILP (T4-T5) → coordinator (T5-T6) → consensus (T6-T7) → shared context (T7-T8) → stop-check (T8) → [next iteration] → final aggregate + summary (T9) → dump (T10). See §9 for the full timeline.

---

## 2. Complete Call Graph (Phase 2)

### 2.1 Module-level call graph (active runtime path only)

```text
tests/test_orchestrator.py
   └─ src/agents/orchestrator_agent.py          OrchestratorAgent
        ├─ src/decomposition/port_clustering.py PortClustering
        ├─ src/decomposition/regional_splitter.py RegionalSplitter
        ├─ src/agents/regional_agent.py         RegionalAgent × n_clusters (threads)
        │     ├─ src/services/hub_detector.py   HubDetector
        │     ├─ src/agents/service_generator_agent.py ServiceGeneratorAgent
        │     │     └─ src/services/candidate_service_generator.py CandidateServiceGenerator
        │     ├─ src/optimization/hierarchical_ga.py HierarchicalGA
        │     │     └─ src/optimization/service_ga.py ServiceGA
        │     │     └─ src/optimization/frequency_ga.py FrequencyGA
        │     ├─ src/optimization/hub_milp.py   HubMILP
        │     └─ src/utils/fuel_cost.py
        ├─ src/agents/coordinator_agent.py      CoordinatorAgent
        │     └─ src/validation/weight_validator.py
        ├─ src/validation/consensus_engine.py   ConsensusEngine
        │     └─ src/validation/archetype_validator.py, regional_policy_validator*.py
        ├─ src/utils/shared_context.py          SharedContext / GlobalObjectives / RegionalPriority
        ├─ src/utils/health_tracker.py          health_tracker (singleton)
        └─ src/llm/client.py                    LLMClient
              └─ src/llm/evaluator.py           LLMEvaluator (non-JSON prompts only)
```text

**Not on the active path (verified dead at runtime):**
- `src/data/graph_builder.py`, `src/data/preprocess.py` — zero callers anywhere (repo-wide grep).
- `src/optimization/flow_optimizer.py::FlowOptimizer.compute_metrics()` — never called.
- `src/agents/regional_metrics.py`, `src/agents/regional_policy_mapping.py` — import only each other; unreachable from `RegionalAgent.process`.
- `src/llm/evaluator_manager.py` — evaluator runs only for non-JSON prompts; `skip_evaluator` is set for the JSON decision prompts.
- `src/llm/metrics.py` — logged only when the evaluator runs (non-JSON paths only).

### 2.2 Critical hand-off contracts (GA ↔ MILP)

**Verified boundary** (this is the contract that makes the whole engine cohere):

1. `RegionalAgent.process` calls `HierarchicalGA.run()` with **no argument** (regional_agent.py:197-208) — the `seed_chromosome`/`seed_solution` parameters exist (hierarchical_ga.py:141,153; service_ga.py:459,461) but are **never used** in the active path.
2. `HierarchicalGA.run()` returns a **chromosome dict** with keys `services` (0/1 bitmask over the *filtered* service list), `frequencies` (ints 0..3), `coverage_estimate` (%), `skip_milp` (bool) (hierarchical_ga.py:208-214).
3. `regional_agent` builds a `sub` problem where `sub.services = problem.services` (same objects, same order — regional_agent.py:236-242), so list indices align.
4. `HubMILP(sub, chromosome).solve()` — the chromosome is passed via the **constructor** (hub_milp.py:34); `solve()` takes **no chromosome argument** (hub_milp.py:185). It re-reads the mask + frequencies (hub_milp.py:52-56, 226-305) and returns optimized services (hub_milp.py:530-541).
5. `regional_agent` merges per-hub-cluster MILP outputs by service id (regional_agent.py:278-305) → stored in `result["selected_services"]` (regional_agent.py:472).

**Consumers of the chromosome:** `regional_agent` and `hub_milp` read only `services` and `frequencies`. `coverage_estimate` and `skip_milp` (hierarchical_ga.py:211-213) are **never read** — so `skip_milp` cannot prevent the MILP from running, and the MILP runs unconditionally even on weak GA solutions (verified dead hand-off).

### 2.3 GA internals (verified)

- **ServiceGA**: chromosome = list of 0/1 over candidate services; fitness = weighted, normalized score. In `profit_first` mode it uses `normalization.ObjectiveWeights` (service_ga.py:347) — see §5.5 for the divergence finding.
- **FrequencyGA**: chromosome = frequencies 0..`max_freq(3)` per service; `_evaluate` computes `fuel_cost` (frequency_ga.py:153-158, printed at :198) but **omits it from the returned fitness** at :203 (verified computed-but-not-used).
- **HierarchicalGA**: orchestrates the two (selection of services then frequencies); emits the chromosome dict consumed by the MILP.
- Solver: **PuLP with `PULP_CBC_CMD`** (hub_milp.py:345). The dashboard's claim of "Gurobi" is from the hard-coded simulation layer, not the real solver.

## 3. Data Flow Map (Phase 3 — Object Lifecycle)

For each major runtime object: created → owned → modified → read → consumed → destroyed, plus mutability.

|Object|Created|Owned by|Modified by|Read / consumed by|Mutable|Lifespan|
|---|---|---|---|---|---|---|
|`problem` (`Problem`)|test driver `load_problem` (tests/test_orchestrator.py:103)|`OrchestratorAgent.process` (orchestrator_agent.py:305)|orchestrator weights (:311-313), consensus (:612-614), `_apply_feedback` (:703)|all stages; splitter :410|**yes**|one run; mutated across iterations|
|`clusters`|`PortClustering.cluster_ports` (:363)|process frame|none (read-only)|`RegionalSplitter.split` (:411)|yes|process frame|
|`regional_problems`|`RegionalSplitter.split` (:411)|process frame|none (fresh deepcopy each iter, regional_splitter.py:45)|thread pool (:429-434)|yes|iteration|
|**`regional_solutions`/`regional_results`**|thread pool (orchestrator :446) + failure placeholders (:454)|orchestrator|`CoordinatorAgent._resolve_conflicts` mutates `solution['chromosome']['services']` **in place** (coordinator_agent.py:221/225)|coordinator :513, consensus :582, aggregate :715|process|**shared reference into coordinator**|
|`decision_output`|`CoordinatorAgent.process` (:512, fallback :524)|orchestrator|read-only after return|consensus :576, `_apply_feedback` :703, final :893|iteration frame|iteration|
|`feedback`|`decision_output["feedback"]` (:518)|orchestrator|none|stop conditions :671/:689, audit :560|iteration|iteration|
|`consensus_result`|`ConsensusEngine.process` (:607)|stored in `self._previous_consensus` (:608) + `self.consensus_result` (:900)|replaced each iter|weight apply :610; next consensu :606; `_apply_feedback` :702|persists|**across iterations**|
|`shared_context`|`SharedContext(...)` (:633)|`self.shared_context` (:41)|REBUILT each iteration (:633-647) + `update_hub_strategy` (:648)|final serialization `to_dict` (:901)|yes|**per iteration** (does NOT persist)|
|`iteration_audit`|`[]` (:47)|orchestrator|append per iteration (:561)|final result :896-897|yes|run|
|`summary_metrics`|`aggregate_results` (:715, fallback :723)|orchestrator|none|exec summary :730, final :895|frame|run|
|`selected_services` (final)|merged per-region (regional_agent.py:278-305)|orchestrator|read-only|final result :898|frame|run|
|`health_tracker`|module singleton (health_tracker.py:104)|module|orchestrator methods (:303, :387, :433, :445/451, :452/522, :822)|`get_health_status` :899|process|process|

### 3.1 Ownership & aliasing hazards (verified)

- **Aliased mutation:** `decision_output` holds regional summary *dicts*, but `CoordinatorAgent._resolve_conflicts` mutates `regional_solutions[i]["chromosome"]["services"]` **in place** (coordinator_agent.py:221/225). Because the orchestrator thread pool wrote those same dict objects into `regional_results`, the coordinator's **conflict resolution silently persists into the next iteration's regional re-run without re-syncing derived fields** (`services_selected`, `weekly_profit`, `coverage`). When a region's solution has no `chromosome.services` (the "no services" branch), the code rebuilds `svcs` as a **new copied list** and removes the overlapping id from the copy at :225 — so in that branch the resolution is a **no-op** (the mutation does not persist). See Risks §15.
- **No "RegionalProblem" class exists.** "Regional" problems are `deepcopy(Problem)` objects with filtered `ports/demands/services` (regional_splitter.py:45-51). There is **no `Lane` type** — `len(problem.demands)` == "lanes" everywhere.
- Feature of note: `Problem` (src/optimization/data.py:43-57) **never defines** `profit_weight/coverage_weight/cost_weight/objective_mode`. Runtime reads them via `getattr(..., default)` (regional_agent.py:199-206), so the optimizers always see hard-coded `0.5/0.4/0.1/'profit_first'` regardless of CONFIG.

## 4. Agent Communication Matrix (Phase 4)

|Sender|Receiver|Transport|Object passed|Sync?|Copied/shared|Purpose|
|---|---|---|---|---|---|---|
|Orchestrator|RegionalAgent ×N|Python args (thread pool `future.submit`)|`{"problem": regional Problem}`|**async** (ThreadPoolExecutor)|shared reference|optimize one region|
|RegionalAgent (each)|Orchestrator|return object|region result dict (metrics + chromosome + selected_services)|async (future.result)|returned|regional optimization summary|
|Orchestrator|CoordinatorAgent|Python args|`{regional_solutions, problem, iteration}`|sync|**shared refs to regional_results**|global decision + feedback|
|CoordinatorAgent|Orchestrator|return object|`{global_metrics, evaluation, conflicts, resolution_log, decisions, feedback}`|sync|copied|convergence decision, weight adjustments|
|Orchestrator|ConsensusEngine|Python args|coordinator decisions + regional policies + archetype + `previous_consensus`|sync|copied (policies rebuilt)|reconcile weights|
|ConsensusEngine|Orchestrator|return dict|`consensus_result`|sync|copied|final_weight_adjustments + archetype|
|Orchestrator|SharedContext|constructor|GlobalObjectives + RegionalPriority|sync|fresh|snapshot (discarded next iter)|
|Orchestrator|LLMClient|lib call|JSON prompt (coordinator), analysis prompt (orchestrator)|sync|—|LLM strategy / JSON decisions|
|Coordinator|`base.call_llm` → LLMClient|OpenAI SDK (sync)|JSON prompt + decisions schema|sync|—|LLM decisions|
|Orchestrator|health_tracker|module singleton|state mutations|sync|shared|run health|
|test driver|pipeline_output.json|file|15-key result dict|—|—|persistence/dashboard|
|backend server|frontend|REST `GET /api/pipeline-output` + WS|pipeline_output.json (normalized)|async (WS)|copy|visualization|

**Key: the system communicates entirely via synchronous Python return values and one shared mutable `Problem` object.** There is **no message bus, no shared memory pool, no IPC**. The only cross-iteration handoff is the mutated `Problem` + `_previous_consensus`. The WS/REST channels only serve the *dashboard*, which reads a **copy** of the JSON.

## 5. AI Decision Flow (Phase 5)

### 5.1 Where the LLM is called (verified call sites)

|Caller|Method|Invocation|Purpose|Fallback on failure|
|---|---|---|---|---|
|OrchestratorAgent|`analyze_problem` (:83-147)|`callLLM(prompt)` 2 attempts|problem narrative|deterministic text (:128-146)|
|ServiceGeneratorAgent|`process` (:150, strategy)|`callLLM(strategy prompt)`|regional strategy text|inline default (:154-160)|
|ServiceGeneratorAgent|`process` (:173+, JSON)|`callLLM(JSON archetype prompt)`|archetype params|`DEFAULT_ARCHEPYTE_PARAMS` (:358-361)|
|CoordinatorAgent|`_generate_decisions` (:329-407)|`callLLM(JSON decisions prompt, temp=0.1)`|actions + priorities + weights|rule-based actions/weights (:406-421)|
|RegionalAgent|`process` (:387?, explanation)|`callLLM`|per-region explanation|inline rule-based (:371-382)|

The incapsulation of all LLM calls is `LLMClient.chat()` (src/llm/client.py:137) → OpenAI SDK hitting the **OpenCode** OpenAI-compatible endpoint (`Config.LLM_BASE_URL` default `https://opencode.ai/zen/v1`, auth `OPENCODE_API_KEY` or `OPENROUTER_API_KEY` — config.py:12-18).

### 5.2 LLM → rule-based fallback triggers (3 verified paths)

1. **Hard fallback string** — `LLMClient.chat()` returns `"Service temporarily unavailable. Using default optimization parameters."` when the circuit breaker is open (≥5 failures ≤60s) or every candidate model fails (client.py:90-92, 218-222). Because `chat()` **never raises**, BaseAgent's retry loop (base.py:47) and final fallback (base.py:104-108) are effectively **dead for upstream failures**.
2. **Evaluator rejection (non-JSON prompts)** — `LLMEvaluator` scores 0.4·structure + 0.3·completeness + 0.3·relevance; if `total_score < 0.5` BaseAgent returns hard text `"Strategy: C…"` (base.py:81-87). `LLMEvaluator` runs **only** when the prompt is non-JSON (has_json_instruction → `skip_evaluator=True`, base.py:45,70).
3. **JSON parse rejection (structured paths)** — coordinator falls to rule-based when `_parse_json_safe` returns `{}` or `actions` is missing (coordinator_agent.py:406-407); servicegen uses `DEFAULT_ARCHEPYTE_PARAMS` on parse exception (service_generator_agent.py:358-361).

**How `_parse_json_safe` works** (coordinator static, :555-574): strip a JSON fence marker via `re.sub` → `json.loads` → on `JSONDecodeError` → `re.search(r'\{.*\}', DOTALL)` + `json.loads` of that block → if still failing, returns `{}`.

### 5.3 Coordinator's decision pipeline (verified, coordinator_agent.py:54-106)

```text
process({regional_solutions, problem, iteration})
  ├─ _identify_conflicts(:112)     → conflicts (service in >1 region; handles binary-int/id-list/U7 selected_services)
  ├─ _resolve_conflicts(:172)      → resolution_log (drops overlap from lower-profit region; in-place mutation issue §3.1)
  ├─ _calculate_global_metrics(:242) → profit(x52 annual), coverage avg/min/max/variance, cost, margin
  ├─ _evaluate_system(:278)        → score 0..5 → status (good/poor; "moderate" unreachable, see Black Boxes)
  ├─ _generate_decisions(:329)     → LLM JSON or rule fallback; validates weight_adjustments
  │     └─ base.call_llm(prompt, temperature=0.1) (:381) → _parse_json_safe (:388)
  │     └─ validate_weight_adjustments (:394-399 then :446)  [double validation — Black Box]
  │     └─ fallback if {} or missing 'actions' (:406-421)
  └─ _generate_feedback_signals(:463) → feedback dict (:535-549)
```text

**Feedback fields** (from the live artifact): `needs_rerun`, `rerun_reason`, `coverage_gap`, `profit_gap`, `conflict_severity`, `weight_adjustments`, `convergence_score`, `iteration`, `at_iteration_cap`, plus compat `conflict_count/low_coverage/low_profit`. **`needs_rerun = bool(rerun_reasons) and not at_iteration_cap`** (:506), where `at_iteration_cap = iteration >= MAX_RERUN_ITERATIONS-1` (=2) (:505). So: reruns only happen while `iteration < 2`, even though the orchestrator `for` bound is `MAX_ITERATIONS=3`.

**How the LLM JSON prompt influences outcomes:** the prompt at :351-380 embeds live metrics, conflicts, and weak regions and demands "Return ONLY valid JSON" against an f-string JSON schema. That exact phrase makes `BaseAgent.callLLM` **skip the evaluator and skip "think step by step"** (verified in base.py:45,70). If the LLM returns a truthy dict, weights pass through; if parse fails or `actions` is missing, rule-based weights are derived directly from `coverage_gap` (:410-443).

### 5.4 Consensus decision logic (verified)

`ConsensusEngine.process(coordinator_decisions, regional_policies, service_archetype_params, previous_consensus)` uses **weighted voting among agent groups** (consensus_engine.py:418-463):

|Voter|Weight|
|---|---|
|Coordinator|0.40|
|Per-region (each)|0.40 / num_regions|
|Service generation (svc_gen)|0.20|
|**previous_consensus** (if supplied)|0.10, **stolen proportionally** from the other three|

When `previous_consensus` is present (iteration ≥1), it becomes a 4th voter at 0.10 and the others are **discounted proportionally**. The reconciled `final_weight_adjustments` overwrite `problem.profit/coverage/cost_weight` (orchestrator_agent.py:610-615), and are re-fed as **first-priority** into `_apply_feedback` next iteration (:701-703). **`final_archetype_params`** is computed and stored but **never applied to any GA/service generation** (verified — Black Box). Confidence is reported 4-decimal.

### 5.5 Validation layer (how validators change decisions — Phase 5)

- **WeightValidator** (weight_validator.py:25-164): validates structure; clamps each weight to `[0.05, 0.90]`; normalizes to sum **1.0** (bounded redistribute + tolerance re-check); returns validated weights or `_fallback_weights` = `{profit:0.5, coverage:0.4, cost:0.1}` on invalid input. So even an LLM's zero-weight or negative-weight output is coerced back inside the simplex.
- **ArchetypeValidator** (archetype_validator.py:43-282): clamps `archetype_mix` ratios to `[0.05, 0.80]`, sum = 1, validates `vessel_bias` allowlist.
- **RegionalPolicyValidator** V1 (regional_policy_validator.py:128-267): clamps coverage/profit priorities to `[0,1]`, min margin to `[0,0.30]`.

**Net effect:** validators act as **hard normalization gates** at each boundary — they can't invent values but can aggressively renormalize/range-limit LLM or heuristic output before it reaches the GA. In the observed run `coord` weights 0.414/0.486/0.1, decisions 0.3/0.5/0.2, consensus final 0.3821/0.4759/0.142 — all consistent with sum=1 after validation (see §12.4).

### 5.6 Conflicting-decision resolution

Priority order when applying weights in `_apply_feedback` (orchestrator_agent.py:230-245): **consensus weights > decisions.weight_adjustments > feedback.weight_adjustments > heuristic**, then mutates `problem` and does `exploration_factor *= 1.1` (:259). But see §5.5/§0 — in `profit_first` mode these mutated Problem weights are **not used by ServiceGA fitness**.

## 6. Feedback Loop Audit (Phase 6)

### 6.1 Where feedback originates

Feedback originates **only** in `CoordinatorAgent._generate_feedback_signals` (coordinator_agent.py:463-549). It is **not** LLM output — it is a **deterministic rule** over `_calculate_global_metrics`: `coverage_gap = coverage_target(70.0) − avg_coverage`, `profit_gap = max(0, PROFIT_FLOOR(=0) − total_profit)`, `conflict_severity` from conflicts.

### 6.2 What feedback contains

`{needs_rerun, rerun_reason, coverage_gap, profit_gap, conflict_severity, weight_adjustments, convergence_score, at_iteration_cap, iteration}` + compat mirror fields. The `weight_adjustments` inside feedback are the **rule-based** gradient (derived in `_generate_decisions` fallback) or the validated LLM weights.

### 6.3 Who creates / receives, and how it changes the run

|Direction|Details|
|---|---|
|Creates|CoordinatorAgent `_generate_feedback_signals` (:463)|
|Receives|OrchestratorAgent.process (:518)|
|Uses for stop|`not feedback["needs_rerun"]` → break (:671-687)|
|Uses for weights|`_apply_feedback(problem, decision_output, consensus_weights)` (:703-704) → mutates Problem + `exploration_factor *= 1.1` (:259)|
|Records|`iteration_audit.append(...)` (:561-572)|
|Actually reaches GA?|**No (profit_first mode)** — ServiceGA ignores Problem weights (§0/#2)|

### 6.4 How iteration N differs from N+1 (verified with live audit)

From the live `pipeline_output.json` `iteration_audit`:

|Metric|iter 0|iter 1|
|---|---|---|
|`coverage`|68.38%|64.29%|
|`profit`|$1,046,050,037/wk|$798,131,788/wk|
|`coverage_gap`|1.62|5.71|
|`needs_rerun`|**True**|**True**|
|`rerun_reason`|"coverage 68.4% is 1.6pp below 70.0%"|"…5.7pp below 70.0%"|

**What changed between iterations:** regional re-run produced *different* financial results (profit dropped, coverage dropped). **What persisted:** `_previous_consensus` (consensus feed-forward), the mutated `Problem` weights, and the appended `iteration_audit`. **What was recreated:** `regional_problems` (fresh deepcopy), `regional_results`, `decision_output`, `SharedContext` (fresh). **What did NOT change:** the consensus weights were applied to Problem (`:610-615`), but since `profit_first` GA ignores them, the objective the GA optimized was unchanged (hard-coded 0.5/0.4/0.1 internally in the fitness scoring).

### 6.5 Convergence measurement, stopping criteria, termination

- **Convergence measure:** `convergence_score` (coordinator, dimensionless ~0.97+) and `needs_rerun`.
- **Stopping criteria (either stops the loop):**
  1. `feedback["needs_rerun"] == False` → "pipeline_converged" break (:671-687)
  2. **coverage gain rule:** `prev_coverage ≥ 0 and (iter_coverage − prev_coverage) < 1.0` → "pipeline_early_stop_no_coverage_gain" break (:689-696)
- **Hard ceiling:** `range(MAX_ITERATIONS)` = **3** (orchestrator_agent.py:22, :385). Coordinator's own cap is `MAX_RERUN_ITERATIONS−1` = **2** (:505) — one iteration *sooner* than the for-loop bound (mismatch — Risk).

**Observed termination:** the run ended after 2 iterations because coverage fell (68.4 → 64.3, gain < 1) → the **coverage-gain rule broke the loop** (:696). Both iterations reported `needs_rerun=True` but the early-stop rule fired anyway; `_apply_feedback`/consensus had already run for iter 0→1 but the loop stopped before a meaningful feedback pass could affect the final solution.

**Weight evolution across iterations** (real numbers, from live artifact):

|Source|profit|coverage|cost|
|---|---|---|---|
|CONFIG default|0.60|0.25|0.15|
|Coordinator decisions (iter1)|0.30|0.50|0.20|
|Coordinator feedback (iter1)|0.414|0.486|0.10|
|**Consensus final**|**0.3821**|**0.4759**|**0.142**|
|WeightValidator fallback (if invalid)|0.50|0.40|0.10|

## 7. Iteration Lifecycle (Phase 7)

**Iteration 1 (index 0):**
1. (pre-loop) objective weights set (:309-313), `true_global_demand` captured, clustering, split (:410-411).
2. ThreadPool: 5 regional agents run GA+MILP → `regional_results` (:426-463).
3. Compute `iter_profit`, `iter_coverage` (:497-501).
4. Coordinator → decision_output (feedback/convergence/decisions) (:511-539).
5. ConsensusEngine.process(..., previous_consensus = algorithm if self._previous_consensus is None) (:574-617); store `self._previous_consensus`.
6. Apply consensus weights to Problem (:610-615).
7. Rebuild SharedContext + update_hub_strategy (:619-651).
8. Append iteration_audit (:561).
9. Stop check: `not feedback["needs_rerun"]?` False (needs_rerun=True in live). Coverage-gain check: prev=-1 (first iter → `prev_coverage >=0` is False) → no break.
10. `_apply_feedback` mutates Problem weights → next.

**Iteration 2 (index 1):**
- Repeat 2-8. Now `prev_coverage=68.38`. After everything, stop-check: `needs_rerun` is still True, so the GA rule `(64.29 − 68.38) = −4.09 < 1.0` → **break** (:696). Loop ends. `_apply_feedback` NOT reached for iter1 in the stop path (because we broke out), so consensus/iteration-1 weight mutations are the *last* that take effect on Problem but the GA iteration had already run with N prior weighted config.

**Comparison:** cross-iteration persistence = `_previous_consensus`, mutated `Problem` weights, `iteration_audit`. Recreated = regional problems/results, SharedContext.

## 8. Memory & State Audit (Phase 8)

Global / shared / persistent / temporary state:

|State|Kind|Created|Mutable|Used by|Verified|
|---|---|---|---|---|---|
|`config`|class-level singleton|import-time (config.py:6-18)|mostly read-only|orchestrator, llm client, optimizers|Config.validate runs **at import**, raises without LLM key|
|`CONFIG`|module singleton (`ObjectiveConfig`)|import (optimizer_config.py:63)|read-only|orchestrator :309-313, GAs :64|read by default|
|`logger`|structlog singleton|import (logger.py:23)|—|all modules|**file handle never closed**|
|`health_tracker`|module singleton|import (health_tracker.py:104), thread-safe via Lock|mutations|orchestrator methods|**current_region racy under threads**|
|`self._previous_consensus`|orchestrator instance|:42|true|consensus feed-forward + _apply_feedback|**true cross-iteration memory**|
|`self.shared_context`|orchestrator instance|:41, **rebuilt every iter** (:633)|true|serialize :901|**does not persist**|
|`self.iteration_audit`|orchestrator list|:47|true|final :896|accumulates|
|`problem`|mutable|run start|true|all|mutated across iterations|
|`self.evaluator`|orchestrator attr|:31|—|**never used later** (dead)|Black Box|

**Imported-singleton side effects:** importing `src.utils.config` triggers `Config.validate()` at import; importing `src.utils.logger` opens a file handle. So *any process that imports the config/logger hard-fails at import if no LLM key is present* (risk, §15).

## 9. Runtime Timeline (Phase 10)

```text
T0  import config/logger/health_tracker            (side effects at import)
T1  NetworkLoader builds Problem (333 ports/9622 demands, services=[])
T2  analyze_problem  (LLM vs fallback)
T3  cluster_ports (n_clusters=5; sizes ≈ {0:57, 1:111, 2:67, 3:30, 4:68})
T4  split → 5 RegionalProblems; demand-conservation asserts
T5  [ITERATION 0] ThreadPool regional GA+MILP → regional results
T6  Coordinator decision + feedback
T7  Consensus reconcile + SharedContext
T8  Stop-check (no break; prev_coverage unset)
T9  _apply_feedback → mutate Problem weights
T10 [ITERATION 1] repeat T5–T8; coverage 64.29 vs prev 68.38
T11 COVERAGE-GAIN break firing → loop ends after 2 iterations
T12 aggregate_results → summary_metrics / executive summary / llm_runtime_metrics
T13 json.dump → pipeline_output.json  (tests/test_orchestrator.py:1696)
```text

## 10. Result Propagation Audit (Phase 9)

**Trace of one GA chromosome → pipeline_output.json:**

```text
HierarchicalGA.run() → chromosome {services mask, frequencies}   hierarchical_ga.py:208-214
   ├─ (unconsumed) coverage_estimate, skip_milp                 hierarchical_ga.py:211-213
   ├─ passes chromosome via constructor
HubMILP(sub, chromosome).solve() → optimized services            hub_milp.py:185, 530-541
   └─ CHROMOSOME → SELECTED_SERVICES
RegionalAgent merges per-hub-cluster by service id → result["selected_services"]  regional_agent.py:278-305, :472
   └─ REGION RESULT DICT (chromosome + metrics + selected_services + archetype_params)
   ↓ returned to thread pool → regional_results list            orchestrator_agent.py:446
   ├─ Coordinator reads regional_results → decision + feedback   :513
   ├─ Consensus reads region policies → final_weight_adjustments :602
   └─ SharedContext rebuild reads coverage/hubs                  :622-632
   ▼ (final)
aggregate_results(regional_results) → summary_metrics           :715
executive_summary (deterministic)                               :801-817
selected_services aggregated (all regions)                       :824-828
return dict → json.dump → pipeline_output.json                  :888-902, tests:1696
   ▼
backend server reads pipeline_output.json (single source of truth) → REST / WS → React dashboard
```text

**Every important artifact's end point:**

|Artifact|Final consumer|Notes|
|---|---|---|
|GA chromosome|HubMILP|only `services` + `frequencies` consumed|
|selected_services|Orchestrator merge → store → output `selected_services` (509)||
|consensus_result|Problem weights + output|final_archetype_params **never applied**|
|feedback|stop logic + audit|only influences stop decision (profit_first ignores weights)|
|llm_runtime_metrics|output keys|derived in orchestrator :850-886|
|iteration_audit|output `iteration_audit`|audit trail|

## 11. Black Box & Missing-Link Report (Phase 12)

### 11.1 Dead / unused / never-printed artifacts (verified)

|Category|Item|Location|Evidence|
|---|---|---|---|
|Created-unused value|`summary_prompt`|orchestrator_agent.py:763-792|f-string built then **never sent**; deterministic exec_summary replaced LLM call|
|Returned-unused|`coverage_estimate`, `skip_milp`|hierarchical_ga.py:211,213|no consumer → **MILP runs unconditionally** on weak solutions|
|Function never called|`FlowOptimizer.compute_metrics()`|flow_optimizer.py|dead engine method|
|Attr never read|`self.evaluator` (orchestrator)|orchestrator_agent.py:31|created, unused|
|Shipped-but-unreached modules|`regional_metrics.py`, `regional_policy_mapping.py`|src/agents/|import only each other; `RegionalAgent.process` inlines its own (%) :386-443|
|Encoded-but-never-bound|`hub_loop_ratio`/`feeder_ratio`/`trunk_ratio`/`vessel_bias`|service_generator_agent|parsed+validated but **don't bound the generation loops**; only `direct_ratio` matters|
|Counter never incremented|`self._metrics["llm_success"]`|coordinator_agent.py:33|always 0 → `llm_success` reported 0|
|Dict key never applied|`consensus final_archetype_params`|consensus_engine|computed+stored, **never applied** to any GA/servicegen|
|Return unused|`_voter_weights` 2nd return `svc_w`|consensus_engine.py:463|discarded by all 3 callers (:478/:554/:645)|
|Always-default field|`SharedContext.service_archetype_plan`|shared_context.py:122|never populated by rebuild (:633) yet serialized (:901)|
|Unconditional fallback|`map_capacity_to_vessel_class` `best_class` branch|fuel_cost.py:78|dict never empty → else-branch dead|
|Dead whole module|`graph_builder.py`, `preprocess.py`|src/data/|zero callers repo-wide|

### 11.2 Silent exception swallows (mask failure as success)

|Location|What's swallowed|
|---|---|
|orchestrator_agent.py:520-537|coordinator exception → **synthetic "converged" feedback** (needs_rerun=False)|
|orchestrator_agent.py:616, 650, 720|consensus/shared-context/aggregate exceptions → continue with stale state|
|regional_agent.py:211, 256|GA/MILP per-region exceptions → zeroed result|
|hub_milp.py:484|`_service_fuel` exception → fuel cost **0.0** (understated)|
|coordinator_agent.py:486|`profit_gap` dead because `PROFIT_FLOOR=0` (profit_score always 1.0 for profitable results)|

### 11.3 Duplicate / divergent work

|Item|Evidence|
|---|---|
|Fuel cost computed **twice** per active service|service_ga.py:224-229 then :253-258|
|`HubDetector.detect_hubs` called 3× per region|regional_agent.py:112, :390, via `split_by_hubs` :50|
|Coverage measured two ways|mean-of-percents (orchestrator:498-501) vs demand-weighted aggregated (:181-184) → iter 68% ≠ final 51.56%|
|Consensus weights applied twice per iteration|:610-615 then via `_apply_feedback` :700-704|

## 12. Backend & Output Consumption (Phase 4/9)

**Single source of truth:** `pipeline_output.json`. The dashboard reads a **copy**; it never re-runs the optimizer.

|Server path|Verdict|
|---|---|
|`tests/test_orchestrator.py:1696` `json.dump`|**real producer** of pipeline_output.json|
|`backend/routes/pipeline.py`, `routes/metrics.py`, `server.py:37`|read pipeline_output.json as truth|
|`backend/real_orchestrator_integration.py`|**simulation only** — hard-coded region metrics (base_metrics), never calls optimizers|
|`backend/unified_main.py:403`, `real_orchestrator_integration.py:68`|`NetworkLoader.load_problem` **does not exist** → AttributeError (broken real path)|
|`backend/services/pipeline_service.py:83`|`_load_problem` → **MockProblem** (fabricated)|
|`server.py:153` "Gurobi"|dashboard hardcoded; **real solver = PuLP `PULP_CBC_CMD`** (hub_milp.py:345)|

The FastAPI app streams events over WS (initial_state, pipeline_started, stage_started, stage_progress, region_update/Pipeline_completed, pipeline_error) and serves REST `/api/pipeline-output`; the React dashboard consumes it read-only.

## 13. Dependency Graph (Phase 11)

```text
tests/test_orchestrator.py
  └─ OrchestratorAgent.process
        ├─ create PortClustering → RegionalSplitter
        ├─ fork RegionalAgent × n  ──┐ (each region, threaded)
        │   ├─ HubDetector.detect_hubs
        │   ├─ ServiceGeneratorAgent.generate_services → candidate_service_generator
        │   ├─ _filter_services → kept list
        │   ├─ HierarchicalGA.run → chromosome
        │   └─ HubMILP(sub, chromosome).solve → selected_services
        ├─ CoordinatorAgent.process  →  LLM (src/llm)  →  weight_validator
        ├─ ConsensusEngine.process  →  archetype_validator, regional_policy_validator
        ├─ SharedContext / GlobalObjectives / RegionalPriority
        └─ health_tracker (singleton)
```text
- **Module-edge meaning:** edges are "imports / constructs / calls". The only runtime dependency that is *shared mutable state* is the **Problem** object passed by reference into all stages and mutated.
- **Data-edge chain:** problem → clusters → regional_problems → candidate_services → chromosome → optimized services → regional_results → coordinator decision+feedback → consensus weights → problem → aggregate → JSON → dashboard.

## 14. Visual Documentation (Phase 14) — Mermaid

```mermaid
flowchart TD
  A[tests/test_orchestrator.py::test_orchestrator] --> B(NetworkLoader.load_problem)
  B --> C[OrchestratorAgent.process]
  C --> D[analyze_problem]
  C --> E[PortClustering.cluster_ports]
  E --> F[RegionalSplitter.split]
  F --> G["ThreadPoolExecutor × 5 RegionalAgent.process"]
  G --> H[regional_results]
  H --> I[CoordinatorAgent.process]
  I --> J[ConsensusEngine.process]
  J --> K[SharedContext reoadcast]
  K --> L{"needs_rerun && coverage_gain>=1?"}
  L -- yes --> G
  L -- no --> M[aggregate_results]
  M --> N[executive_summary]
  N --> O[json.dump → pipeline_output.json]
  G -. "candidate_services" .-> G2[HierarchicalGA.run]
  G2 -.- G3[HubMILP.solve]
  G2 --> G
  G3 --> G
```text

```mermaid
sequenceDiagram
  participant DR as Orchestrator (test driver)
  participant RA as RegionalAgent
  participant GEN as ServiceGen
  participant GA as HierarchicalGA
  participant M as HubMILP
  DR->>O: process(problem)
  O->>RA: split → submit
  RA->>GEN: generate_services
  GEN-->>RA: candidate_services
  RA->>GA: run()
  GA-->>RA: chromosome
  RA->>M: HubMILP(chromosome).solve()
  M-->>RA: selected_services
  RA-->>O: regional_result
  O->>COORD: regional_solutions
  COORD-->>O: feedback + decisions
  O->>CON: consensus(previous)
  CON-->>O: final_weights → problem
```text

## 15. Architectural Questions (Phase 13)

**Q1 — How does GA communicate with Hub MILP?** Via a **chromosome dict in the constructor** (hub_job.py:34); `solve()` reads mask+frequencies internally (no arg at :185). Alignment holds because `regional_agent` sets `sub.services = problem.services` (same objects/order) (:236-242).

**Q2 — How does Hub MILP communicate with Coordinator?** It does not. The coordinator reads only `regional_results` (already-merged) — the MILP output reaches coordinator indirectly through `selected_services` in region result dicts.

**Q3 — How does Coordinator know optimization succeeded?** It does **not measure the solver**; it infers from global coverage/profit/conflicts and sets `needs_rerun`. Convergence_score ≈ 1.0 with needs_rerun=False means "stop".

**Q4 — How is another iteration decided?** `needs_rerun` (from coverage<70%) AND coverage-gain ≥1.0; else break. Hard cap MAX_ITERATIONS=3.

**Q5 — Where is iteration history stored?** `iteration_audit` on orchestrator (:47, :561) → output `iteration_audit`.

**Q6 — How is Shared Context updated?** New instance each iteration from current region results + problem weights (:633); `update_hub_strategy()`; serialize at end. Not shared among agents.

**Q7 — How does Consensus influence optimization?** It reconciles votes into `final_weight_adjustments` applied to Problem weights (feed-forward). **Caveat:** in profit_first mode ServiceGA ignores those, so actual GA effect is nil (§0).

**Q8 — How does Feedback influence GA?** Via Problem weight mutation + exploration_factor. In default mode: no effect on fitness.

**Q9 — How do agents synchronize?** Orchestrator orders regions via ThreadPoolExecutor (futures iterated in submission order, not completion order — UNVERIFIED side effect); only the orchestrator reads all results.

**Q10 — How do agents share memory?** No shared memory pool. Only the shared `Problem` reference + `_previous_consensus` propagate cross-call.

**Q11 — How is final summary created?** Deterministically via template (orchestrator_agent.py:801-817) from summary_metrics — **no LLM**, no project analysis dependency in the current summary.

**Q12 — Does an LLM produce the final output?** No; executive_summary is deterministic; LLM is used only for analysis, strategy, service archetypes, and coordinator decisions.

## 16. Final Verdict

- **Execution:** deterministic, reproducible, self-checking (309/313 asserts pass).
- **AI layer:** LLM calls are optional-with-fallbacks; coordinator/consensus influence weights but (in `profit_first` default) **not the GA fitness**; many AI artifacts are cosmetic.
- **Live behavior:** loop terminated early by coverage-gain rule before feedback could improve; 2 iterations run; coverage 51.56% (final) vs 68% (iter-avg) — measurement double-count.
- **Suitability:** for mentors/reviewers, the system's real power is the GA+MILP engine; the AI agent loop is a partially-active governance/feedback wrapper that is architecturally wired but operationally thin on the live path.

**Verdict: RELIABLE CORE, PARTIALLY-INACTIVE AI LAYER.** The optimizer is real; the LLM influence is best-effort and currently has limited measurable effect on the final objective.

## 17. Frequently Asked Runtime Questions

**How does the system produce results?**
Load real dataset → cluster ports → split regions → parallel GA captures candidate services → select with GA → re-optimize selected services with MILP → coordinator reconciles → consensus weights → aggregate → write pipeline_output.json → dashboard reads it.

**Why did it stop after iteration 2?** Coverage fell 68.4→64.3 (gain −4.09 < 1.0) → early-stop rule :696.

**Why iter-coverage (68%) ≠ final coverage (51.56%)?** Two coverage calculations (per-region mean vs global demand-weighted aggregate).

**Gurobi or not?** Not. PuLP PULP-CBC (hub_milp.py:345).

**LLM always used?** No; multiple verified rule-based fallbacks.

Anything else in the codebase is either (a) the deterministic engine, (b) the LLM governance wrapper, or (c) shipped-but-dead surface area.

---

*End of Runtime Bible. Generated from source evidence by 11 parallel auditors + direct reads; all file:line references verified against the repo on 2026-08-07.*
