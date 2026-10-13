# PHASE P — P1: PROMPT INVENTORY

**Baseline:** v1_runtime_integrated | **Date:** 2026-06-23

## Complete Prompt Inventory

| # | Name | File:Line | Function | Agent | Model | Type | Est. Tokens | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | Coordinator Decisions | `coordinator_agent.py:324-352` | `_generate_decisions()` | Coordinator | ORCHESTRATOR_MODEL | JSON | ~260 | ACTIVE |
| 2 | ServiceGen Strategy | `service_generator_agent.py:290-303` | `process()` | ServiceGen | REGIONAL_MODEL | Free-text | ~200 | PARTIALLY ACTIVE |
| 3 | ServiceGen Archetype | `service_generator_agent.py:318-325` | `process()` | ServiceGen | REGIONAL_MODEL | JSON | ~75 | ACTIVE |
| 4 | Regional Strategy | `regional_agent.py:134-147` | `process()` | Regional | REGIONAL_MODEL | Free-text | ~175 | PARTIALLY ACTIVE |
| 5 | Regional Explanation | `regional_agent.py:339-361` | `process()` | Regional | REGIONAL_MODEL | Free-text | ~300 | DISPLAY ONLY |
| 6 | Orchestrator Analysis | `orchestrator_agent.py:103-117` | `analyze_problem()` | Orchestrator | ORCHESTRATOR_MODEL | Free-text | ~125 | DISPLAY ONLY |
| 7 | Orchestrator Summary | `orchestrator_agent.py:763-789` | `process()` | Orchestrator | ORCHESTRATOR_MODEL | Free-text | ~325 | DISPLAY ONLY (BROKEN) |
| 8 | Base LLM Enhancement | `base.py:30` | `call_llm()` | All | N/A | Append | ~15 | ACTIVE |

## System Prompts (4)

- **Coordinator** (coordinator_agent.py:32-40): 8 lines, maritime decision agent, no hedging
- **Service Generator** (service_generator_agent.py:21-28): 7 lines, service design specialist, cite numbers
- **Regional Agent** (regional_agent.py:31-39): 9 lines, optimisation analyst, no vague language  
- **Orchestrator** (orchestrator_agent.py:52-60): 8 lines, master orchestrator, evidence-based analysis

## Metrics

- **Total runtime prompts:** 8
- **ACTIVE prompts:** 2 (Coordinator Decisions, ServiceGen Archetype JSON)
- **PARTIALLY ACTIVE:** 2 (ServiceGen Strategy, Regional Strategy)
- **DISPLAY ONLY:** 3 (Regional Explanation, Orchestrator Analysis, Orchestrator Summary)
- **DISPLAY ONLY (BROKEN):** 1 (Orchestrator Summary — empty response bug)
- **Total LLM calls per pipeline run:** 9 (1 coordinator + 2 service gen + 5 regional × 2 prompts + 2 orchestrator = 9)
- **Total token estimate:** ~3,360 per run
- **Active + partially active token share:** ~1,535 (46%)
- **Display-only / wasted token share:** ~1,825 (54%)

## LLM Client

`src/llm/client.py` — Single OpenAI-compatible client with:
- Base URL: `https://opencode.ai/zen/v1`
- Primary model: `opencode/deepseek-v4-flash-free` (both orchestrator + regional)
- Fallback chain: `qwen3.6-plus-free` → `minimax-m3-free` → `mimo-v2.5-free` → `nemotron-3-ultra-free`
- Circuit breaker: 5 failures → 60s timeout
- Cache: MD5-based, shared across all agents
- **Critical bug in response extraction (line 156-169):** Empty `content` falls through to `str(message)` which serializes the entire API response object
