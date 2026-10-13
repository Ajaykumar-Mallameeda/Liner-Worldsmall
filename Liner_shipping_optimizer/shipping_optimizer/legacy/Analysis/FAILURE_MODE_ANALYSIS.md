# FAILURE MODE ANALYSIS

## Executive Summary

**10 critical/high-severity bugs identified** that could cause system failures or produce invalid optimization results. The most severe issues could lead to silent corruption of optimization results, making the system unsafe for production deployment.

---

## CRITICAL SEVERITY BUGS

### Bug #1 - Fleet Capacity Constraint Not Enforced
**Location**: `src/optimization/hub_milp.py:249`  
**Type**: Logic / Constraint Violation  
**Description**: The fleet capacity constraint (≤300 vessels) is commented out in the MILP, only checked after optimization with a warning.

**Root Cause**:
```python
# Line 249 - Constraint commented out!
#prob += total_vessels_used <= self.fleet_size
```

**Failure Scenario**:
1. High demand regions require 450 vessels collectively
2. MILP solves without fleet constraint
3. System logs warning but continues with invalid solution
4. Deployment impossible - fleet doesn't exist

**Impact**: Silent generation of infeasible solutions that cannot be implemented

**Fix**:
```python
# Uncomment and enforce the constraint
prob += total_vessels_used <= self.fleet_size
```

---

### Bug #2 - MILP Infeasibility Not Checked
**Location**: `src/optimization/hub_milp.py:287-304`  
**Type**: Numerical / Assumption Violation  
**Description**: MILP solver status is not validated before reading variable values.

**Root Cause**:
```python
status = pulp.LpStatus[prob.status]  # Status captured but not checked
# Variables read without checking if status is "Infeasible"
```

**Failure Scenario**:
1. Contradictory constraints (demand > total capacity)
2. MILP returns "Infeasible" status
3. pulp.value() returns None for all variables
4. None converted to 0.0, fake metrics generated

**Impact**: Garbage output presented as valid solution

**Fix**:
```python
if status != "Optimal":
    logger.error(f"MILP failed with status: {status}")
    return {"status": status, "error": f"MILP infeasible: {status}"}
```

---

### Bug #3 - FFE/TEU Unit Confusion
**Location**: `src/data/network_loader.py:68`  
**Type**: Logic / Unit Mismatch  
**Description**: Demand loaded as FFE but capacity calculations assume TEU (1 FFE = 2 TEU).

**Root Cause**:
```python
# Demand loaded as FFE
weekly_teu=float(row["FFEPerWeek"])  # Should convert to TEU!
```

**Failure Scenario**:
1. Demand: 1000 FFE/week loaded
2. Service capacity: 800 TEU/week  
3. System thinks can serve 80% (actually 40%)
4. Coverage metrics double the real value

**Impact**: All coverage calculations wrong by 2x, leading to incorrect decisions

**Fix**:
```python
weekly_teu=float(row["FFEPerWeek"]) * 2.0  # Convert FFE to TEU
```

---

## HIGH SEVERITY BUGS

### Bug #4 - Infinite Rerun Loop
**Location**: `src/agents/coordinator_agent.py:441-442`  
**Type**: Logic / Infinite Loop  
**Description**: Feedback loop can run indefinitely due to weak convergence criteria.

**Root Cause**:
```python
# Only iteration cap, no minimum improvement check
needs_rerun = bool(rerun_reasons) and not at_iteration_cap
```

**Failure Scenario**:
1. System stuck at 69% coverage with marginal gains
2. All 3 iterations run with <1% total improvement
3. Wastes 3x computation time

**Impact**: Resource waste, SLA violations

**Fix**:
```python
# Add minimum improvement check
if prev_coverage >= 0 and (iter_coverage - prev_coverage) < 0.5:
    logger.info("no_meaningful_improvement")
    break
```

---

### Bug #5 - Zero-Demand Services
**Location**: `src/optimization/service_ga.py:96-99`  
**Type**: Assumption / Edge Case  
**Description**: Services with zero direct demand cause mutation and fitness issues.

**Root Cause**:
```python
# Warning logged but no handling for zero direct demand
if scores.sum() == 0:
    scores = np.array([len(svc.ports) for svc in self.problem.services])
```

**Failure Scenario**:
1. Service covers ports with no matching demand pairs
2. direct_demand = 0, GA keeps selecting it due to mutation bias
3. Wastes capacity on zero-revenue routes

**Impact**: Suboptimal service selection, reduced profit

**Fix**: Pre-filter services with zero direct demand or handle them explicitly

---

### Bug #6 - Floating Point Tolerance
**Location**: `src/agents/orchestrator_agent.py:381-387`  
**Type**: Logic / Data Corruption  
**Description**: Demand conservation assertion has too tight tolerance for large numbers.

**Root Cause**:
```python
assert abs(total_demand_before - total_demand_after) < 1.0  # Too tight!
```

**Failure Scenario**:
1. Before split: 833,484.0 TEU
2. After split: 833,483.999999 TEU (FP rounding)
3. Assertion fails with 0.000001 difference
4. Entire pipeline crashes

**Impact**: Pipeline crashes on valid data

**Fix**:
```python
rel_diff = abs(total_demand_before - total_demand_after) / max(total_demand_before, 1.0)
assert rel_diff < 1e-6, f"Demand conservation failed: {rel_diff}"
```

---

## MEDIUM SEVERITY BUGS

### Bug #7 - Empty Demands List
**Location**: `src/optimization/frequency_ga.py:158`  
**Type**: Numerical / Index Error  
**Description**: Transship cost uses hardcoded first demand's revenue.

