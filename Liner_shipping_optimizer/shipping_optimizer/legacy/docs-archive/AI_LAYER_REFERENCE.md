# AI Layer Reference — AI Vessel Routing System

## Artificial Intelligence Integration Architecture, Prompt Engineering, and Multi-Agent Orchestration

| Field | Value |
|---|---|
| **Document Title** | AI Layer Reference — AI Vessel Routing System |
| **Version** | v1.0.0-rc1 |
| **Date** | 2026-07-11 |
| **Repository** | `Liner_shipping_optimizer/shipping_optimizer` |
| **Status** | Release Candidate 1 |
| **AI Architecture** | Multi-agent LLM orchestration with validation |
| **Primary Model** | `opencode/deepseek-v4-flash-free` |
| **Prompt Templates** | 11 distinct templates across 4 agent types |
| **Validation Layers** | 5 (weight + archetype + policy v1/v2 + consensus) |
| **AI Log Tags** | 8 (AI_GENERATED, AI_VALIDATED, AI_REJECTED, AI_FALLBACK, etc.) |

---

## Table of Contents

1. [AI System Overview](#1-ai-system-overview)
2. [AI Evolution](#2-ai-evolution)
3. [AI Architecture](#3-ai-architecture)
4. [Complete Agent Inventory](#4-complete-agent-inventory)
5. [Prompt Engineering](#5-prompt-engineering)
6. [Prompt Flow](#6-prompt-flow)
7. [Context Engineering](#7-context-engineering)
8. [LLM Providers](#8-llm-providers)
9. [AI Inputs](#9-ai-inputs)
10. [AI Outputs](#10-ai-outputs)
11. [Prompt Variables](#11-prompt-variables)
12. [AI Decision Making](#12-ai-decision-making)
13. [AI Safety](#13-ai-safety)
14. [AI ↔ Optimization Interaction](#14-ai--optimization-interaction)
15. [Runtime Execution Trace](#15-runtime-execution-trace)
16. [AI Performance](#16-ai-performance)
17. [Failure Analysis](#17-failure-analysis)
18. [AI vs Classical Optimization](#18-ai-vs-classical-optimization)
19. [Real-World Justification](#19-real-world-justification)
20. [Future AI Roadmap](#20-future-ai-roadmap)

---

## 1. AI System Overview

### 1.1 Why AI Exists in This Project

Liner shipping network optimization is a multi-commodity network design problem with fleet constraints — a known NP-hard problem class. The current test dataset contains 333 ports and 9,622 origin-destination lanes, yielding over 110,000 possible route candidates. Traditional optimization alone faces three fundamental challenges:

**Challenge 1 — Search Space Explosion.** The combinatorial space of service configurations grows exponentially with port count. A monolithic MILP formulation of the full problem would exceed solvable size for commercial solvers within reasonable time (the current pipeline allocates 120s per MILP solve per hub cluster, demonstrating the scale constraint).

**Challenge 2 — Dynamic Weight Selection.** The GA optimizer requires relative weights for profit, coverage, and cost objectives. These weights must adapt to regional demand characteristics — a profit-heavy configuration works for dense trade lanes but fails for developing markets where coverage matters more. Hard-coded weights cannot adapt across the five global regions (Asia, Europe, Americas, Middle East, Africa), each with fundamentally different demand profiles.

**Challenge 3 — Human Interpretability.** A pure optimization pipeline produces a numerical solution (service set + frequencies + flows) without explanation. Vessel routing decisions affect billion-dollar fleet deployments; operators require justification. LLM-generated explanations bridge the gap between mathematical optimization and human decision-making.

### 1.2 What Problems AI Solves

The AI layer addresses four concrete problems:

| Problem | AI Solution | Implementation |
|---|---|---|
| Adaptive weight selection | LLM generates profit/coverage/cost weights based on iteration metrics | CoordinatorAgent._generate_decisions() |
| Regional strategy classification | LLM classifies each region as Type A (direct), Type B (hybrid), or Type C (hub-dominant) | RegionalAgent strategy prompt |
| Service archetype design | LLM generates service mix ratios (direct/hub-loop/feeder/trunk) per region | ServiceGeneratorAgent archetype prompt |
| Post-hoc explanation | LLM generates human-readable verdicts with strengths/weaknesses/actions | RegionalAgent explanation prompt |

### 1.3 What Remains Deterministic

The following system components are entirely deterministic — AI has no influence:

| Component | File | Reason |
|---|---|---|
| GA population initialization | `src/optimization/service_ga.py` | Demand-proportional random seed |
| GA fitness evaluation | `src/optimization/service_ga.py` | Mathematical formula with AI-supplied weights |
| MILP flow optimization | `src/optimization/hub_milp.py` | PuLP/CBC solver, formal optimization |
| Regional metrics computation | `src/agents/regional_metrics.py` | 10 deterministic statistics |
| Regional policy derivation | `src/agents/regional_policy_mapping.py` | Rule-based mapping from metrics |
| Consensus voting | `src/validation/consensus_engine.py` | Weighted average, no AI |

**Key insight:** AI influences the *parameters* of optimization (weights, archetype ratios, strategy labels) but never the *computation* of the optimization itself. Every service selection, frequency assignment, and flow allocation is computed by GA or MILP, not hallucinated by an LLM.

### 1.4 Architecture Diagram

![AI System Architecture](docs/generated/ai/png/ai_01_overview.png){#fig:ai-overview}

**Figure 1 — AI System Architecture Overview.** This diagram shows the six-layer AI architecture: Prompt Engineering (system prompts for all 4 agent types), Context Engineering (metrics injection into prompts), LLM Client (singleton wrapper with caching and circuit breaker), LLM Provider (primary model + 4 fallback providers), Evaluator (3-axis scoring with threshold), and Validation (weight/archetype/policy validators + ConsensusEngine weighted voting).

---

## 2. AI Evolution

### 2.1 Chronological Development

The AI subsystem evolved through six distinct phases:

**Phase P (Prompt Audit, March-May 2025):** Systematically audited every LLM prompt path. Discovered that DeepSeek models return empty content when asked to both "think step by step" and "return ONLY valid JSON" simultaneously. Led to the skip_evaluator mechanism for JSON prompts (base.py:34-37).

**Phase A (Agent Activation, June 2025):** Activated all 4 agent types with LLM integration. Implemented the OrchestratorAgent problem analysis, CoordinatorAgent decision generation, RegionalAgent strategy/explanation, and ServiceGeneratorAgent archetype generation.

**Phase B (Validation Layer, July 2025):** Added all validators: weight_validator (clamp + normalize), archetype_validator (ratio constraints), regional_policy_validator (key validation), and the V2 policy validator with anti-neutrality and drift detection.

**Phase C (Consensus Engine, August 2025):** Implemented the ConsensusEngine (975 lines) with weighted voting reconciliation. Added conflict detection across weight disparity, archetype mismatch, and hub set conflicts.

**Phase D (Dashboard Integration, September 2025):** Added AI metrics display to the frontend dashboard. Integrated WebSocket events for real-time LLM call monitoring. Added AI log tag visualization.

**Phase 1.0 (Current Release, June 2026):** Final hardening with fleet constraint verification, deterministic fallback refinement, comprehensive regression testing (270/274 assertions passing).

![Project Timeline](docs/generated/assets/svg/MASTER_TECHNICAL_DOCUMENTATION_V2_mermaid_002.png){#fig:ai-timeline}

**Figure 2 — AI Evolution Timeline.** Gantt chart showing the six development phases from initial prompt audit through current release candidate.

### 2.2 Key Design Decisions

**Decision 1: Skip Evaluator for JSON Prompts.** The LLMEvaluator checks for "Strategy"/"Reason" keywords (structure score = 40% of total). JSON output never contains these keywords, causing guaranteed false rejection. JSON prompts have their own downstream validators (weight_validator, archetype_validator) that are more appropriate for structured output validation. (base.py:40-45)

**Decision 2: Deterministic Executive Summary.** The OrchestratorAgent originally called the LLM for an executive summary. The LLM response was unreliable — it returned content='' (empty string) which serialized as a Python object rather than text. This was replaced with a deterministic template (orchestrator_agent.py:791-817) that never fails. The LLM summary prompt template remains in the codebase as dead code for reference.

**Decision 3: Circuit Breaker Pattern.** After observing 5+ consecutive LLM failures during API outages, the circuit breaker was added (client.py:70-85). On 5 consecutive failures, the breaker opens for 60 seconds, rejecting all requests immediately. This prevents cascade failures and allows recovery without manual intervention.

---

## 3. AI Architecture

### 3.1 Multi-Agent Architecture

![Multi-Agent Architecture](docs/generated/ai/png/ai_02_agents.png){#fig:ai-agents}

**Figure 3 — Multi-Agent Architecture.** The four agent types (Orchestrator, Coordinator, Regional x5, ServiceGenerator) each have distinct system prompts, temperature settings, and call frequencies. Each agent calls the LLMClient singleton which handles caching, circuit breaking, and provider fallback. Outputs flow to the optimization pipeline (GA + MILP) and ConsensusEngine for validation.

### 3.2 Agent Hierarchy

```
OrchestratorAgent (line 25, src/agents/orchestrator_agent.py, 903 lines)
├── Creates: 5× RegionalAgent, 1× CoordinatorAgent
├── Creates: 1× ConsensusEngine, 1× SharedContext
├── Creates: PortClustering, RegionalSplitter
├── LLM calls: 1× analysis + 1× summary (summary now deterministic)
└── Temperature: 0.1

RegionalAgent (line 24, src/agents/regional_agent.py, 474 lines) ×5
├── Creates: ServiceGeneratorAgent, HubDetector
├── Creates: HierarchicalGA, HubMILP instances
├── LLM calls: 1× strategy + 1× explanation
└── Temperature: 0.1

CoordinatorAgent (line 18, src/agents/coordinator_agent.py, 574 lines)
├── Uses: validate_weight_adjustments from src.validation
├── LLM calls: up to 3× (once per iteration) decisions JSON
├── skip_evaluator: True
└── Temperature: 0.1

ServiceGeneratorAgent (line 16, src/agents/service_generator_agent.py, 374 lines)
├── Creates: HubDetector, CandidateServiceGenerator
├── LLM calls: 1× strategy prose + 1× archetype JSON
├── skip_evaluator: True (for JSON prompt)
└── Temperature: 0.1
```

### 3.3 LLM Integration Architecture

![LLM Client Architecture](docs/generated/ai/png/ai_06_llm_client.png){#fig:ai-llm-client}

**Figure 4 — LLM Client Architecture.** The singleton LLMClient wraps the OpenAI Python SDK with MD5 response caching, a circuit breaker (5 failures = 60s timeout), and a fallback chain across five model providers. Each provider attempt allows up to 2 retries before advancing to the next provider.

---

## 4. Complete Agent Inventory

### 4.1 OrchestratorAgent

**File:** `src/agents/orchestrator_agent.py` (903 lines)  
**Role:** Master controller of the optimization pipeline  
**Model:** `opencode/deepseek-v4-flash-free`  
**Temperature:** 0.1  
**LLM calls per run:** 2 (1 analysis, 1 summary — summary now replaced by deterministic template)  
**skip_evaluator:** False

**Purpose:** The OrchestratorAgent manages the complete optimization lifecycle. It receives a Problem object (ports + demands + fleet), analyzes it via LLM, decomposes it into 5 regional sub-problems, dispatches RegionalAgents in parallel (ThreadPoolExecutor, max_workers=5), aggregates results, and manages up to 3 iterations with feedback from the CoordinatorAgent.

**Inputs:**
- `Problem` object (`src/optimization/data.py`): ports, demands, services (initially empty), distance matrix
- `ObjectiveConfig` (`src/config/optimizer_config.py`): initial weights

**Outputs:**
- `pipeline_output.json`: Complete runtime state including all regional results, consensus result, LLM metrics
- `executive_summary`: Deterministic text report (since Phase P+1C)

**Internal workflow:**
```
process(input_data):
    1. analyze_problem(problem) — LLM call → problem_analysis text
    2. PortClustering.cluster_ports(ports) → Dict[cluster_id, port_ids]
    3. RegionalSplitter.split(clusters) → Dict[cluster_id, Problem]
    4. For iteration in 1..3:
       a. ThreadPoolExecutor(max_workers=5):
          5× RegionalAgent.process() → regional_results
       b. CoordinatorAgent.process() → decision_output
       c. ConsensusEngine.process() → consensus_result
       d. SharedContext.update_hub_strategy()
       e. _apply_feedback() → updated problem weights
    5. aggregate_results() → global metrics
    6. generate_summary() → executive_summary (deterministic)
```

**Error handling:** If analysis LLM fails (2 retries, each retried internally by LLMClient), a deterministic fallback using computed statistics is used (orchestrator_agent.py:128-146). The executive summary is always deterministic.

### 4.2 CoordinatorAgent

**File:** `src/agents/coordinator_agent.py` (574 lines)  
**Role:** Global decision agent for network-wide coordination  
**Model:** `opencode/deepseek-v4-flash-free`  
**Temperature:** 0.1  
**LLM calls per run:** ≤3 (once per iteration)  
**skip_evaluator:** True

**Purpose:** The CoordinatorAgent performs inter-regional conflict detection, system evaluation, decision generation, and feedback signal computation. It receives 5 regional solutions, identifies overlapping services, resolves conflicts (drops lower-profit services), calculates global metrics, evaluates system health (score 0-5), generates JSON-structured decisions with weight adjustments, and computes gradient feedback signals for the next iteration.

**Inputs:**
- `regional_solutions`: List[Dict] — results from 5 RegionalAgents
- `iteration`: int — current iteration number (0, 1, or 2)

**Outputs:**
- `decision_output`: Dict with `actions`, `priorities`, `weight_adjustments`, `notes`
- `feedback_signals`: Dict with `needs_rerun`, `coverage_gap`, `profit_gap`, `convergence_score`

**Internal workflow (6 stages):**
```
_process(input_data):
    1. _identify_conflicts(regional_solutions) — service overlap detection
    2. _resolve_conflicts(conflicts, regional_solutions) — drop lower-profit
    3. _calculate_global_metrics(regional_solutions) — aggregate metrics
    4. _evaluate_system(metrics, conflicts) → score 0-5, status
    5. _generate_decisions(...) — LLM call (skip_evaluator=True) → JSON
       Fallback: rule-based weight adjustment from coverage gap
    6. _generate_feedback_signals(...) — deterministic gradient computation
```

**Decision prompt:** Returns JSON with `actions` array, `priorities` array, `weight_adjustments` object (profit/coverage/cost). Validated by weight_validator.

**Metrics tracked:** `llm_calls`, `json_parse_success`, `validator_executed`, `fallback_count`

### 4.3 RegionalAgent (×5)

**File:** `src/agents/regional_agent.py` (474 lines)  
**Role:** Regional optimization analyst  
**Model:** `opencode/deepseek-v4-flash-free`  
**Temperature:** 0.1  
**LLM calls per run:** 2 (1 strategy + 1 explanation)  
**skip_evaluator:** False

**Purpose:** Each RegionalAgent optimizes a single geographic region. It receives a regional sub-problem, generates a strategy via LLM (Type A = hub-and-spoke, Type B = direct, Type C = hybrid), generates candidate services via ServiceGeneratorAgent, filters by profitability, runs HierarchicalGA optimization (ServiceGA + FrequencyGA), distributes to HubMILP for flow optimization, generates an LLM explanation of results, and derives a deterministic regional policy from computed metrics.

**Inputs:**
- `Problem` (regional sub-problem): subset of ports, demands, distance matrix
- `archetype_params`: from ServiceGeneratorAgent (or defaults)

**Outputs:**
- Regional result dict with: `selected_services`, `weekly_profit`, `coverage_percent`, `operating_cost`, `fuel_cost`, `hub_ports`, `strategy` (A/B/C), `explanation`, `regional_policy`

**Strategy prompt:** Strict format with `Strategy: <A|B|C>`, `Selected: <hub_and_spoke|direct|hybrid>`, two reasons with specific numbers, and hub ports list.

**Explanation prompt:** Strict format with `Verdict: <Good|Moderate|Poor>`, Strengths (2 items), Weaknesses (2 items), Improvement Actions (2 items).

**Error handling:** Strategy LLM has digit validation — if response has no digits, appends a computed reason. Explanation LLM has keyword validation (Verdict/Strengths/Weaknesses/Improvement + 2+ digit number). Up to 2 retries each.

### 4.4 ServiceGeneratorAgent

**File:** `src/agents/service_generator_agent.py` (374 lines)  
**Role:** Service archetype designer  
**Model:** `opencode/deepseek-v4-flash-free`  
**Temperature:** 0.1  
**LLM calls per run:** 2 (1 strategy prose + 1 archetype JSON)  
**skip_evaluator:** True (for JSON prompt)

**Purpose:** The ServiceGeneratorAgent produces service design parameters. It analyzes the regional network, generates an LLM-based archetype classification, and produces structured JSON parameters controlling the service generation ratios (direct/hub-loop/feeder/trunk), vessel bias, and hub focus.

**Inputs:**
- `Problem` (regional, filtered after profitability gate)
- Pre-computed `archetype` and `rationale` from demand analysis

**Outputs:**
- `archetype_params`: Dict with `archetype_mix`, `vessel_bias`, `hub_focus`, `notes`
- 5 categories of candidate services generated by CandidateServiceGenerator

**Archetype selection (deterministic pre-computation, lines 271-289):**
- Median demand ≤ 10 AND lanes > 1000 → HYBRID
- Top-3 share > 35% → HUB-AND-SPOKE
- Otherwise → HYBRID

**JSON archetype prompt structure:**
```json
{
  "direct_ratio": 0.05-0.80,
  "hub_loop_ratio": 0.05-0.80,
  "feeder_ratio": 0.05-0.80,
  "trunk_ratio": 0.05-0.80,
  "vessel_bias": "small|balanced|large",
  "hub_focus": ["PORT_ID", ...],
  "notes": "brief rationale"
}
```

**Error handling:** If JSON parse fails, uses DEFAULT_ARCHETYPE_PARAMS (direct=0.60, hub_loop=0.15, feeder=0.20, trunk=0.05).

---

## 5. Prompt Engineering

### 5.1 Orchestrator System Prompt

**File:** `src/agents/orchestrator_agent.py:53-60`  
**Purpose:** Establishes the agent's role as the master controller of a GA+MILP pipeline. Instructs grounded, evidence-based output.

```
"You are the Master Orchestrator of a global liner shipping network "
"optimization system built on a GA + MILP solver pipeline.\n\n"
"Your output is used directly by a Decision Agent and reviewed by "
"pipeline operators and downstream consumers. Every claim MUST be grounded in the numeric "
"data supplied. Do not generalise, hedge, or repeat the question. "
"Produce concise, evidence-based analysis only."
```

**Variables:** None (static)
**Temperature:** N/A (system prompt only)
**Design rationale:** Short, role-defining system prompt. The "no hedging" instruction is critical — LLMs naturally produce vague output ("consider optimizing the network") which is useless for downstream processing.

### 5.2 Orchestrator Analysis Prompt

**File:** `src/agents/orchestrator_agent.py:103-117`  
**Purpose:** Generate problem analysis for network decomposition.

```
Network statistics (ground truth):
  Ports: {num_ports}, Lanes: {num_lanes}, Services: {num_services}
  Total demand: {total_demand:,.0f} TEU/wk, Avg/lane: {avg_demand:,.1f} TEU
  Density: {density_ratio}%, Top-5 share: {top5_share}%

TOP-5 CORRIDORS:
{top5_text}

STRICT FORMAT:
Size: {size_label}
Complexity Drivers:
- [Driver 1 with specific statistic]
- [Driver 2 with specific statistic]
- [Driver 3 with specific statistic]
Demand Concentration: [high/moderate/low] - [one sentence implication]
Decomposition Rationale: [one sentence with ~{num_ports//3} ports per region]
```

**Variables:** `num_ports`, `num_lanes`, `num_services`, `total_demand`, `avg_demand`, `density_ratio`, `top5_share`, `top5_text`, `size_label` (Small/Medium/Large)
**Temperature:** 0.1
**Validation:** `_is_valid_analysis()` checks for 4 key headers + any digit
**Fallback:** Deterministic template using computed statistics (orchestrator_agent.py:128-146)

### 5.3 Coordinator System Prompt

**File:** `src/agents/coordinator_agent.py:39-48`  
**Purpose:** Establishes role as global decision agent.

```
"You are a global shipping network decision agent act as maritime analyst "
"from global liner shipping company.\n\n"
"You ANALYZE, DECIDE, and CORRECT — not summarise.\n\n"
"Rules:\n"
"- Every decision must cite a specific number.\n"
"- Actions must be concrete and measurable.\n"
"- Output valid JSON only when requested.\n"
"- No hedging language."
```

**Design rationale:** The three verbs "ANALYZE, DECIDE, CORRECT" are intentionally emphasized to prevent the agent from producing vague summaries. The "no hedging" rule is repeated in multiple prompts for reinforcement.

### 5.4 Coordinator Decision Prompt

**File:** `src/agents/coordinator_agent.py:351-380`  
**Purpose:** Generate structured JSON decisions with weight adjustments.

```

Global shipping network decision — iteration {iteration} results:

Metrics:
  Total profit   : ${metrics['total_profit']:,.0f}/week
  Annual profit  : ${metrics['annual_profit']:,.0f}
  Avg coverage   : {metrics['average_coverage']:.1f}%
  Min coverage   : {metrics['min_coverage']:.1f}%
  Coverage variance: {metrics['coverage_variance']:.1f}%
  Total cost     : ${metrics['total_cost']:,.0f}/week
  Profit margin  : {metrics['profit_margin_pct']:.1f}%
  Evaluation     : {evaluation['status']} (score {evaluation['score']}/{evaluation['max']})

Conflicts detected: {len(conflicts)}
Weak regions (coverage < {COVERAGE_TARGET}%): {weak_summary or 'none'}

Return ONLY valid JSON (no markdown, no preamble):
{{
  "actions": [
    {{"region": "<name>", "action": "<verb> <object>", "expected_gain": "<metric change>"}}
  ],
  "priorities": ["<priority 1>", "<priority 2>"],
  "weight_adjustments": {{
    "profit_weight":   <0.0-1.0>,
    "coverage_weight": <0.0-1.0>,
    "cost_weight":     <0.0-1.0>
  }},
  "notes": "<one sentence with specific numbers>"
}}
```

**Variables:** `iteration`, all 8 metrics, `len(conflicts)`, `weak_summary`
**Temperature:** 0.1
**skip_evaluator:** True (JSON output never passes keyword-based evaluator)
**Validation:** `_parse_json_safe()` → `validate_weight_adjustments()`
**Fallback:** Rule-based: `cov_boost = min(0.2, coverage_gap/100.0)`, then derive weights

### 5.5 Regional System Prompt

**File:** `src/agents/regional_agent.py:31-39`  
**Purpose:** Establishes regional analyst role.

```
"You are a liner shipping network optimisation analyst for the {self.region} region.\n\n"
"Your output is consumed by the Global Decision Agent for network-wide coordination.\n"
"1. Every claim must cite a specific number from the data.\n"
"2. No vague language: 'consider', 'explore', 'may', 'could potentially'.\n"
"3. Strategy reasons must name specific port IDs or TEU volumes.\n"
"4. Improvement actions must be specific and measurable."
```

**Variable:** `self.region` (Asia/Europe/Americas/Middle East/Africa)
**Design rationale:** Banned word list explicitly enumerates hedging language. Rules 3-4 enforce specificity.

### 5.6 Regional Strategy Prompt

**File:** `src/agents/regional_agent.py:134-147`  
**Purpose:** Classify region as strategy type A/B/C.

```
REGIONAL DATA - {self.region.upper()}:
  Ports: {num_ports}, Lanes: {num_lanes}, Median demand: {median_demand} TEU/lane
  Total demand: {total_demand:,.0f} TEU/wk, Top-3 share: {top3_share}%
  Hub ports: [{hub_ids_str}]

TOP-5 CORRIDORS:
{corridor_table}

DECISION RULE: {decision_rule}

STRICT FORMAT:
Strategy: <A | B | C>
Selected: <hub_and_spoke | direct | hybrid>
Reason 1: [cite median demand {median_demand} TEU/lane and >=1 port ID]
Reason 2: [cite port count {num_ports} and lane count {num_lanes}]
Hub Ports: [{hub_ids_str}]
```

**Variables:** `self.region`, `num_ports`, `num_lanes`, `median_demand`, `total_demand`, `top3_share`, `hub_ids_str`, `corridor_table`, `decision_rule`
**Temperature:** 0.1
**Validation:** `any(c.isdigit() for c in response)` — minimal check
**Fallback:** Pre-computed decision rule from demand analysis

### 5.7 Regional Explanation Prompt

**File:** `src/agents/regional_agent.py:339-361`  
**Purpose:** Generate human-readable explanation of solver results.

```
Maritime logistics analyst evaluating {self.region.upper()} region.

SOLVER RESULTS:
  Services generated/filtered/selected: {services_generated}/{services_filtered}/{services_selected}
  Weekly profit: ${profit:,.0f} | Annual: ${profit * 52:,.0f}
  Cost: Operating ${operating_cost:,.0f} | Transship ${transship_cost:,.0f} | Port ${port_cost:,.0f}
  Margin: {profit_margin_pct}% | Profit/svc: ${profit_per_service:,.0f}/wk
  Coverage: {coverage:.1f}% | Unserved: {uncovered_pct:.1f}% ({unserved_teu:,.0f} TEU/wk)
  Hub ports: [{hub_ids_str}]

TOP-5 CORRIDORS:
{corridor_table}

STRICT FORMAT:
Verdict: <Good | Moderate | Poor>
  [Cite margin {profit_margin_pct}% and coverage {coverage:.1f}%]

Strengths:
- [Cite profit ${profit:,.0f} and profit/service]
- [Cite coverage {coverage:.1f}% and satisfied TEU]

Weaknesses:
- [Cite unserved {uncovered_pct:.1f}% = {unserved_teu:,.0f} TEU/wk]
- [Cite transship ${transship_cost:,.0f} and port ${port_cost:,.0f}]

Improvement Actions:
- [Action 1: target {unserved_line}]
- [Action 2: hub [{hub_ids_str}] expansion for {uncovered_pct:.1f}% gap]
```

**Variables:** 15 regional metrics
**Temperature:** 0.1
**Validation:** `is_valid_explanation()`: "Verdict:", "Strength", "Weakness", "Improvement" + a 2+ digit number
**Fallback:** Margin-based triage (orchestrator_agent.py:128-146 style)

### 5.8 ServiceGenerator System Prompt

**File:** `src/agents/service_generator_agent.py:28-35`  
**Purpose:** Establishes service design specialist role.

```
"You are a liner shipping service design specialist.\n\n"
"Advise on service archetypes for a given port network. "
"Ground every recommendation in the network statistics provided. "
"Every statement must cite a specific number. "
"Do not use vague language. Do not repeat the question."
```

### 5.9 ServiceGenerator Archetype JSON Prompt

**File:** `src/agents/service_generator_agent.py:325-332`  
**Purpose:** Generate structured archetype parameters.

```
{prompt}

Return ONLY valid JSON (no markdown, no preamble):
{"direct_ratio": <0.05-0.80>, "hub_loop_ratio": <0.05-0.80>, 
"feeder_ratio": <0.05-0.80>, "trunk_ratio": <0.05-0.80>, 
"vessel_bias": "small"|"balanced"|"large", 
"hub_focus": ["PORT_ID", ...], 
"notes": "<brief rationale>"}
```

**Variables:** The full strategy prompt (Section 5.6 equivalent) is prepended as `{prompt}`
**Temperature:** 0.1
**skip_evaluator:** True
**Validation:** `json.parse` + `validate_archetype_params()`
**Fallback:** `DEFAULT_ARCHETYPE_PARAMS`

---

## 6. Prompt Flow

![Prompt Execution Flow](docs/generated/ai/png/ai_03_prompt_flow.png){#fig:prompt-flow}

**Figure 5 — Prompt Execution Flow.** The complete lifecycle of an LLM call through the system. Starting from agent method invocation, context collection, prompt assembly, JSON detection (which controls eval), caching check, circuit breaker check, API call with model fallback chain, response evaluation, downstream validation, and finally acceptance or fallback.

### 6.1 Execution Sequence

```
1. Agent method called (e.g., analyze_problem, generate_decisions)
2. Context collected: metrics, statistics, region data
3. Prompt assembled: system_prompt + user_message with injected variables
4. JSON detection: "Return ONLY valid JSON" in user_message?
   |-- YES: skip "think step by step" augmentation
   |-- YES: skip evaluator (JSON never contains keyword-based evaluation tokens)
   |-- NO: append "Think step by step. Follow the output format strictly."
5. LLMClient.chat() called with model, system, user_message, temperature
6. Cache check: MD5(model|system|user_message) → return cached if hit
7. Circuit breaker check: 5 consecutive failures → return fallback
8. API call: POST to LLM_BASE_URL with OpenAI-compatible format
9. Model fallback: if primary fails, try fallback 1-5 (each with 2 retries)
10. Response extracted: handle content='', tool_calls, reasoning_content
11. If not skip_evaluator: LLMEvaluator scores response
    |-- Score >= 0.5: continue
    |-- Score < 0.5: use hardcoded fallback string
12. Downstream validator: weight_validator / archetype_validator / policy_validator
    |-- Valid: accepted
    |-- Invalid: use fallback defaults
13. Response cached for future requests
```

---

## 7. Context Engineering

### 7.1 Context Sources

Every prompt is injected with context from the following sources:

| Context Source | Data | Used By |
|---|---|---|
| Problem object | Ports, Demands, Services | Orchestrator analysis |
| Regional metrics | 10 computed metrics | Regional strategy |
| Solver results | Profit, coverage, costs | Regional explanation |
| Global metrics | Aggregated profit, coverage | Coordinator decisions |
| Network statistics | Density, Top-5 share | ServiceGenerator |
| Top-5 corridors | Port pairs + TEU volume | All prompts |
| System evaluation | Score 0-5, status | Coordinator decisions |
| Hub ports | Detected hub port IDs | Regional + SvcGen |

### 7.2 Context Limits

- No prompt exceeds 2,000 tokens (max_tokens=2000 in LLMClient)
- System prompts are 150-340 characters each
- User messages vary from 500-2,000 characters depending on problem size
- Top-5 corridors are truncated to 5 items regardless of problem size (prevents context overflow)
- Hub ports are limited to detected hubs (typically 3-8 per region)

### 7.3 Token Optimization

The system uses several techniques to minimize token usage:

1. **Static system prompts** — Never re-computed per call. Cached as part of MD5 cache key.
2. **Truncated data** — Only top-5 corridors, not all lanes. Only detected hubs, not all ports.
3. **Summary statistics** — Percentages and averages instead of raw arrays.
4. **JSON structure hints** — Templates in the prompt guide the LLM to produce structured output without needing additional formatting instructions.
5. **Deterministic fallback** — When LLM fails, no tokens are wasted on retries beyond the configured limit (2 attempts per agent + 2 internal retries per model attempt).

---

## 8. LLM Providers

### 8.1 Provider Configuration

**File:** `src/llm/client.py:12-41`

| Rank | Model | Status | Latency | Context | Notes |
|---|---|---|---|---|---|
| 1 | `opencode/deepseek-v4-flash-free` | Active | ~8s | 128K | Primary model |
| 2 | `mimo-v2.5-free` | Active | ~1s | 32K | Fast fallback |
| 3 | `nemotron-3-ultra-free` | Active | ~50s | 128K | Slow but reliable |
| 4 | `qwen3.6-plus-free` | Expired | N/A | N/A | Free promo ended |
| 5 | `minimax-m3-free` | Expired | N/A | N/A | Free promo ended |

**Configuration via `.env`:**
```
OPENCODE_API_KEY=<key>
LLM_BASE_URL=https://opencode.ai/zen/v1
ORCHESTRATOR_MODEL=opencode/deepseek-v4-flash-free
REGIONAL_MODEL=opencode/deepseek-v4-flash-free
```

### 8.2 Selection Criteria

The primary model (`deepseek-v4-flash-free`) was selected based on:

1. **Zero cost** — Free-tier access for development and testing
2. **128K context window** — Sufficient for all prompts (max ~2K used)
3. **OpenAI-compatible API** — Drop-in replacement via standard SDK
4. **Multi-provider fallback** — Graceful degradation if primary unavailable

### 8.3 Trade-offs

| Factor | Primary (DeepSeek) | Fallback (Mimo) |
|---|---|---|
| Quality | Higher reasoning capability | Faster (~1s vs ~8s) |
| Reliability | Free tier sometimes rate-limited | More consistent uptime |
| JSON output | Requires skip_evaluator (returns empty if forced to "think step by step" + "return JSON") | Same SDK interface |
| Availability | 24/7 with occasional throttling | 24/7 |

### 8.4 API Configuration

```
API Type:    OpenAI-compatible (POST /v1/chat/completions)
Base URL:    Config.LLM_BASE_URL (default: https://opencode.ai/zen/v1)
Auth:        Config.LLM_API_KEY (API key in Authorization header)
Timeout:     60 seconds per request
Max retries: 2 per model in fallback chain
Max tokens:  4096 (default)
Temperature: 0.1 (all agents)
```

---

## 9. AI Inputs

### 9.1 Input Sources

Every AI input is sourced from the running optimization pipeline:

| Input | Source | Format | Example |
|---|---|---|---|
| Port count | `len(problem.ports)` | Integer | `333` |
| Lane count | `len(problem.demands)` | Integer | `9,622` |
| Total demand | `sum(d.weekly_teu)` | Float | `1,894,489 TEU/wk` |
| Average demand | total / lanes | Float | `196.9 TEU/lane` |
| Density ratio | lanes / (ports × (ports-1)/2) × 100 | Float | `17.4%` |
| Top-5 share | sum(top5 TEU) / total × 100 | Float | `31.2%` |
| Median demand | `statistics.median()` | Float | `45.0 TEU` |
| Top-3 share | sum(top3 TEU) / total × 100 | Float | `22.8%` |
| Fleet size | total vessels across classes | Integer | `501` |
| Iteration | current iteration counter | Integer | `0, 1, 2` |
| Coverage | satisfied / total demand × 100 | Float | `66.2%` |
| Weekly profit | revenue - total_cost | Float | `$773.6M` |
| Profit margin | profit / (profit + cost) × 100 | Float | `84.0%` |
| Operating cost | sum of service operating costs | Float | `$210.6M` |
| Fuel cost | sum of voyage/bunker costs | Float | `$1.68B` |
| Port cost | sum of handling + port call costs | Float | `$72.3M` |
| Transship cost | transshipment TEU × $80/TEU | Float | `$57.5M` |
| Hub ports | detected hub port IDs | List[str] | `["CNSHA", "SGSIN"]` |
| Top-5 corridors | port pairs + TEU | String table | `Port A → Port B: 50,000 TEU` |
| System score | _evaluate_system() result | Integer 0-5 | `3` |
| Conflicts | overlapping services detected | Integer | `2` |

### 9.2 Static Configuration Inputs

| Input | Source | Value |
|---|---|---|
| Coverage target | `coordinator_agent.py:22` | `70.0%` |
| Max iterations | `orchestrator_agent.py:26` | `3` |
| Fleet limit | `hierarchical_ga.py:164` | `300` |
| Transship cost | `service_ga.py:28` | `$80/TEU` |

---

## 10. AI Outputs

### 10.1 Output Types

| Output | Agent | Format | Schema |
|---|---|---|---|
| Problem analysis | Orchestrator | Structured text | Lines with `Size:`, `Complexity Drivers:`, `Demand Concentration:`, `Decomposition Rationale:` |
| Decision JSON | Coordinator | JSON | `{actions: [{region, action, expected_gain}], priorities: [string], weight_adjustments: {profit, coverage, cost}, notes: string}` |
| Regional strategy | Regional | Structured text | `Strategy: A|B|C\nSelected: ...\nReason 1: ...\nReason 2: ...\nHub Ports: [...]` |
| Regional explanation | Regional | Structured text | `Verdict: Good|Moderate|Poor\nStrengths: -\nWeaknesses: -\nImprovement Actions: -` |
| Archetype prose | ServiceGen | Free text | 2-sentence strategy confirmation |
| Archetype JSON | ServiceGen | JSON | `{direct_ratio, hub_loop_ratio, feeder_ratio, trunk_ratio, vessel_bias, hub_focus, notes}` |

### 10.2 Fallback Outputs

When LLM fails, the system uses these fallbacks:

| Expected Output | Fallback | Source |
|---|---|---|
| Problem analysis | Deterministic template from computed stats | orchestrator_agent.py:128-146 |
| Decision JSON | Rule-based from coverage gap | coordinator_agent.py:406-443 |
| Regional strategy | Pre-computed decision rule | regional_agent.py:116-132 |
| Regional explanation | Margin-based triage template | regional_agent.py:371-382 |
| Archetype JSON | DEFAULT_ARCHETYPE_PARAMS | archetype_validator.py:25 |

---

## 11. Prompt Variables

| Variable | Source | Type | Used In | Example |
|---|---|---|---|---|
| `{self.region}` | Agent init | string | Regional system + strategy | "Asia" |
| `{num_ports}` | `len(problem.ports)` | int | Orchestrator analysis | 333 |
| `{num_lanes}` | `len(problem.demands)` | int | Orchestrator analysis | 9622 |
| `{num_services}` | `len(problem.services)` | int | Orchestrator analysis | 0 (initial) |
| `{total_demand}` | `sum(d.weekly_teu)` | float | All metric prompts | 1894489 |
| `{avg_demand}` | total / lanes | float | All metric prompts | 196.9 |
| `{density_ratio}` | lanes / pairs × 100 | float | Orchestrator analysis | 17.4 |
| `{top5_share}` | sum(top5) / total × 100 | float | Orchestrator analysis | 31.2 |
| `{top5_text}` | Top 5 corridors text | string | All analysis prompts | "Port A -> Port B: 50000" |
| `{size_label}` | ports < 50 / ≤200 / >200 | string | Orchestrator analysis | "Large" |
| `{median_demand}` | `statistics.median()` | float | Regional strategy | 45.0 |
| `{top3_share}` | sum(top3) / total × 100 | float | Regional strategy | 22.8 |
| `{hub_ids_str}` | hub port IDs | string | Regional strategy | "CNSHA, SGSIN" |
| `{corridor_table}` | Top 5 formatted | string | Regional explanation | formatted table |
| `{decision_rule}` | Pre-computed rule | string | Regional strategy | "Hybrid for balanced" |
| `{profit}` | weekly profit | float | Regional explanation | 773616415 |
| `{profit * 52}` | annual profit | float | Regional explanation | 40228053557 |
| `{operating_cost}` | sum of op costs | float | Regional explanation | 210561250 |
| `{transship_cost}` | sum of transship | float | Regional explanation | 57476255 |
| `{port_cost}` | sum of port costs | float | Regional explanation | 72348689 |
| `{profit_margin_pct}` | profit / (profit+cost) × 100 | float | Regional explanation | 84.0 |
| `{profit_per_service}` | profit / services | float | Regional explanation | 1663680 |
| `{coverage}` | satisfied / total × 100 | float | All metric prompts | 66.2 |
| `{uncovered_pct}` | 100 - coverage | float | Regional explanation | 33.8 |
| `{unserved_teu}` | total - satisfied | float | Regional explanation | 644356 |
| `{services_generated}` | initial candidates | int | Regional explanation | 800 |
| `{services_filtered}` | after profitability | int | Regional explanation | 500 |
| `{services_selected}` | after MILP | int | Regional explanation | 93 |
| `{unserved_line}` | Top unserved lane | string | Regional explanation | "Port X -> Port Y" |
| `{iteration}` | iteration counter | int | Coordinator decisions | 1 |
| `{weak_summary}` | weak regions list | string | Coordinator decisions | "Asia, Europe" |
| `{len(conflicts)}` | conflict count | int | Coordinator decisions | 2 |

---

## 12. AI Decision Making

### 12.1 Strategy Classification

The RegionalAgent classifies each region as strategy type A, B, or C. This classification is the primary AI influence on the optimization pipeline:

**Type A — Hub-and-Spoke (Top-3 share > 35%):**
- Concentrate cargo through hub ports
- Most services are feeder lines to/from hubs
- Inter-hub trunk services for high-volume lanes
- Appropriate for: Middle East, Africa (dense hub regions)

**Type B — Direct (high median demand, low dispersion):**
- Point-to-point services between high-demand port pairs
- Minimal transshipment
- Appropriate for: Dense corridors with balanced demand

**Type C — Hybrid (default, mixed characteristics):**
- Combination of direct, hub-and-spoke, and feeder services
- Archetype ratios from LLM (ServiceGeneratorAgent)
- Appropriate for: Asia, Europe, Americas (diverse demand patterns)

### 12.2 Decision Heuristics

The CoordinatorAgent uses these heuristics for decision generation:

**Weight Adjustment (fallback):**
```
cov_gap = max(0, COVERAGE_TARGET - avg_coverage)  # COVERAGE_TARGET = 70.0%
cov_boost = min(0.2, cov_gap / 100.0)
profit_weight = max(0.3, 0.5 - cov_boost)
coverage_weight = min(0.6, 0.4 + cov_boost)
cost_weight = 0.1
```

**Conflict Resolution (always deterministic):**
```
For each overlapping service between regions:
    Compare weekly profit in each region
    Drop the service from the region with lower profit
```

### 12.3 Reasoning Constraints

All LLM reasoning is constrained by:
- **Specific numeric citations required** — Every reason must cite port IDs, TEU volumes, or percentages
- **No hedging language** — Banned: "consider", "explore", "may", "could potentially"
- **Strict output format** — Every prompt specifies exact section headers or JSON structure
- **Validation at every step** — Format + content checks before acceptance

### 12.4 Fallback Behavior

When LLM output fails validation, the system degrades gracefully:

1. **Retry** — 2 attempts at agent level, 2 internal retries per model
2. **Provider fallback** — Chain through 5 model providers
3. **Circuit breaker** — 60s cooldown after 5 consecutive failures
4. **Hardcoded fallback** — Deterministic default output

---

## 13. AI Safety

### 13.1 Hallucination Prevention

The system prevents hallucination through multiple mechanisms:

1. **Grounded prompts** — Every prompt embeds actual computed values (metrics, statistics) rather than asking the LLM to recall data. The LLM only provides reasoning and formatting, never factual recall.

2. **Strict format constraints** — Every prompt specifies exact output format. Non-conforming outputs are rejected and retried.

3. **Deterministic validation** — After the LLM response, values are validated against known ranges. A coverage weight of 2.5 (impossible) would be clamped to 0.9 by weight_validator.

4. **Downstream overwrite** — Even if the LLM produces incorrect recommendations, the optimization pipeline converts recommendations into actual GA/MILP computations. The LLM cannot cause the optimizer to compute an incorrect result — only to compute a less optimal one.

### 13.2 Output Validation

**Layer 1 — Evaluator** (`src/llm/evaluator.py`):
- Structure: 40% — Checks for "Strategy"/"Reason" keywords
- Completeness: 30% — Line count threshold (≥3 = 1.0, 2 = 0.7, <2 = 0.3)
- Relevance: 30% — Domain keywords (demand, port, hub, capacity, route)
- Threshold: total < 0.5 → fallback

**Layer 2 — Schema Enforcement** (for JSON outputs):
- `validate_weight_adjustments()`: 3 keys, each in [0,1], sum to 1.0
- `validate_archetype_params()`: 4 ratios in [0.05, 0.90], sum to 1.0
- `validate_regional_policy_v2()`: Anti-neutrality, metric citation, vessel sanity, drift

**Layer 3 — Consensus Reconciliation** (`src/validation/consensus_engine.py`):
- Weighted voting: coordinator 0.4 + regional 0.4 + service generator 0.2
- Confidence scoring: >0.7 = ACCEPTED, 0.3-0.7 = MODIFIED, <0.3 = REJECTED
- Conflict detection across weight disparity, archetype mismatch, hub conflict

### 13.3 AI Log Tags

Every AI interaction is tagged for auditability:

| Tag | Meaning | Generated By |
|---|---|---|
| `AI_GENERATED` | LLM produced valid output | All validators |
| `AI_VALIDATED` | Validator accepted the output | All validators |
| `AI_REJECTED` | Validator rejected, used fallback | All validators |
| `AI_FALLBACK` | LLM failed entirely, fallback used | All validators |
| `AI_APPLIED` | Validated output applied to pipeline | Regional/SvcGen agents |
| `CONSENSUS_ACCEPTED` | Confidence > 0.7 | ConsensusEngine |
| `CONSENSUS_MODIFIED` | Confidence 0.3-0.7 | ConsensusEngine |
| `CONSENSUS_REJECTED` | Confidence < 0.3 | ConsensusEngine |

---

## 14. AI ↔ Optimization Interaction

![AI-Optimizer Interaction](docs/generated/ai/png/ai_04_optimization_interaction.png){#fig:ai-optimization}

**Figure 6 — AI-Optimizer Interaction.** This diagram shows how AI outputs (strategy type, archetype params, decision weights) flow into the optimization pipeline (GA selection, GA fitness, MILP) and how the validation layer (WeightValidator, PolicyValidator V2, ConsensusEngine) validates and reconciles them before acceptance.

### 14.1 Interaction Points

There are exactly four points where AI influences optimization:

| Point | AI Output | Optimization Input | Effect |
|---|---|---|---|
| 1 | Archetype parameters (direct/hub-loop/feeder/trunk ratios) | CandidateServiceGenerator service mix | Determines how many services of each type are generated |
| 2 | Strategy type (A/B/C) | Service filtering + frequency optimization | Informs aggressive/conservative service selection |
| 3 | Decision weights (profit/coverage/cost) | ServiceGA fitness function | Alters the trade-off in service selection |
| 4 | Hub port focus | HubMILP cluster assignment | Guides which ports become hubs |

### 14.2 Complete Execution Flow

```
1. Problem loaded (NetworkLoader → Problem dataclass)
2. Metric computation (regional_metrics.py → 10 deterministic metrics)
3. OrchestratorAgent.analyze_problem() ← LLM call #1
4. PortClustering + RegionalSplitter → 5 sub-problems
5. Iteration 0:
   For each region (parallel):
     a. RegionalAgent.strategy() ← LLM call #2 [type A/B/C]
     b. ServiceGenerator.archetype() ← LLM call #3 [mix ratios]
     c. CandidateServiceGenerator creates services
     d. Profitability gate filters services
     e. ServiceGA evaluates fitness using AI weights
     f. FrequencyGA optimizes frequencies
     g. HubMILP solves flow assignment (PuLP/CBC)
     h. RegionalAgent.explanation() ← LLM call #4 [optional]
     i. Regional policy derived (deterministic)
   CoordinatorAgent.decisions() ← LLM call #5 [weights]
   ConsensusEngine reconciles
6. _apply_feedback() updates weights for next iteration
7. Iteration 1 (same flow, updated weights)
8. Iteration 2 (same flow, updated weights, max)
9. aggregate_results() → global metrics
10. pipeline_output.json
```

### 14.3 What AI Cannot Override

The following optimizations are entirely AI-independent:

- **GA population initialization** — Demand-proportional, random seed
- **Crossover and mutation** — Fixed operators
- **MILP constraints** — Fleet ≤ 300, flow conservation, port capacity
- **Fitness computation** — Formula is fixed; only weights vary
- **Conflict resolution** — Profit-based drop rule

---

## 15. Runtime Execution Trace

### 15.1 Observed Execution (from pipeline_output.json)

The following trace was captured from a live run:

```
=== ITERATION 0 ===
[0.0s]  Orchestrator.analyze_problem() → LLM call
[8.2s]  LLM response: Size: Large, Complexity Drivers: 333 ports, 9622 lanes...
[8.3s]  PortClustering: KMeans(k=5) on 333 ports
[8.5s]  RegionalSplitter: 5 sub-problems created
[8.5s]  ThreadPoolExecutor: dispatching 5 RegionalAgents

[8.5s]  RegionalAgent.Asia: strategy() → LLM call
[12.1s]  LLM response: Strategy: C (Hybrid)
[12.2s]  ServiceGenerator: archetype() → LLM call
[15.8s]  LLM response: {direct: 0.60, hub_loop: 0.15, feeder: 0.20, trunk: 0.05}
[15.8s]  ArchelogyValidator: AI_VALIDATED
[15.8s]  CandidateServiceGenerator: 845 services
[15.9s]  Profitability gate: 512 services pass
[15.9s]  HierarchicalGA: ServiceGA (80 pop × 120 gen)
[87.3s]  ServiceGA converged (8 gens no improvement)
[87.3s]  FrequencyGA (≤300 fleet)
[105.1s]  FrequencyGA converged, 247 vessels used
[105.1s]  HubMILP: PuLP/CBC solve (120s limit)
[157.3s]  MILP solved: profit=$145.2M, coverage=71.3%
[157.4s]  RegionalAgent.Asia: explanation() → LLM call
[163.1s]  LLM response: Verdict: Good, Profit margin 84.0%...

[163.1s] CoordinatorAgent.decisions() → LLM call
[168.4s]  LLM response JSON: {profit: 0.435, coverage: 0.465, cost: 0.10}
[168.4s]  WeightValidator: AI_VALIDATED
[168.5s]  ConsensusEngine: weight disparity detected
[168.5s]  Confidence: 0.85 → CONSENSUS_ACCEPTED
[168.5s]  _apply_feedback(): weights updated

=== ITERATION 1 ===
[168.5s]  Regional agents dispatched with new weights (p=0.435, c=0.465, k=0.10)
...

=== ITERATION 2 ===
...
[395.0s]  aggregate_results()
[395.1s]  generate_summary() → deterministic
[395.2s]  pipeline_output.json written
```

**Total run time:** ~395 seconds  
**Total LLM calls:** ~15 (1 analysis + 5 strategy + 5 archetype + decision + 3 explanations from iterations where evaluator triggered)  
**Total tokens:** Not tracked in current implementation  

---

## 16. AI Performance

### 16.1 LLM Call Latency

Measured from live runs (opencode/deepseek-v4-flash-free model):

| Call Type | Average | Min | Max | Count |
|---|---|---|---|---|
| Orchestrator analysis | 8.2s | 5.1s | 12.3s | 3 runs |
| Regional strategy | 3.6s | 2.1s | 8.4s | 15 calls |
| ServiceGenerator | 3.6s | 2.4s | 7.1s | 15 calls |
| Coordinator decisions | 5.3s | 3.8s | 9.2s | 3 calls |
| Regional explanation | 5.7s | 3.1s | 11.2s | 15 calls |
| **All calls** | **4.7s avg** | **2.1s** | **12.3s** | **~51 calls** |

### 16.2 Success Rates

| Metric | Rate | Notes |
|---|---|---|
| JSON parse success | ~80% | Coordinator decisions |
| Archetype validator pass | ~70% | ServiceGenerator JSON |
| Weight validator pass | ~85% | After normalization |
| Overall LLM-to-acceptance | ~65% | Through all layers |
| Fallback rate | ~35% | When LLM fails or validation rejects |

### 16.3 Cost Analysis

At current free-tier pricing:
- Total LLM calls per full run: ~15-25
- Estimated cost at $0.50/1M tokens: < $0.01 per run
- Primary cost: free (opencode/deepseek-free)
- Estimated commercial cost (GPT-4o equivalent): $0.15-0.50 per run

---

## 17. Failure Analysis

### 17.1 Historical Failures

| Failure Mode | Frequency | Impact | Mitigation |
|---|---|---|---|
| LLM returns empty content | ~5% | JSON parse failure → fallback | skip_evaluator for JSON prompts |
| LLM returns non-JSON text | ~15% | Parse failure → rule-based fallback | _parse_json_safe() JSON extraction |
| Evaluator false rejection | ~30% | False fallback for JSON prompts | skip_evaluator=True mechanism |
| API timeout (>60s) | ~2% | Circuit breaker trip → fallback chain | Provider fallback to faster models |
| Model unavailable (401) | ~3% | Provider skip | Multi-provider fallback chain |
| Hallucinated values | ~10% | Validator rejection → defaults | Multi-layer validation |
| Rate limiting | ~5% | Delayed responses | Circuit breaker + retry |

### 17.2 Recovery Strategy

```
Failure → Retry (2 attempts, agent level)
   ↓
Failure → Retry (2 attempts, internal LLMClient retry)
   ↓
Failure → Provider fallback chain (5 models)
   ↓
Failure → Circuit breaker (60s cooldown)
   ↓
Failure → Hardcoded fallback (deterministic)
```

### 17.3 Known Issues

1. **Expired free models** — qwen3.6-plus-free and minimax-m3-free promos expired June 2026. These entries are retained in the fallback chain for backward compatibility but always return 401 errors.

2. **Nemotron latency** — nemotron-3-ultra-free takes ~50s per request. When it becomes the active fallback, pipeline runtime increases substantially.

3. **No token tracking** — The current implementation does not capture prompt_tokens or completion_tokens from API responses. These fields are available in the response.usage object but are not logged or reported.

---

## 18. AI vs Classical Optimization

### 18.1 Where AI Excels

| Dimension | AI (LLM) | Classical Optimization |
|---|---|---|
| **Weight selection** | Adaptive — adjusts profit/coverage/cost balance based on iteration results | Fixed — requires manual tuning |
| **Strategy classification** | Contextual — classifies regions using natural language understanding of demand patterns | Rule-based threshold |
| **Service design** | Generative — produces novel archetype mixes | Pre-defined templates |
| **Explanation** | Human-readable — produces verdict, strengths, weaknesses | Not available |
| **Adaptability** | High — one system prompt + few-shot examples for new scenarios | Requires model reformulation |

### 18.2 Where Classical Optimization Dominates

| Dimension | Classical Optimization | AI (LLM) |
|---|---|---|
| **Solution optimality** | Guaranteed (MILP) or bounded (GA convergence) | Not optimal — heuristic guidance |
| **Determinism** | Reproducible results | Probabilistic — different output per call |
| **Speed** | < 10ms for fitness evaluation | 3-12 seconds per LLM call |
| **Scalability** | Handles 110,000+ route candidates | Limited to ~2K tokens per prompt |
| **Verification** | Mathematical proof of constraints | Validation layers only |
| **Cost** | CPU time only | API calls + tokens |

### 18.3 Why Hybrid Is Necessary

The system's architecture reflects a deliberate design decision: AI provides directional guidance (weights, strategy, archetype ratios) while classical optimization provides computational correctness (service selection, frequency optimization, flow assignment).

This hybrid approach is justified because:
1. **AI reduces the search space** — Archetype ratios limit service generation to likely-productive regions of the candidate space
2. **AI adapts between iterations** — Weight adjustments respond to coverage gaps that a fixed-weight approach would miss
3. **Classical optimization guarantees constraints** — AI-recommended weights never violate fleet constraints (≤300) or flow conservation
4. **Graceful degradation** — If AI fails entirely, deterministic fallbacks produce a valid (though potentially less optimal) solution

---

## 19. Real-World Justification

### 19.1 Value for Shipping Companies

The AI layer provides specific value for liner shipping operators:

**Scenario 1 — Network Planning.** A shipping company managing 300+ ports needs to decide which services to operate. The AI layer automatically classifies regions by demand pattern (Type A/B/C) and recommends service mixes. Without AI, a human planner would spend days analyzing demand distributions across regions.

**Scenario 2 — Demand Shifts.** If Asia-Europe demand shifts by 20%, the AI layer's iterative weight adjustment detects the coverage gap and rebalances profit/coverage weights in the next iteration. A classical optimizer would need operator intervention to adjust weights.

**Scenario 3 — Port Disruption.** If a hub port becomes unavailable, the ConsensusEngine detects hub conflicts and the OrchestratorAgent re-runs with adjusted hub assignments. The LLM explanation provides operators with actionable information about the change.

### 19.2 AI as Decision Support

The system is designed as decision support, not autonomous operation:

- Operators review LLM-generated explanations before accepting results
- The dashboard shows AI decisions alongside optimizer outputs
- AI log tags provide full audit trail of each decision
- Deterministic fallbacks ensure the system produces valid results even if the LLM is unavailable

### 19.3 Why Not Pure Optimization

A pure optimization approach (no AI) would:
1. Require manual weight tuning per region/dataset
2. Provide no explanation for service selection decisions
3. Be unable to adapt weights between iterations without external input
4. Limit the service archetype diversity to pre-programmed templates

The hybrid architecture preserves optimization correctness while adding AI's adaptive and explanatory capabilities.

---

## 20. Future AI Roadmap

### 20.1 Short-Term Improvements

| Enhancement | Effort | Impact | Dependencies |
|---|---|---|---|
| Token tracking in LLMMetrics | Low | Performance monitoring | None — response.usage already available |
| Confidence-weighted voting | Low | Better consensus | None — weights already configurable |
| Prompt versioning | Low | Audit trail | None |

### 20.2 Medium-Term Enhancements

| Enhancement | Effort | Impact | Dependencies |
|---|---|---|---|
| RAG integration | Medium | Context-aware decisions | Vector database |
| Knowledge graph for port geography | Medium | Geographically aware reasoning | Graph database |
| Fine-tuned small model | High | Reduced latency, lower cost | Training dataset |

### 20.3 Long-Term Vision

- **Autonomous planning** — The AI layer suggests full network redesigns based on seasonal demand patterns
- **Digital twin integration** — AI recommendation validated against a simulated shipping network
- **Multi-modal inputs** — Incorporate satellite data (port congestion), weather (routing), and economic indicators (demand forecasting)
- **RLHF for weight selection** — Operator feedback on weight adjustments trains the model to produce better recommendations

*This document is generated from the actual implementation at `src/`, `backend/`, and `frontend/`. All prompt templates, validation logic, and agent workflows are reconstructed from source code, not inferred from documentation.*

---

## Appendix A — Prompt Inventory

### A.1 Complete Prompt Register

| # | Agent | Prompt Name | File | Lines | Type | skip_eval | Temp |
|---|---|---|---|---|---|---|---|
| 1 | Orchestrator | System Prompt | orchestrator_agent.py:53-60 | 8 lines | Role definition | N/A | N/A |
| 2 | Orchestrator | Analysis Prompt | orchestrator_agent.py:103-117 | 15 lines | Structured text | No | 0.1 |
| 3 | Orchestrator | Summary Prompt | orchestrator_agent.py:763-789 | 27 lines | Structured text | No | 0.1 |
| 4 | Coordinator | System Prompt | coordinator_agent.py:39-48 | 10 lines | Role definition | N/A | N/A |
| 5 | Coordinator | Decision Prompt | coordinator_agent.py:351-380 | 30 lines | JSON | Yes | 0.1 |
| 6 | Regional | System Prompt | regional_agent.py:31-39 | 9 lines | Role definition | N/A | N/A |
| 7 | Regional | Strategy Prompt | regional_agent.py:134-147 | 14 lines | Structured text | No | 0.1 |
| 8 | Regional | Explanation Prompt | regional_agent.py:339-361 | 23 lines | Structured text | No | 0.1 |
| 9 | ServiceGen | System Prompt | service_generator_agent.py:28-35 | 8 lines | Role definition | N/A | N/A |
| 10 | ServiceGen | Strategy Prompt | service_generator_agent.py:297-310 | 14 lines | Free prose | No | 0.1 |
| 11 | ServiceGen | Archetype JSON | service_generator_agent.py:325-332 | 8 lines | JSON | Yes | 0.1 |

### A.2 Prompt Design Patterns

All 11 prompts follow consistent design patterns:

**Pattern 1 — Role Definition (System Prompts):**
All four system prompts follow the structure: "You are a <role>. Your output is consumed by <audience>. Rules: <numbered constraints>."

**Pattern 2 — Metrics Injection (User Prompts):**
Every user prompt begins with a block of computed metrics: "Network statistics (ground truth): Ports: 333, Lanes: 9622..."

**Pattern 3 — Strict Format (Output Constraint):**
Every prompt ends with a STRICT FORMAT or Return ONLY valid JSON instruction specifying exact output structure.

**Pattern 4 — Template Hints:**
Format sections include embedded variable references: `[Cite margin {profit_margin_pct}% and coverage {coverage:.1f}%]` — the LLM sees the actual values as hints.

**Pattern 5 — No Hedging:**
Four of five system prompts explicitly prohibit hedging language: "Do not generalise, hedge, or repeat the question."

---

## Appendix B — Configuration Inventory

### B.1 Environment Variables

| Variable | Default | Purpose | Used By |
|---|---|---|---|
| `OPENCODE_API_KEY` | (required) | Primary LLM API key | LLMClient |
| `OPENROUTER_API_KEY` | (fallback) | Legacy fallback API key | LLMClient (deprecated) |
| `LLM_BASE_URL` | `https://opencode.ai/zen/v1` | OpenAI-compatible API base | LLMClient |
| `ORCHESTRATOR_MODEL` | `opencode/deepseek-v4-flash-free` | Orchestrator LLM model | OrchestratorAgent |
| `REGIONAL_MODEL` | `opencode/deepseek-v4-flash-free` | Regional agent LLM model | RegionalAgent |
| `GA_POPULATION_SIZE` | `80` | GA population size | HierarchicalGA |
| `GA_GENERATIONS` | `120` | GA max generations | ServiceGA |
| `MILP_TIME_LIMIT` | `120` | MILP solver time limit (s) | HubMILP |

### B.2 Algorithmic Constants

| Constant | Value | File | Purpose |
|---|---|---|---|
| `FLEET_SIZE` | 300 | `hierarchical_ga.py:164` | Maximum deployable vessels |
| `MAX_ITERATIONS` | 3 | `orchestrator_agent.py:26` | Max optimization iterations |
| `COVERAGE_TARGET` | 70.0% | `coordinator_agent.py:22` | Minimum demand coverage target |
| `ELITE_SIZE` | 10 | `service_ga.py:14` | Elite chromosomes retained |
| `NO_IMPROVE_LIMIT` | 8 | `service_ga.py:15` | Early stop generations |
| `GA_MAX_RUNTIME` | 90s | `service_ga.py:16` | GA solver time limit |
| `MILP_TIME_LIMIT` | 120s | `Config class` | MILP solver time limit |
| `TRANSSHIP_COST` | 80 $/TEU | `service_ga.py:28` | Transshipment unit cost |
| `UNSERVED_PENALTY` | 300 $/TEU | `hub_milp.py:25` | Unserved demand penalty |
| `BUNKER_PRICE` | 600 $/ton | `fuel_cost.py:62` | Fuel price per ton |
| `COORDINATOR_WEIGHT` | 0.40 | `consensus_engine.py:12` | Coordinator voting weight |
| `REGIONAL_WEIGHT` | 0.40 | `consensus_engine.py:13` | Regional voting weight |
| `SERVICE_GENERATOR_WEIGHT` | 0.20 | `consensus_engine.py:14` | SvcGen voting weight |

### B.3 Validation Thresholds

| Threshold | Value | File | Meaning |
|---|---|---|---|
| `MIN_WEIGHT` | 0.05 | `weight_validator.py:10` | Minimum allowed weight |
| `MAX_WEIGHT` | 0.90 | `weight_validator.py:11` | Maximum allowed weight |
| `RATIO_MIN` | 0.05 | `archetype_validator.py:10` | Minimum archetype ratio |
| `RATIO_MAX` | 0.80 | `archetype_validator.py:11` | Maximum archetype ratio |
| `TOLERANCE` | 0.02 | `weight_validator.py:12` | Weight sum tolerance |
| `CONSENSUS_ACCEPTED_MIN` | 0.70 | `consensus_engine.py:20` | Confidence for accepted |
| `CONSENSUS_REJECTED_MAX` | 0.30 | `consensus_engine.py:21` | Confidence for rejected |
| `FEEDER_HIGH_THRESHOLD` | 0.40 | `consensus_engine.py:17` | Feeder ratio conflict trigger |
| `PROFIT_HIGH_THRESHOLD` | 0.60 | `consensus_engine.py:15` | Profit weight disparity trigger |
| `COVERAGE_HIGH_THRESHOLD` | 0.70 | `consensus_engine.py:16` | Coverage priority trigger |
| `DRIFT_THRESHOLD` | 0.6 | `policy_validator_v2.py` | Max policy drift from baseline |

---

## Appendix C — Agent Glossary

| Term | Definition |
|---|---|
| **OrchestratorAgent** | Master controller managing the complete optimization pipeline lifecycle across up to 3 iterations. Creates sub-agents, dispatches parallel optimization, and aggregates results. |
| **CoordinatorAgent** | Global decision agent performing conflict detection, system evaluation (score 0-5), LLM decision generation, and gradient feedback computation between iterations. |
| **RegionalAgent** | Regional optimization analyst (×5: Asia, Europe, Americas, Middle East, Africa). Executes service generation, GA optimization, MILP solving, and explanation generation per region. |
| **ServiceGeneratorAgent** | Service archetype designer producing LLM-guided service mix ratios (direct/hub-loop/feeder/trunk) and vessel bias recommendations per region. |
| **ConsensusEngine** | Validation and reconciliation module (975 lines) performing weighted voting across coordinator, regional, and service generator agents with confidence scoring. |
| **LLMClient** | Singleton wrapper (254 lines) around the OpenAI Python SDK with MD5 response caching, circuit breaker pattern (5 failures = 60s timeout), and 5-model fallback chain. |
| **LLMEvaluator** | Response scoring module (67 lines) evaluating LLM outputs on Structure (40%), Completeness (30%), and Relevance (30%) with a 0.5 acceptance threshold. |
| **LLMMetrics** | Runtime metrics tracker (24 lines) recording per-agent evaluation scores and aggregate statistics across the optimization run. |

## Appendix D — Abbreviations

| Abbreviation | Full Form |
|---|---|
| LLM | Large Language Model |
| GA | Genetic Algorithm |
| MILP | Mixed-Integer Linear Programming |
| OR | Operations Research |
| TEU | Twenty-foot Equivalent Unit |
| FFE | Forty-foot Equivalent Unit |
| RAG | Retrieval-Augmented Generation |
| RLHF | Reinforcement Learning from Human Feedback |
| CBC | Coin-or Branch and Cut (MILP solver) |
| PuLP | Python Linear Programming |
| MD5 | Message Digest 5 (hash function) |
| CORS | Cross-Origin Resource Sharing |
| ASGI | Asynchronous Server Gateway Interface |
| WS | WebSocket |
| DAG | Directed Acyclic Graph |
| KPI | Key Performance Indicator |

## Appendix E — References

### E.1 Source Files

| File | Lines | Purpose |
|---|---|---|
| `src/llm/client.py` | 254 | LLM API client with caching and circuit breaker |
| `src/llm/evaluator.py` | 67 | Response evaluation and scoring |
| `src/llm/evaluator_manager.py` | 2 | Singleton wrapper |
| `src/llm/metrics.py` | 24 | Runtime metrics tracking |
| `src/agents/base.py` | 107 | Abstract base agent with call_llm() wrapper |
| `src/agents/orchestrator_agent.py` | 903 | Master orchestration controller |
| `src/agents/coordinator_agent.py` | 574 | Global coordination and decisions |
| `src/agents/regional_agent.py` | 474 | Regional optimization (×5) |
| `src/agents/service_generator_agent.py` | 374 | Service archetype generation |
| `src/agents/regional_metrics.py` | 250 | Deterministic 10-metric computation |
| `src/agents/regional_policy_mapping.py` | 309 | Deterministic policy derivation |
| `src/validation/weight_validator.py` | 204 | Weight clamp + normalize |
| `src/validation/archetype_validator.py` | 283 | Archetype ratio validation |
| `src/validation/regional_policy_validator.py` | 268 | Policy key validation |
| `src/validation/regional_policy_validator_v2.py` | 271 | Strict V2 validation |
| `src/validation/consensus_engine.py` | 975 | Weighted voting reconciliation |
| `src/utils/config.py` | 37 | Environment config loader |
| `src/config/optimizer_config.py` | 62 | ObjectiveConfig dataclass |

### E.2 Total AI Subsystem Lines of Code

| Component | Files | Lines |
|---|---|---|
| LLM Integration | 4 | 347 |
| Agents | 7 | 3,585 |
| Validation | 6 | 2,265 |
| Config | 2 | 99 |
| **Total AI Subsystem** | **19** | **6,296** |

### E.3 Key Design Documents

- `ARCHITECTURE_REFERENCE.md` — System architecture and deployment
- `CODE_REFERENCE.md` — API documentation and source code reference
- `MASTER_TECHNICAL_DOCUMENTATION_V2.md` — Complete system documentation
- `Analysis/AI_INFLUENCE_VERIFICATION_REPORT.md` — AI influence analysis
- `Analysis/CONSENSUS_INFLUENCE_REPORT.md` — Consensus weight impact analysis
- `Analysis/COORDINATOR_FORENSIC_TRACE.md` — Coordinator agent behavior trace
- `Analysis/PHASE_P_PROMPT_TRUTH_AUDIT_MASTER_REPORT.md` — Prompt audit results



---

## Appendix F — Prompt Analysis Methodology

### F.1 Prompt Structure Analysis

Each prompt in the system follows a consistent architecture designed for reliability with probabilistic LLMs:

**Layer 1 — Role Definition (System Prompt):**
Every system prompt establishes the agent's persona, constraints, and output expectations. The role definition grounds the LLM in a specific decision-making context.

- Orchestrator: "You are the Master Orchestrator..." — emphasizes authority and pipeline oversight
- Coordinator: "You ANALYZE, DECIDE, and CORRECT — not summarise." — emphasizes action over analysis
- Regional: "You are a liner shipping network optimisation analyst for the {region} region." — scopes to geographic domain
- ServiceGen: "You are a liner shipping service design specialist." — scopes to service design

**Layer 2 — Context Injection (User Message):**
All numeric data is computed before the LLM call and injected as formatted text. The LLM never computes or recalls statistics — it only reasons about pre-computed values. This prevents hallucination of network statistics.

**Layer 3 — Format Constraint (Strict Format / JSON Return):**
Every prompt specifies exact output format. Non-JSON prompts use section headers (e.g., "Size:", "Complexity Drivers:") that are validated by keyword checks after response. JSON prompts use the exact JSON structure as a template in the prompt.

**Layer 4 — Citation Hooks (Embedded Variables):**
Format constraints include variables that appear as hints: "[Cite margin {profit_margin_pct}% and coverage {coverage:.1f}%]". The LLM sees the numeric values and is expected to incorporate them into the response.

### F.2 Prompt Length Analysis

| Component | System Prompt | User Message | Total (chars) | Tokens (est.) |
|---|---|---|---|---|
| Orchestrator analysis | 341 chars | ~600 chars | ~940 | ~250 |
| Coordinator decision | 244 chars | ~800 chars | ~1,044 | ~275 |
| Regional strategy | 327 chars | ~400 chars | ~727 | ~190 |
| Regional explanation | 327 chars | ~700 chars | ~1,027 | ~270 |
| ServiceGen archetype | 208 chars | ~500 chars | ~708 | ~185 |
| Maximum | 341 chars | ~800 chars | ~1,140 | ~300 |

All prompts use less than 0.3% of the model's 128K context window.

### F.3 Prompt Version History

**V1 (Initial, Phase A):** Simple role + task prompts. No format constraints. Output was inconsistent — LLM would produce narrative text when JSON was expected, or omit required fields.

**V2 (Structured, Phase B):** Added STRICT FORMAT sections. Output quality improved but some fields still missing.

**V3 (Validated, Phase C):** Added validation checks after each prompt. Retry loop added for non-conforming outputs.

**V4 (Current, Release):** Added skip_evaluator for JSON prompts (fixes false rejection), deterministic fallbacks for all prompt paths, and "no hedging" language in system prompts.

---

## Appendix G — Consensus Engine Detail

### G.1 Voting Weights Rationale

The ConsensusEngine uses asymmetric voting weights:
- **Coordinator: 0.40** — Highest weight because the Coordinator has global visibility across all 5 regions
- **Regional: 0.40** — Highest weight, shared equally among 5 regions (0.08 each) because regions have local knowledge
- **Service Generator: 0.20** — Lower weight because the SvcGen's archetype focus is narrower

The 0.40/0.40/0.20 split ensures broad agreement is required for consensus.

### G.2 Conflict Detection Algorithms

**Weight Disparity Detection:**
```
Condition: coordinator_profit > 0.6 AND any region_coverage > 0.7
Action: Flag as conflict -> reconcile via weighted average
Signal: Coordinator favors profit while region favors coverage
```

**Archetype Mismatch Detection:**
```
Forward: feeder_ratio > 0.4 AND vessel_bias equals "large"
Reverse: direct_ratio > 0.5 AND vessel_bias equals "small"
Action: Flag as conflict -> reconcile via weighted mode
```

**Hub Conflict Detection:**
```
Condition: service_hubs AND regional_hubs are disjoint, or neither is a subset of the other
Action: Flag as conflict -> reconcile via support-weighted voting
```

### G.3 Confidence Scoring

```
confidence = 1.0
confidence -= 0.15 x num_conflicts_detected
confidence -= 0.25 x num_conflicts_unresolved
if num_regions > 0: confidence += 0.05
confidence = max(0.0, confidence)

Classification:
  > 0.70 -> CONSENSUS_ACCEPTED
  0.30-0.70 -> CONSENSUS_MODIFIED
  < 0.30 -> CONSENSUS_REJECTED (use DEFAULT_CONSENSUS)
```

### G.4 Default Consensus Fallback

```python
DEFAULT_CONSENSUS = {
    "final_weight_adjustments": {
        "profit_weight": 0.50,
        "coverage_weight": 0.40,
        "cost_weight": 0.10
    },
    "final_archetype_params": {
        "direct_ratio": 0.60, "hub_loop_ratio": 0.15,
        "feeder_ratio": 0.20, "trunk_ratio": 0.05
    },
    "confidence_score": 0.0,
    "conflicts_resolved": [],
    "conflicts_remaining": ["fallback_used"],
    "notes": "Fallback consensus applied; confidence below 0.3 threshold."
}
```

---

## Appendix H — LLMClient Implementation Detail

### H.1 Request Lifecycle

```python
def chat(model, system, user_message, temperature=0.1):
    # 1. Generate cache key (MD5 of model|system|user_message)
    cache_key = hashlib.md5(f"{model}|{system}|{user_message}".encode()).hexdigest()

    # 2. Check cache
    if cache_key in self.cache:
        return self.cache[cache_key]

    # 3. Check circuit breaker
    if self._is_circuit_open():
        return self._get_hard_fallback_response()

    # 4. Build candidate model list
    candidates = [primary] + [m for m in fallbacks if m != primary]

    # 5. Try each candidate (each with 2 retries)
    for candidate in candidates:
        for attempt in range(self.max_retries + 1):
            try:
                response = self._try_call(candidate, system, user_message)
                if response:
                    self.cache[cache_key] = response
                    return response
            except Exception:
                continue

    # 6. All models failed
    self.failure_count += 1
    return self._get_hard_fallback_response()
```

### H.2 Circuit Breaker States

```
CLOSED (Normal): Pass through to API. Count failures. 5 failures -> OPEN.
OPEN (Tripped): Reject all requests for 60s. Return hard fallback. Timeout -> HALF-OPEN.
HALF-OPEN (Testing): Allow 1 test request. Success -> CLOSED. Failure -> OPEN.
```

### H.3 Response Extraction Logic

The _extract_response_content() method handles four response types:
- Normal text: message.content is not None -> return content
- Tool calls: message.tool_calls present -> return str(tool_calls)
- Reasoning only: content is None, reasoning exists -> return None (skip candidate)
- Empty: both None -> return None

---

## Appendix I — Deterministic Metrics Engine

### I.1 The 10 Regional Metrics

| # | Metric | Formula | Categorical Labels | Use |
|---|---|---|---|---|
| 1 | total_demand | sum of weekly TEU | -- | Scale indicator |
| 2 | top10_concentration | sum(top10) / total x 100 | -- | Inequality measure |
| 3 | top3_corridor_share | sum(top3) / total x 100 | very_high >30, high >10, moderate >5, low | Demand focus |
| 4 | median_lane_volume | median of lane TEU | -- | Central tendency |
| 5 | avg_lane_volume | total / n_lanes | -- | Average lane size |
| 6 | network_density | lanes / (ports*(ports-1)/2) x 100 | very_dense >100, dense >60, moderate >30, sparse >10, very_sparse | Connectivity |
| 7 | hub_centrality | max(hub_score)/sum(all) x 100 | dominant >20, strong >15, moderate >10, distributed | Hub dominance |
| 8 | import_export_imbalance | mean(abs(out-in)/(out+in)) x 100 | severe >40, moderate >20, mild >10, balanced | Directionality |
| 9 | dominant_vessel_requirement | classify from median TEU | feeder, small, balanced, large | Vessel sizing |
| 10 | service_fragmentation | avg_ports / n_lanes | -- | Service dispersion |

### I.2 Metric to Policy Mapping

The deterministic policy mapper converts metrics into policy:

**Coverage/Profit Priority:**
- Base from concentration: very_high -> profit=0.85, low -> profit=0.25
- Nudged by density: very_dense +0.10 profit, very_sparse -0.05 profit
- Nudged by imbalance: severe +0.10 profit
- Clamped to [0, 1]

**Vessel Bias:**
- From density: very_dense -> "large", moderate -> "balanced", sparse -> "small"
- Overridden by median lane volume: <10 TEU -> "small", >5000 TEU -> "large"

**Service Margin:**
- From density: very_dense -> 0.03, very_sparse -> 0.12
- Plus imbalance bonus: severe +0.05
- Plus vessel bonus: large -0.02, feeder +0.03
- Clamped to [0, 0.30]

---

## Appendix J — AI Interaction Patterns with GA and MILP

### J.1 AI to GA Communication

Three channels by which AI influences GA:

**Channel 1 — Fitness Weights (per iteration):**
```
AI Input:  {profit: 0.4244, coverage: 0.4656, cost: 0.11}
GA Effect: Fitness = 0.4244 * norm_profit + 0.4656 * norm_coverage - 0.11 * norm_cost
```

**Channel 2 — Strategy Type (per region):**
```
AI Input:  Strategy C (Hybrid)
GA Effect: No direct GA impact (guides service generation)
```

**Channel 3 — Archetype Mix (per region):**
```
AI Input:  {direct: 0.60, hub_loop: 0.15, feeder: 0.20, trunk: 0.05}
GA Effect: Candidate service pool composition
```

### J.2 AI to MILP Communication

**Channel 1 — Hub Port Selection:**
```
AI Input:  Hub focus ports from archetype analysis
MILP Effect: HubMILP transshipment pair prioritization
```

**Channel 2 — Strategic Filtering:**
```
AI Input:  Strategy type (A/B/C) influences filter aggressiveness
MILP Effect: Sub-problem size passed to MILP
```

### J.3 Iterative Feedback Loop

```
iteration_n: GA runs with AI weights -> MILP solves -> metrics computed
    |
    v
iteration_n+1: Coordinator receives metrics -> LLM evaluates coverage gap
    -> recommends new weights -> GA runs with adjusted weights
```

---

## Appendix K — AI Runtime Impact Analysis

### K.1 Pipeline Runtime Breakdown

| Phase | Duration | AI Overhead |
|---|---|---|
| Data Loading | ~2s | None |
| Problem Analysis (LLM) | ~8s | +8s |
| Regional Optimization x5 | ~150s | None (parallel GA/MILP) |
| Regional Strategy (5 x LLM) | ~18s | +18s |
| Service Archetype (5 x LLM) | ~18s | +18s |
| Regional Explanation (5 x LLM) | ~28s | +28s |
| Coordinator Decision | ~5s | +5s |
| Aggregate + Consensus | ~2s | None |
| Total per iteration | ~231s | +77s (49% overhead) |
| Total 3 iterations | ~395s | +125s (46% overhead) |

### K.2 Value of AI Overhead

The 46% runtime overhead buys:
1. Adaptive weight adjustment across iterations
2. Human-readable explanations per region
3. Graceful degradation (no pipeline crashes)
4. Full audit trail with AI log tags
5. Regional customization of service archetypes

---

## Appendix L — LLM Evaluation Scoring Detail

### L.1 Scoring Formula

```python
structure_score = keyword_matches / 2  # "Strategy" and "Reason"
completeness_score = 1.0 if lines >= 3 else 0.7 if lines == 2 else 0.3
relevance_score = domain_keyword_matches / 5  # demand, port, hub, capacity, route

total_score = 0.4 * structure + 0.3 * completeness + 0.3 * relevance
```

### L.2 Scoring Examples

**Passing (total=0.79):**
```
Strategy: C
Reason 1: Balanced network design across 50+ ports
Reason 2: Handles demand variability for 100+ lanes
```
Structure=1.0, Completeness=0.7, Relevance=0.6 -> Total=0.79 (PASS)

**Failing (total=0.09):**
```
The network should be optimized.
```
Structure=0.0, Completeness=0.3, Relevance=0.0 -> Total=0.09 (FAIL -> FALLBACK)

---

## Appendix M — Error Recovery Matrix

| Failure Point | Error Signal | Recovery | Recovery Time |
|---|---|---|---|
| LLMClient API timeout | Exception | Retry x2, next provider | 3 x 60s worst |
| All models failed | Empty response | Hard fallback string | ~0ms |
| Circuit breaker open | Open state | 60s timeout then half-open | 60s |
| Evaluator < 0.5 | Low score | Hard fallback string | ~0ms |
| Analysis invalid format | Validation fail | Deterministic template | ~0ms |
| JSON parse failure | Parse exception | Rule-based weights | ~0ms |
| Strategy no digits | Validation fail | Append computed reason | ~0ms |
| Explanation missing keywords | Validation fail | Margin-based triage | ~0ms |
| Consensus confidence < 0.30 | Low confidence | DEFAULT_CONSENSUS | ~0ms |
| Policy anti-neutral | Neutrality check | Baseline policy | ~0ms |

---

## Appendix N — Complete Prompt Templates (Redacted)

### N.1 Orchestrator Analysis Prompt

```
Network statistics (ground truth):
  Ports: {num_ports}, Lanes: {num_lanes}, Services: {num_services}
  Total demand: {total_demand:,.0f} TEU/wk, Avg/lane: {avg_demand:,.1f} TEU
  Density: {density_ratio}%, Top-5 share: {top5_share}%

TOP-5 CORRIDORS:
{top5_text}

STRICT FORMAT:
Size: {size_label}
Complexity Drivers:
- [Driver 1 with specific statistic]
- [Driver 2 with specific statistic]
- [Driver 3 with specific statistic]
Demand Concentration: [high/moderate/low] - [one sentence implication]
Decomposition Rationale: [one sentence with ~{num_ports//3} ports per region]
```

### N.2 Coordinator Decision Prompt (JSON)

```
Global shipping network decision -- iteration {iteration} results:

Metrics:
  Total profit   : ${profit}/week
  Avg coverage   : {coverage}%
  ...

Return ONLY valid JSON (no markdown, no preamble):
{{
  "actions": [{{"region": "...", "action": "...", "expected_gain": "..."}}],
  "priorities": ["..."],
  "weight_adjustments": {{
    "profit_weight": <0.0-1.0>,
    "coverage_weight": <0.0-1.0>,
    "cost_weight": <0.0-1.0>
  }},
  "notes": "..."
}}
```

### N.3 Regional Strategy Prompt

```
REGIONAL DATA - {REGION}:
  Ports: {num_ports}, Lanes: {num_lanes}, Median demand: {median_demand} TEU/lane
  Total demand: {total_demand:,.0f} TEU/wk, Top-3 share: {top3_share}%
  Hub ports: [{hub_ids_str}]

TOP-5 CORRIDORS:
{corridor_table}

DECISION RULE: {decision_rule}

STRICT FORMAT:
Strategy: <A | B | C>
Selected: <hub_and_spoke | direct | hybrid>
Reason 1: [cite median demand and port ID]
Reason 2: [cite port count and lane count]
Hub Ports: [{hub_ids_str}]
```

### N.4 Regional Explanation Prompt

```
Maritime logistics analyst evaluating {REGION} region.

SOLVER RESULTS:
  Services gen/filtered/select: {gen}/{filter}/{select}
  Weekly profit: ${profit:,.0f} | Annual: ${profit*52:,.0f}
  Margin: {margin}% | Profit/svc: ${pps}/wk
  Coverage: {coverage:.1f}% | Unserved: {uncovered}%

TOP-5 CORRIDORS:
{corridor_table}

STRICT FORMAT:
Verdict: <Good | Moderate | Poor>
Strengths:
- [Cite profit and profit/service]
- [Cite coverage and satisfied TEU]
Weaknesses:
- [Cite unserved % and TEU]
- [Cite transship and port costs]
Improvement Actions:
- [Action 1: target unserved line]
- [Action 2: hub expansion]

---

*Document generated from actual implementation. All prompt templates, validation logic, and agent workflows reconstructed from source code.*

**End of Document — AI Layer Reference v1.0.0-rc1**


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


### 15.2 Complete LLM Call Log (from live run)

The following is a complete record of all LLM interactions during a single optimization run:

```
[0.0s]  CALL #1: Orchestrator.analyze_problem()
[0.0s]  PROMPT -> System: "You are the Master Orchestrator..."
[0.0s]  PROMPT -> User: "Network statistics (ground truth): Ports: 333, Lanes: 9622..."
[8.2s]  RESPONSE <- "Size: Large, Complexity Drivers: 333 ports span 6 continents..."
[8.2s]  EVAL: Structure=1.0 Completeness=1.0 Relevance=1.0 Total=1.00 -> PASS
[8.3s]  PortClustering: KMeans(k=5) on geographic coordinates -> 5 clusters
[8.5s]  RegionalSplitter -> 5 sub-problems created (Asia=57, Europe=65, Americas=70, ME=45, Africa=50 ports)

[8.5s]  CALL #2: RegionalAgent.Asia.strategy()
[8.5s]  PROMPT -> System: "You are a liner shipping network optimisation analyst for the Asia region."
[8.5s]  PROMPT -> User: "REGIONAL DATA - ASIA: Ports: 57, Lanes: 2104, Median demand: 45 TEU..."
[12.1s] RESPONSE <- "Strategy: C, Selected: hybrid, Reason 1: Median demand 45 TEU/lane..."
[12.1s] EVAL: Structure=0.5 Completeness=1.0 Relevance=0.4 Total=0.62 -> PASS

[12.2s] CALL #3: ServiceGenerator.Asia.archetype()
[12.2s] PROMPT -> System: "You are a liner shipping service design specialist."
[12.2s] PROMPT -> User: "Liner shipping service design for 57-port network... Return ONLY valid JSON..."
[15.8s] RESPONSE <- {"direct_ratio": 0.60, "hub_loop_ratio": 0.15, "feeder_ratio": 0.20, ...}
[15.8s] VALIDATION: JSON parse OK -> ArchetypeValidator -> AI_VALIDATED

[CALLS #4-6: REGIONAL AGENTS Europe, Americas, Middle East run in parallel]
[CALLS #7-11: SERVICE GENERATORS for all 5 regions run after strategies are ready]
[CALLS #12-16: REGIONAL EXPLANATIONS for all 5 regions run after MILP completes]

[157.4s] CALL #17: CoordinatorAgent.decisions()
[157.4s] PROMPT -> System: "You are a global shipping network decision agent..."
[157.4s] PROMPT -> User: "Global shipping network decision -- iteration 0 results:..."
[162.7s] RESPONSE <- {"actions": [{"region": "Asia", "action": "increase coverage", ...}], ...}
[162.7s] VALIDATION: JSON parse OK -> WeightValidator -> AI_VALIDATED
[162.7s] ConsensusEngine: Confidence=0.85 -> CONSENSUS_ACCEPTED

[ITERATION 1: Same pattern with adjusted weights]
[ITERATION 2: Same pattern with further adjusted weights]

[393.0s] aggregate_results() -> global metrics
[393.1s] generate_summary() -> deterministic executive summary
[393.2s] pipeline_output.json written (complete runtime truth)
```

Total wall-clock: ~393 seconds  |  Total LLM calls: ~17  |  Total tokens: Not tracked.

### 16.4 Token Utilization Analysis

While token counts are not currently tracked in the LLMMetrics module, the following estimates can be derived from prompt lengths:

| Call Type | Input Tokens (est.) | Output Tokens (est.) | Total (est.) |
|---|---|---|---|
| Orchestrator analysis | 250 | 100 | 350 |
| Regional strategy (x5) | 190 each | 50 each | 1,200 |
| ServiceGen archetype (x5) | 185 each | 50 each | 1,175 |
| Regional explanation (x5) | 270 each | 150 each | 2,100 |
| Coordinator decision (x3) | 275 each | 100 each | 1,125 |
| **Total per full run** | **~3,875** | **~1,750** | **~5,625** |

At the current free-tier pricing ($0/M tokens for the primary model), token cost is $0 per run. At commercial API pricing (approximately $2-5/1M tokens), the cost per run would be approximately $0.01-0.03.

### 16.5 Reliability Metrics

| Metric | Value | Measurement Period |
|---|---|---|
| LLM API success rate | ~95% | Over 500+ calls |
| JSON parse success rate | ~80% | Coordinator decisions |
| Archetype validation pass rate | ~70% | ServiceGenerator outputs |
| Weight validation pass rate | ~85% | After normalization |
| Evaluator pass rate (non-JSON) | ~85% | Strategy + explanation |
| Overall acceptance rate | ~65% | Through all validation layers |
| Fallback rate | ~35% | All causes |
| Average LLM latency | ~4.7s | All call types |
| P95 LLM latency | ~11.2s | Slowest regional explanations |
| Circuit breaker trips per 100 runs | ~2 | Typically from API rate limiting |


### 4.5 Agent Comparison Matrix

| Characteristic | Orchestrator | Coordinator | Regional | ServiceGenerator |
|---|---|---|---|---|
| File | orchestrator_agent.py | coordinator_agent.py | regional_agent.py | service_generator_agent.py |
| Lines of code | 903 | 574 | 474 | 374 |
| LLM calls per run | 1-2 | up to 3 | up to 6 | up to 10 |
| skip_evaluator | False | True | False | True (JSON only) |
| Temperature | 0.1 | 0.1 | 0.1 | 0.1 |
| Validation type | Keyword check | JSON parse + weight check | Keyword + digit check | JSON parse + ratio check |
| Fallback type | Deterministic template | Rule-based formula | Pre-computed rule | DEFAULT constants |
| Retry attempts | 2 | 0 (fallback on parse fail) | 2 on eval fail | 2 |
| Primary output | Analysis text | JSON decisions | Strategy text + explanation | Archetype JSON |
| Output consumed by | RegionalSplitter + summary | ConsensusEngine + GA | GA + MILP + dashboard | CandidateServiceGenerator |

### 4.6 Agent Error Handling Patterns

All four agent types share a common error handling pattern inherited from BaseAgent:

```
call_llm() -> 2 retries at agent level
  Each retry -> LLMClient.chat() -> 2 retries at client level
    Each client retry -> model attempt (5 models in chain)
      -> circuit breaker check (open/closed)
        -> API call with 60s timeout
```

This gives a maximum of 2 x 2 x 5 = 20 API attempts per agent-level call before fallback. In practice, the system typically succeeds on attempt 1-3 (first model, first or second try).

### 4.7 Agent Dependencies

```
OrchestratorAgent depends on:
  - LLMClient (for LLM calls)
  - PortClustering (for KMeans decomposition)
  - RegionalSplitter (for sub-problem creation)
  - RegionalAgent x5 (for regional optimization)
  - CoordinatorAgent (for global decisions)
  - ConsensusEngine (for reconciliation)
  - SharedContext (for cross-agent state)

RegionalAgent depends on:
  - LLMClient (for strategy + explanation LLM calls)
  - ServiceGeneratorAgent (for archetype generation)
  - HierarchicalGA (ServiceGA + FrequencyGA)
  - HubMILP (for flow optimization)
  - FlowOptimizer (for post-MILP metrics)
  - HubDetector (for hub port identification)

CoordinatorAgent depends on:
  - LLMClient (for decision JSON)
  - weight_validator (for decision validation)

ServiceGeneratorAgent depends on:
  - LLMClient (for archetype JSON)
  - HubDetector (for hub identification)
  - CandidateServiceGenerator (for service creation)
  - archetype_validator (for archetype validation)
```

### 4.8 Agent Initialization Sequence

```python
# OrchestratorAgent initializes (src/agents/orchestrator_agent.py:28-50)
self.regional_agents = {
    "Asia": RegionalAgent(name="RegionalAgent.Asia", region="Asia"),
    "Europe": RegionalAgent(name="RegionalAgent.Europe", region="Europe"),
    "Americas": RegionalAgent(name="RegionalAgent.Americas", region="Americas"),
    "Middle East": RegionalAgent(name="RegionalAgent.Middle East", region="Middle East"),
    "Africa": RegionalAgent(name="RegionalAgent.Africa", region="Africa"),
}
self.coordinator = CoordinatorAgent(name="CoordinatorAgent")
self.consensus = ConsensusEngine()
self.shared_context = SharedContext()
```

Each RegionalAgent creates its own ServiceGeneratorAgent, HubDetector, and optimization module instances at runtime during process() execution. This lazy initialization pattern ensures resources are not wasted on unused agents.

### 4.9 Thread Safety

RegionalAgents execute in parallel via ThreadPoolExecutor (max_workers=5). The system uses these patterns for thread safety:

1. **Immutable inputs**: Each regional sub-problem is a separate Problem object with no shared mutable state.
2. **Separate LLMClient**: The LLMClient is a singleton but uses a lock-free cache (dict access is atomic in CPython for simple operations).
3. **Coordinator synchronization**: The OrchestratorAgent awaits all regional results via executor.shutdown(wait=True) before calling the CoordinatorAgent.
4. **SharedContext locking**: The SharedContext uses a threading.Lock for hub strategy updates across iterations.

### 13.4 Validation Chain Diagram

```
LLM Output
    |
    v
[weight_validator.py]
    - Clamp each weight to [0.05, 0.90]
    - Normalize to sum = 1.0
    - Tag: AI_GENERATED / AI_VALIDATED / AI_REJECTED
    - Fallback: (profit=0.50, coverage=0.40, cost=0.10)
    |
    v
[archetype_validator.py]
    - Each ratio in [0.05, 0.80]
    - Sum of ratios = 1.0 (+/- 0.02 tolerance)
    - vessel_bias in (small, balanced, large)
    - Tag: AI_GENERATED / AI_VALIDATED / AI_REJECTED
    - Fallback: DEFAULT_ARCHETYPE_PARAMS
    |
    v
[regional_policy_validator.py (V1)]
    - coverage/profit priority non-negative
    - min_service_margin in [0, 0.30]
    - vessel_bias valid
    |
    v
[regional_policy_validator_v2.py (V2)]
    - Anti-neutrality check (reject 0.5/0.5)
    - Metric citation check (must reference computed data)
    - Vessel sanity check (volume -> appropriate vessel size)
    - Drift check (change from previous iteration <= 0.3)
    - Tags: V2_VALIDATED / V2_REJECT_NEUTRAL / etc.
    - Fallback: baseline policy from regional metrics
    |
    v
[ConsensusEngine]
    - detect_weight_disparity() -> conflict if profit > 0.6 AND coverage > 0.7
    - detect_archetype_mismatch() -> conflict if feeder > 0.4 AND vessel_bias = "large"
    - detect_hub_conflict() -> conflict if hub sets are disjoint
    - reconcile_weights() -> weighted average (0.4/0.4/0.2)
    - reconcile_archetype() -> weighted average of ratios
    - reconcile_hubs() -> support-weighted hub selection
    - compute_confidence() -> score 0.0-1.0
    - Tags: CONSENSUS_ACCEPTED / MODIFIED / REJECTED
    - Fallback: DEFAULT_CONSENSUS
    |
    v
[Accepted Output -> Optimization Pipeline]


### 17.5 Failure Recovery Case Studies

**Case Study 1: OpenRouter API Key Expiry (Phase A)**

When the original OpenRouter API key expired during development, the LLMClient returned 401 errors for all requests. The system:
1. Primary model: 2 retries -> 2 failures
2. Fallback models: All returned 401 -> all failed
3. Circuit breaker: After 5 consecutive failures across all providers, opened for 60s
4. Agent fallback: All 4 agent types returned deterministic defaults
5. Pipeline: Completed with DEFAULT configuration (zero AI influence)

Result: The optimization pipeline completed normally with default weights (profit=0.50, coverage=0.40, cost=0.10) and default archetype parameters. The solution was valid but not AI-optimized.

**Lesson learned:** The free-tier fallback chain was added to reduce API dependency.

**Case Study 2: Invalid JSON from Coordinator (Phase B)**

The CoordinatorAgent's LLM prompt returned free-form text instead of JSON:
```
Response: "I think the weights should be adjusted. Consider increasing profit weight to 0.45..."
```
The system:
1. _parse_json_safe("I think the weights...") -> regex search for {.*} -> no match -> returns {}
2. validate_weight_adjustments({}) -> AI_REJECTED -> returns fallback weights
3. Coordinator_metrics: fallback_count incremented

**Lesson learned:** The JSON extraction regex `{.*}` was enhanced to handle cases where the LLM wraps JSON in explanatory text. The _parse_json_safe method now also strips markdown code fences before parsing.

**Case Study 3: Empty LLM Response (Phase P+1C)**

The DeepSeek model returned content='' when asked to both "think step by step" AND "return ONLY valid JSON" simultaneously:
```
System: "You are a coordinator..."
User: "Think step by step. Return ONLY valid JSON: {profit_weight: ...}"
Response: "" (empty string)
```
The system:
1. call_llm() receives empty string
2. skip_evaluator is False (evaluator runs on empty string)
3. Evaluator score: 0.0 (no keywords, no lines, no domain terms)
4. Hardcoded fallback returned

**Lesson learned:** The skip_evaluator mechanism was created for JSON prompts. The "Think step by step" augmentation is now suppressed when JSON output is requested.

### 17.6 Failure Prevention Checklist

The following safeguards prevent LLM-related failures from affecting the optimization pipeline:

- [x] All prompt paths have deterministic fallback
- [x] All JSON parse failures return default configuration
- [x] All validation failures return default values
- [x] Circuit breaker prevents cascading API failures
- [x] MD5 cache prevents redundant API calls
- [x] Agent-level retry (2 attempts) handles transient failures
- [x] LLMClient retry (2 attempts per model) handles per-request failures
- [x] Provider fallback chain (5 models) handles provider-level failures
- [x] Pipeline continues with defaults even if ALL LLMs fail
- [x] All agent outputs validated before optimizer consumption

### 19.4 Industry Applicability

The AI layer's design makes it applicable to several real-world shipping scenarios:

**Scenario: Planned Network Restructure**
A shipping operator wants to redesign service networks for a new season. The AI layer:
1. Analyzes demand patterns across 333 ports
2. Recommends archetype mixes per region (e.g., more direct services for Asia, more feeder services for Africa)
3. Generates candidate services matching the recommended archetype
4. Optimizes frequencies and flows using GA + MILP
5. Provides explanations for every decision

Without AI, this process requires 2-3 weeks of manual analysis by a team of network planners. With AI, a full recommendation can be generated in ~7 minutes (395s pipeline runtime).

**Scenario: Disruption Response**
A major hub port experiences a 2-week closure. The operator:
1. Marks the hub as unavailable in the problem configuration
2. Re-runs the pipeline
3. The AI layer detects the hub change, adjusts hub assignments
4. The ConsensusEngine detects hub conflicts between regional agents
5. Generates a new network design without the affected hub
6. The dashboard shows the redesigned network with explanations

Without AI, replanning during disruptions requires manual re-optimization that typically takes 3-5 days.

**Scenario: New Market Entry**
The operator adds 20 new ports in a previously unserved region. The AI layer:
1. Automatically clusters the new ports into the nearest existing region (or creates a new cluster)
2. Generates region-specific archetype parameters based on demand characteristics
3. The deterministic metrics engine analyzes the new region's demand patterns
4. Produces optimized service recommendations with explanations

Without AI, adding new ports requires re-evaluating the entire network model, typically a 1-2 week effort.

### 20.4 AI Enhancement Priority Matrix

| Enhancement | Technical Feasibility | Business Impact | Implementation Effort | Priority |
|---|---|---|---|---|
| Token tracking in metrics | High (data already available) | Medium | Low (< 1 day) | High |
| Prompt version control | High | Medium | Low (< 2 days) | High |
| Response caching across runs | High | High (cost reduction) | Medium | High |
| RAG with historical runs | Medium | High | Medium | Medium |
| Knowledge graph for ports | Low | High | High | Medium |
| Fine-tuned small model | Medium | High | High | Low |
| Multi-modal input | Low | Medium | High | Low |
| RLHF for weight selection | Low | Medium | High | Low |

The highest-priority enhancements (token tracking, prompt version control, persistent caching) are all achievable with minimal implementation effort and provide immediate quality-of-life and auditability improvements.


### 4.10 Agent State Management

Agent state during pipeline execution is managed through the SharedContext singleton (src/utils/shared_context.py):

```python
class SharedContext:
    def __init__(self):
        self.hub_strategy = {}
        self.global_objectives = GlobalObjectives()
        self.regional_priorities = {}
        self._lock = threading.Lock()
    
    def update_hub_strategy(self, consensus_result):
        with self._lock:
            self.hub_strategy = consensus_result.get("hub_focus", {})
    
    def get_hub_strategy(self):
        return self.hub_strategy
```

The SharedContext provides:
- Thread-safe access to cross-agent state via threading.Lock
- Hub strategy propagation between iterations
- Global objectives tracking (profit/coverage/cost targets)
- Regional priority assignments

### 4.11 Agent Lifecycle

```
1. INITIALIZATION
   - Agents created by OrchestratorAgent.__init__()
   - Each agent stores its name, role, and model
   - LLMClient and evaluator are global singletons

2. PROCESS (per optimization run)
   - Agent.process() called with specific input data
   - LLM calls made via BaseAgent.call_llm()
   - Validators check outputs
   - Results returned to OrchestratorAgent

3. CLEANUP
   - Agent instances persist across iterations
   - LLMClient cache persists across iterations (optimization)
   - No explicit cleanup required (no mutable agent state)

4. REUSE
   - Same agent instances used for all 3 iterations
   - RegionalAgents receive different Problem objects per iteration
   - Coordinator receives different metrics per iteration
   - LLMClient cache benefits from repeated prompts across iterations
```

### 20.5 AI Architecture Evolution Roadmap

**Near-term (1-3 months):**
- Implement token tracking in LLMMetrics for cost and performance analysis
- Add prompt version control with git-based prompt template management
- Implement cross-run response caching for frequently repeated prompts
- Add regression tests for all 11 prompt templates

**Medium-term (3-6 months):**
- Implement RAG pipeline with historical run data as knowledge base
- Build knowledge graph of port relationships for context-aware decisions
- Create automated prompt regression testing framework
- Add A/B testing framework for comparing LLM recommendations vs deterministic baselines

**Long-term (6-12 months):**
- Fine-tune a small model (e.g., Llama 3B) on shipping-specific prompts
- Implement multi-modal inputs: satellite port congestion, weather routing, economic indicators
- Build digital twin integration for simulated validation of AI recommendations
- Deploy RLHF pipeline for operator feedback on weight recommendations

### 20.6 Research Opportunities

The system presents several research-worthy questions:

1. **Weight adaptation dynamics**: How does the GA respond to weight changes between iterations? The observed behavior (coverage dropped despite increased coverage weight) suggests complex dynamics between weight space and solution space.

2. **Optimal consensus weights**: Are the current 0.4/0.4/0.2 weights optimal? Could learned weights improve convergence?

3. **Prompt sensitivity**: How sensitive are the prompts to small variations in wording? A systematic prompt perturbation study could identify robustness issues.

4. **Fallback quality**: What is the quality gap between LLM-guided and deterministic-fallback solutions? Quantifying this gap would guide investment in LLM reliability vs. improved fallback algorithms.

5. **Model comparison**: How do different LLMs (DeepSeek, Llama, GPT, Claude) perform on the specific shipping optimization tasks? A systematic comparison would guide model selection.

---

## Appendix T — Quick Reference Card

### T.1 Agent Quick Reference

| Agent | LLM Calls/Run | Temp | skip_eval | Output Format | Fallback |
|---|---|---|---|---|---|
| Orchestrator | 1-2 | 0.1 | No | Structured text | Deterministic template |
| Coordinator | ≤3 | 0.1 | Yes | JSON | Rule-based formula |
| Regional (×5) | ≤6 | 0.1 | No | Structured text | Pre-computed rule |
| ServiceGenerator | ≤10 | 0.1 | Yes (JSON) | JSON | DEFAULT constants |

### T.2 Validation Quick Reference

| Validator | Input | Checks | Fallback |
|---|---|---|---|
| weight_validator | {profit, coverage, cost} | [0,1], sum=1.0 | (0.50, 0.40, 0.10) |
| archetype_validator | {direct, hub_loop, feeder, trunk} | [0.05,0.80], sum=1.0 | (0.60, 0.15, 0.20, 0.05) |
| policy_validator_v2 | {coverage, profit, margin, bias} | Anti-neutral, sanity, drift | Baseline policy |
| ConsensusEngine | All agent outputs | Conflict detection, voting | DEFAULT_CONSENSUS |

### T.3 LLM Client Quick Reference

| Feature | Setting |
|---|---|
| Primary model | opencode/deepseek-v4-flash-free |
| Temperature | 0.1 (all agents) |
| Max tokens | 4,096 |
| Cache key | MD5(model|system|user_message) |
| Cache type | In-memory dict |
| Circuit breaker | 5 failures → 60s timeout |
| Provider fallback | 5 models (2 active, 2 expired, 1 slow) |
| Max retries per model | 2 |

### T.4 Runtime Quick Reference

| Metric | Typical Value |
|---|---|
| Total runtime (3 iterations) | ~395s |
| LLM overhead | ~77s per iteration (+49%) |
| LLM calls per run | ~15-25 |
| Average LLM latency | ~4.7s |
| Fallback rate | ~35% |
| Coverage target | 70.0% |
| Fleet constraint | ≤300 vessels |
| GA population | 80 |
| GA generations | 120 (max) |
| MILP time limit | 120s |

---

*Document generated from actual implementation at src/, backend/, and frontend/. All prompt templates, validation logic, and agent workflows reconstructed from source code, not inferred from documentation.*

**End of Document — AI Layer Reference v1.0.0-rc1**
