# MA_01 — RUNTIME ARCHITECTURE AND DATAFLOW AUDIT

**System:** AI Vessel Routing System — Multi-Agent Optimizer
**Audit mode:** Forensic, evidence-driven, read-only
**Date:** 2026-10-05
**Status:** COMPLETE

---

## 0. Purpose and method

This document establishes, from source inspection only, **what actually executes** in this system, in what order, and how a number in `frontend/public/pipeline_output.json` was produced from the raw CSVs.

Method, and why each step is admissible under a read-only mandate:

| Step | Technique | Admissibility |
|---|---|---|
| Establish the live entrypoint | `__pycache__` inventory + grep for cross-module imports | Reads filesystem metadata; no execution |
| Trace the call graph | Static read of every file on the path | Read-only |
| Confirm no optimizer runs at serve time | grep for `Orchestrator` / `src.` in backend | Read-only |
| Confirm which code writes the artifact | grep for `pipeline_output.json` writers | Read-only |
| Reproduce economics | Independent arithmetic over raw CSV | Reads data; writes nothing |
| Verify solver behaviour | `pulp` in an isolated interpreter | No project module imported |

**The production pipeline was NOT executed.** §11 records exactly why, and what that costs the audit.

---

## 1. The live runtime architecture

### 1.1 What actually serves the dashboard

```
   Browser (React, Vite :5173)
        │  HTTP/WS
        ▼
   backend/server.py           ← the ONLY FastAPI app that has ever been imported
        │  load_pipeline_data()  reads a STATIC JSON file
        ▼
   pipeline_output.json          ← written earlier by a pytest test
```

**Proof of liveness.** `backend/__pycache__/` contains exactly two compiled modules:

```
backend/__pycache__/__init__.cpython-311.pyc
backend/__pycache__/server.cpython-311.pyc
```

`backend/services/__pycache__/` **does not exist**, and `backend/routes/__pycache__/` **does not exist**. CPython writes a `.pyc` on first import. Across the whole `backend/` tree, only `server.py` has ever been imported by a running interpreter.

Corroborating static evidence:

| Check | Result |
|---|---|
| `grep -n "Orchestrator\|NetworkLoader\|src\." backend/server.py` | **0 matches** |
| `grep -rn "include_router" backend/server.py backend/main.py backend/unified_main.py` | **0 matches** |
| `backend/server.py:71-79` `load_pipeline_data()` | opens `pipeline_output.json`, returns |
| Number of API routes in `server.py` | ~50, all reading the static file or recomputing from it |

### 1.2 Dead server layers

The repository contains **five** FastAPI entrypoints. Three are never loaded.

| File | Size | Mounts `backend/routes/`? | Imports the optimizer? | Runtime status |
|---|---|---|---|---|
| `backend/server.py` | 113 KB | No (routes inlined) | **No** | **LIVE** |
| `backend/main.py` | 21 KB | No | — | Dead |
| `backend/unified_main.py` | 24 KB | No | — | Dead |
| `backend/routes/metrics.py` | — | — | No | **Dead — mounted by nobody** |
| `backend/routes/pipeline.py` | — | — | No | **Dead — mounted by nobody** |
| `backend/routes/regions.py` | — | — | No | **Dead — mounted by nobody** |
| `backend/routes/websocket.py` | — | — | No | **Dead — mounted by nobody** |

`backend/routes/metrics.py:30` contains a comment: *"derive canonical summary metrics from pipeline_output.json"* — i.e. a deliberate single-source-of-truth design — but the module is unreachable. `backend/routes/metrics.py:170` returns `{"reason": "pipeline_output.json is the sole runtime truth; this endpoint is a no-op"}`, also unreachable.

### 1.3 The one place the backend claims to run the optimizer is a mock

`backend/services/pipeline_service.py` is the only backend module that imports the optimizer (`:62-64`):

