# MA_05 — SERVICE GENERATION AND FLEET FEASIBILITY AUDIT

**System:** AI Vessel Routing System — Multi-Agent Optimizer
**Audit mode:** Forensic, evidence-driven, read-only
**Date:** 2026-10-05
**Status:** COMPLETE

---

## 0. The headline

**The system deploys 624 vessels against a 263-vessel fleet — a 2.4× overcommitment that no layer detects.**

Each region is independently checked against the **full 263-vessel fleet**. The three checks pass individually (208, 200, 216 ≤ 263). The **sum is never checked against anything.** The MILP, which makes the final allocation, has no working fleet constraint at all.

This is a different finding from the "fleet constraint is a no-op" reported earlier (MA-01-03). That was true but incomplete. The constraint is **doubly** defective: it is a no-op *and* the GA-level check that does work has the wrong scope.

---

## 1. Corrections to earlier working assumptions

Stated explicitly, because the audit mandate requires prior findings be treated as hypotheses:

| Earlier assumption | Status on verification |
|---|---|
| "312 services against 263 vessels = 19% overcommit" | **Incomplete.** 312 is *services*, not vessels. Each service needs `ceil(cycle_time × f / 7)` vessels. At cycle_time 14, f=1 → **2 vessels per service**. |
| "FrequencyGA ignores the fleet" | **Wrong.** `frequency_ga.py:128-138` reads `problem.fleet.total_vessels` and hard-rejects (`-1e9`) when exceeded. The GA-level check is real. |
| "Fleet is never enforced" | **Wrong at the GA level, right at the MILP level.** |
| "312 services" | **Confirmed** — 104 + 100 + 108 = 312, matching `total_services`. *(An earlier working note of 309/98/107 was wrong and is corrected here.)* |

The 263-vessel fleet **is** loaded on the production path (`regional_agent.py:360` passes `fleet=problem.fleet` into every sub-problem), so the fleet data is available to every layer. It is simply never summed.

---

## 2. The vessel-counting formula

```python
# hierarchical_ga.py:175-180  and  frequency_ga.py:133
vessels(i) = math.ceil(cycle_time_i × max(1, frequency_i) / 7)
```

A service with cycle_time 14 days and weekly frequency 1 requires 2 vessels. This is the standard liner round-trip requirement and is **correctly formulated**.

### 2.1 Cycle time on the production path

```python
# regional_agent.py:266-274
norm.append(Service(
    id=s.get("id", i), ports=s["ports"],
    capacity=s.get("capacity", 5000),
    weekly_cost=s.get("weekly_cost", 150_000),
    cycle_time=s.get("cycle_time", 14),        # ← default 14
    vessel_class=vessel_class
))
```

