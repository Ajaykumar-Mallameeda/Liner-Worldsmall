# FALLBACK PATH TRACE

## Complete Map of Every Fallback Mechanism in the AI Decision Pipeline

---

## 1. LLM Client Fallbacks

### 1a. Candidate Model Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/llm/client.py` |
| **Lines** | 123-145 |
| **Trigger** | Primary model fails (network error, timeout) |
| **Action** | Try each fallback model sequentially: qwen3.6-plus-free → minimax-m3-free → mimo-v2.5-free → nemotron-3-ultra-free |
| **Retries** | 3 attempts per model (line 40) |
| **Response** | Result from first successful candidate |

### 1b. Hard Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/llm/client.py` |
| **Lines** | 83-85 |
| **Trigger** | ALL model candidates fail |
| **Action** | Return hardcoded string: `"Service temporarily unavailable. Using default optimization parameters."` |
| **Detection** | Callers can check for this string |
| **Log** | `llm_all_candidates_failed` |

### 1c. Empty Response Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/llm/client.py` |
| **Lines** | 177-179 |
| **Trigger** | `not result or result.lower() == "none"` |
| **Action** | `result = self._get_hard_fallback_response()` |
| **Note** | This runs AFTER `str(message)` serialization. Since `str(message)` is non-empty, this fallback does NOT trigger |

### 1d. Circuit Breaker Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/llm/client.py` |
| **Lines** | 66-76, 112-116 |
| **Trigger** | `failure_count >= 5` AND `time.time() - last_failure_time <= 60` |
| **Action** | Return hard fallback string |
| **Reset** | On success (line 139) or after 60s timeout |

---

## 2. Base Agent Fallbacks

### 2a. LLM Response Evaluator Auto-Reject
| Attribute | Detail |
|---|---|
| **File** | `src/agents/base.py` |
| **Lines** | 61-71 |
| **Trigger** | `evaluator.evaluate(response)["total_score"] < 0.5` |
| **Action** | Replace response with: `"Strategy: C\nReason 1: Balanced network design across 50+ ports\nReason 2: Handles demand variability for 100+ lanes"` |
| **Log** | `llm_low_quality` |
| **Current state** | Serialized object strings score > 0.5 (reasoning_content contains keywords) → this fallback does NOT trigger |

### 2b. Exception Retry
| Attribute | Detail |
|---|---|
| **File** | `src/agents/base.py` |
| **Lines** | 74-83 |
| **Trigger** | Exception during `llm_client.chat()` call |
| **Action** | Retry (up to 2 attempts total) |
| **Log** | `llm_retry` |

### 2c. Final Exception Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/agents/base.py` |
| **Lines** | 84-88 |
| **Trigger** | Both call_llm attempts fail with exceptions |
| **Action** | Return same fixed strategy string as 2a |

---

## 3. Coordinator Agent Fallbacks

### 3a. JSON Parse Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/agents/coordinator_agent.py` |
| **Lines** | 354, 518-537 |
| **Function** | `_parse_json_safe()` |
| **Trigger** | json.loads() fails (non-JSON input) |
| **Action** | Try regex extraction; if that also fails, return `{}` |
| **Result** | Empty dict `{}` |

### 3b. Rule-Based Decision Fallback (PRIMARY FALLBACK for coordinator)
| Attribute | Detail |
|---|---|
| **File** | `src/agents/coordinator_agent.py` |
| **Lines** | 370-406 |
| **Trigger** | `if not decisions or "actions" not in decisions:` |
| **Condition evaluation** | `not {}` is `True` → FALLBACK ENTERED |
| **Action** | Generate actions from weak_regions; compute weight_adjustments from coverage gap formula |
| **Formula** | `cov_boost = min(0.2, gap/100)`, `profit = max(0.3, 0.5-cov_boost)`, `coverage = min(0.6, 0.4+cov_boost)`, `cost = 0.1` |
| **Notes** | `"Rule-based fallback: coverage X%, profit $Y/week, Z conflicts."` |
| **Evidence** | pipeline_output.json line 8343 |

### 3c. Weight Validator Normalization
| Attribute | Detail |
|---|---|
| **File** | `src/agents/coordinator_agent.py` |
| **Lines** | 408-413, `src/validation/weight_validator.py` |
| **Trigger** | Always called on fallback weights |
| **Action** | Normalizes weights to [0.05, 0.90] range summing to 1.0 |
| **Log** | `AI_FALLBACK` |

---

## 4. Service Generator Fallbacks

### 4a. Strategy Prompt Exception Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/agents/service_generator_agent.py` |
| **Lines** | 307-313 |
| **Trigger** | Exception during strategy LLM call |
| **Action** | Return formatted strategy string with archetype and rationale |

### 4b. JSON Extraction Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/agents/service_generator_agent.py` |
| **Lines** | 333-336 |
| **Trigger** | json.loads() raises JSONDecodeError |
| **Action** | Regex `\{.*\}` extraction; if that fails, `parsed = {}` |