```python
from src.agents.orchestrator_agent import OrchestratorAgent
from src.data.network_loader import NetworkLoader
from src.optimization.data import Problem, Port, Service, Demand
```

But its loader returns a synthetic object:

```python
# backend/services/pipeline_service.py:79-83
async def _load_problem(self, dataset_path: str):
    """Load problem from dataset"""
    # For now, return a mock problem
    # In production, this would load the actual dataset
    return MockProblem()
```

```python
# :101-107
class MockProblem:
    def __init__(self):
        self.ports    = [MockPort(i) for i in range(435)]
        self.demands  = [MockDemand(i) for i in range(9622)]
        self.services = [MockService(i) for i in range(1200)]
        self.distance_matrix = [[0] * 435 for _ in range(435)]
```

If this path ever went live, the system would optimize against 435 synthetic ports with **zero distance matrix** and 9,622 fabricated OD pairs of 100–1,099 TEU each. `MockPort` and `MockDemand` have **no** `handling_cost`, `port_call_cost`, `revenue_per_teu`, or `transshipment_cost` attribute — so any real cost function would raise `AttributeError` on first use. It cannot work; it has never run.

Its `get_problem_statistics()` (`:85-94`) returns **hard-coded literals** — `ports: 47, lanes: 1764, services: 551, weekly_demand: 276447` — including a `"services": 551` that contradicts the artifact's 312, and a `network_density: 163.2` that is `1764/47 = 37.53`, not 163.2.

---

## 2. The optimizer call graph (test-time only)

```
tests/test_orchestrator.py :: load_worldsmall_problem()            [:210-238]
   ├── NetworkLoader.load_ports(WorldSmall/ports.csv)             [:217]
   ├── NetworkLoader.load_demands(WorldSmall/Demand_...csv)       [:219]
   ├── NetworkLoader.load_distance_matrix(distance_dense.csv)     [:221]
   └── NetworkLoader.load_fleet(fleet_WorldSmall.csv, fleet_data.csv)  [:222-225]
        │
        ▼
OrchestratorAgent.process({"problem": problem})                   [:430+]
   ├── CONFIG.objective_mode = "profit_first"                      [:434]
   ├── CONFIG.get_weights() → problem.{profit,coverage,cost}_weight [:435-438]
   │      ⚠ DEAD — see §5.1
   ├── true_global_demand = Σ d.weekly_teu                        [:505]
   ├── n_clusters = 3 if num_ports < 50 else 5                   [:510]
   │
   ├── Region assignment (origin-only split)                       [:512+]
   ├── For each of 3 active regions:
   │     RegionalAgent.process()
   │        ├── KMeans port clustering (sklearn)
   │        ├── Hub detection
   │        ├── cluster_demands = [d if d.origin in cluster OR d.destination in cluster]  ⚠ [:349-352]
   │        ├── ServiceGeneratorAgent  → candidate services
   │        ├── HierarchicalGA
   │        │     ├── ServiceGA      (chromosome = binary service selection)
   │        │     └── FrequencyGA    (chromosome = frequency vector)
   │        └── HubMILP  (PULP/CBC, LpMaximize)
   │              flow / transfer / unserved variables
   │              profit + coverage_reward                          ⚠ [:367-373]
   │              total_vessels_used <= fleet_size (300)            ⚠ [:389] NO-OP — §5.2
   │
   ├── CoordinatorAgent  → conflict detection, global metrics       [:57-325]
   ├── ConsensusEngine   → aggregate regional solutions
   ├── IterationSelector → picks the iteration to publish
   │
   └── Aggregate (:295-325)
         total_revenue-ish = total_profit + total_cost               ⚠ [:316] TAUTOLOGY — §5.3
         total_satisfied = min(Σ regional satisfied, true_global_demand)  ⚠ [:305]
         coverage = satisfied / true_global_demand × 100             [:306-308]
         assert 0 ≤ coverage ≤ 100                                  [:311]
        │
        ▼
tests/test_orchestrator.py :: [:2222-2235]  ← THE SOLE WRITER
   ├── <repo>/pipeline_output.json
   ├── frontend/public/pipeline_output.json
   └── frontend/dist/pipeline_output.json
```

