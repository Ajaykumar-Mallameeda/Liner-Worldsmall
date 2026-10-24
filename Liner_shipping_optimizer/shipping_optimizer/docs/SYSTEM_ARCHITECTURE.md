# AI Vessel Routing System - Architecture Documentation

> Updated to follow `System_Architecture_Diagram_Large_Font.pdf` (4 pages). Blocks are referred to as *page.number*
> (for example **3.7** = page 3, block 7); the numbers are reference numbers used in this document only (left to right,
> top to bottom on each page) and are not printed on the PDF; use the block names to find a block there. Sections that the diagram
> does not show (data structures, performance, configuration, monitoring, error handling, security, future work) are
> unchanged from the earlier version of this document; where the earlier text conflicts with the diagram, the diagram applies.

## System Overview

The AI Vessel Routing System is a hierarchical multi-agent framework for liner shipping network design. It splits the
problem into regions, searches for candidate services regionally (genetic algorithms and a regional MILP), makes the
network decision with **one global network optimisation** over all demand, and has every result re-derived by an
**independent ledger** before it is reported. Large language models (LLMs) advise and describe; every suggestion is
validated and the economic accounting never depends on them.

### Core Problem Domain

- **Scale**: 435 ports, ~1,200 services, 9,600 demand lanes, 800K+ TEU/week
- **Constraints**: Fleet ≤ 300 vessels, transit time limits, port draft restrictions
- **Objective**: Maximize profit while meeting demand coverage targets

### Key Innovations

1. **Hierarchical Decomposition**: the global problem is split into regional sub-problems (k-means port clusters, demand split by origin); the regional agents run in parallel
2. **Regional search, global decision**: regional GA and MILP produce candidates and hints; one network MILP over all demand decides, and regional economics are indicative only
3. **Independent verification**: a separate ledger re-derives revenue, every cost item and every constraint from the raw data; the plan is reported as unverified if its profit differs from the optimiser's
4. **LLM advice behind a trust boundary**: every LLM suggestion is validated and has a rule-based fallback
5. **Iterative Refinement**: a feedback loop of 3 iterations; the best one is selected

## Architecture Diagram

### Page 1 - Hierarchical multi-agent architecture

```
 [1.1] Inputs --> [1.2] Orchestrator Agent (LLM) --> [1.3] Problem Decomposition
 ports, OD demand,  analysis, iteration control,     k-means port clusters,
 distances, fleet,  final selection                  demand split by origin
 port and canal costs                                        |
                       +-------------------------------------+-------------------------------------+
                       v                                     v                                     v
              [1.4] Regional Agent-1                [1.4] Regional Agent-2                [1.4] Regional Agent-3
                       +-------------------------------------+-------------------------------------+
                                  (regional agents run in parallel)                                |
                                                                                                   v
                                           [1.5] Candidate Services & Frequencies
                                           rotations - class screening - GA - regional MILP
                                                                  |
                                                                  v
                                           [1.6] Global Network Optimisation
                                           pooled candidates - one network MILP over all demand
                                             [1.7] Network MILP             LP bound - integer plan
                                             [1.8] Local Search & Flow Re-optimisation   exact LP moves
                                             [1.9] Profit-floor Repair      only if profit < 0
                                                                  |
                                                                  v
                                           [1.10] Independent Ledger Validator Agent
                                           revenue - six cost items - profit - every constraint
                                                                  |
                                                                  v
    [1.13] Resolutions  ---------------->  [1.11] Coordinator Decision Agent  ------->  [1.12] OPTIMISED NETWORK SOLUTION
    regional results and context to the Coordinator:                                    services - frequencies - vessels -
    conflict detection - overlap resolution -                                           cargo flows - revenue - costs -
    consensus weights                                                                   profit - coverage
                                                                  |
    [1.14] Feedbacks  (back to the Orchestrator):  coverage gap - profit gap - conflicts - objective weights -
    rerun signal  (3 iterations, best one selected)
```

