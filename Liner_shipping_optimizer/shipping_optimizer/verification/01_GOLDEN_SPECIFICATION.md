#Liner Shipping Network Optimization using Multi-Agent AI,Genetic ALgorithms and Mixed-Integer Linear Programming.

#The Problem:
-Liner shipping — the scheduled, repeatable transport of containerized cargo along fixed routes — moves the majority of global trade by value. The Liner Shipping Network Design Problem (LSNDP) asks: given a set of ports, stochastic demand between port pairs, a heterogeneous fleet of vessels with different capacities and fuel consumptions, and a set of candidate services (routes), which services should be activated, at what frequency, and how should cargo be allocated across them — so that profit is maximized while demand is served and fleet, capacity, and route constraints are respected.



#The System's Approach

The system uses a multi-agent, multi-method hybrid optimization pipeline with three nested layers:

Layer 1 — Problem Decomposition

The global problem (333 ports, 9,622 demand lanes, 1,219 candidate services) is split geographically by KMeans clustering into regional sub-problems. Demand is assigned by origin only, preserving conservation; cross-region demands appear in the origin region's MILP as unserved if no path exists.

Layer 2 — Per-Region Optimization (Two-Phase Heuristic + Exact)

Each regional agent runs a hierarchical GA→MILP pipeline:
1. ServiceGA — a genetic algorithm evolves a binary chromosome selecting which candidate services to include, scored on a multi-objective fitness (profit / coverage / cost with penalty terms for unserved demand and overcapacity).
2. FrequencyGA — a second GA assigns integer sailing frequencies (1–3 per week) to the selected services, using an analytical starting point derived from route-level demand divided by vessel capacity.
3. HubMILP — a PuLP mixed-integer linear program solves the final flow assignment: which demanded TEU go direct vs. transshipment, subject to port capacity, fleet size, and service capacity constraints, with a coverage-reward bonus in the objective.

Layer 3 — Global Coordination

Across iterations (hard minimum of 3):
1. CoordinatorAgent detects cross-region service conflicts (same service proposed in multiple regions), resolves them by dropping the lower-profit instance, computes global metrics, and proposes weight adjustments.
2. ConsensusEngine reconciles the coordinator's proposals with each region's policy preferences and the service generator's archetype plan via weighted voting (coordinator 0.40, regions 0.40 combined, service generator 0.20).
3. SharedContext carries the reconciled weights and archetype ratios back into the next iteration's regional problems.
4. After the loop, IterationSelector evaluates all captured iteration snapshots using Pareto dominance analysis and weighted scoring to pick the single best iteration as the final output — not simply the last one.

Supporting Mechanisms

- LLM-assisted design: A Groq-hosted LLM guides service archetype composition (direct/hub-loop/trunk/feeder ratios) and proposes inter-iteration weight adjustments; both have deterministic rule-based fallbacks and never override the mathematical optimizer.
- Maritime intelligence bridge: Real-time weather speed factors and congestion-derived port-capacity reductions are injected into the fuel-cost and MILP constraints respectively; absent data degrades gracefully to the pre-maritime baseline.
- Demand-conserving split: An assertion guarantees global demand equals the sum of regional demands within 1 TEU, preventing double-counting or loss.

#What the system is fundamentally trying to achieve?
- To determine the optimal assignment of vessels to predefined liner shipping services — including which services to operate, at what frequency, and how to route container flows through them — so that the weighted combination of profit and demand coverage is maximized while respecting fleet-size, port-capacity, and service-frequency constraints.

In maritime terms: given a fixed fleet, a set of candidate round-trip services, and global trade-lane demand, decide which services sail, how often, and how cargo flows across them (directly or via transshipment hubs) to make the most profit while serving the most demand.


#Main Objective : Maximize the weighted sum of weekly profit (revenue-operating+fuel+port+transhipment costs) and global demand weighted service coverage,subjected to fleet-size,port-capacity and frequency constraints.
--The system minimizes the total operating costs which includes all the constraints which are described in the proposed profit calculation,which is the cost term in the multi objective weighted score. 

#Complete System Input Inventory 
IN-001: FLEET (6 inputs)

┌──────────┬────────────────────────────┬─────────────┬──────────────────────────────────────────────┬─────────────────────────────────────────────────┐
│    ID    │           Input            │    Unit     │                    Source                    │                    Required?                    │
├──────────┼────────────────────────────┼─────────────┼──────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│ IN-001-A │ Vessel class               │ string enum │ fleet_world_large.csv → service.vessel_class │ Yes (defaults Post_panamax)                     │
├──────────┼────────────────────────────┼─────────────┼──────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│ IN-001-B │ Fleet quantity per class   │ int         │ fleet_world_large.csv (6 rows)               │ Partially — benchmark hard-codes fleet_size=300 │
├──────────┼────────────────────────────┼─────────────┼──────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│ IN-001-C │ Capacity per vessel class  │ TEU         │ Hardcoded in fuel_cost.py                    │ Yes                                             │
├──────────┼────────────────────────────┼─────────────┼──────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│ IN-001-D │ Consumption rate per class │ tons/day    │ Hardcoded in fuel_cost.py                    │ Yes                                             │
├──────────┼────────────────────────────┼─────────────┼──────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│ IN-001-E │ Service speed per class    │ knots       │ Hardcoded in fuel_cost.py                    │ Yes                                             │
├──────────┼────────────────────────────┼─────────────┼──────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│ IN-001-F │ Bunker fuel price          │ USD/ton     │ Hardcoded BUNKER_PRICE_PER_TON = 600.0       │ Yes                                             │
└──────────┴────────────────────────────┴─────────────┴──────────────────────────────────────────────┴─────────────────────────────────────────────────┘

IN-002: PORTS (13 inputs from ports.csv, 435 rows)

┌──────────┬─────────────────────────┬─────────┬───────────────────────────┬────────────────────────────────┐
│    ID    │          Input          │  Unit   │       Source Column       │           Required?            │
├──────────┼─────────────────────────┼─────────┼───────────────────────────┼────────────────────────────────┤
│ IN-002-A │ UNLocode                │ string  │ UNLocode                  │ Yes — primary key              │
├──────────┼─────────────────────────┼─────────┼───────────────────────────┼────────────────────────────────┤
│ IN-002-B │ Port name               │ string  │ name                      │ No                             │
├──────────┼─────────────────────────┼─────────┼───────────────────────────┼────────────────────────────────┤
│ IN-002-C │ Latitude                │ degrees │ Latitude                  │ Yes — dropped if missing       │
├──────────┼─────────────────────────┼─────────┼───────────────────────────┼────────────────────────────────┤
│ IN-002-D │ Longitude               │ degrees │ Longitude                 │ Yes — dropped if missing       │
├──────────┼─────────────────────────┼─────────┼───────────────────────────┼────────────────────────────────┤
│ IN-002-E │ Country                 │ string  │ Country                   │ No                             │
├──────────┼─────────────────────────┼─────────┼───────────────────────────┼────────────────────────────────┤
│ IN-002-F │ Cabotage_Region         │ string  │ Cabotage_Region           │ No                             │
├──────────┼─────────────────────────┼─────────┼───────────────────────────┼────────────────────────────────┤
│ IN-002-G │ D_Region                │ string  │ D_Region                  │ No                             │
├──────────┼─────────────────────────┼─────────┼───────────────────────────┼────────────────────────────────┤
│ IN-002-H │ Draft                   │ meters  │ Draft                     │ Stored but unused in optimizer │
├──────────┼─────────────────────────┼─────────┼───────────────────────────┼────────────────────────────────┤
│ IN-002-I │ Handling cost           │ USD/FFE │ CostPerFULL (×2.0)        │ Yes                            │
├──────────┼─────────────────────────┼─────────┼───────────────────────────┼────────────────────────────────┤
│ IN-002-J │ Transshipment cost      │ USD/FFE │ CostPerFULLTrnsf (×2.0)   │ Yes                            │
├──────────┼─────────────────────────┼─────────┼───────────────────────────┼────────────────────────────────┤
│ IN-002-K │ Port call fixed cost    │ USD     │ PortCallCostFixed         │ Yes                            │
├──────────┼─────────────────────────┼─────────┼───────────────────────────┼────────────────────────────────┤
│ IN-002-L │ Port call variable cost │ USD/FFE │ PortCallCostPerFFE (×2.0) │ Yes                            │
├──────────┼─────────────────────────┼─────────┼───────────────────────────┼────────────────────────────────┤
│ IN-002-M │ Internal port id        │ int     │ port_mapping.csv:id       │ Yes                            │
└──────────┴─────────────────────────┴─────────┴───────────────────────────┴────────────────────────────────┘

IN-003: DEMAND (9 inputs from demand_world_large.csv, 9,622 rows)

┌──────────┬───────────────────────────┬─────────┬────────────────────────────────────────┬───────────────────┐
│    ID    │           Input           │  Unit   │             Source Column              │     Required?     │
├──────────┼───────────────────────────┼─────────┼────────────────────────────────────────┼───────────────────┤
│ IN-003-A │ Origin                    │ string  │ Origin                                 │ Yes               │
├──────────┼───────────────────────────┼─────────┼────────────────────────────────────────┼───────────────────┤
│ IN-003-B │ Destination               │ string  │ Destination                            │ Yes               │
├──────────┼───────────────────────────┼─────────┼────────────────────────────────────────┼───────────────────┤
│ IN-003-C │ FFE per week              │ FFE/wk  │ FFEPerWeek                             │ Yes               │
├──────────┼───────────────────────────┼─────────┼────────────────────────────────────────┼───────────────────┤
│ IN-003-D │ Revenue per FFE           │ USD/FFE │ Revenue_1                              │ Yes               │
├──────────┼───────────────────────────┼─────────┼────────────────────────────────────────┼───────────────────┤
│ IN-003-E │ Transit time              │ days    │ TransitTime                            │ Stored but unused │
├──────────┼───────────────────────────┼─────────┼────────────────────────────────────────┼───────────────────┤
│ IN-003-F │ FFE→TEU conversion factor │ ratio   │ Hardcoded dict (17 lanes, default 2.0) │ Yes               │
├──────────┼───────────────────────────┼─────────┼────────────────────────────────────────┼───────────────────┤
│ IN-003-G │ Weekly TEU (derived)      │ TEU/wk  │ FFEPerWeek × factor                    │ Yes               │
├──────────┼───────────────────────────┼─────────┼────────────────────────────────────────┼───────────────────┤
│ IN-003-H │ Revenue per TEU (derived) │ USD/TEU │ Revenue_1 × factor                     │ Yes               │
├──────────┼───────────────────────────┼─────────┼────────────────────────────────────────┼───────────────────┤
│ IN-003-I │ Same-origin exclusion     │ bool    │ origin≠destination filter              │ Structural rule   │
└──────────┴───────────────────────────┴─────────┴────────────────────────────────────────┴───────────────────┘

##IN-004: DISTANCE (6 inputs from distance_dense.csv, 62,002 rows)

┌──────────┬───────────────────────┬────────────────┬─────────────────┬────────────────────────┐
│    ID    │         Input         │      Unit      │  Source Column  │       Required?        │
├──────────┼───────────────────────┼────────────────┼─────────────────┼────────────────────────┤
│ IN-004-A │ From UNLocode         │ string         │ fromUNLOCODe    │ Yes                    │
├──────────┼───────────────────────┼────────────────┼─────────────────┼────────────────────────┤
│ IN-004-B │ To UNLocode           │ string         │ ToUNLOCODE      │ Yes                    │
├──────────┼───────────────────────┼────────────────┼─────────────────┼────────────────────────┤
│ IN-004-C │ Distance              │ nautical miles │ Distance        │ Yes                    │
├──────────┼───────────────────────┼────────────────┼─────────────────┼────────────────────────┤
│ IN-004-D │ Draft constraint      │ meters         │ Draft           │ No — loaded but unused │
├──────────┼───────────────────────┼────────────────┼─────────────────┼────────────────────────┤
│ IN-004-E │ Panama Canal flag     │ bool           │ IsPanama        │ No — loaded but unused │
├──────────┼───────────────────────┼────────────────┼─────────────────┼────────────────────────┤
│ IN-004-F │ Suez Canal flag       │ bool           │ IsSuez          │ No — loaded but unused │
├──────────┼───────────────────────┼────────────────┼─────────────────┼────────────────────────┤
│ IN-004-G │ Missing-pair fallback │ nm             │ Hardcoded 500.0 │ Yes                    │
└──────────┴───────────────────────┴────────────────┴─────────────────┴────────────────────────┘

## IN-005: COST PARAMETERS

These are mostly hardcoded constants; a few are loaded from port data (see IN-002).