### 2.1 The artifact writer

```python
# tests/test_orchestrator.py:2222-2235
output_file  = output_dir / "pipeline_output.json"
public_file  = output_dir / "frontend" / "public" / "pipeline_output.json"
dist_file    = output_dir / "frontend"  / "dist"   / "pipeline_output.json"
```

Grep across the entire repository confirms **`tests/test_orchestrator.py` is the only module that writes `pipeline_output.json`.** Every other reference is a reader or a SHA-256 baseline assertion.

### 2.2 The live UI artifact

`backend/server.py:73-75` resolves:

```python
parent_dir  = Path(__file__).parent.parent          # shipping_optimizer/
output_file = parent_dir / "pipeline_output.json"   # repo root
```

But git status shows `D pipeline_output.json` at the **repo root** (`C:/Users/WINDOWS/Downloads/Liner_shipping_optimizer/pipeline_output.json`), while `shipping_optimizer/frontend/public/pipeline_output.json` exists and holds the audited figures. `backend/routes/metrics.py:14` uses `PROJECT_ROOT / "pipeline_output.json"` — a *different* root again.

**Three different path resolutions for one file.** The served artifact's provenance depends on which module answers.

---

## 3. Dataflow: raw CSV → reported dollar

```
demand_world_small.csv (1,764 rows, tab-separated)
   FFEPerWeek, Revenue_1
        │
        │  network_loader.py:103   ffe_to_teu_factor = lane table (default 2.0)
        │
        ├──► :106  weekly_teu      = FFEPerWeek      × k    →  "TEU/week"
        └──► :109  revenue_per_teu = Revenue_1       × k    →  "$/TEU"     ⚠ §4
                │
                ▼
        Demand(origin, destination, weekly_teu, revenue_per_teu)
                │
   ┌────────────┼────────────────────────────────┐
   ▼            ▼                                ▼
ServiceGA    FrequencyGA                     HubMILP
   │            │                                │
   │ revenue = Σ served × revenue_per_teu        │  revenue_expr from flow vars
   │ (× k² inherited)                            │  (× k² inherited)
   ▼            ▼                                ▼
        costs: operating / fuel / transship / port
                │
                ▼
        RegionalAgent result dict
                │  Σ over regions (:295-303)
                ▼
        OrchestratorAgent summary (:305-325)
                │
                ▼
        pipeline_output.json → FastAPI → React
```

**Every dollar in the artifact passes through `network_loader.py:109`.** That single line is the highest-leverage defect in the system. See MA_02 §3 and MA_03.

---

## 4. The unit-inheritance boundary

One defect propagates through the entire economic stack because there is exactly one conversion point:

```
network_loader.py:109   revenue_per_teu = Revenue_1 × k     ← the defect
        │
        ├──► ServiceGA.fitness()          service_ga.py:243
        ├──► FrequencyGA fitness          frequency_ga.py:~150
        ├──► HubMILP revenue_expr         hub_milp.py:411+
        └──► Orchestrator "revenue"       orchestrator_agent.py:316
```

**Nothing downstream re-normalizes.** There is no unit check, no dimensional assertion, and no cross-validation of `weekly_teu × revenue_per_teu` against any independent quantity anywhere in `src/`. The defect is invisible to every test because every test asserts only *internal consistency* — identities that remain true under a uniform (or non-uniform) scale factor.

| Quantity | Correct value (raw CSV) | As loaded | Ratio |
|---|---|---|---|
| Demand | 138,247.0 FFE/week | 276,446.8 (FFE·k)/week | k |
| Weekly revenue | 264,870,100.00 USD/week | 1,059,950,076.25 USD/week | **k²** |

