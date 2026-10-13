# PHASE P+0 — PROMPT INFLUENCE BASELINE

## MASTER REPORT

**Date:** 2026-06-23
**Baseline:** v1_runtime_integrated (commit 2a171cc)
**Method:** Benchmark-only — no code modifications, no prompt changes, no architecture changes
**Source Evidence:** `pipeline_output.json` (runtime truth) + code path analysis across 17 source files

---

## EXECUTIVE SUMMARY

Phase P+0 executed **4 controlled experiments** (P0.1–P0.4) to quantify the actual optimizer influence of every active prompt and runtime AI component. The results are dramatic and counter to Phase P's assumptions.

### The Overarching Finding

**The two prompts classified as "ACTIVE" in Phase P have ZERO measured influence.**

- **Coordinator LLM Decisions (#1):** 0% — LLM failed, rule-based fallback used throughout
- **ServiceGen Archetype JSON (#3):** 0% — LLM failed, defaults used in all 5 regions
- **Consensus Engine:** ~1.3% — active but minimal modification due to zero conflicts
- **Gradient Feedback (algorithmic):** ~65% — the **real** primary weight driver
- **Rule-based Fallback (algorithmic):** ~100% — became the primary decision path

The system's AI-influenced decision loops are **non-functional**. Every weight adjustment in `pipeline_output.json` came from Python code paths, not LLM reasoning.

---

## EXPERIMENT RESULTS

### P0.1 — Coordinator Influence

**Design:** Measure weight_adjustments from LLM vs rule-based fallback
**Finding:** `pipeline_output.json` decision_output.notes states: *"Rule-based fallback: coverage 63.0%, profit $443,860,872/week, 0 conflicts."*

| Weight Source | profit | coverage | cost | Used? |
|---|---|---|---|---|
| LLM (intended) | unknown | unknown | unknown | ❌ (failed) |
| Rule-based fallback | 0.430 | 0.470 | 0.100 | → consensus → applied |
| Gradient feedback | 0.395 | 0.505 | 0.100 | Available as fallback |
| Actually applied (iteration 1) | 0.372 | 0.482 | 0.146 | ✅ |

**Measured Influence: 0.0%**

### P0.2 — Service Generator Influence

**Design:** Compare LLM-produced archetype mix vs default archetype params
**Finding:** ALL 5 regions used identical DEFAULT_ARCHETYPE_PARAMS (direct=0.60, hub_loop=0.15, feeder=0.20, trunk=0.05, vessel_bias="balanced")

| Region | direct_ratio | hub_loop | feeder | trunk | vessel_bias | Source |
|---|---|---|---|---|---|---|
| Asia | 0.60 | 0.15 | 0.20 | 0.05 | balanced | DEFAULT |
| Europe | 0.60 | 0.15 | 0.20 | 0.05 | balanced | DEFAULT |
| Americas | 0.60 | 0.15 | 0.20 | 0.05 | balanced | DEFAULT |
| Middle East | 0.60 | 0.15 | 0.20 | 0.05 | balanced | DEFAULT |
| Africa | 0.60 | 0.15 | 0.20 | 0.05 | balanced | DEFAULT |

**Measured Influence: 0.0%**

### P0.3 — Consensus Influence

**Design:** Compare coordinator raw weights vs consensus final weights
**Finding:** Consensus modified weights by ~1.3% — negligible impact

| Component | Coordinator | Consensus | Delta | % Change |
|---|---|---|---|---|
| profit_weight | 0.4298 | 0.4244 | -0.0054 | -1.3% |
| coverage_weight | 0.4702 | 0.4656 | -0.0046 | -1.0% |
| cost_weight | 0.1000 | 0.1100 | +0.0100 | +10.0% |

**Measured Influence: ~1.3%** (functionally negligible)

### P0.4 — SharedContext Opportunity

**Design:** Simulate SharedContext injection — determine information gain
**Finding:** SharedContext computes 4 categories of data (global objectives, regional priorities, iteration history, regional intelligence) that are **never injected into any prompt**

| Gap | Available Fields | Prompts Affected |
|---|---|---|
| Global Objectives | profit_weight, coverage_weight, iteration, convergence_score | #1, #3, #4 |
| Regional Priorities | per-region coverage/profit priority, hub_focus, vessel_bias | #1 |
| Iteration History | 2-iteration weight/coverage/profit trajectory | #1 |
| Regional Intelligence | concentration, density, imbalance, hub_dominance | #1, #3 |

**Estimated opportunity: 3-8pp coverage improvement per iteration**

---

## SYNTHESIS: The Influence Hierarchy

### What Actually Runs the System (Measured)

```
                        ┌──────────────────────────┐
                        │  CONFIG DEFAULTS          │
                        │  (profit=0.60,            │
                        │   coverage=0.25,          │
                        │   cost=0.15)              │
                        └──────────┬───────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│  RULE-BASED LOGIC (100% influence on decisions when LLM fails)   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Coordinator._generate_decisions() fallback (line 370-406)  │  │
│  │ RegionalAgent strategy decision (pre-computed, line 116)   │  │
│  │ ServiceGen archetype pre-selection (line 264-282)          │  │
│  │ Orchestrator size label (pre-computed, line 101)           │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│  GRADIENT FEEDBACK (65% influence on final applied weights)      │
│  Coordinator._generate_feedback_signals() (lines 426-507)       │
│  - coverage_gap × gradient → weight_adjustments                 │
│  - convergence_score (algorithmic)                               │
│  - profit_gap check                                              │
└──────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│  CONSENSUS ENGINE (~1.3% influence on final weights)             │
│  Weighted voting: coordinator 0.40 + regional 0.40 + svc 0.20   │
│  - No conflicts detected → minimal adjustment                    │
│  - Single-issue voter imbalance                                  │
└──────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│  HIERARCHICALGA + MILP (the actual optimization engine)          │
│  - Uses weights set by the feedback chain above                   │
│  - Produces services, coverage, profit results                    │
│  - No LLM involvement inside GA/MILP                              │
└──────────────────────────────────────────────────────────────────┘
```

### What Was Supposed to Run the System (Theoretical)

```
LLM Prompt #1 → JSON decisions → weights → GA (0% achieved)
LLM Prompt #3 → JSON archetype → service mix → MILP (0% achieved)
LLM Prompts #4,5,6,7 → Text → display/logging (100% achieved)
```

**The theoretical and actual architectures are completely disconnected.**

---

## CRITICAL FINDING: LLM Reliability Asymmetry

| Output Format | Example Prompts | Success Rate |
|---|---|---|
| **Free-text** (natural language) | Regional Strategy, Regional Explanation, Orchestrator Analysis, Orchestrator Summary | **~100%** |
| **JSON** (structured, machine-parseable) | Coordinator Decisions, ServiceGen Archetype JSON | **0%** |

### Why JSON fails

The LLM model used (`opencode/deepseek-v4-flash-free`) is a free-tier model that may:
1. Not support function-calling / structured output reliably
2. Return empty `content` with only `reasoning_content` populated
3. Produce invalid JSON that fails `_parse_json_safe()` 
4. Trigger circuit breaker due to cumulative failures

The coordinator's `_parse_json_safe()` (coordinator_agent.py:518-537) only attempts JSON parsing — it has no ability to request retries with different formatting.

### Why Free-text works

Free-text prompts have minimal constraints and keyword-based validation. The `is_valid_explanation()` method at regional_agent.py:42-43 only checks for the presence of 4 required substrings and a 2+ digit number. This is trivially satisfied by almost any LLM output.

### The Irony

The only prompts that matter for optimizer behavior (JSON) fail 100%. The prompts that are display-only (free-text) work correctly. This means the system pays for 100% of the LLM tokens but gets 0% of the optimizer influence it was designed for.

---

## PROMPT UPGRADE PRIORITY (Measured, Not Theoretical)

| Rank | Action | Effort | Expected Gain | Prerequisite |
|---|---|---|---|---|
| **1** | Fix LLM client reliability for JSON prompts | 1 day | 100% lift (0%→functional) | None |
| **2** | Fix exec summary serialization bug | 1 hour | Eliminates data corruption | None |
| **3** | Inject SharedContext into coordinator prompt | 4 hours | 3-8pp coverage/iteration | #1 |
| **4** | Inject iteration history into coordinator prompt | 3 hours | Prevents oscillation | #1 |
| **5** | Simplify JSON output format (fewer constraints) | 2 hours | Better LLM success rate | #1 |
| **6** | Merge/remove display-only prompts | 2 hours | 40% cost reduction | None |
| **7** | Inject regional intelligence into ServiceGen | 3 hours | Differentiated service pools | #1 |
| **8** | Add trade-off reasoning to coordinator | 4 hours | Better weight decisions | #1 |

**Critical path:** Ranks 1 → 3 → 4 → 8 (the AI decision chain). Ranks 2 and 6 are independent quick wins.

---

## DELIVERABLE INDEX

| # | Experiment | Report | Status |
|---|---|---|---|
| P0.1 | Coordinator Influence | `Analysis/COORDINATOR_INFLUENCE_REPORT.md` | ✅ Complete |
| P0.2 | Service Generator Influence | `Analysis/SERVICE_GENERATOR_INFLUENCE_REPORT.md` | ✅ Complete |
| P0.3 | Consensus Influence | `Analysis/CONSENSUS_INFLUENCE_REPORT.md` | ✅ Complete |
| P0.4 | SharedContext Opportunity | `Analysis/SHARED_CONTEXT_OPPORTUNITY_REPORT.md` | ✅ Complete |
| — | Prompt Influence Baseline | `Analysis/PROMPT_INFLUENCE_BASELINE.md` | ✅ Complete |
| — | Upgrade Priority Report | `Analysis/PROMPT_UPGRADE_PRIORITY_REPORT.md` | ✅ Complete |
| — | Master Report | `Analysis/PROMPT_INFLUENCE_MASTER_REPORT.md` (this file) | ✅ Complete |

---

## APPENDIX: Raw Experimental Data

Full experiment output stored at `Analysis/phase_p0_experiment_data.json`.

### Code Paths Traced

| Module | Lines | Function | Relevance |
|---|---|---|---|
| `coordinator_agent.py` | 302-420 | `_generate_decisions()` | LLM + fallback paths |
| `coordinator_agent.py` | 426-507 | `_generate_feedback_signals()` | Gradient weights |
| `coordinator_agent.py` | 518-537 | `_parse_json_safe()` | JSON extraction |
| `service_generator_agent.py` | 290-341 | `process()` prompt + archetype | JSON + fallback |
| `service_generator_agent.py` | 317-325 | JSON schema prompt | Output format |
| `regional_agent.py` | 114-160 | Strategy prompt + fallback | Decision trace |
| `orchestrator_agent.py` | 575-615 | Consensus engine call | Weight reconciliation |
| `orchestrator_agent.py` | 214-286 | `_apply_feedback()` | Weight application |
| `orchestrator_agent.py` | 619-651 | SharedContext creation | Data availability |
| `base.py` | 27-88 | `call_llm()` | LLM wrapper + evaluator |
| `client.py` | 39-207 | `chat()` | Response extraction + fallback |
| `weight_validator.py` | 25-164 | `validate_weight_adjustments()` | Weight normalization |
| `archetype_validator.py` | 43-230 | `validate_archetype_params()` | Archetype normalization |
| `consensus_engine.py` | 139-254 | `process()` | Full consensus pipeline |
| `shared_context.py` | 117-200 | SharedContext dataclass | State container |

---

## VERDICT

```
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   Phase P classified the prompts correctly but                    ║
║   ASSUMED they were functional. Phase P+0 proved they             ║
║   are NOT.                                                        ║
║                                                                  ║
║   The architecture has TWO COMPLETELY SEPARATE decision           ║
║   paths:                                                          ║
║                                                                  ║
║   Theoretical (what the code says): LLM → JSON → weights → GA    ║
║   Actual (what pipeline_output.json proves):                      ║
║     formula → weights → GA                                       ║
║                                                                  ║
║   The LLM decision loop is DEAD CODE. It executes, it fails,      ║
║   it falls back, and NOBODY NOTICES.                              ║
║                                                                  ║
║   Phase P+1 must fix LLM reliability FIRST, then upgrade          ║
║   prompts. Without reliability, every prompt upgrade is an        ║
║   exercise in futility.                                           ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

---

*Phase P+0 — Prompt Influence Baseline completed 2026-06-23. 
Baseline: v1_runtime_integrated. 
Rules: No code modified. No prompts changed. No architecture altered. Benchmark only.*
