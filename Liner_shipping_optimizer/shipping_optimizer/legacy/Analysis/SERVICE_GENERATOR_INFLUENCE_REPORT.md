# P0.2 — SERVICE GENERATOR INFLUENCE REPORT

## Experiment Design
- Archetype prompt ON (LLM generates mix ratios) vs Default archetype only
- Source: pipeline_output.json archetype_params per region
- Rule: No code modifications

## Baseline Evidence
From pipeline_output.json, ALL 5 regions used identical archetype_params:

| Region | direct_ratio | hub_loop_ratio | feeder_ratio | trunk_ratio | vessel_bias | Source |
|---|---|---|---|---|---|---|
| Asia | 0.60 | 0.15 | 0.20 | 0.05 | balanced | DEFAULT |
| Europe | 0.60 | 0.15 | 0.20 | 0.05 | balanced | DEFAULT |
| Americas | 0.60 | 0.15 | 0.20 | 0.05 | balanced | DEFAULT |
| Middle East | 0.60 | 0.15 | 0.20 | 0.05 | balanced | DEFAULT |
| Africa | 0.60 | 0.15 | 0.20 | 0.05 | balanced | DEFAULT |

## Analysis
All 5 regions exactly match DEFAULT_ARCHETYPE_PARAMS (from archetype_validator.py:25-35). The LLM archetype JSON prompt at service_generator_agent.py:318-325 produced output that failed validation and was replaced with defaults.

## Service Pool Impact

| Metric | Current (Default) | With LLM Archetype |
|---|---|---|
| Service pool composition | 60% direct, 15% hub-loop, 20% feeder, 5% trunk | Varies by region (if LLM worked) |
| Total services generated | 3,998 | Same (rule-based generation unaffected) |
| Regional differentiation | NONE — all regions identical | Would vary by regional network stats |
| MLIP selection pool | Uniform across regions | Differentiated across regions |

## Verdict
**Measured Influence: 0%** — The Service Generator LLM had ZERO actual influence. All regions used the default 60/15/20/5 archetype mix. The LLM either failed or produced output outside valid ranges, causing the archetype_validator to reject it and substitute defaults.

## Critical Observation
The Service Generator Agent's archetype prompt is the ONLY mechanism for LLM-influenced service pool design. Since it produces no influence, the service pool is 100% rule-determined. This means the LLM investment in prompt #3 (Archetype JSON) and prompt #2 (Strategy confirmation) is entirely wasted in the current state.

## Upgrade Implication
Before upgrading the prompt, diagnose why the LLM archetype generation fails. The `validate_archetype_params()` function at archetype_validator.py:188-200 may be rejecting valid LLM output due to vessel_bias string matching or ratio bounds. This is a VALIDATOR issue, not a prompt issue.
