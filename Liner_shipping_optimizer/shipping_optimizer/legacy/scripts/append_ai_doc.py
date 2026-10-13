#!/usr/bin/env python3
"""Append expanded content to AI_LAYER_REFERENCE.md"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

extra = r"""

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
"""

with open(ROOT / 'AI_LAYER_REFERENCE.md', 'a', encoding='utf-8') as f:
    f.write(extra)

print(f"Appended {len(extra.split(chr(10)))} lines to AI_LAYER_REFERENCE.md")
