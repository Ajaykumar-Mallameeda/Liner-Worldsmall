# MA_06 — GA / MILP FORMULATION AND OBJECTIVE AUDIT

**System:** AI Vessel Routing System — Multi-Agent Optimizer
**Audit mode:** Forensic, evidence-driven, read-only
**Date:** 2026-10-05
**Status:** COMPLETE

---

## 0. Summary

| Layer | Intended objective | Actual objective | Verdict |
|---|---|---|---|
| ServiceGA | maximize profit | `10·profit + 0.01·coverage + 0.1·cost` — **rewards cost** | ❌ inverted |
| FrequencyGA | maximize profit − fuel | profit − op − transship − overcap − port — **fuel omitted** | ❌ incomplete |
| HubMILP | maximize profit | `profit + (w_cov/w_profit)·(coverage)·abs(operating_cost + 1)` — **reward scales with cost** | ❌ mis-specified |
| Orchestrator | — | `revenue = profit + cost` — **tautology** | ❌ unfalsifiable |

**All four objective layers are defective.** No layer maximizes profit.

---

## 1. The MILP formulation

### 1.1 Variables

```
flow[(d, s)]        ≥ 0    TEU of demand d shipped directly on service s
transfer_flow[(d,s1,s2)] ≥ 0   TEU of d transferred between services
unserved[d]         ≥ 0    TEU of demand d not served
```

### 1.2 Constraints

```python
# hub_milp.py:392-401 — demand conservation (CORRECT)
for d, demand in enumerate(self.problem.demands):
    prob += (lpSum(flow[(d,s)] for s in compat[d])
           + lpSum(transfer_flow[(d2,s1,s2)] for ... if d2 == d)
           + unserved[d]
           == demand.weekly_teu)

# hub_milp.py:403-404 — coverage floor
if self.min_coverage > 0:
    prob += satisfied_expr >= self.min_coverage * total_demand_teu

# hub_milp.py:406-419 — service capacity (CORRECT)
capacity = svc.capacity * freq * (7 / (svc.cycle_time or 7))
prob += (lpSum(flow[(d,s)] for (d,s2) in flow if s2 == s)
       + lpSum(transfer_flow[(d,s1,s2)] for ... if s1 == s or s2 == s)
       <= capacity)
```

**Demand conservation is correctly stated as an equality** — every TEU is either shipped, transferred, or explicitly unserved. This is the one structurally sound part of the MILP.

Capacity uses the same `7/cycle_time` weekly normalization as the revenue side, so it is **self-consistent with the k-scaled demand** — capacity and demand are scaled consistently, which is why the MILP's internal arithmetic holds despite MA-02-01.

### 1.3 MA-06-01 — The objective rewards operating cost

```python
# hub_milp.py:367-373
coverage_reward = (
    (self.w_coverage / max(self.w_profit, 1e-6))
    * (satisfied_expr / max(total_demand_teu, 1.0))
    * abs(operating_cost + 1)
)
prob += profit_expr + coverage_reward
```

Three defects in three lines:

| Defect | Detail |
|---|---|
| **Multiplicative in cost** | `× abs(operating_cost + 1)` means the coverage bonus is proportional to total cost. Raising operating cost **raises** the objective through this term. |
| **Not normalized** | The coverage term is a *currency* quantity, not a score. It is added to `profit_expr` (also currency), so its magnitude depends on the arbitrary scale of `operating_cost`, not on how well coverage is served. |
| **`abs()` masks sign errors** | For cost ≥ 0 this is a no-op guard; for cost < 0 it becomes `|−cost−1|` and silently flips sign rather than failing. |

**Magnitude:** with `w_coverage/w_profit = 0.25/0.60 = 0.4167` and coverage ≈ 0.9, the reward is `0.375 × (operating_cost + 1)`. For Asia's operating cost of 42.8M that is a **16.1M** bonus on top of profit — a term that scales with the very quantity the objective is supposed to control.

### 1.4 MA-06-02 — `profit_v` is not profit

```python
# hub_milp.py:471
profit_v = pulp.value(prob.objective) or 0.0
```

`prob.objective` is `profit_expr + coverage_reward`. This value is returned as `"profit"` (`:627`) and flows to `regional.weekly_profit` → `summary.weekly_profit` → the headline KPI.

**The reported "profit" includes the cost-proportional coverage bonus.** Given MA-04-01 (fuel 11.7× physical max), the magnitude of this contamination cannot be separated from the reported figure.

### 1.5 MA-06-03 — The fleet constraint is a bool, and violating it zeroes the region