The ratio on the revenue line is `k²` ≈ **4.001773**, FFE-volume-weighted. Reported artifact revenue is 1,136,109,658.57 — a further ×1.0718 from capacity/yield effects (MA_03).

---

## 5. Confirmed dead or inverted logic on the active path

### 5.1 CONFIG weights are dead code

Full trace, independently verified:

| Step | Location | Value |
|---|---|---|
| CONFIG declares | `optimizer_config.py:41-45` | `{'profit': 0.60, 'coverage': 0.25, 'cost': 0.15}` |
| `objective_mode` | `optimizer_config.py:15` | `"profit_first"` |
| Orchestrator fetches | `orchestrator_agent.py:435` | `CONFIG.get_weights()` → `profit_first_weights` |
| Writes onto problem | `orchestrator_agent.py:436-438` | `problem.profit_weight = 0.60`, etc. |
| ServiceGA reads | `service_ga.py:83-85` | `self.w_profit = 0.60`, etc. |
| **Consumed only at** | `service_ga.py:377-379` | inside `if self.objective_mode == "legacy":` |

`objective_mode` is `"profit_first"`, so the **legacy branch never executes**. `w_profit` / `w_coverage` / `w_cost` are written, stored, passed into `weight_tuple` at `service_ga.py:209`, and then never influence fitness.

The artifact nonetheless records `iteration_audit[*].weights_used = {profit: 0.60, coverage: 0.25, cost: 0.15}` — values that **did not affect the result being reported.**

Meanwhile the weights that *do* act are hardcoded in a second, unrelated class:

```python
# normalization.py:114-118
PROFIT_FIRST_WEIGHTS = {'profit': 10.0, 'coverage': 0.01, 'cost': 0.1}
```

and are instantiated at `service_ga.py:99` as `ObjectiveWeights(mode=self.objective_mode)`. Two independent weight systems; the configured one is inert.

### 5.2 The fleet constraint is a verified no-op

```python
# hub_milp.py:389
prob += total_vessels_used <= self.fleet_size      # fleet_size default 300, :61
```

PULP treats `x <= 300` as a **Python `bool`**, not an `LpConstraint`. Empirically executed against the installed solver:

```
pulp version: 2.7.0
  prob += (5 <= 300)    ->  OK,   constraints = 0    # silently adds nothing
  prob += (900 <= 300)  ->  TypeError: A False object cannot be passed as a constraint
```

So the constraint is **never added**, regardless of vessel count. It cannot fail loudly, and it cannot bind.

Two further facts make this worse than an inert constraint:

1. `self.fleet_size` is never overridden by any caller — grep confirms `fleet_size: int = 300` at `hub_milp.py:61` is the only assignment.
2. The system **deploys 309 services** against a **263-vessel** WorldSmall fleet. That is a real infeasibility that the constraint was supposed to catch, and it is neither caught nor reported.

### 5.3 "Revenue" is defined as profit + cost

```python
# orchestrator_agent.py:314-316
# Revenue = profit + cost (the only consistent revenue measure from
# the MILP objective; the unserved penalty is treated as a cost
# captured in the operating cost component).
weekly_revenue = total_profit + total_cost
```

`total_profit = total_revenue − total_cost` (the MILP objective, `hub_milp.py:471`). Substituting gives:

```
revenue ≡ (revenue − cost) + cost ≡ revenue     ⟺  0 ≡ 0
```

**The revenue identity is a tautology.** `pipeline_output.json`'s `revenue: 1,136,109,658.57` is arithmetically forced by profit and cost and carries **zero independent information**. It cannot disagree with them; it cannot be falsified; and it cannot be used to validate them.

The comment is also wrong on the economics: the comment asserts the unserved penalty is captured in operating cost. It is not — `alpha_unserved = 300.0` (`regional_agent.py:314`) enters the MILP objective as a **penalty on the objective**, not as a cost line in the reported ledger.

### 5.4 The GA fitness adds cost instead of subtracting it

