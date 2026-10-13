# PHASE P — P6: PROMPT INTELLIGENCE GAPS

## The 8 Intelligence Gaps

### Gap 1: No Trade-off Reasoning
**Severity: HIGH**
- Prompts ask for single-dimension decisions (increase X weight by Y)
- No prompt asks about coverage-vs-profit trade-offs
- Pipeline evidence: increasing coverage_weight from 0.25→0.482 made coverage WORSE (64.7%→63.0%)
- Missing: "If you increase coverage_weight by 0.10, how much profit are you willing to sacrifice?"

### Gap 2: No Network Effects
**Severity: HIGH**
- Each region optimized independently with no cross-region awareness
- Asia's hub ports are all US ports (LAX, EWR, ILM, CHS, HOU) — regional decomposition creates artificial boundaries
- Missing: Transshipment flows, hub overlap, cross-region service dependencies

### Gap 3: No Convergence Awareness
**Severity: HIGH**
- Each iteration is stateless (no memory of what previous adjustments did)
- Pipeline evidence: iteration 0→1 saw coverage and profit both decline, but iteration 1 made the same mistake
- Missing: "Last time you increased coverage_weight, coverage dropped 1.7pp. What's different this time?"

### Gap 4: No Consensus Awareness
**Severity: MEDIUM**
- Consensus Engine may override coordinator's weight suggestions
- Coordinator never learns its suggestions were modified
- Missing: "Your previous weight suggestions were modified by consensus to profit=0.42, coverage=0.47. Do you agree?"

### Gap 5: No Fleet Awareness
**Severity: LOW**
- Vessel costs are standardized; no prompt considers actual fleet economics
- Missing: Fuel costs per vessel class per route, vessel speed trade-offs

### Gap 6: No Economic Depth
**Severity: LOW**
- Only superficial metrics: profit, cost, coverage
- Missing: ROIC, service-level economics, port throughput, slot utilization

### Gap 7: No Risk Assessment
**Severity: LOW**
- Deterministic framing assumes all parameters are stable
- Missing: Demand volatility, port congestion, fuel price sensitivity

### Gap 8: No Regional Differentiation (CRITICAL)
**Severity: CRITICAL**
- 10 regional intelligence metrics computed but never injected into any prompt
- The Phase F work (regional_policy_mapping.py, regional_metrics.py) is entirely disconnected from the prompt layer
- Coordinator treats all regions identically despite massive structural differences
- Missing: Concentration, density, imbalance, hub dominance per region injected into prompts

## What "Intelligence" Is Actually Missing (Coordinate by Prompt)

| Prompt | Missing Intelligence | Gap # |
|---|---|---|
| #1 Coordinator Decisions | Regional metrics, convergence history, consensus output, trade-off framing | 1,3,4,8 |
| #2/#3 Service Generator | Regional policies, hub strategy, fleet economics | 2,5,8 |
| #4/#5 Regional Agent | Global objectives, other region performance, consensus policy | 2,4 |
| #6/#7 Orchestrator | Iteration history, weight effectiveness, regional rationale | 3 |

## The Fundamental Problem

The architecture has evolved to include:
- Consensus Engine (Phase C)
- SharedContext (Phase C)
- Regional Intelligence Metrics (Phase F)
- Regional Policy Mapping (Phase F)
- Iteration Audit (Phase H)

But the prompts were written BEFORE (or during) these phases and were never updated to leverage them. The prompts reflect the architecture as it was, not as it is.
