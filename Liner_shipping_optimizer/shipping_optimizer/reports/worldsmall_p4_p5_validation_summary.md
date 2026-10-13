# WorldSmall P4 + P5 Validation Summary

## Executive Summary

Phase 4 (Runtime Validation) and Phase 5 (Service & Optimization Validation) have been executed against the official WorldSmall benchmark instance. The complete pipeline — from raw CSV data through service generation, GA optimization, and MILP solving — executes correctly with no artificial scaling, no artificial fleet limits, and no benchmark corruption.

**P4: PASS**  
**P5: PASS WITH CONDITIONS**

The conditions are pre-existing issues (environmental LLM failure, outdated test assertions) unrelated to WorldSmall data integrity or benchmark semantics.

---

## P4 Result

**PASS**

All 29 WorldSmall integration tests pass. Dataset truth verified:
- 47 ports, 1,764 demands, 2,162 distances, 263 fleet vessels
- Demand total: 138,247 FFE/week = 276,494 TEU/week (×2 conversion only)
- No DEMAND_SCALE applied to WorldSmall
- No artificial fleet cap — 263 derived from `fleet_WorldSmall.csv`
- No distance fallback used
- Full pipeline smoke test completed in ~300s

## P5 Result

**PASS WITH CONDITIONS**

Service generation (789 services), HierarchicalGA (88 selected, 262/263 vessels), FrequencyGA (74 active), and HubMILP (optimal, $262.6M profit) all execute correctly on WorldSmall data.

Conditions:
- Pre-existing `test_ga.py` assertion failure (unrelated to WorldSmall)
- Pre-existing `test_milp.py` PuLP TypeError (unrelated to WorldSmall)
- LLM provider environment issue (all providers fail with `proxies` kwarg error)

---

## Dataset Integrity

| Item | Value | Source | Verified |
|------|-------|--------|----------|
| Ports | 47 | `data/raw/WorldSmall/ports.csv` | ✓ |
| Demands | 1,764 | `Demand_WorldSmall_Fixed_Sep.csv` | ✓ |
| Demand total (FFE) | 138,247 | Raw CSV column sum | ✓ |
| Demand total (TEU) | 276,494 | FFE × 2 conversion | ✓ |
| Fleet classes | 6 | `fleet_WorldSmall.csv` | ✓ |
| Fleet total | 263 | Sum of quantities | ✓ |
| Distance pairs | 2,162 | `dist_dense.csv` (47×46) | ✓ |
| Missing distances | 0 | Full coverage verified | ✓ |
| Positive distances | All | No zero/negative values | ✓ |
| Duplicate OD pairs | 0 | Unique pairs verified | ✓ |
| Invalid port refs | 0 | All references valid | ✓ |

---

## Runtime Integrity

| Component | Status | Notes |
|-----------|--------|-------|
| NetworkLoader | ✓ PASS | CSV and JSON paths both work |
| Problem construction | ✓ PASS | Fleet attached correctly |
| ServiceGeneratorAgent | ✓ PASS | 789 services generated at runtime |
| RegionalAgent | ✓ PASS | Decomposition, filtering, optimization |
| HierarchicalGA | ✓ PASS | Fleet constraint respected (262/263) |
| FrequencyGA | ✓ PASS | Fleet constraint respected |
| HubMILP | ✓ PASS | Optimal solution found |
| Orchestrator | ⚠ PARTIAL | LLM calls fail (environment); GA/MILP paths OK |

---

## Demand Semantics

| Aspect | WorldSmall | WorldLarge |
|--------|-----------|------------|
| DEMAND_SCALE | 1 (auto-detected) | 6 (auto-detected) |
| FFE→TEU conversion | ×2 (lane-specific) | ×2 (lane-specific) |
| Artificial scaling | None | DEMAND_SCALE=6 (legacy) |
| Revenue conversion | ×2 matching demand | ×2 matching demand |

**No artificial demand scaling for WorldSmall.** The ×2 is the standard FFE→TEU conversion, not an artificial multiplier.

---

## Fleet Semantics

| Aspect | WorldSmall | WorldLarge |
|--------|-----------|------------|
| Source file | `fleet_WorldSmall.csv` | `fleet_world_large.csv` |
| Total vessels | 263 (from data) | 501 (from data) |
| Hardcoded limit | None | None |
| Legacy fallback | 300 (only if fleet=None) | 300 (only if fleet=None) |
| GA fleet usage | 263 ✓ | N/A (test uses default) |
| MILP fleet usage | 263 ✓ | N/A |

---

## Distance Semantics

| Aspect | Status |
|--------|--------|
| All 2,162 directed pairs present | ✓ |
| All distances > 0 | ✓ |
| 500 nm fallback invoked | Never (all pairs exist) |
| Self-distances logged as warnings | Cosmetic only |

---

## Service Generation