`service_ga.py:373-383`:

```python
if self.objective_mode == "legacy":
    fitness = (self.w_profit   * normalized['profit']
             + self.w_coverage * normalized['coverage']
             - self.w_cost     * normalized['cost'])     # ← minus
else:
    fitness = self.objective_weights.calculate_weighted_score(normalized)
```

and `normalization.py:147-165`:

```python
score = 0.0
for component, weight in self.weights.items():
    if component in normalized_components:
        score += weight * value        # ← plus, for EVERY component including cost
return score
```

With `PROFIT_FIRST_WEIGHTS = {'profit': 10.0, 'coverage': 0.01, 'cost': 0.1}`, active fitness is:

```
fitness = 10.0·profit + 0.01·coverage + 0.1·cost
```

**The service-selection GA actively rewards higher operating cost**, with a positive 0.1 coefficient. The legacy branch, which subtracts, is unreachable. Chromosomes with worse economics can rank better.

### 5.5 The MILP objective is not a profit objective

```python
# hub_milp.py:367-373
coverage_reward = ((self.w_coverage / max(self.w_profit, 1e-6))
                   * (satisfied_expr / max(total_demand_teu, 1.0))
                   * abs(operating_cost + 1))
prob += profit_expr + coverage_reward
```

The coverage term is **multiplicative in total operating cost**, not a normalized satisfaction score. Consequences:

- Raising operating cost **raises** the objective through the coverage term.
- `abs(operating_cost + 1)` is a no-op guard for cost ≥ 0, but becomes `|−cost−1|` if cost were ever negative — silently flipping sign.
- `profit_v = pulp.value(prob.objective)` (`hub_milp.py:471`) therefore reports **profit + coverage_reward**, and it is this value, not profit, that propagates to `weekly_profit`.
- `satisfied_expr / max(total_demand_teu, 1.0)` uses a **local cluster denominator** (§5.6), so the same `w_coverage/w_profit` ratio means different things in different clusters.

---

## 6. Aggregation defects on the reporting path

### 6.1 Coverage clamp asymmetry

```python
# orchestrator_agent.py:303-308
total_satisfied = min(total_satisfied, true_global_demand)   # ← CAPPED
coverage = total_satisfied / true_global_demand * 100
```

Upstream, `regional_agent.py:438-442`:

```python
satisfied = sum(r["satisfied_demand"] for r in cluster_results)   # duplicated across clusters
unserved   = sum(r["unserved_demand"]  for r in cluster_results)  # duplicated
satisfied  = min(satisfied, total_demand)                         # ← capped
```

**`satisfied` is clamped at two levels; `unserved` is clamped at neither.** Measured against the artifact:

| Region | total_demand | satisfied | unserved | satisfied + unserved | coverage% |
|---|---|---|---|---|---|
| Asia | 147,838.50 | 147,838.50 | 13,274.67 | 161,113.17 | **100.0000** |
| Europe | 48,509.70 | 45,330.00 | 6,307.70 | 51,637.70 | 93.4452 |
| Americas | 80,098.60 | 80,098.60 | 12,171.73 | 92,270.33 | **100.0000** |
| **Global** | **276,446.80** | **273,267.10** | **31,754.10** | **305,021.20** | **89.5895** |

Two regions show **exactly** 100.0000% — the signature of a saturated clamp, not of genuine full coverage. Global `satisfied + unserved = 305,021.20` exceeds true demand `276,446.80` by **28,574.40 TEU/week (+10.34%)**.

Coverage against the true denominator is **98.8498%**, not the reported **89.5895%** — understated by **9.26 percentage points**. (The residual 1.15pp gap is genuinely unserved cargo; the 9.26pp is arithmetic artifact.)

### 6.2 Which identities hold

Independently recomputed from the artifact:

