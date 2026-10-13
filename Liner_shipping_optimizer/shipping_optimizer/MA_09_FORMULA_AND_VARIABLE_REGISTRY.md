# MA_09 — FORMULA AND VARIABLE REGISTRY

**System:** AI Vessel Routing System — Multi-Agent Optimizer
**Audit mode:** Forensic, evidence-driven, read-only
**Date:** 2026-10-05

Machine-readable companions:
- `MA_09_FORMULA_INDEX.json`
- `MA_09_METRIC_LINEAGE.json`
- `MA_09_ACTIVE_DEPENDENCY_MAP.json`

---

## 1. Variable registry

| Variable | Symbol | Layer | Unit as implemented | Unit as declared | Status |
|---|---|---|---|---|---|
| `Demand.weekly_teu` | `q_d` | loader | **FFE·k/week** | TEU/week | ❌ mislabelled (MA-02-01) |
| `Demand.revenue_per_teu` | `r_d` | loader | **$/FFE × k** | $/TEU | ❌ mislabelled, k² error |
| `Port.handling_cost` | `h_p` | loader | $/FFE × 2.0 | $/TEU | ✅ correct conversion |
| `Port.transshipment_cost` | `τ_p` | loader | $/FFE × 2.0 | $/TEU | ✅ correct |
| `Port.variable_port_call_cost` | `φ_p` | loader | $/FFE × 2.0 | $/TEU | ✅ correct |
| `Port.port_call_cost` | `π_p` | loader | $/call | $/call | ✅ correct |
| `Port.draft` | — | loader | m | m | ⚠ loaded, never read |
| `FleetClass.capacity_teu` | — | loader | **FFE** | TEU | ⚠ loaded, never read, mislabelled |
| `FleetClass.tc_rate_daily` | — | loader | $/day | $/day | ⚠ loaded, never read |
| `FleetClass.bunker_consumption_tons_per_day` | `γ_s` | loader | t/day | t/day | ⚠ loaded, never read |
| `FleetClass.panama_fee` / `suez_fee` | — | loader | $/transit | $/transit | ⚠ loaded, never read |
| `Service.capacity` | `C_s` | generator | TEU (synthetic) | TEU | ⚠ invented |
| `Service.weekly_cost` | `K_s` | generator | $/week (synthetic) | $/week | ⚠ ignores `tc_rate_daily` |
| `Service.cycle_time` | `τ_s` | generator | days (7/14/21) | days | ⚠ synthetic, ~5× too low |
| `Service.vessel_class` | — | generator | string | string | ⚠ matched TEU↔FFE ladders |
| `flow[(d,s)]` | `x_{d,s}` | MILP | TEU/week | TEU/week | ✅ continuous |
| `transfer_flow[(d,s1,s2)]` | `t` | MILP | TEU/week | TEU/week | ✅ continuous; hub discarded from key |
| `unserved[d]` | `u_d` | MILP | TEU/week | TEU/week | ✅ continuous slack |
| — | `y_s` | MILP | — | binary | ❌ **does not exist** |
| — | `f_s` | MILP | — | integer | ❌ **fixed from GA, not a variable** |
| `frequencies[s]` | `f_s` | GA | sailings/week | sailings/week | ✅ |
| `avg_rev_per_teu` | `r̄` | ServiceGA | $/FFE × k | $/TEU | ❌ k² inflated |
| `avg_rev_per_teu` | `r̄` | FrequencyGA | **demands[0]** | average | ❌ single arbitrary lane |
| `coverage_reward` | — | MILP | **USD** | dimensionless | ❌ currency in an objective |
| `weekly_revenue` | — | orchestrator | — | USD/week | ❌ tautology |

---

## 2. Formula index

### 2.1 Loading

| ID | Formula | Location | Verdict |
|---|---|---|---|
| F-01 | `weekly_teu = FFEPerWeek × k` | `network_loader.py:106` | ✅ correct |
| F-02 | `revenue_per_teu = Revenue_1 × k` | `network_loader.py:109` | ❌ **×k² revenue** |
| F-03 | `handling_cost = CostPerFULL × 2.0` | `:45` | ✅ correct |
| F-04 | `transshipment_cost = CostPerFULLTrnsf × 2.0` | `:48` | ✅ correct |
| F-05 | `variable_port_call_cost = PortCallCostPerFFE × 2.0` | `:49` | ✅ correct |
| F-06 | `port_call_cost = PortCallCostFixed` | `:47` | ✅ correct |
| F-07 | `weekly_teu *= 6` (JSON path) | `:275-277` | ❌ unscoped scale |
| F-08 | vessel count `= ceil(cycle_time × f / 7)` | `hierarchical_ga.py:177` | ✅ correct arithmetic, ❌ wrong scope |

### 2.2 ServiceGA

| ID | Formula | Location | Verdict |
|---|---|---|---|
| F-09 | `avg_rev_per_teu = Σ(q·r)/Σq` | `service_ga.py:146-148` | ✅ formula, ❌ input k² |
| F-10 | `effective_capacity = C × 7/τ` | `:235` | ✅ |
| F-11 | `served = min(effective_capacity, direct)` | `:236` | ⚠ `direct` double-counts |
| F-12 | `yield_factor = 0.6 + 0.4(served/cap)` | `:242` | ✅ utilization discount |
| F-13 | `revenue = Σ served × r̄ × yield` | `:243` | ❌ network-average rate |
| F-14 | `port_cost = Σ served·h + fixed + served·φ` | `:275` | ❌ `served` is service-total |
| F-15 | `transship = hub_ratio × satisfied × tc_per_teu` | `:331` | ⚠ heuristic ratio |
| F-16 | `overcap = β·unused_cap·(opex/total_cap)` | `:337-338` | ❌ `total_cap` lacks `7/τ` |
| F-17 | `profit = rev − op − fuel − trans − port − penalties` | `:340-350` | ✅ 8 terms |
| F-18 | `fitness = 10·profit + 0.01·cov + 0.1·cost` | `normalization.py:114,160` | ❌ **rewards cost** |
| F-19 | legacy `fitness = w_p·p + w_c·c − w_cost·c` | `service_ga.py:377-379` | ✅ sign correct, ❌ unreachable |
| F-20 | `service_cost` uses stale `port_hc` | `:295` | ❌ last-port-only |