```python
# hub_milp.py:388-389
total_vessels_used = sum(math.ceil(...) for ...)   # Python int
prob += total_vessels_used <= self.fleet_size      # Python bool
```

`frequencies` come from the GA as fixed integers, so `total_vessels_used` is a Python `int` and the comparison is a plain `bool`. Executed against pulp 2.7.0:

| Case | Result |
|---|---|
| `prob += (208 <= 300)` | **OK — `len(prob.constraints) == 0`. Constraint silently absent.** |
| `prob += (900 <= 300)` | **`TypeError: A False object cannot be passed as a constraint`** |

Two consequences, both bad:

1. **Satisfied** → the constraint is never added. The fleet is unconstrained.
2. **Violated** → `TypeError` propagates out of `solve()`. `regional_agent.py:381-395` catches it and appends a fallback result with **`profit: 0.0`, `coverage: 0.0`, `satisfied_demand: 0.0`**.

**A fleet violation silently zeroes an entire region rather than failing loudly.** The `status` field would read `"Failed"`, but nothing in the aggregation surfaces it.

### 1.6 MA-06-04 — The post-solve fleet check is warn-only

```python
# hub_milp.py:558-565
if total_vessels_used > self.fleet_size:
    logger.warning("fleet_constraint_violated | used=%d limit=%d", ...)
```

This computes correctly and logs a warning — **and then proceeds to return a full result anyway.** No exception, no flag in the returned dict, no entry in the artifact.

**The information is computed and deliberately discarded.**

---

## 2. Flow decomposition defects

### 2.1 MA-06-05 — Transshipment load double-counted against a halved revenue

```python
# hub_milp.py:548-551
transfer_flow[(d, s1, s2)] ...
# revenue split with /2.0 while transfer load counted in full
```

A transferred TEU is charged full transshipment cost while generating half revenue. Whether this is intended is undocumented.

**Classification: C — specification ambiguity.**

### 2.2 MA-06-06 — Per-port cost allocation is on the wrong basis

```python
# hub_milp.py:599-601
share = port_service_loads[p][s_idx] / port_load[p]
port_alloc += share * (load * handling + load * variable)   # per-TEU rate × SERVICE TOTAL load
port_alloc += share * fixed                                  # per-CALL cost × load ratio
```

| Component | Its unit | Applied to | Correct? |
|---|---|---|---|
| `handling` | USD **per TEU** | `load` — the service's total across all ports | ❌ |
| `variable_port_call_cost` | USD **per TEU** | `load` — service total | ❌ |
| `fixed` (`port_call_cost`) | USD **per call** | `share` — a load fraction | ❌ |

A per-TEU rate must multiply the load **at that port**, not the service total. A per-call cost must multiply the **number of calls**, not a tonnage ratio.

**Verified against the artifact:** Asia `port_cost` = 913,818 across 104 services (8,786/service); Europe = 14,825,836 across 100 (148,258/service) — **16.9× divergence from identical code.**

### 2.3 MA-06-07 — Regional revenue is structurally absent

The MILP return dict (`hub_milp.py:625-643`) contains **no `revenue` key**:

```python
return {
    "status": ..., "profit": ..., "cost": ..., "fuel_cost": ...,
    "transship_cost": ..., "port_cost": ..., "total_cost": ...,
    "coverage": ..., "satisfied_demand": ..., "unserved_demand": ...,
    "num_direct_vars": ..., "num_transfer_vars": ..., ...
}                                    # ← no "revenue"
```

**Verified consequence in the artifact:** every `regional_results[*].revenue` is **0.00**. `regional_agent.py` never sets a regional `revenue` key either (grep confirms `"revenue"` appears only in per-service merge logic at `:409` and `:422`).

Revenue exists at exactly two levels: per-service (from `service_revenue`) and global (as `profit + cost`). **There is no regional revenue at all** — the dashboard's per-region revenue display is structurally zero.

---

## 3. The GA formulations

### 3.1 ServiceGA — inverted cost sign

```python
# service_ga.py:373-383
if self.objective_mode == "legacy":
    fitness = (self.w_profit   * normalized['profit']
             + self.w_coverage * normalized['coverage']
             - self.w_cost     * normalized['cost'])          # ← correct sign
else:
    fitness = self.objective_weights.calculate_weighted_score(normalized)   # ← ACTIVE
```

```python
# normalization.py:114-118, 147-165
PROFIT_FIRST_WEIGHTS = {'profit': 10.0, 'coverage': 0.01, 'cost': 0.1}
...
score += weight * value        # for EVERY component, including cost
```