| Block | Role |
|---|---|
| 1.1 Inputs | Ports, OD demand, distances, fleet, port and canal costs |
| 1.2 Orchestrator Agent (LLM) | Problem analysis, iteration control (3 iterations), final selection |
| 1.3 Problem Decomposition | k-means port clusters; demand split by origin |
| 1.4 Regional Agent-1, -2, -3 | One agent per region, run in parallel (page 2) |
| 1.5 Candidate Services & Frequencies | Rotations, class screening, GA frequencies and regional MILP results handed to the global stage |
| 1.6 Global Network Optimisation | Pooled candidates, one network MILP over all demand (page 3); contains 1.7 to 1.9 |
| 1.7 Network MILP | Integer plan with an LP bound |
| 1.8 Local Search & Flow Re-optimisation | Exact LP moves; cargo re-routed over all valid paths |
| 1.9 Profit-floor Repair | Only if profit < 0 |
| 1.10 Independent Ledger Validator Agent | Re-derives revenue, the six cost items, profit and every constraint |
| 1.11 Coordinator Decision Agent | Conflict detection, overlap resolution, consensus weights, feedback |
| 1.12 Optimised Network Solution | Services, frequencies, vessels, cargo flows, revenue, costs, profit, coverage |
| 1.13 Resolutions | Regional results and context to the Coordinator |
| 1.14 Feedbacks | Coverage gap, profit gap, conflicts, objective weights, rerun signal back to the Orchestrator |

### Page 2 - Regional Agent: candidate generation, search and allocation

One instance per region, run in parallel; its results become candidates and hints for the global stage.

```
 [2.1] Regional Problem --> [2.2] Regional Agent (LLM) --> [2.3] Service Generation --> [2.4] Feasibility & Class Screening
 own ports, demand owned    hub detection,                 closed rotations of         time - draft - canal - inventory
 by origin, full port       strategy text                  distinct ports, one                       |
 catalogue                       ^                         vessel class each                         v
                                 | [2.10] Archetype hints                                [2.5] Economic Filter
                                 |  LLM candidate-mix suggestion,                        cap the pool by stand-alone economics
                                 |  validated before use                                              |
   generators inside 2.3:                                                                               v
     A Direct services      top demand corridors                                         [2.6] Service GA
     B Hub loops            multi-port via each hub                                      binary selection - surrogate fitness
     C Hub trunks           hub-to-hub rotations                                                        |
     D Feeders              spoke to best hub                                                           v
     E Heuristic pool       base candidates                                              [2.7] Frequency GA
     F Demand-coherent loops  3-5 ports, grown from strongest ODs                        integer departures per week
                                                                                                        |
                                                                                                        v
 [2.9] Regional result  <------------------------------------------------------  [2.8] Regional MILP
 candidate pool - frequency hints - to the global stage                            fixed frequencies - cargo allocation
        |
        +--> [2.11] Feedbacks to the Regional Problem: objective weights and regional policy from the Coordinator,
             applied in the next iteration
```

Regional economics are indicative only: the global stage re-solves the pooled network and its verified figures replace them.

| Block | Role |
|---|---|
| 2.1 Regional Problem | The region's own ports, the demand owned by its origin ports, the full port catalogue |
| 2.2 Regional Agent (LLM) | Hub detection and strategy text; receives the archetype hints (2.10) |
| 2.3 Service Generation | Candidate pool of closed rotations of distinct ports, one vessel class each, from generators A to F |
| A Direct services | Top demand corridors |
| B Hub loops | Multi-port loops via each hub |
| C Hub trunks | Hub-to-hub rotations |
| D Feeders | Spoke to best hub |
| E Heuristic pool | Base candidates |
| F Demand-coherent loops | 3 to 5 ports, grown from the strongest ODs |
| 2.4 Feasibility & Class Screening | Time, draft, canal and inventory checks per rotation and vessel class |
| 2.5 Economic Filter | Caps the pool by stand-alone economics |
| 2.6 Service GA | Binary service selection with a surrogate fitness |
| 2.7 Frequency GA | Integer departures per week |
| 2.8 Regional MILP | Cargo allocation with the frequencies fixed |
| 2.9 Regional result | Candidate pool and frequency hints for the global stage |
| 2.10 Archetype hints | LLM candidate-mix suggestion, validated before use |
| 2.11 Feedbacks | Objective weights and regional policy from the Coordinator, applied in the next iteration |