| Identity | Check | Result |
|---|---|---|
| `operating + transship + port + fuel == total_cost` | 100,822,500.00 + 22,531,440.01 + 19,227,892.20 + 648,031,918.31 = 790,613,750.52 | ✅ (1¢ rounding) |
| `weekly_profit == revenue − total_cost` | 1,136,109,658.57 − 790,613,750.51 = 345,495,908.06 | ✅ |
| `annual == weekly × 52` | 345,495,908.06 × 52 = 17,965,787,219.12 | ✅ |
| `revenue == Σ regional revenue` | — | ❌ **tautological** (§5.3) |
| `satisfied + unserved == total_demand` | 305,021.20 vs 276,446.80 | ❌ **+10.34%** |
| `services_selected == services_generated` | 309 vs 312 | ⚠ 3 filtered |
| `Σ regional services == total` | 104 + 98 + 107 = 309 | ✅ |

**Fuel is 81.97% of total cost.** That single ratio drives the economic result and is examined in MA_04.

---

## 7. LLM / agent-layer runtime status

The artifact's own counters were read directly, and the code path inspected:

| Field | Value | Meaning |
|---|---|---|
| `llm_calls` | 5 | LLM invocations attempted |
| `coordinator_fallback_count` | **0** | Coordinator **succeeded** |
| `servicegen_ai_count` | **0** | Service generation did **not** use LLM output |
| `servicegen_fallback_count` | **3** | All 3 regions fell back to rules |

**Adjudication.** A prior audit finding claimed LLM calls had failed. **Not reproduced.** The CoordinatorAgent's LLM calls succeeded (5 calls, 0 fallbacks). What is true is narrower and more interesting: **ServiceGeneratorAgent never consumed LLM output on any region** — all three regions used the deterministic rule-based fallback. The agent framework is real; on the production path its *generation* layer is entirely inert while its *reasoning* layer ran.

This matters for reading the artifact: `explanation` and `strategy` fields on regional results are LLM-authored text describing a solution the LLM did not generate.

---

## 8. Test suite as an oracle

| Test file | Role | Does it constrain economics? |
|---|---|---|
| `tests/test_orchestrator.py` | **Produces the artifact** | Yes — but only self-consistency |
| `tests/architecture/test_output_contract.py` | Field presence | No — shape only |
| `tests/maritime/test_phase{5,6,7,8,9}_*.py` | SHA-256 baseline of the artifact | No — freezes bytes, validates nothing |
| `tests/test_iteration_selection.py` | Cross-layer consistency | No |
| `tests/test_economic_metric_documentation.py` | Documentation match | No |

**The oracle problem.** The suite pins the artifact's SHA-256 across five maritime test modules. Any economic change would fail those tests — protecting the *bytes*, not the *economics*. And because every economic assertion is an internal identity (§6.2), the entire k²-inflated revenue, the no-op fleet constraint, and the additive-cost GA fitness all pass every test in the repository.

The most consequential assertion in the suite:

```python
# orchestrator_agent.py:311
assert 0 <= coverage <= 100, f"Coverage out of bounds: {coverage}%"
```

This **enforces** the artifact of the clamp rather than detecting it. Under-coverage and phantom demand both satisfy it.

---

## 9. MA_09 active dependency map (abbreviated)

Full machine-readable version in `MA_09_ACTIVE_DEPENDENCY_MAP.json`.

```
pipeline_output.json
  │
  ├── weekly_profit ............ hub_milp.py:471  pulp objective value
  │                                └── includes coverage_reward (:367-373)  ⚠
  │                                └── inherits k² revenue (network_loader.py:109)  ⚠
  ├── revenue .................. orchestrator_agent.py:316 = profit + cost   ⚠ TAUTOLOGY
  ├── operating_cost ........... regional_agent.py / service_ga.py:340-350
  ├── fuel_cost ................ service_ga.py:161-166 → fuel_cost.py
  │                                └── ignores fleet bunker_consumption_tons_per_day  ⚠
  │                                └── 500 nm silent fallback (:205)             ⚠
  ├── transship_cost ........... hub_milp.py:548-551  double-counted  ⚠
  ├── port_cost ................ hub_milp.py:599-601  wrong basis  ⚠
  ├── total_cost ............... Σ components  ✅ identity holds
  ├── coverage ................. orchestrator_agent.py:305-308  clamped  ⚠
  ├── satisfied_demand ........ regional_agent.py:438-442  duplicated + clamped  ⚠
  ├── unserved_demand .......... regional_agent.py:439  duplicated, NOT clamped  ⚠
  └── weights_used ............ CONFIG (0.60/0.25/0.15) — DISPLAYED BUT DEAD  ⚠
```