| ID | Input | Value | Unit | Source | Required? |
|---|---|---|---|---|---|
| IN-005-A | Transshipment cost per TEU | 80.0 | USD/TEU | `hub_milp.py:DEFAULT_TRANSSHIP_COST` | Yes — penalty for hub routing vs direct |
| IN-005-B | Port handling cost per TEU | 15.0 | USD/TEU | `hub_milp.py:DEFAULT_PORT_COST` | Yes — baseline port cost |
| IN-005-C | Port capacity (default) | 1e9 | TEU | `hub_milp.py:DEFAULT_PORT_CAPACITY` | Yes — effectively unconstrained unless congestion override applied |
| IN-005-D | Unserved demand penalty (MILP) | 300.0 | USD/TEU | `hub_milp.py:alpha_unserved` | Yes — large penalty drives coverage |
| IN-005-E | Unserved demand penalty (GA) | 50.0 | USD/TEU | `service_ga.py:alpha_unserved` / `hierarchical_ga.py:alpha_unserved` | Yes — fitness penalty for unsatisfied demand |
| IN-005-F | Overcapacity penalty (FrequencyGA) | 0.015 | fraction | `frequency_ga.py:overcap_penalty` | Yes — cost of unused capacity |
| IN-005-G | Overcapacity penalty (ServiceGA) | 0.02 | fraction | `service_ga.py:beta_overcapacity` | Yes — fitness penalty |
| IN-005-H | Alignment penalty (ServiceGA) | 0.3 | dimensionless | `service_ga.py:gamma_alignment` | Yes — penalty for zero-demand services |
| IN-005-I | Profit weight (profit_first mode) | 0.60 | weight | `optimizer_config.py:profit_first_weights.profit` | Yes — objective function coefficient |
| IN-005-J | Coverage weight (profit_first mode) | 0.25 | weight | `optimizer_config.py:profit_first_weights.coverage` | Yes — objective function coefficient |
| IN-005-K | Cost weight (profit_first mode) | 0.15 | weight | `optimizer_config.py:profit_first_weights.cost` | Yes — objective function coefficient |
| IN-005-L | Min coverage target | 70.0 | percent | `optimizer_config.py:min_coverage_percent` | Yes — feedback loop trigger |
| IN-005-M | Min margin threshold | 0.05 | fraction (5%) | `optimizer_config.py:min_margin_percent` | Yes — profitability gate |
| IN-005-N | Profitability gate enabled | True | bool | `optimizer_config.py:profitability_gate_enabled` | Yes |
| IN-005-O | Weather speed factor bounds [min, max] | [0.5, 1.5] | ratio | `fuel_cost.py:WEATHER_SPEED_FACTOR_MIN/MAX` | Yes — clamped before use |
| IN-005-P | Max frequency per service | 3 | sailings/week | `frequency_ga.py:MAX_FREQ` | Yes — hard constraint |
| IN-005-Q | Min frequency per service | 1 | sailing/week | `frequency_ga.py:MIN_FREQ` | Yes — hard constraint |
| IN-005-R | GA population size | 80 | individuals | `config.py:GA_POPULATION_SIZE` env, default 80 | Yes |
| IN-005-S | GA generations | 120 | iterations | `config.py:GA_GENERATIONS` env, default 120 | Yes |
| IN-005-T | MILP time limit | 120 | seconds | `config.py:MILP_TIME_LIMIT` env, default 120 | Yes |
| IN-005-U | Max fleet size | 300 | vessels | Hardcoded in `hub_milp.py` constructor | Yes — synthetic, not from fleet_world_large.csv |
| IN-005-V | Iteration selector scoring weights | profit=0.60, coverage=0.25, cost=0.15 | weights | `iteration_selection.py:DEFAULT_SCORING_WEIGHTS` | Yes |
| IN-005-W | Consensus voter weights | coordinator=0.40, regional=0.40, svc_gen=0.20 | weights | `consensus_engine.py:COORDINATOR_WEIGHT etc.` | Yes |
| IN-005-X | Consensus confidence thresholds | accepted>0.70, rejected<0.30 | thresholds | `consensus_engine.py` | Yes |
| IN-005-Y | Min iterations budget | 3 | count | Enforced in `orchestrator_agent.py` as MIN_ITERATIONS | Yes |
| IN-005-Z | No-improve early-stop limit (GA) | 8 | generations | `service_ga.py:NO_IMPROVE_LIMIT` / `frequency_ga.py:NO_IMPROVE_LIMIT` | Yes |
| IN-005-AA | GA hard runtime cap | 90 | seconds | `service_ga.py:MAX_RUNTIME` / `frequency_ga.py:MAX_RUNTIME` | Yes |
| IN-005-AB | Default port cost per TEU (fallback) | 0.0 | USD/TEU | `hierarchical_ga.py:port_cost_per_teu` default — forces dataset costs | Yes |
| IN-005-AC | Strategic service margin threshold | 0.05 | fraction | `hierarchical_ga.py:122` | Yes — strategic services exempt from margin gate |
| IN-005-AD | Expected utilization (direct demand) | 0.60 | fraction | `hierarchical_ga.py:86` | Yes — used in profitability pre-filter |
| IN-005-AE | Expected utilization (indirect/hub) | 0.30 | fraction | `hierarchical_ga.py:86` | Yes — used in profitability pre-filter |

##Summary

┌───────────────────────┬───────┬──────────────────────────────────────────────┐
│       Category        │ Count │                    Files                     │
├───────────────────────┼───────┼──────────────────────────────────────────────┤
│ Fleet inputs          │ 6     │ 1 CSV + hardcoded constants                  │
├───────────────────────┼───────┼──────────────────────────────────────────────┤
│ Port inputs           │ 13    │ ports.csv (435 rows) + port_mapping.csv      │
├───────────────────────┼───────┼──────────────────────────────────────────────┤
│ Demand inputs         │ 9     │ demand_world_large.csv (9,622 rows)          │
├───────────────────────┼───────┼──────────────────────────────────────────────┤
│ Distance inputs       │ 7     │ distance_dense.csv (62,002 rows) + fallback  │
├───────────────────────┼───────┼──────────────────────────────────────────────┤
│ Cost parameters       │ 38    │ Hardcoded constants across optimizer modules │
├───────────────────────┼───────┼──────────────────────────────────────────────┤
│ Configuration         │ 20+   │ .env + constructor defaults                  │
├───────────────────────┼───────┼──────────────────────────────────────────────┤
│ Other/runtime         │ 14    │ Maritime APIs, seeds, archetype plans        │
├───────────────────────┼───────┼──────────────────────────────────────────────┤
│ Total distinct inputs │ ~107  │                                              │
└───────────────────────┴───────┴──────────────────────────────────────────────┘

## System Outputs: Varied by every run.

| ID | Output | Meaning | Unit | Consumer |
|---|---|---|---|---|
| OUT-001 | Services | 497 selected round-trip services (id, ports, vessel_class, capacity) | count / list of objects | Dashboard, benchmark reports, downstream API |
| OUT-002 | Vessel Assignments | Vessels deployed per service (derived from frequency × cycle_time) — total fleet used | vessels | Fleet planner, constraint validator |
| OUT-003 | Demand Served | 900,491 TEU/wk satisfied out of ~1.9M total demand | TEU/week | Coverage KPI, iteration selector |
| OUT-004 | Revenue | $2.95 B/week gross freight revenue across all served lanes | USD/week | Profit calc, economic validator |
| OUT-005 | Total Cost | $2.08 B/week = fuel ($1.72B) + operating ($227M) + port ($75M) + transshipment ($64M) | USD/week | Profit calc, cost-breakdown dashboard |
| OUT-006 | Profit | $861.7 M/week weekly, $44.8 B annual, margin 29.3% | USD/week and USD/year | Objective function, executive summary |
| OUT-007 | Coverage | 47.5% global demand-weighted; 66.5% average regional | percent [0–100] | Convergence check, iteration selection, feedback loop |

## System Decision Variables

| Entity | Meaning | Required Attributes |
|---|---|---|
| Vessel | A single container-carrying ship defined by its class, which determines capacity, fuel consumption rate, and service speed | vessel_class (Feeder_450 / Feeder_800 / Panamax_1200 / Panamax_2400 / Post_panamax / Super_panamax), capacity TEU, consumption_tons_per_day, speed_knots |
| Port | A geographic loading/unloading node identified by UNLocode with coordinates for clustering and cost attributes for handling | id (UNLocode string), name, latitude, longitude, handling_cost, port_call_cost, transshipment_cost, variable_port_call_cost |
| Demand | A trade lane representing weekly container flow between an origin and destination port, with associated revenue | origin (UNLocode), destination (UNLocode), weekly_teu, revenue_per_teu |
| Route | The ordered sequence of ports visited by a single service round-trip; defines the physical path and total distance | ports (ordered list of UNLocode strings), derived distance_nm (sum of pairwise distances from distance matrix), cycle_time days |
| Service | A scheduled round-trip route operated at a chosen frequency with an assigned vessel class — the fundamental decision variable of the optimizer | id, ports, capacity TEU, weekly_cost USD, cycle_time days, speed knots, fuel_cost USD/week, vessel_class |
| Service Archetype | A template describing the intended mix of service types (direct, hub-loop, feeder, trunk) and the preferred vessel size bias for a region or the network | archetype_mix.direct_ratio, archetype_mix.hub_loop_ratio, archetype_mix.feeder_ratio, archetype_mix.trunk_ratio, vessel_bias (small / balanced / large), hub_focus (list of port IDs) |
| Assignment | The allocation of demanded TEU onto one or more selected services on a given lane — direct if both endpoints are on the same service, otherwise split across a origin-service + transshipment + destination-service chain | service_id, load TEU, capacity TEU, revenue USD, cost USD, weekly_profit USD, margin_pct, region |
| Candidate Solution | One complete iteration of the pipeline: all regional GA+MILP runs, the consensus policy, and the set of selected services produced in that iteration — evaluated as one point on the Pareto frontier | iteration index, status, metrics (profit, coverage, cost, margin, convergence), selected_services, weights_used, consensus_result, feedback |
| Regional Solution | The output of a single regional agent: the services it selected, their flows, and its profit/coverage/cost broken down by region — one per active cluster | region, status, services_generated, services_filtered, services_selected (count), weekly_profit, total_cost, coverage_percent, satisfied_demand, unserved_demand, hub_ports, regional_policy |
| Global Solution | The final selected candidate iteration assembled into the canonical output artifact — the system's answer to "which services sail and how much cargo moves where" | status, summary_metrics (weekly_profit, annual_profit, revenue, total_cost, coverage), selected_services (list), iteration_selection (Pareto rationale), consensus_result, llm_runtime_aggregate |

##System Economic Model 

9.1 Revenue

MILP (HubMILP):
Revenue = Σ_d Σ_s r_d × f_{d,s}  +  Σ_d Σ_{s1,s2} r_d × tf_{d,s1,s2}
Where r_d = demand.revenue_per_teu, f = direct flow TEU, tf = transshipment flow TEU

GA (ServiceGA):
Revenue = Σ_i served_i × avg_rev_per_teu × yield_factor_i
yield_factor_i = 0.6 + 0.4 × (served_i / effective_capacity_i)
effective_capacity_i = service.capacity × (7 / cycle_time)

┌─────────────────┬──────────────────────────────────────────────────────┬────────────────────┬────────────────────────────────────────────────────┐
│    Variable     │                       Meaning                        │        Unit        │                       Source                       │
├─────────────────┼──────────────────────────────────────────────────────┼────────────────────┼────────────────────────────────────────────────────┤
│ r_d             │ Revenue per TEU on demand lane d                     │ USD/TEU            │ Demand.revenue_per_teu from demand_world_large.csv │
├─────────────────┼──────────────────────────────────────────────────────┼────────────────────┼────────────────────────────────────────────────────┤
│ f_{d,s}         │ TEU of demand d served directly by service s         │ TEU                │ MILP decision variable                             │
├─────────────────┼──────────────────────────────────────────────────────┼────────────────────┼────────────────────────────────────────────────────┤
│ tf_{d,s1,s2}    │ TEU of demand d served via transshipment (s1→hub→s2) │ TEU                │ MILP decision variable                             │
├─────────────────┼──────────────────────────────────────────────────────┼────────────────────┼────────────────────────────────────────────────────┤
│ served_i        │ Effective TEU satisfied by service i                 │ TEU                │ min(effective_capacity, direct_demand)             │
├─────────────────┼──────────────────────────────────────────────────────┼────────────────────┼────────────────────────────────────────────────────┤
│ avg_rev_per_teu │ Network-wide average revenue per TEU                 │ USD/TEU            │ Weighted average across all demands                │
├─────────────────┼──────────────────────────────────────────────────────┼────────────────────┼────────────────────────────────────────────────────┤
│ yield_factor    │ Utilization-based revenue yield adjustment           │ ratio ∈ [0.6, 1.0] │ Computed per-service                               │
└─────────────────┴──────────────────────────────────────────────────────┴────────────────────┴────────────────────────────────────────────────────┘

9.2 Vessel Fixed Cost

Operating Cost = Σ_s weekly_cost_s × frequency_s

┌───────────────┬───────────────────────────────────────────┬──────────┬───────────────────────────────────────────────┐
│   Variable    │                  Meaning                  │   Unit   │                    Source                     │
├───────────────┼───────────────────────────────────────────┼──────────┼───────────────────────────────────────────────┤
│ weekly_cost_s │ Fixed weekly operating cost of service s  │ USD/week │ Service.weekly_cost from dataset              │
├───────────────┼───────────────────────────────────────────┼──────────┼───────────────────────────────────────────────┤
│ frequency_s   │ Number of sailings per week (integer 1–3) │ count    │ FrequencyGA output; min 1 if service selected │
└───────────────┴───────────────────────────────────────────┴──────────┴───────────────────────────────────────────────┘

9.3 Vessel Dynamic / Fuel Cost

Fuel Cost_s = (distance_cycle_s / (speed_knots × 24 × 0.9)) × consumption_tons_per_day × bunker_price × (7 / cycle_time) × frequency

With weather adjustment: distance_cycle / (speed × 0.9 × 24 × wsf) where wsf ∈ [0.5, 1.5]

┌──────────────────────────┬───────────────────────────────────────────────┬────────────────────┬────────────────────────────────────────────────────────────────┐
│         Variable         │                    Meaning                    │        Unit        │                             Source                             │
├──────────────────────────┼───────────────────────────────────────────────┼────────────────────┼────────────────────────────────────────────────────────────────┤
│ distance_cycle_s         │ Total nautical miles for one round-trip cycle │ nm                 │ Sum of pairwise distances from distance_dense.csv              │
├──────────────────────────┼───────────────────────────────────────────────┼────────────────────┼────────────────────────────────────────────────────────────────┤
│ speed_knots              │ Service speed for vessel class                │ knots              │ VESSEL_FUEL_CONSUMPTION[vessel_class].speed_knots              │
├──────────────────────────┼───────────────────────────────────────────────┼────────────────────┼────────────────────────────────────────────────────────────────┤
│ consumption_tons_per_day │ Fuel burn at service speed                    │ tons/day           │ VESSEL_FUEL_CONSUMPTION[vessel_class].consumption_tons_per_day │
├──────────────────────────┼───────────────────────────────────────────────┼────────────────────┼────────────────────────────────────────────────────────────────┤
│ bunker_price             │ IFO 380 fuel price                            │ USD/ton            │ Hardcoded BUNKER_PRICE_PER_TON = 600.0                         │
├──────────────────────────┼───────────────────────────────────────────────┼────────────────────┼────────────────────────────────────────────────────────────────┤
│ cycle_time               │ Days for one complete round-trip              │ days               │ Service.cycle_time (default 7)                                 │
├──────────────────────────┼───────────────────────────────────────────────┼────────────────────┼────────────────────────────────────────────────────────────────┤
│ wsf                      │ Weather speed factor                          │ ratio ∈ [0.5, 1.5] │ maritime/weather/ feature adapter; None → no adjustment        │
└──────────────────────────┴───────────────────────────────────────────────┴────────────────────┴────────────────────────────────────────────────────────────────┘

9.4 Idle Cost

NOT IMPLEMENTED. No idle/deadweight cost term exists in any optimizer or economic engine.

9.5 Container Handling Cost

Port Handling Cost = Σ_p handling_cost_p × total_TEU_through_p

┌─────────────────────┬──────────────────────────────────┬─────────┬─────────────────────────────────────────────────────┐
│      Variable       │             Meaning              │  Unit   │                       Source                        │
├─────────────────────┼──────────────────────────────────┼─────────┼─────────────────────────────────────────────────────┤
│ handling_cost_p     │ Per-TEU handling cost at port p  │ USD/TEU │ Port.handling_cost = ports.csv:CostPerFULL × 2.0    │
├─────────────────────┼──────────────────────────────────┼─────────┼─────────────────────────────────────────────────────┤
│ total_TEU_through_p │ Total TEU passing through port p │ TEU     │ Sum of all flow variables on services stopping at p │
└─────────────────────┴──────────────────────────────────┴─────────┴─────────────────────────────────────────────────────┘

