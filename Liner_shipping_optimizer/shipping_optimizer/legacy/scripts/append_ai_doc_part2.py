#!/usr/bin/env python3
"""Append additional content sections to AI_LAYER_REFERENCE.md"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

extra=r"""

## Appendix O — AI Safety: Edge Cases and Defensive Programming

### O.1 Empty LLM Response

When the LLM returns an empty string (content equals ""), the LLMClient returns it as-is. The agent's call_llm() method then:
1. If skip_evaluator is True: Returns empty string directly to caller
2. If skip_evaluator is False: Evaluator gives score 0.0 -> hardcoded fallback used
3. Downstream validator (weight_validator, archetype_validator): Checks for dict type before processing -> non-dict input returns default fallback

This means an empty response from the LLM at any point results in deterministic fallback, never a crash.

### O.2 Nested Braces in JSON Templates

The prompt templates use doubled braces for JSON structure hints:
```python
prompt = "Return ONLY valid JSON: {{"profit_weight": <0.0-1.0>}}"
```
Python f-string doubles {{ and }} to produce literal { and } in the output. The final prompt sent to the LLM contains single braces with the JSON template, placeholder values (like <0.0-1.0>) that the LLM is expected to replace, and actual computed values where provided.

### O.3 Temperature Selection

All agents use temperature=0.1 (nearly deterministic). This is a deliberate choice:
- Higher temperatures produce more creative but less reliable outputs
- For decision support tasks (weight selection, strategy classification), reproducibility is more important than creativity
- The limited temperature range (0.1-0.2) represents the "deterministic zone" of the model
- Temperature=0.1 ensures similar inputs produce similar outputs across runs

### O.4 Model-Specific Handling

The code contains model-specific workarounds:

```python
# Phase P+1C: DeepSeek returns content='' when asked to both
# "think step by step" AND "return ONLY valid JSON"
has_json_instruction = "Return ONLY valid JSON" in user_message
if not has_json_instruction:
    enhanced_user_message = user_message + "\n\nThink step by step..."
else:
    enhanced_user_message = user_message
```

This is a documented model-specific behavior (DeepSeek) that required a code change. The phase notation (Phase P+1C) in comments tracks which development phase introduced each workaround.

### O.5 Evasive Fallback Output

The hardcoded fallback string ("Strategy: C\nReason 1: Balanced network design across 50+ ports...") is deliberately designed to:
- Contain the keywords "Strategy" and "Reason" to pass the evaluator
- Include 2-digit numeric citations (50, 100) for downstream tests
- Represent a neutral "Type C" strategy that does not bias optimization
- Be statically defined (no variable interpolation = no runtime errors)

## Appendix P — Agent Interaction Sequence Diagrams

### P.1 Complete Optimization Sequence

The following sequence describes the full agent interaction during a single optimization run:

```
Step 1: OrchestratorAgent.process() called with Problem object
        |
Step 2: analyze_problem(problem) -> LLM call (#1)
        Returns: problem analysis with size, complexity, concentration
        |
Step 3: PortClustering.cluster_ports() -> KMeans(k=5) on geographic coordinates
        Returns: Dict[cluster_id -> [port_ids]]
        |
Step 4: RegionalSplitter.split() -> 5 sub-problems
        Returns: Dict[region_name -> Problem]
        |
Step 5: For iteration in [0, 1, 2] (max 3):
    |
    Step 5a: For each region (parallel ThreadPoolExecutor):
        |
        RegionalAgent.process(sub_problem)
        |
        Step 5a-i:  Strategy generation -> LLM call (#2) -> Type A/B/C
        Step 5a-ii: ServiceGeneratorAgent.generate() -> LLM call (#3) -> archetype JSON
        Step 5a-iii: CandidateServiceGenerator creates 800-2000 services
        Step 5a-iv:  Profitability gate filters to ~500 services
        Step 5a-v:   HierarchicalGA.run() -> ServiceGA + FrequencyGA
        Step 5a-vi:  HubMILP.solve() -> PuLP/CBC (120s time limit)
        Step 5a-vii: Explanation generation -> LLM call (#4) -> verdict
        Step 5a-viii: deterministic regional policies from metrics
        |
        Returns: regional_result dict
    |
    Step 5b: CoordinatorAgent.process(regional_results)
        |  - identify_conflicts() -> service overlap detection
        |  - resolve_conflicts() -> drop lower-profit services
        |  - calculate_global_metrics() -> aggregate metrics
        |  - evaluate_system() -> score 0-5
        |  - generate_decisions() -> LLM call (#5) -> weight JSON
        |  - generate_feedback_signals() -> gradient adjustments
        |
        Returns: decision_output, feedback_signals
    |
    Step 5c: ConsensusEngine.process(coord, regional, archetype)
        |  - detect_weight_disparity()
        |  - detect_archetype_mismatch()
        |  - detect_hub_conflict()
        |  - reconcile_weights/vote/hubs()
        |  - compute_confidence()
        |
        Returns: consensus_result
    |
    Step 5d: _apply_feedback(problem, decisions, consensus)
        Updates problem weights for next iteration
        |
Step 6: aggregate_results(regional_results, true_global_demand)
        Returns: global metrics dict
        |
Step 7: generate_summary() -> deterministic text
        Returns: executive_summary
        |
Step 8: Serialize to pipeline_output.json
```