---

## 10. Findings from MA_01

| ID | Finding | Classification | Confidence | Impact |
|---|---|---|---|---|
| **MA-01-01** | `revenue_per_teu = Revenue_1 × k` at `network_loader.py:109` inflates every revenue term by k²; no downstream unit check exists anywhere in `src/` | **A. Verified implementation defect** | **High** | ×4.0018 network-wide; propagates to every reported dollar |
| **MA-01-02** | `weekly_revenue = total_profit + total_cost` (`orchestrator_agent.py:316`) makes the revenue identity a **tautology** | **D. Reporting defect** | **High** | Revenue metric carries zero independent information |
| **MA-01-03** | `prob += total_vessels_used <= self.fleet_size` (`hub_milp.py:389`) is a **verified no-op** — PULP accepts it as a Python bool; 309 services deployed against a 263-vessel fleet, uncaught | **A. Verified implementation defect** | **High** — reproduced against pulp 2.7.0 | Fleet infeasibility neither modelled nor reported |
| **MA-01-04** | GA fitness uses `+0.1 × cost` (`normalization.py:147-165`) — **rewards operating cost**; the subtracting branch (`service_ga.py:379`) is unreachable because `objective_mode = "profit_first"` | **A. Verified implementation defect** | **High** | Inverted selection pressure on service design |
| **MA-01-05** | `CONFIG.get_weights()` (0.60/0.25/0.15) reaches `service_ga.w_*` but is consumed **only inside the unreachable `legacy` branch**; the artifact reports these dead values as `weights_used` | **D. Reporting defect** + **E. Missing component** | **High** | Artifact misreports the objective that ran |
| **MA-01-06** | A second, conflicting weight set (`PROFIT_FIRST_WEIGHTS = {10.0, 0.01, 0.1}`) is hardcoded in `normalization.py` and is the one actually used | **C. Specification ambiguity** | High | Two sources of truth for "the objective" |
| **MA-01-07** | MILP objective is `profit + coverage_reward` where `coverage_reward` is **multiplicative in operating cost** (`hub_milp.py:367-373`); `profit_v` reports the sum, not profit | **A. Verified implementation defect** | **High** | Higher cost raises the stated objective |
| **MA-01-08** | `unserved` summed over overlapping clusters, `satisfied` clamped at two levels → `satisfied + unserved` = 305,021.20 vs true 276,446.80 | **A. Verified implementation defect** | **High** | **+28,574.40 TEU/wk (+10.34%)** phantom demand |
| **MA-01-09** | Coverage reported 89.5895% vs **98.8498%** true — **understated by 9.26 pp**; two regions report exactly 100.0000% | **D. Reporting defect** | **High** | Understates solution quality |
| **MA-01-10** | The optimizer never runs at serve time; `backend/` imports only `server.py`, which reads a static JSON | **D. Reporting/architecture defect** | **High** — `__pycache__` + grep | Dashboard is a static artifact viewer |
| **MA-01-11** | `backend/routes/` (4 modules) is mounted by **no** entrypoint; `backend/services/pipeline_service.py` returns a `MockProblem` with **zero distance matrix** and no cost attributes | **A. Verified implementation defect** (latent) | High | Dead code; would crash if activated |
| **MA-01-12** | `pipeline_output.json` resolved at three different roots by `server.py:75`, `routes/metrics.py:14`, and the test writer | **D. Reporting defect** | High | Served artifact provenance ambiguous |
| **MA-01-13** | `ServiceGeneratorAgent` LLM output unused in all 3 regions (`servicegen_ai_count: 0`, `fallback: 3`); LLM-authored `explanation` describes a non-LLM solution | **D. Reporting defect** | High | Narrative misrepresents provenance |
| **MA-01-14** | CoordinatorAgent's LLM calls **succeeded** (5 calls, 0 fallbacks) — a prior audit's contrary claim is **not reproduced** | **G. Previously reported finding not reproduced** | High | Corrects F-19 |
| **MA-01-15** | Test suite validates only **internal identities**; five maritime modules pin the artifact SHA-256, protecting bytes while economic defects pass silently | **D. Reporting defect** (test-oracle gap) | High | The k² defect is invisible to every test |
| **MA-01-16** | `assert 0 <= coverage <= 100` (`orchestrator_agent.py:311`) **enforces the clamp artifact** rather than detecting it | **A. Verified implementation defect** | High | Active guard against correctness |