**Root Cause**:
```python
self.problem.demands[0].revenue_per_teu * 0.05  # May not exist!
```

**Failure Scenario**:
1. Empty demands list after filtering
2. IndexError crashes frequency optimization
3. Regional optimization fails

**Impact**: Optimization failure on edge cases

**Fix**: Add empty list check and average revenue calculation

---

### Bug #8 - Port ID Type Mismatch
**Location**: `src/data/network_loader.py:35`  
**Type**: Type / Data Inconsistency  
**Description**: Port ID type mismatch between loader (string) and services (integer).

**Root Cause**:
```python
Port(id=str(row["port_index"]))  # String ID
# Services use integer port IDs
```

**Failure Scenario**:
1. Service has port ID 123 (integer)
2. Port loaded as "ABC" (string)
3. Port lookup fails, handling cost = 0

**Impact**: Incorrect cost calculations

**Fix**: Maintain consistent type (convert all to integers)

---

### Bug #9 - Fractional Frequencies
**Location**: `src/optimization/hub_milp.py:270-279`  
**Type**: Logic / Capacity Miscalculation  
**Description**: Service capacity calculation ignores frequency rounding.

**Root Cause**:
```python
capacity = svc.capacity * freq * (7 / (svc.cycle_time or 7))  # freq may be float
```

**Failure Scenario**:
1. GA evolves freq=2.7 for optimal fitness
2. MILP uses freq=2.7 for capacity
3. Actual deployment needs 3 vessels
4. Underestimates capacity needed

**Impact**: Deployed solution infeasible

**Fix**: Round frequencies to integers before capacity calculation

---

### Bug #10 - Zero Global Demand
**Location**: `src/agents/orchestrator_agent.py:174-179`  
**Type**: Assertion / Edge Case  
**Description**: Coverage assertion doesn't handle zero global demand.

**Root Cause**:
```python
coverage = min(total_satisfied, true_global_demand) / true_global_demand * 100  # Division by zero!
```

**Failure Scenario**:
1. Problem with no demand (edge case)
2. ZeroDivisionError in aggregation
3. Pipeline crashes

**Impact**: Pipeline crashes on edge case

**Fix**: Handle zero demand case explicitly

---

## RISK SUMMARY

| Bug # | Severity | Location                     | Trigger Condition               | Fix Effort |
|-------|----------|------------------------------|---------------------------------|------------|
| 1     | CRITICAL | hub_milp.py:249              | Fleet >300 vessels              | 2 hours    |
| 2     | CRITICAL | hub_milp.py:287              | MILP infeasible                 | 1 hour     |
| 3     | CRITICAL | network_loader.py:68         | FFE/TEU unit mismatch           | 1 hour     |
| 4     | HIGH     | coordinator_agent.py:441     | Stuck in convergence loop       | 2 hours    |
| 5     | HIGH     | service_ga.py:96             | Zero-demand services selected   | 3 hours    |
| 6     | HIGH     | orchestrator_agent.py:381    | FP rounding in demand conservation | 1 hour |
| 7     | MEDIUM   | frequency_ga.py:158          | Empty demands list              | 1 hour     |
| 8     | MEDIUM   | network_loader.py:35         | Port ID type mismatch           | 2 hours    |
| 9     | MEDIUM   | hub_milp.py:270              | Fractional frequency values     | 1 hour     |
| 10    | LOW      | orchestrator_agent.py:174    | Zero global demand edge case    | 0.5 hours  |

---

## PRIORITY FIX ORDER

### Immediate (Fix Before Any Production Run):
1. **Bug #2** - MILP infeasibility check prevents garbage output
2. **Bug #1** - Fleet constraint enforcement prevents infeasible deployments
3. **Bug #3** - Unit correction prevents 2x error in all calculations
4. **Bug #6** - Prevents pipeline crashes on large datasets
5. **Bug #10** - Prevents crashes on edge cases

### Short-term (Fix Before Production Deployment):
6. **Bug #4** - Prevents resource waste from infinite loops
7. **Bug #5** - Improves optimization quality
8. **Bug #7** - Improves robustness for filtered problems
9. **Bug #8** - Fixes cost calculation accuracy
10. **Bug #9** - Ensures deployment feasibility

---

## FAILURE PATTERN ANALYSIS

### Common Root Causes:
1. **Missing Validation**: Most bugs occur because outputs aren't validated
2. **Unit Inconsistency**: Mixed units (FFE/TEU) cause systematic errors
3. **Edge Case Handling**: Assumptions about data lead to crashes
4. **Constraint Enforcement**: Critical constraints commented out or not checked

### Recommended Practices:
1. Always validate solver status before extracting results
2. Convert all units to standard at data loading stage
3. Add assertions for all assumptions
4. Use relative tolerances for floating point comparisons
5. Handle empty list and edge cases explicitly

---

## PREVENTION STRATEGIES

### Code Reviews:
- Check all assumptions are validated
- Verify all constraints are enforced
- Ensure unit consistency throughout
- Look for commented-out code

### Testing:
- Add integration tests with infeasible inputs
- Test with edge cases (empty lists, zero values)
- Validate unit conversions in test suite
- Add performance tests for large datasets

### Runtime Monitoring:
- Log MILP solver status
- Monitor fleet vessel usage
- Track demand conservation
- Alert on unusual optimization patterns

---

## CONCLUSION

The system has several critical bugs that could lead to silent corruption of optimization results or complete system failures. These must be fixed immediately before any production deployment. The good news is that most fixes are straightforward (1-2 hours each) and the issues are well-understood.

After fixing these bugs, the system will be much more reliable and suitable for production use.