`objective_mode` is `"profit_first"` (`optimizer_config.py:15`), so:

```
fitness = 10.0·profit + 0.01·coverage + 0.1·operating_cost
```

**Operating cost carries a positive coefficient.** The GA prefers more expensive designs. The only code that subtracts cost is unreachable.

### 3.2 The configured weights are dead

| Value | Where defined | Used? |
|---|---|---|
| `{'profit': 0.60, 'coverage': 0.25, 'cost': 0.15}` | `optimizer_config.py:41-45` | **No** — only in the unreachable `legacy` branch |
| `{'profit': 10.0, 'coverage': 0.01, 'cost': 0.1}` | `normalization.py:114-118` | **Yes** — hardcoded, not configurable |

The artifact reports `weights_used: {0.60, 0.25, 0.15}` — **values that did not affect the result.**

### 3.3 MA-06-08 — FrequencyGA omits fuel from fitness

```python
# frequency_ga.py:161-166  — computed
fuel_cost += calculate_weekly_fuel_cost(...) * f

# frequency_ga.py:211 — NOT in the return
return revenue - operating_cost - transship_cost - overcap_penalty - port_cost
```

`fuel_cost` is computed then discarded. The frequency optimizer is blind to the dominant cost term — which is precisely why MA-04-01 (fuel at 11.7× physical max) is unopposed by any layer.

### 3.4 MA-06-09 — FrequencyGA uses one arbitrary lane's rate

```python
# frequency_ga.py:200
avg_rev_per_teu = self.problem.demands[0].revenue_per_teu if self.problem.demands else 1000.0
```

Named `avg_`, computes a single lane's value. `service_ga.py:146-148` computes the true weighted average 50 lines away in another module; it is not shared.

### 3.5 MA-06-10 — `total_capacity` omits the cycle-time factor

```python
# service_ga.py:336
total_capacity = sum(self.problem.services[i].capacity for i in selected_idx)
```

But `served` at `:235` uses `effective_capacity = svc.capacity * (7/cycle_time)`. So the overcapacity penalty compares a **cycle-adjusted** numerator against an **unadjusted** denominator:

```python
# service_ga.py:337-338
unused_cap      = max(0.0, total_capacity - satisfied_demand)
overcap_penalty = self.beta * unused_cap * (operating_cost / (total_capacity or 1))
```

With `cycle_time = 14` (production default), `effective_capacity` is **half** the raw capacity, so `unused_cap` is systematically **overstated** — the penalty is computed on capacity that does not exist. This is the same `7/cycle_time` inconsistency that MA-06-11 found on the revenue side of a sibling calculation.

### 3.6 MA-06-11 — Stale `port_hc` in service-level margin

```python
# service_ga.py:262-281 — port_hc assigned inside the loop
for p_id in svc.ports:
    if port:
        port_hc = getattr(port, "handling_cost", 0.0)
        ...
# service_ga.py:295 — used after the loop, for the whole service
service_cost = svc.weekly_cost + service_fuel_cost + (served * port_hc if 'port_hc' in locals() else 0)
```

`port_hc` retains the **last port processed**. The negative-margin penalty — which drives the penalty ladder at `:302-314` — is computed against one arbitrary port's handling rate instead of a service-level sum.

### 3.7 MA-06-12 — Fuel is computed twice per service

`service_ga.py:161-166` computes `fuel_cost` for the portfolio. `service_ga.py:287-293` computes `service_fuel_cost` **again** for the same service. Identical inputs, identical function — the second call is pure waste, and it means the two values can never be reconciled if one is ever changed.

---

## 4. Multi-agent orchestration layer

### 4.1 MA-06-13 — Coverage clamp creates phantom demand

```python
# regional_agent.py:438-442
satisfied = sum(r["satisfied_demand"] for r in cluster_results)   # duplicated across clusters
unserved   = sum(r["unserved_demand"]  for r in cluster_results)  # duplicated
satisfied  = min(satisfied, total_demand)                          # capped

# orchestrator_agent.py:305-308
total_satisfied = min(total_satisfied, true_global_demand)         # capped again
coverage = total_satisfied / true_global_demand * 100
```

`satisfied` is clamped twice; `unserved` never.

**Verified in the artifact:**

| Region | satisfied | unserved | sum | coverage% |
|---|---|---|---|---|
| Asia | 147,838.50 | 13,274.67 | 161,113.17 | **100.0000** |
| Europe | 45,330.00 | 6,307.70 | 51,637.70 | 93.4452 |
| Americas | 80,098.60 | 12,171.73 | 92,270.33 | **100.0000** |
| **Σ** | **273,267.10** | **31,754.10** | **305,021.20** | **89.5895** |