### Page 3 - Global network optimisation and independent verification

One network over all demand: candidates are priced by one service model, solved, improved, and re-derived by a separate ledger.

```
 [3.1] Candidate Pools --> [3.2] Pool Union --> [3.3] Service Models --> [3.4] OD Path Enumeration
 from all regional agents  de-duplicate         cycle time - vessels -    direct - up to 2 transfers -
 + frequency hints         rotations, add       fuel - port calls -       transit-time limit
                           trunk candidates     canal - draft                       |
                           for under-used                                           v
                           vessel classes                    [3.5] LP Relaxation        upper bound - service support
                                                             [3.6] Integer MILP         services - frequencies - vessels - flows
                                                             [3.7] Local Search         add - drop - frequency moves
                                                             [3.8] Flow Re-optimisation all valid paths, fixed network
                                                             [3.9] Profit-floor Repair  only if profit < 0
                                                                                |
                                                                                v
                                    [3.10] Independent Ledger --> [3.11] Verified? --> [3.12] Verified Network Plan
                                    re-derives revenue, every     optimiser profit =   sum of regional figures equals
                                    cost item and every           ledger profit        the network total
                                    constraint from the raw data       |
                                                                       +--> no: plan reported as unverified

 [3.13] Operating profit = Revenue - ( Vessel hire + Fuel + Port calls + Handling + Transshipment )
        unserved cargo carries no penalty; checks: fleet inventory - leg capacity - demand conservation -
        transit time - draft - canal rules
```

| Block | Role |
|---|---|
| 3.1 Candidate Pools | Candidate services and frequency hints from all regional agents |
| 3.2 Pool Union | De-duplicates rotations and adds trunk candidates for under-used vessel classes |
| 3.3 Service Models | Prices every candidate: cycle time, vessels, fuel, port calls, canal, draft |
| 3.4 OD Path Enumeration | Routes per OD pair: direct or up to 2 transfers, within the transit-time limit |
| 3.5 LP Relaxation | Upper bound and service support |
| 3.6 Integer MILP | Services, frequencies, vessels and flows |
| 3.7 Local Search | Add, drop and frequency moves |
| 3.8 Flow Re-optimisation | All valid paths with the network fixed |
| 3.9 Profit-floor Repair | Only if profit < 0 |
| 3.10 Independent Ledger | Re-derives revenue, every cost item and every constraint from the raw data |
| 3.11 Verified? | Optimiser profit must equal the ledger profit; otherwise the plan is reported as unverified |
| 3.12 Verified Network Plan | The final plan; the sum of the regional figures equals the network total |
| 3.13 Profit formula | Operating profit = revenue - (vessel hire + fuel + port calls + handling + transshipment) |

### Page 4 - Agent and LLM layer (trust boundary)

Language models advise and describe; every suggestion is validated, and the economic accounting never depends on them.

```
 [4.1] Agent Request  -->  [4.2] LLM Client  -->  [4.3] Provider Router  -->  [4.4] OpenRouter / Groq / Cerebras / Google
 role - prompt - context   single entry point,    role to model - cache -       |
                           one record per call    circuit breaker - failover    v
                                  ^    |                  ^               [4.5] Model Response (text or structured JSON)
                                  |    +---- [4.10] Roles: orchestrator - regional - service generator -     |
                                  |           coordinator - iteration selector (into the Provider Router)    v
                                  |                                                       [4.6] Validator (schema - range - consensus rules)
                                  |                                                          |                          |
                                  |                                                  accepted|                          |rejected or provider unavailable
                                  |                                                          v                          v
                                  |                                          [4.7] Use LLM output          [4.8] Rule-based Fallback
                                  |                                          decision source: LLM          deterministic template or score
                                  |                                                          |                          |
                                  |                                                          +------------+-------------+
                                  |                                                                       v
                                  +------ [4.11] Telemetry: provider - model - latency - failures ---  [4.9] Decision Applied
                                          - fallback flag, per decision                                  source recorded: LLM or rule-based
```