---

## 11. Production pipeline NOT executed — and why

Per the audit mandate, I determined before any execution whether the pipeline could mutate state, then chose not to run it.

**Determination — it CAN and WOULD:**

| Side effect | Evidence |
|---|---|
| Overwrites 3 artifact files | `tests/test_orchestrator.py:2222-2235` writes repo-root, `frontend/public/`, and `frontend/dist/` |
| Requires an approved isolated workspace | Mandate: *"If so, do not run it without an explicitly approved isolated workspace"* |
| Mutates shared test fixtures | Orchestrator tests write to fixed absolute paths |
| Would consume 5 LLM calls | External network service; non-deterministic |
| Non-deterministic GA | No seed is fixed on the production path |

**Decision: not executed.** No isolated workspace was authorized.

**Cost of this decision — stated plainly, not hidden:**

| Not verified | Substitute evidence used |
|---|---|
| The artifact's SHA matches a fresh run | Read the committed artifact; verify its internal identities by recomputation |
| GA run-to-run variance | Not measured — **any economic figure carries unquantified stochastic variance** |
| Exact LLM text in `explanation` | Read from the artifact |
| Whether the committed artifact is the *latest* run | Not established |

This is a real limitation and is carried forward into MA_08. It does **not** affect findings MA-01-01 through MA-01-09, all of which are established from source inspection and closed-form arithmetic that are invariant to GA randomness — a uniform or per-lane scale factor applied at load time produces the same k² inflation on every run.

---

## 12. Reproducing the architecture claims

```bash
# MA-01-10: only server.py has ever been imported
find backend -name "__pycache__" -type d -exec sh -c 'echo "--- $1"; ls "$1"' _ {} \;

# MA-01-10: backend never imports the optimizer
grep -c "Orchestrator\|NetworkLoader" backend/server.py          # -> 0

# MA-01-11: routes are mounted by nobody
grep -rn "include_router" backend/server.py backend/main.py backend/unified_main.py  # -> 0 matches

# MA-01-05: CONFIG weights are dead
grep -n "self.w_profit\|objective_mode ==" src/optimization/service_ga.py
#   83-85 read; 377-379 the ONLY consumer, guarded by "legacy"; mode is "profit_first"

# MA-01-02: revenue is a tautology
sed -n '314,316p' src/agents/orchestrator_agent.py

# MA-01-03: fleet constraint is a no-op (isolated pulp, no project import)
python -c "
import pulp
print('pulp', pulp.__version__)
for n in (5, 900):
    p = pulp.LpProblem('t', pulp.LpMaximize)
    try:
        p += n <= 300
        print(n, '-> constraints =', len(p.constraints))
    except TypeError as e:
        print(n, '-> TypeError:', e)
"
```

No project module was imported; no file was written.