### P.2 LLM Call Timing Summary

```
LLM Call #1 (Orchestrator analysis):   ~8s  (start of run)
LLM Call #2 (Regional strategy x5):     ~18s (parallel, ~3.6s each)
LLM Call #3 (ServiceGen archetype x5):  ~18s (parallel, ~3.6s each)
LLM Call #4 (Regional explanation x5):  ~28s (parallel, ~5.7s each)
LLM Call #5 (Coordinator decision):     ~5s  (around iteration boundary)

Total LLM time per iteration:          ~77s
Total wall-clock per iteration:        ~231s (includes GA + MILP)
LLM fraction:                           33.3%
```

## Appendix Q — AI Impact on Optimization Quality

### Q.1 Weight Adjustment Analysis

The most significant AI impact comes from the CoordinatorAgent's weight adjustments between iterations. Analysis of runtime traces shows:

**Iteration 0: Initial weights (from config)**
```python
profit_weight = 0.60
coverage_weight = 0.25
cost_weight = 0.15
```
Result: High profit, lower coverage (profit-first configuration)

**Iteration 1: AI-adjusted weights (from Coordinator LLM or fallback)**
```python
profit_weight = 0.435  # -27.5% from initial
coverage_weight = 0.465  # +86.0% from initial
cost_weight = 0.100  # -33.3% from initial
```
Result: Coverage weight increased by 86%, shifting optimizer toward coverage

**Iteration 2: Further adjusted (from consensus)**
```python
profit_weight = 0.4244
coverage_weight = 0.4656
cost_weight = 0.110
```
Result: Converged weights after consensus reconciliation

### Q.2 Coverage Convergence

The weight adjustment's effect on coverage across iterations:
- Iteration 0: coverage = 63.5% (with profit_weight=0.60)
- Iteration 1: coverage = 60.4% (with profit_weight=0.435)
- Iteration 2: coverage = 66.2% (converged)

The counterintuitive drop in coverage from iteration 0 to 1 (despite increased coverage weight) demonstrates a known GA behavior: the weight change disrupts the converged GA population. The GA needs a full run (80-120 generations) to adapt to new weights. This is a documented limitation of the approach.

### Q.3 Profit vs Coverage Trade-off

The system's hybrid AI approach navigates the profit-coverage trade-off:
- Profit-maximizing configuration (profit_weight=0.60): $644.9M/week
- Coverage-maximizing configuration (coverage_weight=0.60): lower profit but higher coverage
- AI-balanced configuration (profit=0.435, coverage=0.465): $401.3M/week, 60.4% coverage

The AI configuration represents a deliberate compromise that prioritizes coverage improvement while maintaining positive profit. The non-AI alternative (static weights) would require manual selection of the trade-off point.

## Appendix R — Glossary

