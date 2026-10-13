# PROMPT INFLUENCE BASELINE

## Measured Influence of Every Active Prompt & AI Component

**Date:** 2026-06-23 | **Baseline:** v1_runtime_integrated | **Source:** pipeline_output.json

---

## Baseline Summary

| Component | Type | Measured Influence | Status |
|---|---|---|---|
| Coordinator LLM Decisions (#1) | Prompt | **0.0%** | LLM FAILED — rule-based fallback used |
| ServiceGen Archetype JSON (#3) | Prompt | **0.0%** | LLM FAILED — defaults used everywhere |
| Consensus Engine | Algorithm | **~1.3%** | Small weight modification (no conflicts) |
| Gradient Feedback Signals | Algorithm | **~65%** | Primary weight driver |
| Rule-based Fallback Logic | Algorithm | **~100%** | Backup became primary |
| Coordinator System Prompt | System Prompt | **0.0%** | LLM never received it (parse failed before call?) |

---

## Baseline Metrics (from pipeline_output.json)

| Metric | Iteration 0 | Iteration 1 | Delta |
|---|---|---|---|
| Weekly Profit | $599,513,064 | $443,860,872 | **-26.0%** |
| Coverage | 64.7% | 63.0% | **-1.7pp** |
| Convergence Score | 0.975 | 0.967 | -0.008 |
| Conflicts | 0 | 0 | 0 |
| Services Selected | — | 424 | — |
| Weights Applied | P=0.60, C=0.25, Co=0.15 | P=0.372, C=0.482, Co=0.146 | — |
| Rerun Reason | Coverage 5.3pp gap | Coverage 7.0pp gap | Worsened |
| Exec Summary | N/A | **CORRUPTED** (raw API object) | — |

## Weight Flow Trace

```
CONFIG (iteration 0):
  profit=0.60, coverage=0.25, cost=0.15
  ↓
COORDINATOR LLM (iteration 0):
  FAILED → Rule-based fallback: profit=0.447, coverage=0.453, cost=0.10
  ↓
GRADIENT FEEDBACK (iteration 0):
  profit=0.395, coverage=0.505, cost=0.10
  ↓
CONSENSUS (iteration 0):
  profit=0.4244, coverage=0.4656, cost=0.11
  ↓
PROBLEM WEIGHTS APPLIED (for iteration 1):
  profit=0.372, coverage=0.482, cost=0.146
  ↓
HIERARCHICAL GA (iteration 1):
  ← (coverage 64.7% → 63.0%, profit -26%)
  ↓
COORDINATOR LLM (iteration 1):
  FAILED → Rule-based fallback: profit=0.430, coverage=0.470, cost=0.10
  ↓
RERUN TRIGGERED (max iterations reached without convergence)
```

## Reliability Assessment

| Component | Call Attempts | Successes | Failure Rate | Detection |
|---|---|---|---|---|
| LLM Client (Coordinator) | 2 | 0 | **100%** | Silent — falls back, no alert |
| LLM Client (ServiceGen) | 5 | 0 | **100%** | Silent — defaults used, no alert |
| LLM Client (Regional Strategy) | 10 | 10 | 0%* | ✅ Working |
| LLM Client (Regional Explanation) | 10 | 10 | 0%* | ✅ Working |
| LLM Client (Orchestrator Analysis) | 2 | 2 | 0% | ✅ Working |
| LLM Client (Orchestrator Summary) | 2 | 2 (buggy) | 0% (corrupted) | ⚠️ Content='' bug |

*\*Regional LLM calls succeeded — the regional strategy and explanation prompts produce output. Only the JSON-format prompts (coordinator decisions, service gen archetype) fail.*

## Key Insight

**The two prompts classified as "ACTIVE" in Phase P (Coordinator Decisions #1 and ServiceGen Archetype #3) have ZERO actual influence.** Both require JSON output that the LLM cannot reliably produce. The prompts classified as "DISPLAY ONLY" (free-text format) work correctly.

This is the opposite of what Phase P expected. The high-influence prompts are broken; the low-influence prompts work fine.
