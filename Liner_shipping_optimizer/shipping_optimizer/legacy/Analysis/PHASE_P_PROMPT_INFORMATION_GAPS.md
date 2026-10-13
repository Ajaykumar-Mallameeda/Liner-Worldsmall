# PHASE P — P4: PROMPT INFORMATION GAP ANALYSIS

## Information Inventory

The following information exists in the system but is **NOT provided to any prompt**:

| Information | Source Module | Available Since | Priority |
|---|---|---|---|
| SharedContext (global objectives + regional priorities) | `shared_context.py` | Phase C | **CRITICAL** |
| Convergence history (iteration audit trail) | `orchestrator.py` iteration_audit | Phase H | **HIGH** |
| Weight adjustment effectiveness (before/after metrics) | iteration_audit | Phase H | **HIGH** |
| Regional intelligence metrics (concentration, density, imbalance) | `regional_metrics.py` | Phase F | **HIGH** |
| Hub strategy (primary_hubs, overlap_hubs) | `shared_context.py` | Phase C | MEDIUM |
| Consensus outputs (confidence, resolved conflicts) | `consensus_engine.py` | Phase C | MEDIUM |
| Regional policy rationale | `regional_policy_mapping.py` | Phase F | MEDIUM |
| Previous iteration service pool metrics | `problem.services` | Baseline | LOW |
| Fleet economics (fuel costs per vessel) | `fuel_cost.py` | Baseline | LOW |
| GA convergence state | HierarchicalGA | Baseline | LOW |

## The Single Largest Gap

**SharedContext is NEVER injected into any prompt.**

The `SharedContext` dataclass (shared_context.py) holds:
- `global_objectives`: profit_weight, coverage_weight, cost_weight, iteration, convergence_score
- `regional_priorities`: per-region coverage_priority, profit_priority, hub_focus, vessel_bias
- `service_archetype_plan`: direct_ratio, hub_loop_ratio, feeder_ratio, trunk_ratio
- `hub_strategy`: primary_hubs, recommended_hubs, overlap_hubs

This data is computed and available at line 633 of orchestrator_agent.py but never reaches the prompt templates.

## Evidence: What Would Have Changed

From pipeline_output.json:
- Coordinator suggested weights profit=0.395, coverage=0.505 at iteration 1
- If coordinator knew regional metrics: Asia (dense, 5.3% top3), Europe (very_dense, 7.8%), Americas (sparse, 34.2%)
- The weight suggestion would likely be different per region
- Instead, uniform weights applied globally made coverage and profit both decline