Used for: narrative text, candidate-mix hints, objective-weight suggestions, iteration choice. Never used for: cost, revenue or profit figures.

| Block | Role |
|---|---|
| 4.1 Agent Request | Role, prompt and context of one agent call |
| 4.2 LLM Client | Single entry point; one record per call |
| 4.3 Provider Router | Role to model, cache, circuit breaker, failover |
| 4.4 OpenRouter / Groq / Cerebras / Google | The model providers |
| 4.5 Model Response | Text or structured JSON |
| 4.6 Validator | Schema, range and consensus rules |
| 4.7 Use LLM output | Accepted answer; decision source: LLM |
| 4.8 Rule-based Fallback | Rejected answer or unavailable provider: deterministic template or score |
| 4.9 Decision Applied | The decision that enters the system; source recorded (LLM or rule-based) |
| 4.10 Roles | orchestrator, regional, service generator, coordinator, iteration selector |
| 4.11 Telemetry | Provider, model, latency, failures and fallback flag per decision |

## Component Inventory

Technology and class names are given where the earlier version of this document recorded them; "-" means the diagram
does not name them.

| Component | Responsibility | Technology | Key Classes | Diagram |
|-----------|----------------|------------|-------------|---------|
| OrchestratorAgent | Problem analysis (LLM), iteration control (3 iterations), final selection | Python + LLM | `OrchestratorAgent` | 1.2 |
| RegionalAgent | Per region: hub detection, strategy text (LLM), service generation, screening, economic filter, GA, regional MILP | DEAP + PuLP | `RegionalAgent` | 2.2 |
| ServiceGeneratorAgent | Candidate service generation, generators A to F | Heuristics | `ServiceGeneratorAgent` | 2.3 |
| HierarchicalGA | Service GA (binary selection) and Frequency GA (integer departures), surrogate fitness | Custom GA (DEAP) | `HierarchicalGA` | 2.6, 2.7 |
| ServiceGA | Service subset selection | DEAP | `ServiceGA` | 2.6 |
| FrequencyGA | Departures per week | Custom GA | `FrequencyGA` | 2.7 |
| HubMILP (Regional MILP) | Cargo allocation with fixed frequencies | PuLP | `HubMILP` | 2.8 |
| Global Network Optimisation | Pool union, service models, OD paths, LP relaxation, integer MILP, local search, flow re-optimisation, profit-floor repair | MILP | - | 1.6 to 1.9, 3.2 to 3.9 |
| Independent Ledger Validator | Re-derives revenue, six cost items, profit and every constraint; verification check | - | - | 1.10, 3.10, 3.11 |
| CoordinatorAgent | Conflict detection, overlap resolution, consensus weights, feedback | Python + LLM | `CoordinatorAgent` | 1.11 |
| LLM layer | LLM Client, Provider Router, Validator, Rule-based Fallback, Telemetry | - | - | 4.1 to 4.11 |

## Optimization Pipeline

### Phase 1: Problem Decomposition (1.2, 1.3)

1. **Problem analysis**: the Orchestrator Agent analyses the inputs (LLM)
2. **Port clustering**: k-means port clusters (3 regions in the earlier version of this document: Asia, Europe, Americas)
3. **Regional splitting**: the demand is split by origin, so each region owns its demand

### Phase 2: Regional Optimisation (1.4, page 2)

Each regional agent, run in parallel, executes:

```
Service Generation (A-F) -> Feasibility & Class Screening -> Economic Filter -> Service GA -> Frequency GA -> Regional MILP
```

#### Service Generation Strategies (2.3)

- **A. Direct services**: top demand corridors
- **B. Hub loops**: multi-port loops via each hub
- **C. Hub trunks**: hub-to-hub rotations
- **D. Feeders**: spoke to best hub
- **E. Heuristic pool**: base candidates
- **F. Demand-coherent loops**: 3 to 5 ports, grown from the strongest ODs

Archetype hints (2.10) from the LLM suggest the candidate mix and are validated before use.

#### Screening and filtering (2.4, 2.5)

Rotations are checked for time, draft, canal and inventory, with a vessel class assigned (2.4); the pool is then capped by stand-alone economics (2.5).