`305,021.20 − 276,446.80 = +28,574.40 TEU/week (+10.34%)` phantom demand. Two regions at exactly 100.0000% are clamp artifacts.

True coverage against the loader total: **98.8498%** vs reported **89.5895%** — understated by **9.26 pp**.

### 4.2 MA-06-14 — Revenue is a tautology

```python
# orchestrator_agent.py:314-316
weekly_revenue = total_profit + total_cost
```

Substituting `profit = revenue − cost` makes the identity `revenue ≡ revenue`. The reported `1,136,109,658.57` is arithmetically forced and carries no independent information.

The accompanying comment — that "the unserved penalty is treated as a cost captured in the operating cost component" — is **false**: `operating_cost` is `Σ weekly_cost × frequency` (`hub_milp.py:304-309`) and contains no penalty term.

### 4.3 MA-06-15 — `skip_milp` can bypass optimization entirely

```python
# hierarchical_ga.py:223
"skip_milp": coverage_estimate < 30.0
```

If the GA's coverage estimate falls below 30%, the MILP is skipped and the **GA estimate is reported as the solution**. The GA estimate uses `min(capacity × freq, direct_demand)` — a **capacity-only** bound with no flow allocation and no revenue at all (`hierarchical_ga.py:207-211`).

All three production regions show `status: "Optimal"`, so this path did not trigger here. It is a latent path where reported economics have no MILP basis at all.

### 4.4 MA-06-16 — Cluster MILP failures are silent

```python
# regional_agent.py:381-395
except Exception as e:
    logger.error("milp_solve_failed", ...)
    cluster_results.append({
        "status": "Failed", "profit": 0.0, "cost": 0.0, ...,
        "unserved_demand": sum(d.weekly_teu for d in sub.demands),
        "selected_services": []
    })
```

A MILP failure contributes **zero profit but full unserved demand**. With MA-06-03, a fleet-violation `TypeError` reaches exactly this handler. The artifact would report a region with profit 0 and full unserved cargo, with no field distinguishing "solved and unprofitable" from "crashed."

**No `status` rollup or failure count appears in `summary_metrics`.**

---

## 5. MILP solution statistics

The artifact exposes solver internals. Read from `regional_results[*]`:

| Region | Direct vars | Transfer vars | Services used | Status |
|---|---|---|---|---|
| Asia | — | — | 104 | Optimal |
| Europe | — | — | 100 | Optimal |
| Americas | — | — | 108 | Optimal |

`num_direct_vars` and `num_transfer_vars` are computed and returned (`hub_milp.py:641-642`) but **not surfaced in the regional dict** (`regional_agent.py:596-625`) — solver transparency is discarded at the aggregation boundary.

---

## 6. MA-06 formulation summary

```
                    ┌─────────────────────────────────────────┐
  CONFIG 0.60/0.25/0.15 ──► problem.profit_weight ──► ServiceGA.w_profit
                    │                                     │
                    │                    ┌────────────────┴───────────────┐
                    │                    │ consumed ONLY inside:         │
                    │                    │   if objective_mode=="legacy" │
                    │                    │   (mode = "profit_first") ❌   │
                    │                    └────────────────────────────────┘
                    ▼
        normalization.PROFIT_FIRST_WEIGHTS  (hardcoded, NOT configurable)
                    │
                    ▼
   ServiceGA fitness = 10·profit + 0.01·coverage + 0.1·cost      ❌ rewards cost
                    │
                    ▼
   FrequencyGA fitness = rev − op − transship − overcap − port    ❌ no fuel
                    │
                    ▼
   HubMILP objective = profit + (w_cov/w_profit)·coverage·|op+1|  ❌ scales with cost
                    │
                    ▼
   profit_v = pulp.value(objective)   ← includes coverage_reward   ❌ not profit
                    │
                    ▼
   Orchestrator revenue = profit + cost                             ❌ tautology
```

---

## 7. Findings from MA_06