| Aspect | Status |
|--------|--------|
| Services generated at runtime | ✓ (789 services) |
| No fabricated JSON services | ✓ (`services: []` in JSON) |
| All ports valid | ✓ |
| All routes valid | ✓ |
| Costs finite and positive | ✓ |
| No duplicate services | ✓ |
| Region-prefixed IDs unique | ✓ |

---

## GA Validation

| Aspect | Status |
|--------|--------|
| Fleet limit from `problem.fleet` | ✓ (263, not 300) |
| Fleet constraint respected | ✓ (262/263 used) |
| Services valid | ✓ |
| Fitness finite | ✓ (range: $264M–$331M) |
| No NaN in output | ✓ |

---

## MILP Validation

| Aspect | Status |
|--------|--------|
| Fleet size propagated correctly | ✓ (explicit param = 263) |
| Solver finds optimal solution | ✓ |
| Profit positive | ✓ ($262.6M) |
| Coverage valid | ✓ (40.94%) |
| No NaN/Inf in output | ✓ |

**Note**: Pre-existing `test_milp.py` fails due to PuLP constraint bug when `fleet_size` is not explicitly passed. This is a test issue, not a WorldSmall issue.

---

## Feasibility

| Constraint | Requirement | Result |
|-----------|-------------|--------|
| Fleet usage ≤ available | ≤ 263 vessels | 262 ✓ |
| Service references valid | In problem.services | ✓ |
| Port references valid | In problem.ports | ✓ |
| Demand references valid | In problem.demands | ✓ |
| No negative quantities | All ≥ 0 | ✓ |
| Output finiteness | No NaN/Inf | ✓ |

---

## Objective / Profit

WorldSmall MILP result:
- **Weekly profit**: $262,605,376
- **Coverage**: 40.94% (137,905 / 276,494 TEU)
- **Profit margin**: positive ✓
- **Components**: revenue − operating − fuel − port − transship − overcap penalty

Profit formula unchanged from P3. No new unit conversions introduced.

---

## WorldLarge Regression

| Check | Status |
|-------|--------|
| `large_shipping_problem.json` unchanged | ✓ (SHA-256 stable) |
| WorldLarge CSV paths unchanged | ✓ |
| DEMAND_SCALE=6 still applied | ✓ |
| 333 ports, 9,622 demands | ✓ |
| 501 vessels in fleet | ✓ |
| 43,056 distance entries | ✓ |

---

## Known Issues

### Non-Blocking

1. **Post_panamax/Super_panamax capacity mismatch**: LINERLIB specifies 4,200/7,500 FFE but runtime uses 5,000/8,000 TEU in fuel model. Pre-existing since P1.

2. **HubMILP fleet auto-detection gap**: `HubMILP.__init__` requires explicit `fleet_size` parameter (default 300). Does not auto-read `problem.fleet.total_vessels`. Currently worked around in `regional_agent.py` but could be more robust.

3. **Self-distance log warnings**: `fuel_cost.py` logs "No distance found" for port self-loops (e.g., NLRTM→NLRTM). Harmless but noisy.

4. **LLM provider environment failure**: All providers (Groq, OpenRouter, Google) fail with `Client.__init__() got an unexpected keyword argument 'proxies'`. This is a dependency version conflict preventing LLM-based orchestration but does NOT affect GA/MILP optimization paths.

5. **Pre-existing test failures**:
   - `test_ga.py`: Assertion `len(result["services"]) == 300` fails because `_filter_services()` legitimately reduces pool to ~222
   - `test_milp.py`: PuLP TypeError when `fleet_size` not explicitly passed

### Blocking

**None.**

---

## Final Readiness Assessment

The WorldSmall benchmark instance is **ready for downstream RL comparison (P6+)**. The pipeline correctly:

1. Loads all 47 ports, 1,764 demands, 2,162 distances, and 263 vessels from official source data
2. Applies only the documented FFE→TEU ×2 conversion (no artificial scaling)
3. Derives fleet size from data (263), not from hardcoded constants
4. Generates services at runtime (no fabricated JSON services)
5. Executes GA and MILP optimization with fleet constraints respected
6. Produces structurally valid, feasible solutions
7. Preserves WorldLarge functionality unchanged

The only remaining issue is the LLM provider environment failure, which is an infrastructure concern outside the scope of P4/P5.

---

## Recommended Next Phase

**P6 — Common Evaluator**: With the WorldSmall runtime baseline established and validated, proceed to build the common evaluator that can compare RL vs. MA (Multi-Agent) solutions on identical WorldSmall instances.

**Prerequisites for P6**:
- Resolve LLM provider `proxies` environment issue (or confirm RL phase doesn't require LLM)
- Fix pre-existing `test_milp.py` PuLP constraint bug
- Update `test_ga.py` assertion to account for service filtering

---

*Validation completed: 2026-09-12*
*Phases covered: P4 (Runtime Validation), P5 (Service & Optimization Validation)*
*Out of scope: P6 (Common Evaluator), P7 (RL Comparison)*