#### Hierarchical GA (2.6, 2.7)

1. **Level 1 - Service GA**: binary selection of services with a surrogate fitness
2. **Level 2 - Frequency GA**: integer departures per week

Parameters of the earlier version of this document (not shown in the diagram): population 80, 120 generations; frequency range 1-3 sailings/week; vessel calculation ceil(cycle_time * frequency / 7).

#### Regional MILP (2.8)

Allocates the cargo with the frequencies fixed. Its result (2.9) is the candidate pool and the frequency hints for the global stage; regional economics are indicative only.

### Phase 3: Global Network Optimisation (1.5 to 1.9, page 3)

1. **Pool Union (3.2)**: regional pools are merged, duplicate rotations removed, trunk candidates added for under-used vessel classes
2. **Service Models (3.3)** and **OD Path Enumeration (3.4)**: every candidate is priced; paths are direct or use up to 2 transfers within the transit-time limit
3. **LP Relaxation (3.5)** and **Integer MILP (3.6)**: upper bound, then the integer plan (services, frequencies, vessels, flows)
4. **Local Search (3.7)** and **Flow Re-optimisation (3.8)**: add, drop and frequency moves; all valid paths with the network fixed
5. **Profit-floor Repair (3.9)**: only if profit < 0

### Phase 4: Independent Verification (1.10, 3.10 to 3.12)

The Independent Ledger re-derives revenue, every cost item and every constraint from the raw data. The plan is verified only if the optimiser profit equals the ledger profit; otherwise it is reported as unverified. Only the verified plan is reported (3.12).

### Phase 5: Coordination and Iteration (1.11, 1.13, 1.14)

1. **Coordination**: the Coordinator Decision Agent receives the regional results and context (Resolutions): conflict detection, overlap resolution, consensus weights
2. **Feedbacks**: coverage gap, profit gap, conflicts, objective weights and a rerun signal return to the Orchestrator; regional agents apply the objective weights and regional policy in the next iteration
3. **Iterations**: 3 iterations; the best one is selected as the Optimised Network Solution (1.12)

## Data Flow Architecture

### Input Data Schema

```python
# Core Data Structures
Port: {
    id: int,
    name: str,
    latitude: float,
    longitude: float,
    handling_cost: float,
    draft: float,
    port_call_cost: float
}

Service: {
    id: int,
    ports: List[int],
    capacity: float,      # TEU
    weekly_cost: float,   # USD/week
    cycle_time: int,      # days
    speed: float,         # knots
    fuel_cost: float
}

Demand: {
    origin: int,
    destination: int,
    weekly_teu: float,
    revenue_per_teu: float
}

Problem: {
    ports: List[Port],
    services: List[Service],
    demands: List[Demand],
    distance_matrix: Dict[int, Dict[int, float]]
}
```

### Data Flow Sequence

```
Inputs -> Orchestrator Agent -> Problem Decomposition -> Regional Agents (candidate generation, screening, GA, regional MILP)
-> candidate pools and frequency hints -> Global Network Optimisation -> Independent Ledger -> Verified?
-> Coordinator Decision Agent -> Feedbacks (3 iterations, best one selected) -> Optimised Network Solution
```

Regional results below are indicative only; the verified global figures replace them (page 2 note, 3.12).

### Intermediate Data Formats

1. **Chromosome**: 
   ```python
   {
       "services": List[int],        # Binary selection mask
       "frequencies": List[int],     # 1-3 sailings/week
       "coverage_estimate": float,   # Percentage
       "skip_milp": bool            # Weak solutions flag
   }
   ```

2. **Regional Result**:
   ```python
   {
       "weekly_profit": float,
       "coverage_percent": float,
       "services_selected": int,
       "operating_cost": float,
       "transship_cost": float,
       "port_cost": float,
       "satisfied_demand": float,
       "unserved_demand": float
   }
   ```

3. **Feedback Signals**:
   ```python
   {
       "needs_rerun": bool,
       "coverage_gap": float,
       "profit_gap": float,
       "conflict_severity": int,
       "weight_adjustments": Dict[str, float],
       "convergence_score": float
   }
   ```