9.6 Transshipment Cost

Transshipment Cost = Σ_{transship flows} tc_per_teu × flow_TEU
or in GA approximation: hub_ratio × satisfied_demand × tc_per_teu

┌────────────┬─────────────────────────────────────────────────┬────────────────────┬────────────────────────────────────────────────────────────────────────┐
│  Variable  │                     Meaning                     │        Unit        │                                 Source                                 │
├────────────┼─────────────────────────────────────────────────┼────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ tc_per_teu │ Cost per TEU to transship at hub port           │ USD/TEU            │ DEFAULT_TRANSSHIP_COST = 80.0 or Port.transshipment_cost × 2 from data │
├────────────┼─────────────────────────────────────────────────┼────────────────────┼────────────────────────────────────────────────────────────────────────┤
│ hub_ratio  │ Estimated fraction of satisfied flow using hubs │ ratio ∈ [0.3, 0.7] │ max(0.3, min(0.7, num_hubs / num_ports)) in GA only                    │
└────────────┴─────────────────────────────────────────────────┴────────────────────┴────────────────────────────────────────────────────────────────────────┘
### hub_ratio bounds

| Bound | Purpose |
|---|---|
| max(0.3, …) | Floor — prevents transshipment cost from collapsing to zero when a tiny problem has very few hub ports (e.g., 5 ports → 1 hub → ratio 0.2, clamped to 0.3). Guarantees a minimum transshipment penalty that reflects real-world hub usage even in small instances. |
| min(0.7, …) | Ceiling — prevents the ratio from exceeding 70% if someone runs the GA on an oddly structured network where many ports happen to be classified as hubs. Keeps the transshipment cost estimate from overshooting reality. |

9.7 Port Call Cost

Port Call Cost = Σ_p [ port_call_cost_p × num_active_services_at_p  +  variable_port_cost_p × total_TEU_through_p ]

┌──────────────────────────┬────────────────────────────────────────────┬─────────┬───────────────────────────────────────────────────────────────────┐
│         Variable         │                  Meaning                   │  Unit   │                              Source                               │
├──────────────────────────┼────────────────────────────────────────────┼─────────┼───────────────────────────────────────────────────────────────────┤
│ port_call_cost_p         │ Fixed cost per port call                   │ USD     │ Port.port_call_cost = ports.csv:PortCallCostFixed                 │
├──────────────────────────┼────────────────────────────────────────────┼─────────┼───────────────────────────────────────────────────────────────────┤
│ num_active_services_at_p │ Number of selected services calling port p │ count   │ From chromosome/frequency solution                                │
├──────────────────────────┼────────────────────────────────────────────┼─────────┼───────────────────────────────────────────────────────────────────┤
│ variable_port_cost_p     │ Variable cost per TEU at port              │ USD/TEU │ Port.variable_port_call_cost = ports.csv:PortCallCostPerFFE × 2.0 │
└──────────────────────────┴────────────────────────────────────────────┴─────────┴───────────────────────────────────────────────────────────────────┘

9.8 Escort / Tug Cost

DOCUMENTED BUT NOT IMPLEMENTED. Referenced in documentation and benchmark schema as a field (escort_fee) but always returns null in code. Never computed or charged.

9.9 Other Costs

┌───────────────────────────┬──────────────────────────────────────────────────────────┬──────────────────┬─────────────────────────────────────────────────────────┐
│           Cost            │                         Formula                          │       Unit       │                         Source                          │
├───────────────────────────┼──────────────────────────────────────────────────────────┼──────────────────┼─────────────────────────────────────────────────────────┤
│ Unserved demand penalty   │ α × Σ_d unserved_d where α = 300                         │ USD/week         │ HubMILP.alpha_unserved = 300.0                          │
│ (MILP)                    │                                                          │                  │                                                         │
├───────────────────────────┼──────────────────────────────────────────────────────────┼──────────────────┼─────────────────────────────────────────────────────────┤
│ Unserved demand penalty   │ α × unserved_demand where α = 50                         │ USD/week         │ ServiceGA.alpha_unserved = 50.0                         │
│ (GA)                      │                                                          │                  │                                                         │
├───────────────────────────┼──────────────────────────────────────────────────────────┼──────────────────┼─────────────────────────────────────────────────────────┤
│ Overcapacity penalty (GA) │ β × unused_capacity × (operating_cost / total_capacity)  │ USD/week         │ ServiceGA.beta_overcapacity = 0.02                      │
│                           │ where β = 0.02                                           │                  │                                                         │
├───────────────────────────┼──────────────────────────────────────────────────────────┼──────────────────┼─────────────────────────────────────────────────────────┤
│ Alignment penalty (GA)    │ γ × weekly_cost for each zero-direct-demand service      │ USD/week         │ ServiceGA.gamma_alignment = 0.3                         │
│                           │ where γ = 0.3                                            │                  │                                                         │
├───────────────────────────┼──────────────────────────────────────────────────────────┼──────────────────┼─────────────────────────────────────────────────────────┤
│ Negative margin penalty   │ Tiered: loss >30% → 100% of loss; 20–30% → 70%; 10–20% → │ USD/week         │ ServiceGA lines 294–310                                 │
│ (GA)                      │  50%; <10% → 20%, capped at $100k                        │                  │                                                         │
├───────────────────────────┼──────────────────────────────────────────────────────────┼──────────────────┼─────────────────────────────────────────────────────────┤
│ Coverage reward (MILP     │ (w_coverage / w_profit) × (satisfied / total_demand) ×   │ dimensionless    │ HubMILP line 367–371 — added to objective but excluded  │
│ objective only)           │ |operating_cost + 1|                                     │ bonus            │ from true economic profit                               │
└───────────────────────────┴──────────────────────────────────────────────────────────┴──────────────────┴─────────────────────────────────────────────────────────┘

9.10 Total Cost

True Economic Profit (benchmark-recomputed, used for fair comparison):
Total Cost = vessel_fixed_cost + fuel_cost + transshipment_cost
           + port_handling_cost + port_fixed_cost + port_variable_cost
           + unserved_penalty
(escort_fee = null / not implemented)

Optimizer Objective (what HubMILP actually maximizes):
Objective = profit_expr + coverage_reward
profit_expr = revenue − operating_cost − fuel_cost − transshipment_cost
              − port_handling_cost − unserved_penalty
coverage_reward = (w_coverage/w_profit) × (satisfied/total_demand) × |operating_cost + 1|

┌───────────────────────────────────────────────────┬───────────────────────────────────────────────────────────────────────────┐
│                       File                        │                               Formula Used                                │
├───────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
│ src/optimization/hub_milp.py:358–373              │ MILP objective (includes coverage_reward)                                 │
├───────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
│ src/optimization/service_ga.py:336–346            │ GA fitness (no coverage_reward, has overcap/alignment/negative penalties) │
├───────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
│ benchmark/comparative/economic_engine.py:159–167  │ True economic total cost (excludes coverage_reward)                       │
├───────────────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────┤
│ benchmark/economics/economic_validator.py:104–109 │ Validator total cost (same as above)                                      │
└───────────────────────────────────────────────────┴───────────────────────────────────────────────────────────────────────────┘

9.11 Profit

True Economic Weekly Profit:
Weekly Profit = Revenue − Total Cost
             = Revenue − (vessel_fixed + fuel + transshipment
                        + port_handling + port_fixed + port_variable
                        + unserved_penalty)
Annual Profit = Weekly Profit × 52
Profit Margin % = (Weekly Profit / Revenue) × 100

Optimizer-reported value (MILP): equals pulp.value(prob.objective) which includes the coverage_reward bonus — therefore optimizer_objective ≥ true_economic_profit whenever coverage_reward > 0.

┌───────────────────┬────────────────────────────────┬──────┬───────────────────────────────────────┐
│       Field       │ Current Value (production run) │ Unit │               Producer                │
├───────────────────┼────────────────────────────────┼──────┼───────────────────────────────────────┤
│ weekly_profit     │ 861,652,013                    │ USD  │ summary_metrics → dashboard           │
├───────────────────┼────────────────────────────────┼──────┼───────────────────────────────────────┤
│ annual_profit     │ 44,805,904,655                 │ USD  │ weekly_profit × 52                    │
├───────────────────┼────────────────────────────────┼──────┼───────────────────────────────────────┤
│ revenue           │ 2,945,463,273                  │ USD  │ sum of per-service revenue            │
├───────────────────┼────────────────────────────────┼──────┼───────────────────────────────────────┤
│ total_cost        │ 2,083,811,260                  │ USD  │ sum of all cost components            │
├───────────────────┼────────────────────────────────┼──────┼───────────────────────────────────────┤
│ profit_margin_pct │ 29.3                           │ %    │ weekly_profit / revenue × 100         │
├───────────────────┼────────────────────────────────┼──────┼───────────────────────────────────────┤
│ coverage          │ 47.5                           │ %    │ satisfied_demand / total_demand × 100 │
└───────────────────┴────────────────────────────────┴──────┴───────────────────────────────────────┘

##CONSOLIDATED CONSTRAINT TABLE

┌─────────┬─────────────────────────────────────┬──────────────────────────┬───────────────────────────────────────────┬───────────────────────────┬───────────────┐
│   ID    │             Constraint              │           Type           │              Enforced Where               │        Verified By        │    Status     │
├─────────┼─────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┼───────────────────────────┼───────────────┤
│ C-001   │ Service load ≤ capacity             │ Hard                     │ MILP (line 412), GA (line 146)            │ V-14                      │ ✓ Active      │
├─────────┼─────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┼───────────────────────────┼───────────────┤
│ C-002   │ Demand = served + unserved          │ Hard                     │ MILP (line 393)                           │ V-11                      │ ✓ Active      │
├─────────┼─────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┼───────────────────────────┼───────────────┤
│ C-003   │ Per-class vessel availability       │ Not enforced             │ —                                         │ —                         │ ✗ Missing     │
├─────────┼─────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┼───────────────────────────┼───────────────┤
│ C-004   │ Valid port sequences                │ Structural               │ MILP compat index                         │ V-5, V-15                 │ ✓ Active      │
├─────────┼─────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┼───────────────────────────┼───────────────┤
│ C-005   │ Port capacity limit                 │ Hard                     │ MILP (line 422)                           │ ❌ Not externally         │ ⚠ Gap         │
│         │                                     │                          │                                           │ verified                  │               │
├─────────┼─────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┼───────────────────────────┼───────────────┤
│ C-006   │ Total fleet ≤ 300                   │ Hard                     │ MILP (line 389), GA early-reject          │ V-9 (NOT_TESTABLE)        │ ⚠ Verifier    │
│         │                                     │                          │                                           │                           │ gap           │
├─────────┼─────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┼───────────────────────────┼───────────────┤
│ C-007   │ Flow non-negativity + conservation  │ Hard                     │ MILP (lines 288–401)                      │ V-11                      │ ✓ Active      │
├─────────┼─────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┼───────────────────────────┼───────────────┤
│ C-008   │ Demand conservation across regions  │ Hard                     │ RegionalSplitter assert                   │ V-12, test_data_integrity │ ✓ Active      │
├─────────┼─────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┼───────────────────────────┼───────────────┤
│ C-009   │ Min coverage threshold              │ Conditional (currently   │ MILP (line 403, guard if min_coverage >   │ V-17 (range check only)   │ ○ Inactive    │
│         │                                     │ 0)                       │ 0)                                        │                           │               │
├─────────┼─────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┼───────────────────────────┼───────────────┤
│ C-010-A │ Frequency ∈ {1,2,3}                 │ Hard                     │ FrequencyGA clamping                      │ Structural                │ ✓ Active      │
├─────────┼─────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┼───────────────────────────┼───────────────┤
│ C-010-B │ GA runtime ≤ 90s, no-improve ≤ 8    │ Hard                     │ Both GAs                                  │ Timing only               │ ✓ Active      │
│         │ gen                                 │                          │                                           │                           │               │
├─────────┼─────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┼───────────────────────────┼───────────────┤
│ C-010-C │ MILP time limit ≤ 120s              │ Hard                     │ CBC solver config                         │ Timing only               │ ✓ Active      │
├─────────┼─────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┼───────────────────────────┼───────────────┤
│ C-010-D │ Profitability gate (5% margin)      │ Hard                     │ HierarchicalGA pre-filter                 │ Structural                │ ✓ Active      │
├─────────┼─────────────────────────────────────┼──────────────────────────┼───────────────────────────────────────────┼───────────────────────────┼───────────────┤
│ C-010-E │ At least one service selected       │ Hard                     │ GA fitness lethal penalty                 │ Structural                │ ✓ Active      │
└─────────┴─────────────────────────────────────┴──────────────────────────┴───────────────────────────────────────────┴───────────────────────────┴───────────────┘

## SERVICE GENERATION

13.1 Purpose

To construct a candidate pool of ~400–1,200 plausible liner shipping services from raw demand data, so that the subsequent GA/MILP optimizers have a rich design space from which to select the optimal subset. The generator does not optimize — it proposes. The optimizer later selects, frequencies, and routes flow.


- ServiceGeneratorAgent.generate_services() (src/agents/service_generator_agent.py) — the production LLM-influenced generator used inside each regional agent. It is the one actually exercised in production.

---

13.2 Inputs

┌──────────────────────────┬──────────────────────────────────────┬─────────────────────────────────────────────────┐
│          Input           │                Source                │                   Description                   │
├──────────────────────────┼──────────────────────────────────────┼─────────────────────────────────────────────────┤
│ problem (Problem object) │ RegionalSplitter output              │ Contains ports, demands, distance_matrix        │
├──────────────────────────┼──────────────────────────────────────┼─────────────────────────────────────────────────┤
│ archetype_params         │ SharedContext / LLM output / DEFAULT │ Dict with archetype_mix, vessel_bias, hub_focus │
├──────────────────────────┼──────────────────────────────────────┼─────────────────────────────────────────────────┤
│ hubs (list of port IDs)  │ HubDetector.detect_hubs(top_k=20)    │ Top-20 ports by demand × connectivity score     │
├──────────────────────────┼──────────────────────────────────────┼─────────────────────────────────────────────────┤
│ top10_hubs               │ hubs[:10]                            │ First 10 of the above, used for trunk routes    │
└──────────────────────────┴──────────────────────────────────────┴─────────────────────────────────────────────────┘

---

### 13.3 Outputs