### 4c. Archetype Validator Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/validation/archetype_validator.py` |
| **Lines** | 77-78 |
| **Trigger** | Empty dict → `if not raw:` |
| **Action** | Return `DEFAULT_ARCHETYPE_PARAMS` |
| **Default values** | direct=0.60, hub_loop=0.15, feeder=0.20, trunk=0.05, vessel_bias=balanced |
| **Log** | `AI_FALLBACK` |

### 4d. Exception Catch-All
| Attribute | Detail |
|---|---|
| **File** | `src/agents/service_generator_agent.py` |
| **Lines** | 338-341 |
| **Trigger** | Any exception in the JSON generation block |
| **Action** | `archetype_params = dict(DEFAULT_ARCHETYPE_PARAMS)` |
| **Log** | `logger.info("archetype_params_generated", tag="AI_FALLBACK", reason="LLM parse failed, using defaults")` |

---

## 5. Orchestrator Fallbacks

### 5a. Problem Analysis Validation Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/agents/orchestrator_agent.py` |
| **Lines** | 127-146 |
| **Trigger** | `_is_valid_analysis()` fails (missing keywords) |
| **Action** | Build formatted analysis from actual data |

### 5b. Executive Summary Validation Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/agents/orchestrator_agent.py` |
| **Lines** | 800-822 |
| **Trigger** | `_is_valid_summary()` fails |
| **Action** | Build formatted summary from actual metrics |
| **Note** | The serialized object contains required keywords in reasoning_content → passes validation → fallback NOT used → corrupted output stored |

### 5c. Coordinator Exception Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/agents/orchestrator_agent.py` |
| **Lines** | 521-537 |
| **Trigger** | Exception in `self.coordinator.process()` |
| **Action** | No-feedback decision_output with `convergence_score=1.0` and `needs_rerun=False` |

### 5d. Consensus Exception Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/agents/orchestrator_agent.py` |
| **Lines** | 616-617 |
| **Trigger** | Exception in `self.consensus_engine.process()` |
| **Action** | Log error and continue (no consensus applied) |

### 5e. Aggregation Exception Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/agents/orchestrator_agent.py` |
| **Lines** | 720-728 |
| **Trigger** | Exception in `self.aggregate_results()` |
| **Action** | Zero-value metrics |

---

## 6. Regional Agent Fallbacks

### 6a. Strategy Exception Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/agents/regional_agent.py` |
| **Lines** | 153-159 |
| **Trigger** | Exception during strategy LLM call |
| **Action** | Build formatted strategy from pre-computed decision_rule |

### 6b. Explanation Validation Retry
| Attribute | Detail |
|---|---|
| **File** | `src/agents/regional_agent.py` |
| **Lines** | 364-369 |
| **Trigger** | `is_valid_explanation()` returns False |
| **Action** | Retry once (2 total attempts) |

### 6c. Explanation Exception Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/agents/regional_agent.py` |
| **Lines** | 371-382 |
| **Trigger** | All explanation attempts fail |
| **Action** | Build formatted explanation from actual metrics |
| **Note** | This is one of the few fallbacks that creates HUMAN-READABLE output |

---

## 7. GA/MILP Fallbacks

### 7a. GA Exception Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/agents/regional_agent.py` |
| **Lines** | 211-220 |
| **Trigger** | Exception in HierarchicalGA.run() |
| **Action** | Zero-chromosome (no services selected) |

### 7b. MILP Exception Fallback
| Attribute | Detail |
|---|---|
| **File** | `src/agents/regional_agent.py` |
| **Lines** | 257-273 |
| **Trigger** | Exception in milp.solve() |
| **Action** | Zero-value cluster result |

---

## Fallback Activation Summary (What Actually Fired)

| Fallback | File | Line | Fired? | Evidence |
|---|---|---|---|---|
| Response serialization | client.py | 169 | ✅ YES | Executive summary shows ChatCompletionMessage string |
| Empty response → hard fallback | client.py | 177-179 | ❌ NO | str(message) is non-empty |
| Evaluator auto-reject | base.py | 61 | ❌ NO | Score > 0.5 (reasoning keywords) |
| JSON parse → empty dict | coordinator_agent.py | 528-536 | ✅ YES | Non-JSON input |
| Rule-based decisions | coordinator_agent.py | 370 | ✅ YES | Empty dict trigger |
| Weight validator | coordinator_agent.py | 409 | ✅ YES (on fallback) | AI_FALLBACK logged |
| JSON extraction → empty dict | service_generator_agent.py | 333-336 | ✅ YES | Non-JSON input |
| Archetype validator → defaults | archetype_validator.py | 77-78 | ✅ YES | Empty dict trigger |
| Gen exception → defaults | service_generator_agent.py | 339-341 | ✅ YES | AI_FALLBACK logged |
| Coordinator exception → no-op | orchestrator_agent.py | 521-537 | ❌ NO | Coordinator ran without exception |
| Aggregation → zeros | orchestrator_agent.py | 720-728 | ❌ NO | Aggregation succeeded |

## Key Finding

**The fallback chain is comprehensive and robust** — every critical component has at least one fallback. The problem is not missing fallbacks but that the PRIMARY path never produces valid output, so the system runs entirely on fallbacks. The pipeline never fails — it just runs on formula-derived weights rather than AI-reasoned weights.