Services arriving from `ServiceGeneratorAgent` as **dicts** take the default `cycle_time = 14`. This is the path taken on production (the artifact's services are dict-shaped with `load`, `capacity`, `vessel_class`). **Every service therefore needs 2 vessels.**

---

## 3. MA-05-01 — Per-region fleet check against an unpartitioned global fleet (CRITICAL)

### 3.1 What the code does

```python
# regional_agent.py:357-362
sub = Problem(
    ports           = ports,
    services        = problem.services,
    demands         = cluster_demands,
    distance_matrix = problem.distance_matrix,
    fleet           = problem.fleet,            # ← the FULL 263-vessel fleet
)
```

```python
# hierarchical_ga.py:170-174
fleet_size = 300  # legacy default
if self.problem.fleet is not None and self.problem.fleet.total_vessels > 0:
    fleet_size = self.problem.fleet.total_vessels     # = 263, for EVERY region
```

### 3.2 The measured consequence

Each of the three regions is checked against 263 vessels **independently**:

| Region | Services | Vessels each | Vessels required | Limit | Passes? |
|---|---|---|---|---|---|
| Asia | 104 | 2 | **208** | 263 | ✅ |
| Europe | 100 | 2 | **200** | 263 | ✅ |
| Americas | 108 | 2 | **216** | 263 | ✅ |
| **Σ** | **312** | — | **624** | **263** | ❌ **2.4× over** |

```
Required  : 624 vessels
Available : 263 vessels
SHORTFALL : 361 vessels
OVERCOMMIT: 2.37×
```

**The system can permit up to 3 × 263 = 789 vessels while possessing 263.**

### 3.3 Why this is a defect and not a formulation choice

A partitioned fleet would be a defensible modelling decision — allocate N vessels to Asia, M to Europe, K to Americas, and constrain each region to its share. **That is not what happens.** The code passes the *entire* fleet to every region and never subtracts what earlier regions consumed. There is no partitioning, no reservation, and no global check. The constraint is applied to the wrong quantity.

Under a correct partitioned scheme the three regions would be capped at their shares (e.g. 88 / 88 / 87) and the selected service count would fall to ~131–145, not 312.

### 3.4 Classification

**A — verified implementation defect.** The check exists, executes, and binds — but against the wrong scope. This is more serious than MA-01-03 (a no-op constraint), because it produces a *plausible-looking* pass.

---

## 4. MA-05-02 — The MILP fleet constraint is a verified no-op

```python
# hub_milp.py:61
fleet_size: int = 300

# hub_milp.py:389
prob += total_vessels_used <= self.fleet_size
```

Executed against the installed solver:

```
pulp version: 2.7.0
  prob += (5 <= 300)    ->  OK,   constraints = 0    # adds nothing
  prob += (900 <= 300)  ->  TypeError: A False object cannot be passed as a constraint
```

`x <= 300` evaluates to a Python `bool` before PULP sees it. PULP never receives a constraint. `len(prob.constraints)` is unchanged.

`self.fleet_size` is never overridden by any caller — `fleet_size: int = 300` at `:61` is the sole assignment, so even the *intended* limit is a hardcoded 300 rather than the real 263.

### 4.1 Consequence

The MILP is where flows, transfers, and the final profit are determined. It has **no fleet constraint whatsoever**. The final 312-service solution is therefore never fleet-checked at the layer that produces the reported economics.

---

## 5. MA-05-03 — Fleet composition is never matched to service requirements

The fleet has **six** classes with distinct capacities and costs:

| Class | Available | Capacity (FFE) | Consumption t/d |
|---|---|---|---|
| Feeder_450 | 24 | 450 | 15 |
| Feeder_800 | 29 | 800 | 25 |
| Panamax_1200 | 68 | 1,200 | 35 |
| Panamax_2400 | 74 | 2,400 | 55 |
| Post_panamax | 58 | 5,000 | 80 |
| Super_panamax | 10 | 8,000 | 100 |

**Nothing checks that a service requiring a 5,000-FFE vessel can be crewed.** `map_capacity_to_vessel_class()` (`fuel_cost.py`) picks the nearest class for *fuel purposes* only. There is no allocation of the 24 + 29 + 68 + 74 + 58 + 10 inventory to the 312 selected services, and no feasibility check against class availability.

A network requiring 312 vessels would need at least 312 from this inventory — but the largest classes total only 68. **Any** deployment above ~200 services is class-infeasible regardless of the total count.

---

## 6. MA-05-04 — Vessel capacity is ignored in the fleet model

`FleetClass.capacity_teu` is loaded from `Capacity FFE` (`network_loader.py:192`) and **never read** — grep confirms zero consumers outside the dataclass and loader.

Consequence: the model has no check that a service's `capacity` is compatible with the vessel assigned to it, and no way to report a capacity-constrained solution. `Service.capacity` is a free parameter from the generator's perspective, defaulting to 5,000 (`regional_agent.py:267`).

Note also that `Capacity FFE` is **FFE**, stored in a field named `capacity_teu`. The same FFE/TEU naming defect as `Demand.weekly_teu` (MA-02-13) — harmless here only because the field is never consumed.

---

## 7. MA-05-05 — Service generation is entirely rule-based

From the artifact's own counters:

| Counter | Value |
|---|---|
| `llm_calls` | 5 |
| `coordinator_fallback_count` | **0** |
| `servicegen_ai_count` | **0** |
| `servicegen_fallback_count` | **3** |

**All three regions used the rule-based fallback.** The LLM contributed nothing to service generation on the production path. (The CoordinatorAgent's 5 LLM calls did succeed — see MA-01-14, which corrects a prior audit's contrary claim.)

Archetype mix is a **hardcoded constant**, identical in all three regions:

```json
"archetype_mix": { "direct_ratio": 0.6, "hub_loop_ratio": 0.15,
                    "feeder_ratio": 0.2, "trunk_ratio": 0.05 }
```

`vessel_bias: "balanced"` — also constant. The regions differ only through port clustering and demand, not through service-generation strategy.

**Consequence.** 2,238 candidate services were generated (812 + 623 + 803) using one fixed heuristic applied to three different port geographies. The agent framework adds no generation diversity.

---

## 8. MA-05-06 — The service filter discards 62% of candidates with no economic rationale

| Region | Generated | Filtered out | Retained | Selected | Retained→Selected |
|---|---|---|---|---|---|
| Asia | 812 | 508 (62.6%) | 304 | 104 | 34.2% |
| Europe | 623 | 405 (65.0%) | 218 | 100 | 45.9% |
| Americas | 803 | 499 (62.1%) | 304 | 108 | 35.5% |
| **Σ** | **2,238** | **1,412 (63.1%)** | **826** | **312** | **37.8%** |

The filter is `_filter_services(problem, region_budget)`, driven by adaptive budget signals and a `min_route_demand_threshold`. Filtering 63% of candidates before optimization is a legitimate heuristic **if** the discarded services are demonstrably inferior. That rationale is **not recorded in the artifact** — no metric explains why any specific service was dropped.

**Classification: C — specification ambiguity.** The filter's criteria are not documented and not reported. Whether it is sound cannot be determined from the artifact.

---

## 9. Vessel feasibility — summary

| Layer | Fleet constraint | Limit used | Effective? |
|---|---|---|---|
| `FrequencyGA._evaluate` | `frequency_ga.py:128-138` | 263 (real) | ✅ **Works** — hard reject at `-1e9` |
| `HierarchicalGA` post-GA prune | `hierarchical_ga.py:182-203` | 263 (real) | ⚠ Works, but **per-region scope** (MA-05-01) |
| `HubMILP.solve` | `hub_milp.py:389` | 300 (hardcoded) | ❌ **No-op** (MA-05-02) |
| **Global / cross-region** | — | — | ❌ **Absent** |
| **Class composition** | — | — | ❌ **Absent** (MA-05-03) |
| **Capacity compatibility** | — | — | ❌ **Absent** (MA-05-04) |

**The final reported solution is fleet-infeasible by 2.4× and this fact appears nowhere in the artifact or the API.**

---

## 10. What the artifact reports

| Field | Present | Value |
|---|---|---|
| Vessels required | ❌ | — |
| Vessels available | ❌ | — |
| Vessel utilization | ❌ | — |
| Fleet feasibility flag | ❌ | — |
| Services selected | ✅ | 312 |

The frontend greps confirm this: `pipeline_output.json` contains **no** `utilization`, `vessels_utilized`, or `fleet` field. `backend/server.py` initializes `current_state["metrics"]["vesselsUtilized"] = None` and `totalTeuMoved = None` — **explicitly null**, acknowledging the absence.

---

## 11. Findings from MA_05

| ID | Finding | Classification | Confidence | Impact |
|---|---|---|---|---|
| **MA-05-01** | Each region is fleet-checked against the **full unpartitioned 263-vessel fleet**; the sum is never checked. Result: **624 vessels required vs 263 available — 2.37× overcommitment**, undetected at every layer | **A. Verified implementation defect** | **High** | **CRITICAL** — the reported network is infeasible |
| **MA-05-02** | `hub_milp.py:389` fleet constraint is a **verified no-op**; `fleet_size` hardcoded at 300, never overridden | **A. Verified implementation defect** | **Very high** — executed against pulp 2.7.0 | Final allocation unconstrained |
| **MA-05-03** | No class-composition feasibility: 312 services need vessels, but Post_panamax + Super_panamax total only 68 | **E. Missing model component** | **High** | Any deployment >~200 services is class-infeasible |
| **MA-05-04** | `FleetClass.capacity_teu` loaded from `Capacity FFE` and **never read**; no capacity↔service compatibility check | **E. Missing model component** | **High** | Capacity constraints unenforced; field also misnamed |
| **MA-05-05** | Service generation entirely rule-based (`servicegen_ai_count: 0`, `fallback: 3`); archetype mix and vessel bias are **hardcoded constants** identical across all regions | **D. Reporting defect** + **E. Missing component** | **High** | No generation diversity; LLM narrative misattributes provenance |
| **MA-05-06** | 63.1% of candidate services filtered with no documented criterion and no per-service rationale recorded | **C. Specification ambiguity** | Medium | Filter quality undeterminable |
| **MA-05-07** | `Problem` construction passes the full fleet to every regional sub-problem; no reservation mechanism exists | **A. Verified implementation defect** (root of MA-05-01) | **High** | Structural cause of the scope error |
| **MA-05-08** | `FrequencyGA` fleet check **works correctly** — recorded to correct an earlier working assumption | **B. Verified correct** | **High** | Partial enforcement exists |
| **MA-05-09** | Artifact and API report **no vessel count, no utilization, no feasibility flag**; `vesselsUtilized` is explicitly `None` | **D. Reporting defect** | **High** | Infeasibility is invisible to every consumer |
| **MA-05-10** | Service `cycle_time` defaults to 14 for all generator-dict services, doubling vessel requirement vs the 7-day assumption used elsewhere | **C. Specification ambiguity** | Medium | 2× vessel multiplier |

---

## 12. Reproducing the fleet overcommitment

```bash
cd shipping_optimizer
python -c "
import math, json
d = json.load(open('frontend/public/pipeline_output.json', encoding='utf-8'))
FLEET = 263
total = 0
for r in d['regional_results']:
    n = r['services_selected']
    v = n * math.ceil(14 * 1 / 7)     # cycle_time 14 default, f=1 -> 2 vessels
    total += v
    print('%-9s %3d services -> %3d vessels  (per-region check vs %d: %s)'
          % (r['region'], n, v, FLEET, 'PASS' if v <= FLEET else 'FAIL'))
print('TOTAL required = %d ; available = %d ; overcommit = %.2fx'
      % (total, FLEET, total / FLEET))
"
```

No project module was imported; no file was written.