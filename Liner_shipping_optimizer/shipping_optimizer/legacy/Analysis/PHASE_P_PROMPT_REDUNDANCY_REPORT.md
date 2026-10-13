# PHASE P — P5: PROMPT REDUNDANCY REPORT

## Classification

### KEEP (2 prompts)
| Prompt | Reason |
|---|---|
| #1 Coordinator Decisions | Core feedback mechanism, optimizer influence |
| #3 ServiceGen Archetype JSON | Active optimizer influence, well-validated |

### MERGE (2 prompts to merge)
| Prompt | Merge Into | Waste Analysis |
|---|---|---|
| #2 ServiceGen Strategy | #3 Archetype JSON | Strategy is pre-computed before prompt; LLM confirms already-made decision |
| #4 Regional Strategy | #5 Regional Explanation | Same agent, same model, same input; strategy is pre-decided |

### REMOVE (2 prompts)
| Prompt | Reason | Risk |
|---|---|---|
| #6 Orchestrator Analysis | Purely display-only, fallback produces adequate text | LOW |
| #7 Orchestrator Summary | Broken output + display-only, fallback produces adequate text | LOW |

## Redundancy Patterns

### Pattern 1: Pre-Computed → LLM Confirmation (3 instances)
- ServiceGen: `archetype` computed → prompt includes it → LLM confirms
- Regional: `decision_rule` computed → prompt includes it → LLM confirms
- Orchestrator: `size_label` computed → prompt includes it → LLM confirms

### Pattern 2: Triple-Nested "Cite Numbers" Instruction
1. System prompt: "Every statement must cite a specific number"
2. User prompt body: "Ground every recommendation in the network statistics"
3. Format spec: "Citation: [...]" in the STRICT FORMAT

### Pattern 3: Duplicate Validator Functions
- `_is_valid_analysis()` → checks keyword set A
- `is_valid_explanation()` → checks keyword set B
- `_is_valid_summary()` → checks keyword set C
- `_parse_json_safe()` → regex extraction

All four solve "LLM output doesn't match expected format → fallback" — could be one shared function.

### Pattern 4: Repetitive LLM Call Pattern
```python
for _ in range(2):
    result = self.call_llm(prompt, temperature=0.1)
    if self._is_valid_*(result): break
if not self._is_valid_*(result): result = fallback
```
This appears 3 times (regional explanation, orchestrator analysis, orchestrator summary). Should be a shared helper.

## Token Waste Summary

Pre-computed answers that the LLM confirms:
- Size label (orchestrator analysis): ~125 tokens wasted
- Strategy type (regional): ~175 tokens wasted  
- Archetype selection (service gen): ~200 tokens wasted
- Verdict (executive summary): ~325 tokens wasted

**Total pre-computation waste:** ~825 tokens per run (55% of LLM spend)