## Performance Characteristics

### Computational Complexity

| Component | Time Complexity | Space Complexity | Typical Runtime |
|-----------|-----------------|------------------|-----------------|
| ServiceGA | O(pop × gen × n) | O(pop × n) | 30-45 seconds |
| FrequencyGA | O(pop × gen × m) | O(pop × m) | 10-15 seconds |
| HubMILP | O(n³) (worst case) | O(n²) | 60-120 seconds |
| Coordinator | O(k) | O(k) | <5 seconds |

Where:
- n = number of services (400-1200)
- m = number of selected services (50-200)
- k = number of regions (3)

### Scalability Features

1. **Regional Decomposition**: Reduces problem size by ~3x per region
2. **Service Filtering**: Cuts candidate pool from ~2000 to ≤400
3. **Transfer Pair Limit**: Caps MILP variables at 2000
4. **Fleet Pruning**: Post-GA vessel count enforcement
5. **Time Budgets**: Hard limits prevent infinite runs

### Memory Optimization

- **Sparse Matrices**: Distance stored only for connected ports
- **Lazy Loading**: Demands loaded per region, not globally
- **Generator Pattern**: Services created on-demand during GA
- **Cleanup**: Intermediate results freed after each iteration

## System Constraints and Objectives

### Hard Constraints

1. **Fleet Limit**: ≤300 vessels globally
2. **Service Integrity**: Selected services must maintain port sequence
3. **Demand Balance**: Flow in = Flow out at hub ports
4. **Capacity Limits**: Service capacity × frequency ≥ allocated flow
5. **Port Handling**: Flow ≤ port handling capacity

### Soft Constraints

1. **Coverage Target**: ≥70% of total demand
2. **Profit Floor**: Weekly profit ≥ $0
3. **Conflict Resolution**: Zero service overlaps between regions
4. **Coverage Balance**: Variance ≤20% between regions

### Objective Function

The global network decision (page 3) maximises operating profit:

```
Operating profit = Revenue - ( Vessel hire + Fuel + Port calls + Handling + Transshipment )
```

Unserved cargo carries no penalty. The independent ledger checks fleet inventory, leg capacity, demand conservation,
transit time, draft and canal rules, and the plan is reported as unverified if the optimiser profit differs from the
ledger profit. The regional GA stage works with a surrogate fitness, and the objective weights returned in the
feedbacks (1.14) are applied by the regional agents in the next iteration (2.11).

## LLM Integration Points

### Trust boundary (page 4)

Language models advise and describe; every suggestion is validated, and the economic accounting never depends on
them. Each call passes the LLM Client (4.2, one record per call) and the Provider Router (4.3: role to model, cache,
circuit breaker, failover) to a provider (OpenRouter, Groq, Cerebras or Google, 4.4). The Model Response (4.5, text or
structured JSON) goes to the Validator (4.6: schema, range, consensus rules). An accepted answer is used (4.7, decision
source: LLM); a rejected answer or an unavailable provider triggers the Rule-based Fallback (4.8, deterministic template
or score). The Decision Applied (4.9) records its source, and Telemetry (4.11) records provider, model, latency,
failures and fallback flag per decision.

**Roles that call the LLM (4.10)**: orchestrator, regional, service generator, coordinator, iteration selector.

**Used for**: narrative text, candidate-mix hints, objective-weight suggestions, iteration choice.
**Never used for**: cost, revenue or profit figures.

### Strategic Decision Points

1. **Problem Analysis** (Orchestrator, 1.2):
   - Network complexity assessment
   - Decomposition strategy validation
   - Size classification (Small/Medium/Large)

2. **Service Strategy** (RegionalAgent, 2.2):
   - Hub detection and strategy text
   - Archetype hints for the candidate mix (2.10), validated before use
   - Hub port selection validation

3. **Conflict Resolution** (Coordinator, 1.11):
   - Weight adjustment recommendations (consensus weights)
   - Priority action identification
   - Convergence diagnosis

4. **Iteration choice**: the iteration selector picks the best of the 3 iterations

### LLM Prompt Engineering