| Output | Type | Count (typical) |
|---|---|---|
| services (List[Service]) | List of Service dataclass instances | ~450 direct + ~10 hub-loops + ~45 trunk + ~1,200 feeders + ~150 heuristic = ~1,855 total (capped at production dataset size) |
| Log events | direct_services_added, hub_loop_services_added, trunk_services_added, feeder_services_added | One per generation phase |

Each Service has: id (int), ports (List[str]), capacity (TEU), weekly_cost (USD), cycle_time (days), speed (knots, default 18), fuel_cost (USD, computed later), vessel_class (str).

---

13.4 Generation Rules

Four deterministic generation phases, weighted by archetype ratios:

Phase A — Direct Services (n_direct corridors):
n_direct = min(800, max(200, int(500 × direct_ratio / 0.60)))
# Takes top-N highest-demand lanes (origin→destination by weekly_teu desc)
# Route: [origin, destination]  (2-port direct line)
# Capacity: round to nearest standard size {1000, 2000, 4500, 8000, 12000, 16000}
#   target = max(1000, demand_teu × 1.2)   # 20% growth buffer
# Weekly cost: 150,000 × (capacity / 8000)
# Cycle time: 14 days

Phase B — Hub-Loop Services (hub_loop_count loops):
hub_loop_count = max(2, int(10 × hub_loop_ratio / 0.15))
# For each of top-10 hubs:
#   Find top-20 spoke ports by demand volume to/from hub
#   Group spokes into batches of 5 → route = [hub, s1, s2, s3, s4, s5, hub]
# Capacity tiers based on loop-level demand:
#   > 8000 TEU → 14,000 TEU, $280K/week
#   > 4000 TEU → 10,000 TEU, $180K/week
#   ≤ 4000 TEU → 8,000 TEU,  $150K/week
# Cycle time: 21 days

Phase C — Trunk Routes (C(10,2) = 45 pairs from top-10 hubs):
# Every pair of top-10 hubs gets a direct trunk service
# Route: [hub_i, hub_j]
# Capacity: 12,000 TEU fixed
# Weekly cost: $200,000 fixed
# Cycle time: 14 days

Phase D — Feeder Services (one per spoke-to-hub pair):
for each non-hub port (spoke):
    Find best hub(s) by demand affinity (total TEU between spoke and hub)
    Connect spoke → top-2 hubs (for redundancy)
    Capacity tiered by spoke demand:
      > 5000 TEU → demand × 1.2, sizes {4500, 8000, 10000, 14000}
      > 2000 TEU → demand × 1.3, sizes {2000, 4500, 8000}
      > 500  TEU → demand × 1.5, sizes {500,  1000, 2000, 4500}
      ≤ 500  TEU → 500 TEU minimum, sizes {500, 1000}
    Weekly cost: 70,000 × (capacity / 4000)
    Cycle time: 7 days

Phase E — Heuristic Base Pool (fallback candidate enrichment):
# CandidateServiceGenerator generates up to 150 additional corridor+feeder services
# Using simpler 25% hub-insertion probability and random nearby-port feeder selection

---

### 13.5 Service Validity Requirements

| Requirement | Enforcement | File |
|---|---|---|
| Valid route (≥ 2 ports) | Hard-coded in each phase; < 2 ports skipped | service_generator_agent.py:131–134 |
| Valid ports (port IDs exist in problem) | Ports drawn from problem.ports and problem.distance_matrix keys | service_generator_agent.py:49 |
| Valid parameters (capacity > 0, cost ≥ 0, cycle_time > 0) | All generated values are positive constants | Per-phase code |
| Valid capacity (rounded to standard sizes) | min(standard_sizes, key=lambda x: abs(x - target)) | Lines 92–93, 222–223 |
| Valid frequency (1–3, set later by FrequencyGA) | Not set during generation; inherited from chromosome | frequency_ga.py:16–17 |
| Valid demand relationship (demand exists on corridor) | Services generated from actual demand data | Lines 82–83 |
| Passes domain validation (vessel_class known type) | map_capacity_to_vessel_class() always returns valid class | fuel_cost.py:93–106 |
| Other: No origin==destination self-loops | Explicitly skipped at line 85–86 | service_generator_agent.py:85 |

## GENETIC ALGORITHM

The system uses two sequential GAs wrapped by a hierarchical orchestrator. They solve different decision layers:

| GA | Chromosome | What it decides | Pop size | Generations | Runtime cap |
|---|---|---|---|---|---|
| ServiceGA | Binary List[int] length N_services | Which services to include | adaptive (60–140) | 120 | 90 s |
| FrequencyGA | Integer List[int] length N_services, values ∈ {0,1,2,3} | How many times/week each selected service sails | 40 | 60 | 90 s |

Both feed into HubMILP (exact solver) which assigns flow; the full pipeline is HierarchicalGA.

---

15.1 Representation

ServiceGA chromosome — binary mask, one bit per candidate service:

chromosome = [s_0, s_1, …, s_{N-1}]   where  s_i ∈ {0, 1}
s_i = 1  ⇔  service i is included in the solution
s_i = 0  ⇔  service i is excluded
- N = problem.num_services (varies per region, typically 300–800)
- File: src/optimization/service_ga.py:171–187

FrequencyGA chromosome — integer vector, one entry per service (including inactive ones):

chromosome = [f_0, f_1, …, f_{N-1}]   where  f_i ∈ {0, 1, 2, 3}
f_i = 0  ⇔  service i is inactive (same as s_i = 0)
f_i ∈ {1,2,3}  ⇔  service i sails f_i times per week
- Inherited from ServiceGA's output: services mask passed as self.services; only indices where services[i]==1 are evolved
- File: src/optimization/frequency_ga.py:20–40

HierarchicalGA chromosome (output wrapper):

{
    "services":          List[int],     # binary mask from ServiceGA
    "frequencies":       List[int],     # integer vector from FrequencyGA
    "coverage_estimate": float,          # GA-level rough estimate
    "skip_milp":         bool            # True if coverage < 30%, skip MILP
}
- File: src/optimization/hierarchical_ga.py:208–214

---

15.2 Initialization

ServiceGA — demand-biased random:

# Score each service by direct + partial corridor demand
scores = direct_demand + 0.3 × partial_demand
probs  = scores / Σ(scores)