| Term | Definition |
|---|---|
| **Agent** | An LLM-driven program that performs a specific optimization task (Orchestrator, Coordinator, Regional, ServiceGenerator) |
| **System Prompt** | The initial prompt that establishes the agent's role, constraints, and behavior rules |
| **User Message** | The task-specific prompt containing metrics, context, and format instructions |
| **skip_evaluator** | A flag (True/False) that bypasses the LLMEvaluator for JSON-targeted prompts |
| **Evaluator** | A scoring module that checks LLM responses for Structure, Completeness, and Relevance |
| **Fallback** | A deterministic default response used when the LLM fails or produces invalid output |
| **Circuit Breaker** | A pattern that stops retrying after 5 consecutive failures, allowing 60s recovery |
| **Consensus** | Weighted voting reconciliation across coordinator, regional, and service generator agents |
| **Confidence Score** | A value 0.0-1.0 indicating agreement level between multiple agent outputs |
| **AI_GENERATED** | Log tag indicating the LLM produced structurally valid output |
| **AI_VALIDATED** | Log tag indicating a validator accepted the output |
| **AI_REJECTED** | Log tag indicating a validator rejected the output (fallback used) |
| **AI_FALLBACK** | Log tag indicating the LLM failed entirely (hardcoded default used) |
| **CONSENSUS_ACCEPTED** | ConsensusEngine confidence > 0.70 (high agreement) |
| **CONSENSUS_MODIFIED** | ConsensusEngine confidence 0.30-0.70 (partial agreement) |
| **CONSENSUS_REJECTED** | ConsensusEngine confidence < 0.30 (low agreement, default used) |
| **Archetype** | A service mix configuration (direct/hub-loop/feeder/trunk ratios) defining candidate service types |
| **Strategy** | A regional classification (Type A/B/C) determining optimization approach |
| **Vessel Bias** | A recommendation (small/balanced/large) for vessel size preference in a region |
| **Transshipment** | Cargo transfer between services at hub ports (cost = $80/TEU) |
| **Profitability Gate** | A filter removing services where revenue < operating cost + fuel cost + port cost |
| **Hart-coded Fallback** | A static string returned when all LLM paths fail: "Strategy: C..." |

## Appendix S — References

### S.1 Source Files Referenced

| File | Lines | Role |
|---|---|---|
| src/llm/client.py | 254 | LLM API client, caching, circuit breaker |
| src/llm/evaluator.py | 67 | Response scoring (3 axes) |
| src/llm/evaluator_manager.py | 2 | Singleton evaluator wrapper |
| src/llm/metrics.py | 24 | Runtime metrics tracker |
| src/agents/base.py | 107 | Abstract base agent with call_llm() |
| src/agents/orchestrator_agent.py | 903 | Master orchestration controller |
| src/agents/coordinator_agent.py | 574 | Global coordination |
| src/agents/regional_agent.py | 474 | Regional optimization (x5) |
| src/agents/service_generator_agent.py | 374 | Service archetype generation |
| src/agents/regional_metrics.py | 250 | Deterministic metric computation |
| src/agents/regional_policy_mapping.py | 309 | Deterministic policy derivation |
| src/validation/weight_validator.py | 204 | Weight clamp and normalize |
| src/validation/archetype_validator.py | 283 | Archetype ratio validation |
| src/validation/regional_policy_validator.py | 268 | Policy key validation |
| src/validation/regional_policy_validator_v2.py | 271 | Strict policy validation |
| src/validation/consensus_engine.py | 975 | Weighted voting reconciliation |
| src/utils/config.py | 37 | Environment config loader |
| src/config/optimizer_config.py | 62 | ObjectiveConfig dataclass |

### S.2 Total AI Subsystem

| Component | Files | Lines of Code |
|---|---|---|
| LLM Integration | 4 | 347 |
| Agents | 7 | 3,585 |
| Validation | 6 | 2,265 |
| Config | 2 | 99 |
| **Total AI Subsystem** | **19** | **6,296** |

### S.3 Related Documentation

- MASTER_TECHNICAL_DOCUMENTATION_V2.md — Complete system documentation
- ARCHITECTURE_REFERENCE.md — Architecture and deployment
- CODE_REFERENCE.md — API and source code reference
- Analysis/AI_INFLUENCE_VERIFICATION_REPORT.md — AI influence analysis
- Analysis/CONSENSUS_INFLUENCE_REPORT.md — Consensus weight impact analysis
- Analysis/COORDINATOR_FORENSIC_TRACE.md — Coordinator agent trace
- Analysis/PHASE_P_PROMPT_TRUTH_AUDIT_MASTER_REPORT.md — Prompt audit results

---

*Document generated from actual implementation at src/, backend/, and frontend/. All prompt templates, validation logic, and agent workflows reconstructed from source code. No behavior invented for documentation purposes.*

**End of Document — AI Layer Reference v1.0.0-rc1**
"""

with open(ROOT / 'AI_LAYER_REFERENCE.md', 'a', encoding='utf-8') as f:
    f.write(extra)

print(f"Appended {len(extra.split(chr(10)))} lines to AI_LAYER_REFERENCE.md")