### 2.3 FrequencyGA

| ID | Formula | Location | Verdict |
|---|---|---|---|
| F-21 | `avg_rev_per_teu = demands[0].revenue_per_teu` | `frequency_ga.py:200` | ❌ single lane |
| F-22 | `fitness = rev − op − transship − overcap − port` | `:211` | ❌ **fuel omitted** |
| F-23 | `cap = C × f × 7/τ` | `:155` | ✅ |
| F-24 | `vessels = ceil(τ·f/7)`; reject if > fleet | `:133-138` | ✅ works |
| F-25 | `transship = hub_ratio × satisfied × r̄ × 0.05` | `:201` | ⚠ 5% magic constant |

### 2.4 HubMILP

| ID | Formula | Location | Verdict |
|---|---|---|---|
| F-25b | `max Π = REV − OPEX − FUEL − TRANS − PORT − 300Σu + COVBONUS` | `hub_milp.py:358-373` | ❌ |
| F-26 | `REV = Σ_d Σ_s r_d·x_ds` | `:294-300` | ⚠ inherits k² |
| F-27 | `OPEX = Σ_{s∈A} K_s·f_s` | `:304-309` | ⚠ Python constant; **not port-filtered** |
| F-28 | `FUEL = Σ_{s∈A} fuel_wk(s)·f_s` | `:312-322` | ⚠ same; unconstrained by fleet |
| F-29 | `TRANS = Σ_d τ(o_d)·t` | `:326-329` | ❌ ignores hub `h` |
| F-30 | `PORT = Σ_p [h_p·Σv + Σ(v·φ_p) + π_p·Σ_s f_s]` | `:341-353` | ❌ per-TEU charged per port |
| F-31 | `COVBONUS = (w_c/w_p)·(Σx+Σt)/D_tot·\|OPEX+1\|` | `:367-373` | ❌ **scales with cost** |
| F-32 | `prob += total_vessels_used <= fleet_size` | `:389` | ❌ Python bool → no-op / TypeError |
| F-33 | C1 `Σx + Σt + u_d = D_d` | `:392-401` | ✅ correct equality |
| F-34 | C2 `Σx+Σt ≥ min_coverage·D_tot` | `:403-404` | ❌ dead (`min_coverage = 0.0`) |
| F-35 | C3 `Σx + Σt ≤ C_s·f_s·7/τ_s` | `:406-419` | ✅ correctly scaled |
| F-36 | C4 `Σv ≤ 50000 + 0.1·demand_score` | `:117-120` | ❌ can never bind |
| F-37 | `profit_v = pulp.value(objective)` | `:471` | ❌ includes COVBONUS |
| F-38 | post-solve fleet warning | `:558-565` | ❌ warn-only |

### 2.5 Orchestrator

| ID | Formula | Location | Verdict |
|---|---|---|---|
| F-39 | `true_global_demand = Σ q_d` | `orchestrator_agent.py:505` | ✅ correct |
| F-40 | `total_satisfied = min(Σ, true_global)` | `:305` | ❌ clamp asymmetry |
| F-41 | `coverage = satisfied/true_global × 100` | `:306-308` | ✅ arithmetic, ❌ input |
| F-42 | `weekly_revenue = total_profit + total_cost` | `:316` | ❌ **tautology** |
| F-43 | `annual_profit = weekly × 52` | `:321` | ✅ |
| F-44 | `n_clusters = 3 if ports < 50 else 5` | `:510` | ⚠ fixed, not data-driven |
| F-45 | `satisfied = min(Σ_clusters, total_demand)` | `regional_agent.py:442` | ❌ clamp |

### 2.6 Fuel

| ID | Formula | Location | Verdict |
|---|---|---|---|
| F-46 | `sailing_days = D/(v × 24 × 0.9)` | `fuel_cost.py:144` | ✅ plausible |
| F-47 | `fuel = sailing_days × γ × 600` | `:155-157` | ⚠ γ from table, not fleet file |
| F-48 | `weekly = cycle_fuel × (7/τ)` | `:209` | ✅ |
| F-49 | missing pair → `+500.0 nm` | `:205` | ❌ silent fallback |

---

## 3. Verified identities

| Identity | Status | Location |
|---|---|---|
| `Σ cost components == total_cost` | ✅ | artifact (1¢) |
| `revenue − total_cost == weekly_profit` | ✅ | artifact |
| `annual == weekly × 52` | ✅ | artifact |
| `Σ regional == global` | ✅ | artifact |
| `Σ regional services == total_services` | ✅ | artifact (312) |
| `coverage == satisfied/true × 100` | ✅ | arithmetic only |
| `satisfied + unserved == true_demand` | ❌ | **+10.34%** |
| `revenue == Σ r_d·x` | ❌ | **tautology** |
| `vessels_required ≤ vessels_available` | ❌ | **2.37×** |
| `revenue ≤ dataset gross revenue` | ❌ | **4.29×** |
| `fuel ≤ fleet physical maximum` | ❌ | **11.71×** |
| `profit ≤ revenue − non-fuel cost` | ❌ | **+$223.2M** |