# Randomly select k services where k ∈ [N/20, N/8], clamped to [5, 10] min
k = randint(max(5, N//20), max(10, N//8))
selected = weighted_choice_without_replacement(N, k, probs)
chromosome = zeros(N); chromosome[selected] = 1
- File: src/optimization/service_ga.py:171–187
- Also accepts an optional seed_solution (previous iteration's best) placed at position 0

FrequencyGA — analytical seed with jitter:

# Analytical starting point: demand-driven optimal frequency
init_freq[i] = clamp(ceil(route_demand[i] / capacity[i]), MIN_FREQ=1, MAX_FREQ=3)
init_freq[i] = 0  if route_demand[i] == 0

# Jitter each active gene by −1, 0, or +1
freq[i] = clamp(init_freq[i] + randint(−1, +1), 0, MAX_FREQ)
- File: src/optimization/frequency_ga.py:86–98, 103–111
- Population of pop_size=40 copies, each with independent jitter

Adaptive parameter tuning (ServiceGA only):

┌────────────────┬──────────┬───────────────┐
│ Services count │ pop_size │ mutation_rate │
├────────────────┼──────────┼───────────────┤
│ < 100          │ 60       │ 0.10          │
├────────────────┼──────────┼───────────────┤
│ 100–499        │ 100      │ 0.15          │
├────────────────┼──────────┼───────────────┤
│ ≥ 500          │ 140      │ 0.20          │
└────────────────┴──────────┴───────────────┘

- File: src/optimization/service_ga.py:155–166

---

15.3 Fitness Function

ServiceGA fitness (single scalar, higher is better):

profit  = revenue − operating_cost − fuel_cost − transship_cost
          − port_cost − unserved_penalty − overcap_penalty
          − alignment_penalty − negative_service_penalty

coverage = satisfied_demand / total_demand

fitness = w_profit × norm(profit)
        + w_coverage × norm(coverage)
        − w_cost      × norm(operating_cost)

Component definitions (per selected service i):

┌──────────────────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┬───────────────┐
│        Component         │                                                     Formula                                                     │    Source     │
├──────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────┤
│ revenue                  │ Σ served_i × avg_rev_per_teu × yield_factor_i<br>yield_factor_i = 0.6 + 0.4 × (served_i / effective_capacity_i) │ Line 238–239  │
├──────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────┤
│ served_i                 │ min(effective_capacity_i, direct_demand_i)                                                                      │ Line 232      │
├──────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────┤
│ effective_capacity_i     │ capacity_i × (7 / cycle_time_i)                                                                                 │ Line 231      │
├──────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────┤
│ operating_cost           │ Σ weekly_cost_i (once per selected service, frequency-independent in ServiceGA)                                 │ Line 251      │
├──────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────┤
│ fuel_cost                │ calculate_weekly_fuel_cost(ports, distance_matrix, vessel_class, cycle_time) — one per selected service         │ Lines 254–260 │
├──────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────┤
│ transship_cost           │ hub_ratio × satisfied_demand × $80/TEU where hub_ratio = clamp(num_hubs/num_ports, 0.3, 0.7)                    │ Lines 321–326 │
├──────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────┤
│ port_cost                │ Σ_port [ handled_teu × handling_cost + fixed_cost + handled_teu × variable_cost ]                               │ Lines 262–274 │
├──────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────┤
│ unserved_penalty         │ α × unserved_demand where α = $50/TEU                                                                           │ Line 330      │
├──────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────┤
│ overcap_penalty          │ β × unused_cap × (operating_cost / total_capacity) where β = 0.02                                               │ Lines 332–334 │
├──────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────┤
│ alignment_penalty        │ γ × weekly_cost for each service with direct_demand == 0 where γ = 0.3                                          │ Lines 277–278 │
├──────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────┤
│ negative_service_penalty │ Tiered by margin %: >30% loss → 100% of loss; 20–30% → 70%; 10–20% → 50%; <10% → 20%; capped at $100k           │ Lines 294–310 │
└──────────────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┴───────────────┘

Normalization: min-max to [0,1] per component using running bounds (ObjectiveNormalizer).

FrequencyGA fitness (simpler, no normalization):

fitness = revenue − operating_cost − fuel_cost − port_cost
          − transship_cost − overcapacity_penalty

┌─────────────────┬───────────────────────────────────────────────────────────────────────────────────────────┐
│    Component    │                                          Formula                                          │
├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────┤
│ revenue         │ satisfied × avg_rev where avg_rev = Σ(d.teu × d.rev) / Σ(d.teu)                           │
├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────┤
│ satisfied       │ Σ_i min(capacity_i × freq_i × 7/cycle_time_i, route_demand_i)                             │
├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────┤
│ operating_cost  │ Σ_i weekly_cost_i × freq_i                                                                │
├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────┤
│ fuel_cost       │ Σ_i fuel_cost_per_cycle_i × freq_i                                                        │
├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────┤
│ port_cost       │ Σ_i [ teu_served_i × handling_cost + fixed_cost × freq_i + teu_served_i × variable_cost ] │
├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────┤
│ transship_cost  │ hub_ratio × satisfied × avg_rev_per_teu × 0.05 (different formula than ServiceGA)         │
├─────────────────┼───────────────────────────────────────────────────────────────────────────────────────────┤
│ overcap_penalty │ β × unused_cap × (operating_cost / total_capacity) where β = 0.015                        │
└─────────────────┴───────────────────────────────────────────────────────────────────────────────────────────┘

Lethal penalties (instant infeasible return):
- Empty chromosome (no services selected) → −1e12 (ServiceGA, line 211–212)
- Fleet exceeds 300 vessels → −1e9 (FrequencyGA, lines 123–130)

---

15.4 Selection

Both GAs use elitist truncation selection:

# ServiceGA (line 507–508)
ranked = heapq.nlargest(10, zip(population, fitness), key=lambda x: x[1])
elite  = [x[0] for x in ranked]          # top-10 survive unchanged

# FrequencyGA (line 223–224)
ranked = sorted(zip(population, fitness), key=lambda x: x[1], reverse=True)
population = [x[0] for x in ranked[:10]]  # top-10 survive unchanged

Parents are drawn uniformly from the top-20 ranked individuals:
p1 = random.choice(ranked[:20])[0]
p2 = random.choice(ranked[:20])[0]

No tournament, no roulette wheel — pure rank-based truncation with elite preservation.

---

15.5 Crossover

Single-point crossover (ServiceGA only; FrequencyGA skips crossover entirely):

@staticmethod
def _crossover(p1, p2):
    point = random.randint(1, len(p1) - 2)   # not at edges
    return p1[:point] + p2[point:]
- File: src/optimization/service_ga.py:483–486
- FrequencyGA does not implement crossover — offspring are created by copying a parent and mutating one gene (see 15.6).

---

15.6 Mutation

ServiceGA mutation (_mutate, line 456–481):

if random.random() < 0.5:
    # 50%: activate a currently-OFF service, biased toward high demand
    off_idx = [i for i if child[i] == 0]
    weights = direct_demand[off_idx]       # fall back to partial_demand, then uniform
    idx = weighted_choice(off_idx, weights)
    child[idx] = 1
else:
    # 50%: flip a random bit (on→off or off→on)
    idx = randint(0, N−1)
    child[idx] = 1 − child[idx]
- Mutation rate: 0.15 (adaptive; see 15.2)
- Applied after crossover with probability mutation_rate

FrequencyGA mutation (inline, line 228–233):

child = p1.copy()
idx = random.choice(active_idx)           # only mutate active services
child[idx] = random.randint(0, max_freq)  # reset to random value in {0,1,2,3}
- Every offspring is mutated exactly once (no probabilistic gate)
- Mutation resets a single gene to a fully random frequency — not a small perturbation

---

15.7 Repair / Constraint Handling

Hard constraints enforced via lethal fitness penalties (no repair operators):

| Constraint | Enforcement | Penalty |
|---|---|---|
| At least one service selected | if not selected_idx: return −1e12 | Lethal |
| Fleet ≤ 300 vessels (FrequencyGA) | if vessels_used > 300: return −1e9 | Lethal |
| Frequency ∈ {0,1,2,3} | randint(0, max_freq) in mutation; clamp() in init | Structural (always valid) |
| Service ID length match | Checked implicitly; wrong-length chromosome returns −1e12 | Lethal |

Post-GA repair (HierarchicalGA only, line 174–195):

# After FrequencyGA completes, if fleet still exceeds 300:
# Greedily deactivate lowest-efficiency services until fleet ≤ 300
efficiency[i] = direct_demand[i] / vessels_required[i]
sort ascending by efficiency
for svc in lowest_efficiency:
    if vessels_used <= 300: break
    best_services[svc] = 0
    best_freq[svc] = 0
    vessels_used -= vessels_required[svc]

This is a greedy post-hoc pruning step, not an in-place repair during GA evolution.

---

15.8 Elitism

Both GAs preserve the top-10 individuals verbatim each generation:

elite = ranked[:10]           # top-10 by fitness
population = elite.copy()     # replace entire population with elites
# Then fill remaining slots (pop_size − 10) from crossover/mutation of top-20

- The best individual is tracked across generations via best_fitness
- No generational gap model — each generation is a full replacement (generational GA, not steady-state)

---

15.9 Termination

Three independent stopping conditions, any one triggers exit:

| Condition | ServiceGA | FrequencyGA |
|---|---|---|
| Max generations reached | generations = 120 | generations = 60 |
| No improvement for N generations | NO_IMPROVE_LIMIT = 8 | NO_IMPROVE_LIMIT = 8 |
| Wall-clock time exceeded | MAX_RUNTIME = 90 s | MAX_RUNTIME = 90 s |

for gen in range(generations):
    if time.time() − start > MAX_RUNTIME: break
    …evaluate…
    if current_best > best_fitness:
        best_fitness = current_best; no_improve = 0
    else:
        no_improve += 1
        if no_improve >= NO_IMPROVE_LIMIT: break
- Files: service_ga.py:491–533, frequency_ga.py:208–249

HierarchicalGA overall budget (max_runtime_sec = 60 s default, line 29): ServiceGA consumes up to 80% of budget; FrequencyGA gets the remainder. If ServiceGA alone exceeds 80%, FrequencyGA is skipped.

---

15.10 GA Invariants

INV-GA-001 — Every chromosome has a valid representation.
- ServiceGA: chromosome is a List[int] of length exactly num_services; every element is 0 or 1. Validated at construction (self.num_services = len(problem.services)) and by the empty-chromosome lethal check (line 211).
- FrequencyGA: chromosome is a List[int] of length num_services; every element is an integer in {0, 1, 2, 3}. Enforced structurally by initialization (clamp(init_freq, 0, MAX_FREQ)) and mutation (randint(0, max_freq)).
- Verified by: tests/test_ga.py:81–82 (length equality), tests/test_ga.py:100–101 (frequency length).

INV-GA-002 — Fitness follows the defined objective.
- ServiceGA fitness is a deterministic function of the chromosome only (no external state, no stochasticity in evaluation). Cache key includes weights to prevent stale results: key = bytes(services) + str((w_profit, w_coverage, w_cost)).encode().
- FrequencyGA fitness recomputes from scratch each call; no cache.
- Both produce float results; empty/invalid input maps to −1e12 or −1e9 respectively.
- Verified by: tests/test_ga.py re-runs same chromosome and checks consistent fitness.

INV-GA-003 — Invalid solutions are handled according to specification.
- Empty service set → −1e12 (ServiceGA, line 211–212).
- Fleet > 300 vessels → −1e9 (FrequencyGA, line 129–130).
- Non-list input → −1e12 (ServiceGA, line 201–202).
- Post-GA fleet prune deactivates lowest-efficiency services until fleet ≤ 300 (HierarchicalGA, lines 174–195).
- No soft constraint violations go unpenalized; every hard constraint has a lethal or explicit penalty path.
- Verified by: tests/test_ga.py fleet-rejection tests; tests/benchmark/test_math_validation.py V-9 fleet limit rule.

INV-GA-004 — Randomness is reproducible where a fixed seed is specified.
- random module is used directly (not numpy.random); random.seed() controls all stochastic operations.
- ServiceGA: _random_solution() uses random.randint and np.random.choice — NumPy uses its own internal RNG state, not the random module seed. Partial reproducibility: Python random is seeded but NumPy is not, so exact bitwise reproducibility across restarts is not guaranteed unless both seeds are set explicitly.
- FrequencyGA: _random_freq() uses random.randint only — fully reproducible with random.seed().
- Benchmark harness sets random_state=42 for KMeans; GA-level seeding is implicit through the caller.
- Verified by: tests/benchmark/test_seed_behavior.py checks determinism across repeated runs with the same seed.

## MILP / MATHEMATICAL OPTIMIZATION

### 16.1 Variables

| Variable | Type | Index | Meaning | File:Line |
|---|---|---|---|---|
| flow[(d, s)] | Continuous ≥ 0 | demand × compatible-service pairs | TEU of demand d served directly on service s | hub_milp.py:273–275 |
| transfer_flow[(d, s1, s2)] | Continuous ≥ 0 | demand × valid hub-pair triples | TEU of demand d served via transshipment (first leg s1, second leg s2) | hub_milp.py:277–286 |
| unserved[d] | Continuous ≥ 0 | all demands | TEU of demand d left unsatisfied | hub_milp.py:288–291 |

Services mask (services) and frequencies (frequencies) are fixed inputs from the GA chromosome, not decision variables.

---

### 16.2 Objective

MAXIMIZE  profit_expr + coverage_reward

| Term | Formula | Nature |
|---|---|---|
| revenue | Σ r_d × flow[(d,s)] + Σ r_d × transfer_flow[(d,s1,s2)] | Linear in variables |
| operating_cost | Σ_s weekly_cost_s × freq_s | Constant (pre-computed from GA chromosome) |
| fuel_cost | Σ_s fuel_cost_per_cycle_s × freq_s | Constant |
| transship_cost | Σ tc_per_teu × transfer_flow[(d,s1,s2)] | Linear in variables |
| port_handling_cost | Σ_p handling_cost_p × Σ_vars + variable_cost_p × Σ_vars + port_call_cost_p × num_services_at_p | Linear in variables + constant |
| unserved_penalty | α × Σ unserved[d] where α = $300/TEU | Linear in variables |
| profit_expr | revenue − operating_cost − fuel_cost − transship_cost − port_handling_cost − unserved_penalty | Combined |
| coverage_reward | (w_coverage / w_profit) × (Σ flow + Σ transfer) / total_demand × \|operating_cost + 1\| | Linear in variables (coefficients are constants) |

Net effect: a single linear objective function maximized by CBC.

---

### 16.3 Constraints

| # | Constraint | Formula | Type | File:Line |
|---|---|---|---|---|
| C1 | Demand conservation | Σ_s flow[(d,s)] + Σ_{s1,s2} transfer_flow[(d,s1,s2)] + unserved[d] = demand.weekly_teu ∀ d | Equality | hub_milp.py:393–401 |
| C2 | Fleet limit | Σ_s ceil(cycle_time_s × freq_s / 7) ≤ 300 | Inequality (constant, pre-checked) | hub_milp.py:389 |
| C3 | Service capacity | Σ_d flow[(d,s)] + Σ_{d,s1,s2:s∈{s1,s2}} transfer_flow[(d,s1,s2)] ≤ capacity_s × freq_s × (7/cycle_time_s) ∀ selected s | Inequality | hub_milp.py:412–419 |
| C4 | Port capacity | Σ flow variables passing through p ≤ port_capacity_map[p] ∀ ports p | Inequality | hub_milp.py:422 |
| C5 | Min coverage (conditional, currently inactive) | Σ flow + Σ transfer ≥ min_coverage × total_demand | Inequality | hub_milp.py:403–404 (skipped when min_coverage == 0.0) |

---

### 16.4 Variable Bounds

| Variable | Lower bound | Upper bound | Source |
|---|---|---|---|
| flow[(d, s)] | 0 (explicit lowBound=0) | demand[d].weekly_teu (implicit from C1) | hub_milp.py:275 |
| transfer_flow[(d, s1, s2)] | 0 (explicit lowBound=0) | demand[d].weekly_teu (implicit from C1) | hub_milp.py:285 |
| unserved[d] | 0 (explicit lowBound=0) | demand[d].weekly_teu (implicit from C1) | hub_milp.py:289 |

No upper-bound declarations are made explicitly; all are implicit via the demand-conservation equality (C1).

---

### Solver Status Table

| Solver Status | Required System Behavior |
|---|---|
| OPTIMAL | Return full solution dict: profit, coverage %, satisfied/unserved demand, direct & transshipment TEU, selected services with load/cost/revenue per service, vessel count |
| TIME LIMIT | Return best incumbent found (not guaranteed optimal); log warning; still compute and return economic metrics from incumbent |
| INFEASIBLE | Return empty result dict with status, profit=0, unserved_demand=total_demand; log error |
| UNBOUNDED | Cannot occur — all variables bounded by demand; treat as ERROR |
| ERROR | Catch exception, log error, return empty result dict (same shape as INFEASIBLE) |
| FEASIBLE | PuLP maps this to OPTIMAL; handle identically to OPTIMAL |
| UNKNOWN | Treat as ERROR — return empty result with status string |

## REGIONAL AGENTS

17.1 Purpose

Each RegionalAgent is a self-contained optimization unit that takes a geographically decomposed sub-problem and produces: (1) a selected set of services with flow assignments, (2) economic metrics (profit, coverage, cost), (3) an LLM-generated strategy explanation, and (4) a validated regional policy dict. Five agents run in parallel (ThreadPoolExecutor), one per KMeans cluster. Their outputs are merged globally by the Orchestrator.

17.2 Inputs

┌───────────────────┬────────────────────────────────┬────────────────────────────────────────────────────────────────────────────────────────┐
│       Input       │              Type              │                                         Source                                         │
├───────────────────┼────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ problem           │ Problem (regional sub-problem) │ RegionalSplitter.split() — ports, demands, services assigned to this region            │
├───────────────────┼────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ name              │ str                            │ "regional_asia", "regional_europe", etc.                                               │
├───────────────────┼────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ region            │ str                            │ Region label: Asia, Europe, Americas, Middle East, Africa                              │
├───────────────────┼────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ model             │ str                            │ Config.REGIONAL_MODEL — LLM model for strategy + explanation calls                     │
├───────────────────┼────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ maritime_features │ optional object                │ Attached by Orchestrator (IP-1); provides weather_speed_factor and congestion_override │
└───────────────────┴────────────────────────────────┴────────────────────────────────────────────────────────────────────────────────────────┘

17.3 Processing

Five sequential stages:

┌───────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┬───────────────────────────┐
│       Stage       │                                                    What happens                                                    │         File:Line         │
├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ 1. Strategy       │ Rule-based decision (A=hub-and-spoke if top-3 demand >35%, else C=hybrid) + LLM call with temperature 0.1;         │ regional_agent.py:196–241 │
│                   │ fallback text if no digits in response                                                                             │                           │
├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ 2. Service        │ Embeds ServiceGeneratorAgent → generates ~781 candidate services with region-prefixed IDs (asia_svc_001)           │ regional_agent.py:244–269 │
│ generation        │                                                                                                                    │                           │
├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ 3. Smart filter   │ Keeps only services covering a demand corridor and passing margin gate (capacity × 0.5 × 150) > weekly_cost;       │ regional_agent.py:144–163 │
│                   │ sorted by capacity/cost ratio, capped at max(400, num_ports)                                                       │                           │
├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ 4. HierarchicalGA │ ServiceGA (binary selection) → FrequencyGA (integer frequencies 1–3) → fleet-prune if >300 vessels; 55-second      │ regional_agent.py:278–301 │
│                   │ budget                                                                                                             │                           │
├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ 5. HubMILP per    │ Splits region into 5 hub-clusters via distance-based assignment; runs independent PuLP MILP per cluster with IP-3  │ regional_agent.py:304–387 │
│ cluster           │ port-capacity override; merges results by service ID (sum load/cost/revenue across clusters)                       │                           │
├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ 6. Aggregation    │ Sums profit/cost/fuel/transship/port across clusters; caps satisfied ≤ total_demand; computes coverage %           │ regional_agent.py:391–411 │
├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ 7. LLM            │ Structured prompt → verdict (Good/Moderate/Poor) + strengths + weaknesses + improvement actions; retries up to 2×; │ regional_agent.py:420–464 │
│ explanation       │  validity requires "Verdict:", "Strength", "Weakness", "Improvement" + 2+ digit numbers                            │                           │
├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ 8. Policy         │ Deterministic rule-based mapping from network metrics (density, top-3 share, margin) → {coverage_priority,         │                           │
│ derivation        │ profit_priority, min_service_margin, vessel_bias, hub_focus, corridor_focus}; validated via                        │ regional_agent.py:496–553 │
│                   │ validate_regional_policy()                                                                                         │                           │
├───────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────┤
│ 9. Actuation      │ Writes provider/model/latency/fallback status to actuation_ledger                                                  │ regional_agent.py:468–494 │
│ record            │                                                                                                                    │                           │
└───────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┴───────────────────────────┘

17.4 Outputs

{
    "agent":               str,              # e.g. "regional_asia"
    "region":              str,              # e.g. "Asia"
    "status":              str,              # "Optimal" / "Failed" / ...
    "services_generated":  int,              # 781 (production)
    "services_filtered":   int,              # 400 (production)
    "services_selected":   int,              # 103 (production)
    "weekly_profit":       float,            # USD
    "annual_profit":       float,            # USD (= weekly × 52)
    "operating_cost":      float,            # USD
    "fuel_cost":           float,            # USD
    "transship_cost":      float,            # USD
    "port_cost":           float,            # USD
    "total_cost":          float,            # USD
    "coverage_percent":    float,            # % [0,100]
    "satisfied_demand":    float,            # TEU/wk
    "unserved_demand":     float,            # TEU/wk
    "total_demand":        float,            # TEU/wk
    "profit_margin_pct":   float,            # %
    "profit_per_service":  float,            # USD/service
    "cost_per_service":    float,            # USD/service
    "uncovered_teu":       float,            # TEU/wk
    "hub_ports":           List[str],        # top-5 hub UNLocodes
    "archetype_params":    Dict,             # from ServiceGeneratorAgent
    "regional_policy":     Dict,             # validated policy dict
    "strategy":            str,              # LLM strategy text
    "explanation":         str,              # LLM explanation text
    "selected_services":   List[Dict],       # per-service economics (103 items)
    "elapsed_sec":         float,            # wall-clock time
    "llm_actuation":       Dict,             # provider/model/latency/fallback ledger
}

17.5 Regional Constraints

┌───────────────────────────┬──────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────┐
│        Constraint         │                           Enforcement                            │                               Detail                                │
├───────────────────────────┼──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ Services cover demand     │ _filter_services() line 152                                      │ covers = any(o in port_set and d in port_set for (o,d) in           │
│ corridors                 │                                                                  │ corridor_set)                                                       │
├───────────────────────────┼──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ Positive margin gate      │ _filter_services() line 153                                      │ (capacity × 0.5 × 150) > weekly_cost                                │
├───────────────────────────┼──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ Max services after filter │ _filter_services() line 159                                      │ min(len(kept), max(400, num_ports))                                 │
├───────────────────────────┼──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ Fleet ≤ 300 vessels       │ FrequencyGA early-reject (line 129) + HierarchicalGA post-prune  │ Greedy deactivation of lowest-efficiency services                   │
│                           │ (lines 174–195)                                                  │                                                                     │
├───────────────────────────┼──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ Frequency ∈ {0,1,2,3}     │ FrequencyGA structural (lines 16–17, 97, 232)                    │ Hard clamped                                                        │
├───────────────────────────┼──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ Port capacity (with       │ HubMILP constraint C4 (hub_milp.py:422)                          │ port_capacity_map[p] × congestion_factor if maritime features       │
│ congestion)               │                                                                  │ present                                                             │
├───────────────────────────┼──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ Demand conservation       │ RegionalSplitter assert (regional_splitter.py:87–91)             │ |global − Σregional| ≤ 1.0 TEU — raised as AssertionError if        │
│ (global)                  │                                                                  │ violated                                                            │
├───────────────────────────┼──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ Service ID uniqueness     │ Region prefix applied (regional_agent.py:268)                    │ f"{region.lower().replace(' ','_')}_svc_{idx:03d}" prevents         │
│                           │                                                                  │ cross-region collisions                                             │
└───────────────────────────┴──────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────┘

17.6 Regional Invariants

INV-REG-001 — Regional input is valid.
The input Problem must have non-empty ports, demands, and services. RegionalSplitter.split() guarantees this by construction from a valid global Problem. If problem.services is empty after filter, HierarchicalGA returns an empty chromosome gracefully (line 147–149). Verified by: tests/test_regional_agent_activation.py.

INV-REG-002 — Regional optimization respects regional constraints.
Fleet ≤ 300 is enforced both pre-check (−1e9 lethal in FrequencyGA) and post-hoc (greedy prune in HierarchicalGA). Port capacity is a hard MILP inequality. Service ID collision is prevented by region-prefixing. Verified by: V-9 fleet limit rule in benchmark/validation/mathematical_validator.py; tests/benchmark/test_data_integrity.py.

INV-REG-003 — Regional output conforms to the expected schema.
All 21 keys listed in §17.4 are present in every output dict. Numeric fields are finite floats (no NaN/inf). selected_services is a list of dicts each containing id, ports, load, capacity, vessel_class, vessel_cost, fuel_cost, port_cost, revenue, cost, weekly_profit, margin_pct, region. regional_policy always passes through validate_regional_policy(). Verified by: tests/test_regional_agent.py, tests/test_regional_agent_activation.py.

INV-REG-004 — Regional output reaches the required downstream component.
The dict returned by process() is collected by OrchestratorAgent.process() via ThreadPoolExecutor.map() and passed to: (1) CoordinatorAgent.process() for conflict detection and global metrics, (2) ConsensusEngine.process() for weight reconciliation, (3) iteration_results snapshot for Pareto selection. If a region raises an exception, the orchestrator logs the error and substitutes an empty-fallback result (zeroed metrics) so the pipeline continues. Verified by: tests/test_multi_agent_coordination.py.

## GLOBAL COORDINATION

18.1 Purpose

Orchestrate the end-to-end optimization pipeline: decompose the global problem into regional sub-problems, run 5 regional agents in parallel, reconcile their decisions via consensus, iterate up to 3 times with weight-feedback until convergence or budget exhaustion, then select the single best iteration via Pareto dominance + weighted scoring. The Orchestrator is the single entry point — nothing runs outside its process() method.

18.2 Inputs

┌─────────────────┬─────────────────────────┬───────────────────────────────────────────────────────────────┐
│      Input      │          Type           │                            Source                             │
├─────────────────┼─────────────────────────┼───────────────────────────────────────────────────────────────┤
│ problem         │ Problem (global)        │ NetworkLoader — all 333 ports, 9,622 demands, 1,219+ services │
├─────────────────┼─────────────────────────┼───────────────────────────────────────────────────────────────┤
│ n_clusters      │ int                     │ Derived: 3 if <50 ports, 5 otherwise                          │
├─────────────────┼─────────────────────────┼───────────────────────────────────────────────────────────────┤
│ regional_agents │ List[RegionalAgent] × 5 │ Hardcoded: Asia, Europe, Americas, Middle East, Africa        │
├─────────────────┼─────────────────────────┼───────────────────────────────────────────────────────────────┤
│ callback        │ Optional callable       │ Registered by backend for real-time WebSocket streaming       │
└─────────────────┴─────────────────────────┴───────────────────────────────────────────────────────────────┘

18.3 Processing

┌──────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┬───────────────────────────────┐
│ Step │                                                            Action                                                            │           File:Line           │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 1    │ Set objective mode + weights on Problem from CONFIG                                                                          │ orchestrator_agent.py:431–436 │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 2    │ Attach maritime features (weather + congestion) via dynamic import, gated on MARITIME_INTELLIGENCE_ENABLED                   │ Lines 438–490                 │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 3    │ Capture true_global_demand before any splitting                                                                              │ Line 503                      │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 4    │ KMeans cluster ports → clusters dict                                                                                         │ Lines 539–540                 │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 5    │ Assert: cluster count == n_clusters, all ports assigned                                                                      │ Lines 550–555                 │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 6    │ Loop for iteration in range(MAX_ITERATIONS=3):                                                                               │ Line 562                      │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 6a   │ Snapshot weights before iteration                                                                                            │ Lines 574–578                 │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 6b   │ RegionalSplitter.split(clusters) → regional Problems                                                                         │ Lines 587–588                 │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 6c   │ Assert: demand conservation |global − Σregional| < 10 TEU                                                                    │ Lines 591–598                 │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 6d   │ ThreadPoolExecutor(max_workers=n_clusters) → parallel regional_agent.process()                                               │ Lines 605–637                 │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 6e   │ Empty/failure results → zeroed fallback dict, logged error                                                                   │ Lines 638–648                 │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 6f   │ CoordinatorAgent.process(regional_results, iteration) → conflicts, global_metrics, feedback                                  │ Line 655                      │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 6g   │ ConsensusEngine.process(coordinator_decisions, regional_policies, archetype_params) → reconciled weights                     │ Line 664                      │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 6h   │ Update SharedContext (global_objectives, regional_priorities, hub_strategy)                                                  │ Lines 667–672                 │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 6i   │ Build deep-copied iteration snapshot → append to iteration_results                                                           │ Lines 675–678                 │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 6j   │ Termination check: budget_satisfied = (iteration+1) >= MIN_ITERATIONS; break if not feedback["needs_rerun"] AND              │ Lines 681–699                 │
│      │ budget_satisfied                                                                                                             │                               │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 6k   │ _apply_feedback(): write coordinator consensus weights onto problem.profit_weight/coverage_weight/cost_weight for next       │ Lines 337–409                 │
│      │ iteration                                                                                                                    │                               │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 7    │ Post-loop: IterationSelector.select(iteration_results) → Pareto + weighted scoring → best iteration index                    │ Line 708                      │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 8    │ Deep-copy selected iteration's regional_results, selected_services, decision_output as final                                 │ Lines 711–722                 │
├──────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────┤
│ 9    │ Aggregate final metrics, LLM summary, actuation ledger → return output dict                                                  │ Lines 725–760                 │
└──────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┴───────────────────────────────┘

18.4 Outputs

{
    "orchestrator":            str,              # "orchestrator"
    "status":                  str,              # "complete"
    "problem_analysis":        str,              # LLM/rule-based size analysis
    "regional_results":        List[Dict] × N,   # 5 regional agent outputs (final iteration only)
    "decision_output":         Dict,             # CoordinatorAgent output (final iteration)
    "executive_summary":       str,              # Human-readable verdict
    "summary_metrics":         Dict,             # 14-key aggregate: profit, cost, coverage, etc.
    "iteration_audit":         List[Dict] × 3,   # Per-iteration weight/feedback snapshot
    "iterations_run":          int,              # 3 (production)
    "selected_services":       List[Dict],       # Final service-level economics (497 items)
    "iteration_results":       List[Dict] × 3,   # Full snapshots of all iterations
    "iteration_selection":     Dict,             # Pareto + weighted + optional LLM selection rationale
    "best_iteration":          int,              # Index of selected iteration (0,1, or 2)
    "final_selected_iteration":int,              # Same as best_iteration
    "health_status":           Dict,             # Runtime health: regions completed/failed
    "consensus_result":        Dict,             # Weighted-reconciled policy
    "shared_context":          Dict,             # Final global objectives + regional priorities
    "llm_runtime_aggregate":   Dict,             # Provider telemetry + actuation ledger
    "test_scorecard":          Dict,             # Assertion pass/fail summary
}

18.5 Global Rules

┌─────────────────────────────────────┬─────────────────────────────────────────────────────────────────────┬────────────────────────────────────────────────────────┐
│                Rule                 │                             Enforcement                             │                         Detail                         │
├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────┤
│ Mandatory 3-iteration budget        │ MAX_ITERATIONS = MIN_ITERATIONS = 3 (hardcoded, lines 27–28)        │ Early convergence suppressed until iteration 2         │
│                                     │                                                                     │ completes                                              │
├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────┤
│ Demand conservation                 │ assert abs(global − Σregional) < 10.0 (line 597)                    │ Raises AssertionError on violation                     │
├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────┤
│ All ports clustered                 │ assert total_clustered_ports == len(problem.ports) (line 555)       │ Ensures no orphan port                                 │
├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────┤
│ Sufficient regional agents          │ assert len(regional_agents) >= n_clusters (line 511)                │ Guards against misconfiguration                        │
├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────┤
│ Feedback weights persist            │ _apply_feedback() mutates problem.weights in-place (line 409)       │ Next iteration uses reconciled weights                 │
├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────┤
│ Selected iteration is deep-copied   │ copy.deepcopy() on regional_results, selected_services (lines       │ Prevents mutation of audit trail                       │
│                                     │ 711–722)                                                            │                                                        │
├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────┤
│ Iteration selection authoritative   │ best_iter = det_iter (deterministic wins over LLM advisory)         │ iteration_selection.py:535–537                         │
├─────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────┤
│ Empty/failed region → zeroed        │ Catch-all in regional result collection (lines 638–648)             │ Pipeline never blocks on one failed region             │
│ fallback                            │                                                                     │                                                        │
└─────────────────────────────────────┴─────────────────────────────────────────────────────────────────────┴────────────────────────────────────────────────────────┘

18.6 Global Invariants

INV-GLOB-001 — All required regional outputs are considered.
Every regional agent's result is collected regardless of success/failure. Failed regions produce a zeroed fallback dict (profit=0, coverage=0, selected_services=[]) and are included in aggregation. No region is skipped or ignored. Verified by: tests/test_multi_agent_coordination.py.

INV-GLOB-002 — Global decisions satisfy global constraints.
Fleet ≤ 300 is enforced per-region (FrequencyGA early-reject + post-GA prune) and the sum across regions is checked implicitly by the coordinator's evaluation rubric. Coverage target (70%) is a soft KPI, not a hard constraint — the coordinator flags low coverage in feedback but does not block pipeline completion. Conflict count is tracked but does not block selection. Verified by: V-9 fleet limit rule; coordinator_agent._evaluate_system() rubric.

INV-GLOB-003 — Regional outputs are not silently discarded.
All 5 regional result dicts are stored in iteration_results[i]["regional_results"] as deep copies. The iteration_audit log records which iteration each regional result belongs to. Even failed regions (with zeroed fallback) appear in the audit trail with status="Failed" and an error note. Verified by: iteration_audit structure in pipeline_output.json.

INV-GLOB-004 — Global decisions are traceable to their inputs.
Every iteration snapshot contains: the weights used at that iteration, the full regional results, the coordinator's conflict list and weight adjustments, the consensus engine's reconciled policy, and the LLM actuation ledger (provider/model/latency/fallback for every LLM call). The iteration_selection dict records the Pareto-frontier membership and weighted score for every candidate iteration, making it auditable why iteration N was chosen over M. Verified by: tests/benchmark/test_provenance.py, llm_runtime_aggregate.actuation_ledger in output.

19. CONSENSUS

19.1 Purpose

Reconcile three potentially conflicting policy proposals (Coordinator's weight adjustments, each Region's priorities, Service Generator's archetype plan) into a single unified policy dict that drives the next iteration's optimization weights and service design mix. Also computes a confidence score that determines whether the consensus is trusted or replaced by DEFAULT_CONSENSUS.

19.2 Inputs

┌──────────────────────────┬────────────────────────────────────────────────────────────┬────────────────────────────────────────────────────────────┐
│          Input           │                            Type                            │                           Source                           │
├──────────────────────────┼────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
│ coordinator_decisions    │ Dict — {weight_adjustments: {profit, coverage, cost}, ...} │ CoordinatorAgent._generate_decisions()                     │
├──────────────────────────┼────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
│ regional_policies        │ Dict[str, Dict] — one per region                           │ Each RegionalAgent.regional_policy                         │
├──────────────────────────┼────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
│ service_archetype_params │ Dict — archetype_mix + vessel_bias                         │ ServiceGeneratorAgent archetype output                     │
├──────────────────────────┼────────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
│ previous_consensus       │ Optional Dict                                              │ Last iteration's consensus_result (weight 0.10 if present) │
└──────────────────────────┴────────────────────────────────────────────────────────────┴────────────────────────────────────────────────────────────┘

19.3 Calculation

Step 1 — Validate inputs: All three inputs pass through their respective validators (weight_validator, regional_policy_validator, archetype_validator). Invalid inputs are clamped/falled back.

Step 2 — Detect conflicts (three types):

┌────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│      Conflict      │                                                        Condition                                                         │
├────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Weight disparity   │ coordinator profit_weight > 0.60 AND any region coverage_priority > 0.70                                                 │
├────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Archetype mismatch │ svc_gen feeder_ratio > 0.40 AND any region vessel_bias="large"; OR direct_ratio > 0.5 AND any region vessel_bias="small" │
├────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Hub conflict       │ svc_gen hub_focus ∩ region hub_focus = ∅ OR partial overlap with exclusive hubs on both sides                            │
└────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

Step 3 — Reconcile via weighted voting:

reconciled_profit_weight = Σ(v_i × w_i) / Σ(w_i)
where voters are: coordinator (w=0.40), each region (w=0.40/N_regions each), svc_gen (w=0.20), previous_consensus (w=0.10, deducted proportionally)

Same formula applied independently to: coverage_weight, cost_weight, direct_ratio, hub_loop_ratio, feeder_ratio, trunk_ratio, hub_focus (accumulated support, threshold = max(0.30, max_support/2)).

Step 4 — Confidence score:
confidence = 1.0
for each conflict detected:       confidence -= 0.15
for each unresolved conflict:     confidence -= 0.25
if num_regions > 0:              confidence += 0.05
confidence = clamp(confidence, 0.0, 1.0)

Step 5 — State classification:

┌────────────────────┬──────────────────────────┬─────────────────────────────────────┐
│       State        │        Threshold         │               Action                │
├────────────────────┼──────────────────────────┼─────────────────────────────────────┤
│ CONSENSUS_ACCEPTED │ confidence > 0.70        │ Use reconciled policy               │
├────────────────────┼──────────────────────────┼─────────────────────────────────────┤
│ CONSENSUS_MODIFIED │ 0.30 ≤ confidence ≤ 0.70 │ Use reconciled policy with notes    │
├────────────────────┼──────────────────────────┼─────────────────────────────────────┤
│ CONSENSUS_REJECTED │ confidence < 0.30        │ Return DEFAULT_CONSENSUS (fallback) │
└────────────────────┴──────────────────────────┴─────────────────────────────────────┘

19.4 Outputs

{
    "final_weight_adjustments": {
        "profit_weight": float,    # e.g. 0.408
        "coverage_weight": float,  # e.g. 0.486
        "cost_weight": float       # e.g. 0.106
    },
    "final_archetype_params": {
        "archetype_mix": {"direct_ratio": 0.47, "hub_loop_ratio": 0.16, "feeder_ratio": 0.30, "trunk_ratio": 0.07},
        "vessel_bias": str,
        "hub_focus": List[str],
        "notes": str
    },
    "confidence_score": float,     # e.g. 1.0 (production run: no conflicts)
    "conflicts_resolved": List[Dict],
    "conflicts_remaining": List[Dict],
    "notes": str
}

19.5 Conflict Handling

Each detected conflict is tagged "resolved": True/False after reconciliation. Resolved conflicts are moved to conflicts_resolved; unresolved stay in conflicts_remaining. Unresolved conflicts lower confidence but do not block output — only confidence < 0.30 triggers the hard fallback to DEFAULT_CONSENSUS.

19.6 Downstream Consumer

OrchestratorAgent._apply_feedback() (line 337–409) reads consensus_result.final_weight_adjustments and writes them onto problem.profit_weight, problem.coverage_weight, problem.cost_weight for the next iteration. final_archetype_params feeds back into the next iteration's ServiceGeneratorAgent call via SharedContext.

19.7 Consensus Invariants

INV-CONS-001 — Consensus inputs are valid.
All three input dicts pass through validators before any conflict detection. Invalid input is never processed — it is clamped/fallback-first. Verified by: tests/test_multi_agent_coordination.py test_all_validators_pass_on_output.

INV-CONS-002 — Consensus calculation follows its defined mathematical rule.
Weighted voting uses the exact formula Σ(v_i × w_i) / Σ(w_i) with hardcoded voter weights (Coordinator=0.40, Regional=0.40/N, SvcGen=0.20, Previous=0.10). Confidence math is 1.0 − 0.15×conflicts − 0.25×unresolved + 0.05×has_regions, clamped to [0,1]. Verified by: tests/test_multi_agent_coordination.py test_confidence_math_with_unresolved, test_confidence_high_when_aligned.

INV-CONS-003 — Consensus output conforms to the expected schema.
Output always contains exactly the 6 keys: final_weight_adjustments, final_archetype_params, confidence_score, conflicts_resolved, conflicts_remaining, notes. Weights always sum to 1.0 (validator enforces). Verified by: tests/test_multi_agent_coordination.py test_weight_sum_to_one.

INV-CONS-004 — Consensus output actually influences the intended downstream behavior.
In every iteration, _apply_feedback() reads consensus_result.final_weight_adjustments and mutates problem.profit_weight/coverage_weight/cost_weight. Production run confirmed: iter 0 weights {0.5, 0.4, 0.1} → iter 1 weights changed per consensus → iter 2 weights changed again. The actuation ledger shows coordinator LLM calls are consumed (decision_consumed=True). Verified by: pipeline_output.json iteration_audit weights_used field across 3 iterations; tests/test_multi_agent_coordination.py test_previous_consensus_influence.

---

20. SHARED CONTEXT

20.1 Purpose

Hold the single source of truth for inter-agent policy state across iterations — global objective weights, per-region priority vectors, the approved archetype mix, and the derived hub strategy. Rebuilt fresh each iteration from current regional results; never persisted between iterations.

20.2 Context Fields

┌─────────────────────────────────────┬────────────────────────────────────────────────┬────────────────────────────────────────────┬───────────────────────────────┐
│                Field                │                    Meaning                     │                  Producer                  │           Consumer            │
├─────────────────────────────────────┼────────────────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────┤
│ global_objectives.profit_weight     │ Optimizer profit coefficient for next          │ CoordinatorAgent → ConsensusEngine         │ HierarchicalGA (via           │
│                                     │ iteration                                      │                                            │ problem.profit_weight)        │
├─────────────────────────────────────┼────────────────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────┤
│ global_objectives.coverage_weight   │ Optimizer coverage coefficient                 │ CoordinatorAgent → ConsensusEngine         │ HierarchicalGA                │
├─────────────────────────────────────┼────────────────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────┤
│ global_objectives.cost_weight       │ Optimizer cost coefficient                     │ CoordinatorAgent → ConsensusEngine         │ HierarchicalGA                │
├─────────────────────────────────────┼────────────────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────┤
│ global_objectives.iteration         │ Current iteration index                        │ Orchestrator                               │ Logging, audit                │
├─────────────────────────────────────┼────────────────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────┤
│ global_objectives.coverage_target   │ Minimum coverage KPI (70%)                     │ CONFIG default                             │ Coordinator evaluation rubric │
├─────────────────────────────────────┼────────────────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────┤
│ global_objectives.convergence_score │ How close to stable                            │ CoordinatorAgent                           │ IterationSelector             │
├─────────────────────────────────────┼────────────────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────┤
│                                     │ Per-region {coverage_priority,                 │ Each RegionalAgent → ConsensusEngine →     │ ConsensusEngine voting;       │
│ regional_priorities.<name>          │ profit_priority, hub_focus, vessel_bias,       │ SharedContext                              │ orchestrator audit            │
│                                     │ min_service_margin}                            │                                            │                               │
├─────────────────────────────────────┼────────────────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────┤
│ service_archetype_plan              │ Approved mix {direct_ratio, hub_loop_ratio,    │ ServiceGeneratorAgent → ConsensusEngine →  │ Next iteration's              │
│                                     │ feeder_ratio, trunk_ratio, vessel_bias}        │ SharedContext                              │ ServiceGeneratorAgent         │
├─────────────────────────────────────┼────────────────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────┤
│ hub_strategy.primary_hubs           │ Ports recommended by ≥2 regions                │ SharedContext.update_hub_strategy()        │ Coordinator conflict          │
│                                     │                                                │                                            │ detection                     │
├─────────────────────────────────────┼────────────────────────────────────────────────┼────────────────────────────────────────────┼───────────────────────────────┤
│ hub_strategy.recommended_hubs       │ Per-region hub recommendations                 │ SharedContext.update_hub_strategy()        │ Audit trail                   │
└─────────────────────────────────────┴────────────────────────────────────────────────┴────────────────────────────────────────────┴───────────────────────────────┘

20.3 Context Lifecycle

Start of iteration N
    ↓
RegionalAgents complete → return regional_policy dicts
    ↓
CoordinatorAgent computes global_metrics + weight_adjustments
    ↓
ConsensusEngine.process() → reconciles all inputs
    ↓
SharedContext rebuilt: global_objectives ← consensus weights,
                       regional_priorities ← each region's policy,
                       service_archetype_plan ← consensus archetype,
                       hub_strategy ← update_hub_strategy()
    ↓
_next iteration's problem.weights ← SharedContext.global_objectives (via _apply_feedback)
Context is rebuilt every iteration — never carried forward as mutable state between loop iterations except through _apply_feedback() writing weights onto the Problem object.

20.4 Update Rules

- global_objectives updated from ConsensusEngine final_weight_adjustments only
- regional_priorities replaced wholesale from current iteration's regional results
- service_archetype_plan updated from ConsensusEngine final_archetype_params.archetype_mix only
- hub_strategy recomputed deterministically from regional_priorities via update_hub_strategy() (hubs appearing in ≥2 regions become primary_hubs)
- No field is partially updated — each is replaced atomically at the end of consensus processing

20.5 Shared Context Invariants

INV-CTX-001 — Required fields exist before consumption.
Before _apply_feedback() runs, ConsensusEngine has already produced final_weight_adjustments with all three weights. Before ServiceGeneratorAgent runs in iteration N+1, service_archetype_plan is populated. Verified by: orchestrator code path order (consensus always precedes feedback application).

INV-CTX-002 — Context values have defined semantics.
All floats are in [0, 1]; weights sum to exactly 1.0 (enforced by weight_validator). vessel_bias is enum {"small", "balanced", "large"}. hub_focus entries are validated against problem.ports. Verified by: validator functions in weight_validator.py, archetype_validator.py, regional_policy_validator.py.

INV-CTX-003 — Context reaches every required consumer.
Global weights reach HierarchicalGA via problem.weight attributes (set in _apply_feedback). Regional priorities reach ConsensusEngine as input. Archetype plan reaches ServiceGeneratorAgent via SharedContext passed as input_data. Verified by: tests/test_multi_agent_coordination.py test_service_archetype_plan_aggregation.

INV-CTX-004 — Context updates occur at the correct stage.
Context is built after consensus (step 6g in §18.3) and before feedback application (step 6k). It is never modified during regional agent execution or coordinator processing. Verified by: orchestrator loop ordering in orchestrator_agent.py:655–699.

INV-CTX-005 — Context information actually influences intended behavior.
Production run confirmed: iter 0 weights {0.50, 0.40, 0.10} → consensus produced {0.408, 0.486, 0.106} → iter 1 used those weights → iter 2 further adjusted. The iteration_audit weights_used field shows different weight sets per iteration. Verified by: pipeline_output.json iteration_audit[0..2].weights_used.

---

21. ITERATIVE OPTIMIZATION

21.1 Iteration Flow

Iteration N
    ↓
[Decompose: RegionalSplitter splits Problem → N regional sub-Problems]
    ↓
[Parallel Regional Optimization: N RegionalAgents run simultaneously
   each running: ServiceGen → SmartFilter → HierarchicalGA → HubMILP×clusters → Policy]
    ↓
[Aggregate: Orchestrator sums regional profits/costs/coverage; asserts demand conservation]
    ↓
[Coordinator: conflict detection + weight adjustment proposal + convergence scoring]
    ↓
[Consensus: weighted voting reconciles coordinator + regions + svc_gen → final weights]
    ↓
[Snapshot: deep-copied iteration result appended to iteration_results list]
    ↓
[Evaluation: budget_satisfied=(N+1≥MIN_ITERATIONS) AND not needs_rerun? break → next]
    ↓
[Feedback: _apply_feedback writes consensus weights onto Problem for next iteration]
    ↓
Iteration N+1

21.2 Iteration Inputs

┌──────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────┐
│                              Input                               │                               Source                                │
├──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ problem with current profit_weight, coverage_weight, cost_weight │ Previous iteration's _apply_feedback() or initial CONFIG weights    │
├──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ clusters (port→region mapping)                                   │ Fixed from initial PortClustering; never recomputed                 │
├──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ shared_context                                                   │ Rebuilt from prior iteration's consensus                            │
├──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
│ previous_consensus                                               │ Last iteration's consensus_result (provides 0.10 continuity weight) │
└──────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────┘

21.3 Iteration Outputs

┌────────────────────┬────────────────────────────────────────────────────────────────────────────────────────┐
│       Output       │                                        Content                                         │
├────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ regional_results   │ List of 5 regional agent output dicts (profit, coverage, selected_services per region) │
├────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ decision_output    │ CoordinatorAgent output (global_metrics, conflicts, weight_adjustments, feedback)      │
├────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ consensus_result   │ ConsensusEngine output (reconciled weights, archetype, confidence)                     │
├────────────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ iteration_snapshot │ Deep-copied dict stored in iteration_results[N] with all fields above + weights_used   │
└────────────────────┴────────────────────────────────────────────────────────────────────────────────────────┘

21.4 Feedback Mechanism

CoordinatorAgent._generate_feedback_signals() produces a dict with:
{
    "needs_rerun": bool,           # True if coverage_gap>0 OR profit_gap>0 OR conflicts>0
    "rerun_reason": str,           # Human-readable explanation
    "coverage_gap": float,         # coverage_target - average_regional_coverage
    "profit_gap": float,           # max(0, profit_floor - total_profit)
    "conflict_severity": int,      # number of unresolved conflicts
    "weight_adjustments": {...},   # proposed new weights (validated)
    "convergence_score": float,    # [0,1] how close to stable
}
needs_rerun=False when all three gaps are zero AND conflicts are zero. But convergence is suppressed until iteration + 1 >= MIN_ITERATIONS (mandatory 3-iteration budget).

21.5 Update Mechanism

OrchestratorAgent._apply_feedback(problem, decision_output, consensus_weights):
if consensus_weights:
    problem.profit_weight   = consensus_weights["profit_weight"]
    problem.coverage_weight = consensus_weights["coverage_weight"]
    problem.cost_weight     = consensus_weights["cost_weight"]
elif decision_output.get("weight_adjustments"):
    problem.profit_weight   = decision_output["weight_adjustments"]["profit_weight"]
    ...
# Exploration factor bumped +10% each iteration
problem.exploration_factor = getattr(problem, "exploration_factor", 1.0) * 1.10

21.6 Termination

Two conditions, both must be met:
1. budget_satisfied = (iteration + 1) >= MIN_ITERATIONS (i.e., at least 3 iterations completed)
2. not feedback["needs_rerun"] (no coverage gap, no profit gap, no conflicts)

If needs_rerun=True but budget is satisfied → loop continues to exhaust the 3-iteration cap with at_iteration_cap flag set. If needs_rerun=False and budget satisfied → break.

Post-loop: IterationSelector.select(iteration_results) evaluates all 3 snapshots; deterministic Pareto + weighted scoring picks the best.

21.7 Iteration Invariants

INV-ITER-001 — Iteration N+1 receives required information from iteration N.
Each iteration receives: the Problem object (with updated weights from _apply_feedback), the fixed cluster assignment, and the previous consensus as previous_consensus. Verified by: orchestrator loop structure lines 562–699.

INV-ITER-002 — Feedback is actually consumed.
Production run: iteration_audit[0].weights_used = {0.5, 0.4, 0.1}, iteration_audit[1].weights_used differs, iteration_audit[2].weights_used differs again. Coordinator LLM actuation shows decision_consumed=True on all 3 iterations. Verified by: pipeline_output.json iteration_audit field.

INV-ITER-003 — The iteration loop terminates correctly.
MAX_ITERATIONS = MIN_ITERATIONS = 3 guarantees exactly 3 iterations run regardless of convergence. Post-loop IterationSelector always receives a non-empty list. Verified by: tests/test_multi_agent_coordination.py and production run showing iterations_run=3.

INV-ITER-004 — The reported iteration count is accurate.
iterations_run in output equals the number of times the loop body executed. In production: iterations_run=3, iteration_audit has 3 entries, iteration_results has 3 entries. Verified by: pipeline_output.json.

---

22. LLM / AI COMPONENTS

Component Inventory

┌──────────────────────────┬─────────────────────┬─────────────────────────────────┬─────────────────────────────────────────────────────┬──────────────────────────┐
│        Component         │        Input        │             Output              │                     Validation                      │    Downstream Effect     │
├──────────────────────────┼─────────────────────┼─────────────────────────────────┼─────────────────────────────────────────────────────┼──────────────────────────┤
│                          │                     │ JSON with direct_ratio,         │ validate_archetype_params() — clamps ratios to      │ Shapes candidate service │
│ ServiceGeneratorAgent    │ Problem stats +     │ hub_loop_ratio, feeder_ratio,   │ [0.05, 0.80], normalizes sum to 1.0, validates      │  pool composition (Phase │
│ (LLM call)               │ archetype prompt    │ trunk_ratio, vessel_bias,       │ vessel_bias enum, filters hub_focus to valid port   │  A/B/C/D counts)         │
│                          │                     │ hub_focus                       │ IDs                                                 │                          │
├──────────────────────────┼─────────────────────┼─────────────────────────────────┼─────────────────────────────────────────────────────┼──────────────────────────┤
│ CoordinatorAgent (LLM    │ Regional solutions  │ JSON with weight_adjustments    │ validate_weight_adjustments() — clamps each weight  │ Proposes weight changes  │
│ call)                    │ + iteration counter │ {profit, coverage, cost},       │ to [0.05, 0.90], normalizes sum to 1.0, up to 5     │ applied to next          │
│                          │                     │ actions, priorities             │ passes                                              │ iteration's Problem      │
├──────────────────────────┼─────────────────────┼─────────────────────────────────┼─────────────────────────────────────────────────────┼──────────────────────────┤
│                          │ Regional stats      │                                 │                                                     │ Determines high-level    │
│ RegionalAgent (strategy  │ (ports, lanes,      │ Text: Strategy A/B/C + Selected │ is_valid_explanation() — requires digits +          │ approach; does NOT       │
│ LLM call)                │ median demand,      │  type + Reasons                 │ structured format; fallback rule-based if invalid   │ affect optimization math │
│                          │ top-3 share)        │                                 │                                                     │                          │
├──────────────────────────┼─────────────────────┼─────────────────────────────────┼─────────────────────────────────────────────────────┼──────────────────────────┤
│                          │ Solver results      │ Text: Verdict + Strengths +     │ Requires "Verdict:", "Strength", "Weakness",        │ Purely narrative;        │
│ RegionalAgent            │ (profit, cost,      │ Weaknesses + Improvement        │ "Improvement" + 2+ digit number; retry 2× then      │ appears in output but    │
│ (explanation LLM call)   │ coverage, margins)  │ Actions                         │ fallback                                            │ does NOT influence       │
│                          │                     │                                 │                                                     │ optimization             │
├──────────────────────────┼─────────────────────┼─────────────────────────────────┼─────────────────────────────────────────────────────┼──────────────────────────┤
│                          │                     │                                 │ Deterministic winner is authoritative; LLM          │ LLM provides reasoning   │
│ IterationSelector (LLM   │ All scorecards +    │ JSON with selected_iteration    │ selection is accepted only if it matches the        │ text only; cannot        │
│ call, optional)          │ iteration metrics   │ index, confidence, reasoning    │ deterministic choice; otherwise rejected with       │ override deterministic   │
│                          │                     │                                 │ warning                                             │ selection                │
└──────────────────────────┴─────────────────────┴─────────────────────────────────┴─────────────────────────────────────────────────────┴──────────────────────────┘

22.1 AI Output Schema

┌────────────────────┬───────────────────────────────────────────────────────────────────────────────────────────┬───────────────────────────────────────────────────┐
│     Component      │                                      Expected Schema                                      │                   Parse Method                    │
├────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│                    │ {"direct_ratio": <float>, "hub_loop_ratio": <float>, "feeder_ratio": <float>,             │ _parse_json_safe() — strips markdown fences,      │
│ ServiceGenerator   │ "trunk_ratio": <float>, "vessel_bias": "small"|"balanced"|"large", "hub_focus": [<str>,   │ regex-extracts first {...} block                  │
│                    │ ...]}                                                                                     │                                                   │
├────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ Coordinator        │ {"weight_adjustments": {"profit_weight": <float>, "coverage_weight": <float>,             │ Same parser; then validate_weight_adjustments()   │
│                    │ "cost_weight": <float>}, "actions": [...], "priorities": [...]}                           │ clamps + normalizes                               │
├────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ Regional strategy  │ Plain text with Strategy: <A|B|C>, Selected: <...>, Reason 1:, Reason 2:, Hub Ports:      │ String parsing; fallback to rule-based if no      │
│                    │ [...]                                                                                     │ digits found                                      │
├────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ Regional           │ Plain text with Verdict:, Strengths:, Weaknesses:, Improvement Actions:                   │ Keyword search; retry 2× then hardcoded fallback  │
│ explanation        │                                                                                           │                                                   │
├────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────┼───────────────────────────────────────────────────┤
│ IterationSelector  │ {"selected_iteration": <int>, "confidence": <float>, "reasoning": <str>}                  │ JSON parse; cross-checked against deterministic   │
│                    │                                                                                           │ winner                                            │
└────────────────────┴───────────────────────────────────────────────────────────────────────────────────────────┴───────────────────────────────────────────────────┘

22.2 AI Validation

Required flow (applies to all structured JSON outputs):
AI Output (raw string)
    ↓
Parsing (_parse_json_safe: strip fences, regex extract first {...})
    ↓
Schema Validation (validate_*: clamp ranges, normalize sums, enum check)
    ↓
Domain Validation (hub_focus ⊆ valid_port_ids, ratios sum ≈ 1.0)
    ↓
Accept → use validated dict
Reject → use DEFAULT_* fallback

Project-specific validation:
- Weight adjustments: each weight ∈ [0.05, 0.90], sum normalized to 1.0 via iterative bound-respecting redistribution (max 5 passes), fallback to {0.50, 0.40, 0.10}
- Archetype params: each ratio ∈ [0.05, 0.80], sum normalized to 1.0 (last bucket absorbs remainder), vessel_bias ∈ {"small","balanced","large"}, hub_focus filtered to valid IDs
- Regional policy v2: anti-neutral check (0.5/0.5/balanced/[] rejected without evidence), cov+prof ≈ 1.0 (tolerance 0.4), vessel_bias sanity vs median_lane_volume, baseline drift Euclidean distance > 0.6 without citation → fallback

22.3 AI Failure Behavior

┌────────────────────────────────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│              Failure Mode              │                                                         Behavior                                                          │
├────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Valid output                           │ Used as-is after validation; flows to downstream consumer                                                                 │
├────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Invalid output (bad JSON, missing      │ Parser returns {} → validate_* returns DEFAULT_* → fallback values used                                                   │
│ required fields)                       │                                                                                                                           │
├────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Malformed JSON                         │ _parse_json_safe() strips markdown fences, tries regex {...} extraction; on failure returns {}                            │
├────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Missing fields                         │ Validator fills missing fields from defaults (e.g., missing vessel_bias → "balanced")                                     │
├────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ API failure (provider returns error)   │ Router returns ErrorType.AUTH/INVALID_MODEL/UNKNOWN → provider switched or hard fallback "Service temporarily             │
│                                        │ unavailable..." → agent uses rule-based fallback                                                                          │
├────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Timeout                                │ Catch Exception in agent's LLM call block → rule-based fallback text used                                                 │
├────────────────────────────────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Model unavailable                      │ Health check marks provider as unreachable → router skips to next provider in order → if all fail → deterministic         │
│                                        │ fallback                                                                                                                  │
└────────────────────────────────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

22.4 AI Invariants

INV-AI-001 — Invalid AI output cannot silently become a production decision.
Every LLM code path has an explicit except Exception block with a deterministic fallback. The decision_source field in the actuation ledger is set to "rule-based" whenever a fallback is used, making silent AI decisions impossible. Verified by: src/llm/actuation.py — decision_consumed is only True when the source is valid LLM output.

INV-AI-002 — AI-generated parameters are validated before use.
validate_weight_adjustments(), validate_archetype_params(), and validate_regional_policy() are called on every LLM output before the result is written to SharedContext or applied to Problem weights. Invalid values are clamped/fallback — never passed through raw. Verified by: tests/test_provider_system/, tests/test_multi_agent_coordination.py.

INV-AI-003 — Fallback behavior is explicitly defined.
Five tiers of fallback are defined and documented: (1) JSON parse failure → {}, (2) validator clamp/fallback → DEFAULT_*, (3) API error → next provider, (4) all providers fail → hard fallback string, (5) rule-based heuristic fallback with documented decision logic. Each tier's trigger condition and output are specified in code comments. Verified by: actuation ledger fallback_uses counter tracks every fallback event.

INV-AI-004 — Claimed AI influence on downstream optimization is demonstrable.
The actuation ledger records per-component: decision_source (llm vs rule-based), decision_consumed (True/False), fallback_uses count, provider, model, latency. Production run confirms: coordinator iter 0 used LLM (consumed), iter 1 used rule-based fallback (1 fallback), iter 2 used LLM (consumed); all regional agents except Middle East used fallback. The weight changes across iterations are measurable in iteration_audit[].weights_used. Verified by: pipeline_output.json llm_runtime_aggregate.actuation_ledger.

---

23. FINAL CANDIDATE SELECTION

23.1 Candidate Filtering

All 3 iteration snapshots enter the candidate pool. An iteration is marked "invalid" (excluded from ranking) if: status != "completed" OR metrics is not a dict OR regional_results is empty OR selected_services is empty. In production, all 3 iterations have status "completed" with valid data — all 3 remain candidates. Verified by: iteration_selection.py:202–209.

23.2 Feasibility Filtering

No feasibility filter is applied at selection time — feasibility was already enforced during regional optimization (MILP constraints, fleet prunes, GA lethal penalties). The selector trusts that iteration_results only contains successfully completed iterations.

23.3 Ranking

Multi-objective normalization: Each metric is min-max normalized to [0,1] across all candidates. Flat series (all candidates equal) normalizes to 1.0. Direction-aware: higher-better metrics (profit, coverage) use (v-min)/(max-min); lower-better metrics (cost, unserved) use (max-v)/(max-min).

Rank assignment: Each candidate gets a rank (1=best) for each of 4 objectives: weekly_profit (higher better), global_demand_weighted_coverage (higher better), operating_cost (lower better), profit_margin_pct (higher better).

Pareto dominance: Candidate A dominates B if A is ≥ B on all 7 Pareto objectives AND strictly > on at least one:
PARETO_OBJECTIVES = [
    "weekly_profit",               # higher better (+1)
    "global_demand_weighted_coverage",  # higher better (+1)
    "operating_cost",              # lower better (-1)
    "unserved_demand",             # lower better (-1)
    "negative_profit_regions",     # lower better (-1)
    "constraint_violations",       # lower better (-1)
    "conflict_count",              # lower better (-1)
]

Overall score: Weighted sum of normalized objectives:
score = 0.60 × norm(profit) + 0.25 × norm(coverage) + 0.15 × norm(cost_inverse)

23.4 Tie Breaking

Tie-breakers applied in order to the deterministic winner candidate:
1. weekly_profit (higher better)
2. global_demand_weighted_coverage (higher better)
3. operating_cost (lower better)
4. profit_margin_pct (higher better)
5. unserved_demand (lower better)
If still tied after all tie-breakers, the lowest iteration index wins (earliest = most conservative).

23.5 Final Selection Rule

# Step 1: Deterministic selection (authoritative)
det_iter, det_method = self.deterministic_select(scorecards)

# Step 2: Optional LLM enrichment (cannot override)
llm_iter, llm_reasoning = self.llm_select(scorecards, iteration_results)

# Step 3: Cross-check
if llm_iter is not None and llm_iter != det_iter:
    # LLM chose differently — log warning, keep deterministic
    logger.warning("llm_vs_deterministic_mismatch ...")

best_iter = det_iter  # ← deterministic ALWAYS wins
best_method = "deterministic_multi_objective"
The LLM's role is purely advisory: it provides confidence, reasoning, and tradeoffs text. The actual selected iteration is always the deterministic winner.

23.6 Selection Invariants

INV-SEL-001 — Infeasible candidates cannot become final feasible solutions.
Only iterations with status == "completed" and non-empty selected_services enter the candidate pool. Failed iterations (MILP infeasible, GA crash) produce zeroed fallback results but still enter — however they receive the worst possible scores (profit=0, unserved=total_demand) and are dominated by any valid iteration. In production, all 3 iterations were feasible. Verified by: iteration_selection.py:202–209 validity check.

INV-SEL-002 — Ranking follows the defined objective.
The scoring uses DEFAULT_SCORING_WEIGHTS = {profit: 0.60, coverage: 0.25, cost: 0.15} with min-max normalization per objective across the candidate set only. Directions are correct: profit/coverage positive, cost negative. services_deployed is deliberately excluded from scoring. Verified by: iteration_selection.py:61–77 (OBJECTIVE_DIRECTIONS, PARETO_OBJECTIVES, DEFAULT_SCORING_WEIGHTS).

INV-SEL-003 — Tie-breaking follows the defined rule.
TIE_BREAKERS = ["weekly_profit", "global_demand_weighted_coverage", "operating_cost", "profit_margin_pct", "unserved_demand"] applied sequentially. In production: iter 2 won outright (profit $861.7M > iter 0's $861.0M; coverage 47.5% > 47.2%), so tie-breaking was not exercised. Verified by: iteration_selection.py:80–85.

INV-SEL-004 — Selected solution is independently evaluable.
The selected iteration's selected_services list is deep-copied from the iteration snapshot and written to pipeline_output.json.selected_services. Each service entry contains id, ports, load, capacity, vessel_class, vessel_cost, fuel_cost, port_cost, revenue, cost, weekly_profit, margin_pct, region — enough to independently recompute all economic metrics. The iteration_selection dict records the full scorecard for every candidate, making the selection auditable. Verified by: pipeline_output.json — production selected iteration 2 with score 0.8500 vs iter 0 at 0.8156 vs iter 1 at 0.1500.