- **Structured Outputs**: JSON format with required fields
- **Fallback Logic**: Rule-based when LLM fails (4.8)
- **Validation Checks**: Presence of numeric citations
- **Temperature Control**: 0.1 for consistent outputs

## Configuration Management

### Environment Variables

```bash
# API Configuration
OPENROUTER_API_KEY=sk-or-xxx
ORCHESTRATOR_MODEL=openrouter/gpt-oss-120b
REGIONAL_MODEL=meta-llama/llama-3.1-8b-instruct

# GA Parameters
GA_POPULATION_SIZE=80
GA_GENERATIONS=120

# MILP Parameters
MILP_TIME_LIMIT=120

# Cost Constants (USD)
TRANSSHIP_COST_PER_TEU=80.0
PORT_COST_PER_TEU=15.0
ALPHA_UNSERVED=300.0
```

### Runtime Tuning

1. **Coverage Target**: 70% (adjustable via COVERAGE_TARGET)
2. **Max Iterations**: 3 (hard limit in MAX_ITERATIONS)
3. **Service Limits**: 400 minimum, port-count dependent
4. **Transfer Pairs**: 2000 per MILP solve

## Monitoring and Observability

### Key Metrics

1. **Convergence Metrics**:
   - Coverage improvement per iteration
   - Profit change trajectory
   - Conflict resolution rate

2. **Performance Metrics**:
   - GA fitness evolution
   - MILP solver status
   - Runtime per component

3. **Quality Metrics**:
   - Demand satisfied vs target
   - Vessel utilization rate
   - Hub transshipment percentage

### Logging Strategy

- **Structured Logging**: JSON format with context
- **Level Control**: INFO for normal, WARNING for anomalies
- **Component Tags**: agent, region, iteration for correlation
- **Performance Marks**: t0/perf_counter() for elapsed timing

## Error Handling and Recovery

### Common Failure Modes

1. **MILP Infeasibility**:
   - Cause: Over-constrained capacity
   - Recovery: Reduce service selection, increase fleet

2. **Zero Service Selection**:
   - Cause: Aggressive filtering
   - Recovery: Lower margin threshold, increase candidates

3. **LLM API Failure**:
   - Cause: Rate limits or network issues
   - Recovery: Rule-based fallback logic

4. **Memory Overflow**:
   - Cause: Too many transfer pairs
   - Recovery: Reduce MAX_TRANSFER_PAIRS

### Recovery Strategies

1. **Graceful Degradation**: Continue with reduced functionality
2. **Circuit Breaker**: Skip failed components, use defaults
3. **Checkpoint/Resume**: Save state after each iteration
4. **Validation Gates**: Pre-flight checks before expensive operations

## Security and Safety

### Input Validation

1. **Port IDs**: Must exist in distance matrix
2. **Service Routes**: Valid port sequences
3. **Demand Values**: Non-negative TEU values
4. **Distance Matrix**: Symmetric, positive values

### Output Sanitization

1. **Fleet Enforcement**: Hard cap on vessel count
2. **Flow Conservation**: Balance verification
3. **Cost Reasonableness: Prevent negative costs
4. **Coverage Capping**: Maximum 100% demand

### Audit Trail

1. **Iteration Log**: All decisions and changes recorded
2. **Weight History**: Track GA weight evolution
3. **Conflict Resolution**: Document all service conflicts
4. **Performance Trace**: Runtime and memory usage

## Future Extensions

### Scalability Enhancements

1. **Dynamic Region Count**: Auto-adjust based on port count
2. **Parallel MILP**: Solve hub clusters simultaneously
3. **Incremental GA**: Warm start from previous solutions
4. **Distributed Computing**: Regional agents on separate nodes

### Algorithm Improvements

1. **Adaptive GA**: Dynamic parameter tuning
2. **Learning MILP**: Warm starts from previous solves
3. **Reinforcement Learning**: LLM weight optimization
4. **Meta-heuristics**: Simulated annealing, tabu search

### Integration Opportunities

1. **Real-time Data**: Live demand and weather integration
2. **Market Simulation**: Competitor service optimization
3. **Carbon Accounting**: Emission optimization module
4. **Risk Analysis**: Disruption scenario testing