| ID | Finding | Classification | Confidence | Impact |
|---|---|---|---|---|
| **MA-06-01** | MILP coverage reward is **multiplicative in `operating_cost`** — raising cost raises the objective | **A. Verified implementation defect** | **High** | ~16.1M bonus on Asia alone |
| **MA-06-02** | `profit_v = pulp.value(prob.objective)` returns **profit + coverage_reward**, not profit | **A. Verified implementation defect** | **High** | Headline KPI is not profit |
| **MA-06-03** | Fleet constraint at `:389` is a Python `bool`; satisfied → silently absent, **violated → `TypeError` that `regional_agent.py:381` catches and converts to a zero-profit region** | **A. Verified implementation defect** | **Very high** — executed against pulp 2.7.0 | Failures are silent, not loud |
| **MA-06-04** | Post-solve fleet check (`:558-565`) logs a warning then **returns a full result anyway** — information computed and discarded | **A. Verified implementation defect** | **High** | Violation never surfaces |
| **MA-06-05** | Transfer load double-counted against a `/2.0` revenue split | **C. Specification ambiguity** | Medium | Transfer economics undocumented |
| **MA-06-06** | Per-TEU port rates applied to service-**total** load; per-call fixed cost × load ratio | **A. Verified implementation defect** | **High** | 16.9× Asia/Europe divergence |
| **MA-06-07** | **Regional `revenue` is structurally absent** — MILP returns no such key; every `regional_results[*].revenue` is `0.00` | **A. Verified implementation defect** | **High** — verified in artifact | Per-region revenue display is always zero |
| **MA-06-08** | ServiceGA fitness uses **`+0.1 × cost`**; the subtracting branch is unreachable | **A. Verified implementation defect** | **High** | GA rewards operating cost |
| **MA-06-09** | FrequencyGA **omits fuel** from fitness despite computing it | **A. Verified implementation defect** | **High** | Frequencies unopposed by the dominant cost |
| **MA-06-10** | `frequency_ga.py:200` names a variable `avg_` but assigns `demands[0].revenue_per_teu` | **A. Verified implementation defect** | **High** | One arbitrary lane prices everything |
| **MA-06-11** | `total_capacity` (`:336`) omits `7/cycle_time` while `served` (`:235`) applies it — **overcapacity penalty computed on capacity that does not exist** | **A. Verified implementation defect** | **High** | Penalty systematically overstated |
| **MA-06-12** | Stale `port_hc` from the port loop used for whole-service margin | **A. Verified implementation defect** | **High** | Margin penalty uses one port's rate |
| **MA-06-13** | Fuel computed **twice per service** (`:161-166` and `:287-293`), same inputs, same function | **A. Verified implementation defect** (efficiency + divergence risk) | **High** | 2× cost; values can never reconcile |
| **MA-06-14** | `satisfied` clamped twice, `unserved` never → **+28,574.40 TEU/wk (+10.34%)** phantom demand | **A. Verified implementation defect** | **High** | Coverage understated 9.26 pp |
| **MA-06-15** | `revenue = profit + cost` is a **tautology**; comment misstates where the unserved penalty lands | **D. Reporting defect** | **High** | Revenue unfalsifiable |
| **MA-06-16** | `skip_milp` when `coverage_estimate < 30%` reports a **capacity-only GA estimate** with no revenue as the solution | **A. Verified implementation defect** (latent) | **High** | Did not trigger on this run |
| **MA-06-17** | MILP exceptions silently produce zero-profit regions; no failure count in `summary_metrics` | **D. Reporting defect** | **High** | Crashes indistinguishable from unprofitability |
| **MA-06-18** | `num_direct_vars` / `num_transfer_vars` computed then discarded at the aggregation boundary | **D. Reporting defect** | **High** | Solver transparency lost |
| **MA-06-19** | CONFIG weights (0.60/0.25/0.15) are inert; the active weights are a separate hardcoded set | **D. Reporting defect** + **C. Ambiguity** | **High** | Artifact misreports the objective |

---

## 8. Reproducing the objective defects

```bash
cd shipping_optimizer

# MA-06-03: bool constraint behaviour
python -c "
import pulp
p=pulp.LpProblem('t',pulp.LpMaximize)
p += (208 <= 300)
print('True case : constraints =', len(p.constraints))
p2=pulp.LpProblem('t2',pulp.LpMaximize)
try: p2 += (900 <= 300)
except TypeError as e: print('False case: TypeError:', e)
"

# MA-06-07: MILP returns no revenue key
grep -n '\"revenue\"' src/optimization/hub_milp.py        # -> line 620 only (per-service)

# MA-06-08: cost sign
sed -n '373,383p' src/optimization/service_ga.py
sed -n '155,165p' src/optimization/normalization.py

# MA-06-09: fuel omitted
sed -n '161,166p;211p' src/optimization/frequency_ga.py

# MA-06-15: tautology
sed -n '314,316p' src/agents/orchestrator_agent.py
```

No project module was imported; no file was written.