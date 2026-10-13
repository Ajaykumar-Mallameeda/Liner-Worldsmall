# AI Vessel Routing System - Architecture Documentation

## System Overview

The AI Vessel Routing System is a multi-agent optimization framework designed for global liner shipping networks. It combines Genetic Algorithms (GA), Mixed-Integer Linear Programming (MILP), Large Language Models (LLMs), and multi-agent coordination to optimize vessel deployment, service selection, and cargo flow allocation across maritime networks.

### Core Problem Domain

- **Scale**: 435 ports, ~1,200 services, 9,600 demand lanes, 800K+ TEU/week
- **Constraints**: Fleet ≤ 300 vessels, transit time limits, port draft restrictions
- **Objective**: Maximize profit while meeting demand coverage targets

### Key Innovations

1. **Hierarchical Decomposition**: Global problem split into regional sub-problems
2. **Hybrid GA-MILP**: GA for service selection, MILP for flow optimization
3. **LLM-Driven Decisions**: Strategic weight adjustments based on solution analysis
4. **Iterative Refinement**: Feedback loop with max 3 iterations for convergence

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                           │
│                  (Master Controller)                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Problem Analysis│  │ Port Clustering │  │ Global Metrics  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                   REGIONAL SPLITTER                             │
│            (Decompose by Geographic Clusters)                  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
┌─────────────────┐         ┌─────────────────┐
│ REGIONAL AGENT  │         │ REGIONAL AGENT  │
│      Asia       │         │     Europe      │
└─────────────────┘         └─────────────────┘
        │                           │
        └─────────────┬─────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                COORDINATOR AGENT                                │
│            (Conflict Resolution & Feedback)                     │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                 ITERATION CONTROL                              │
│         (Max 3 iterations with weight adjustment)              │
└─────────────────────────────────────────────────────────────────┘
```

## Component Inventory

| Component | Responsibility | Technology | Key Classes |
|-----------|----------------|------------|-------------|
| OrchestratorAgent | System entry point, iteration control, problem analysis | Python + LLM | `OrchestratorAgent` |
| RegionalAgent | Regional GA+MILP optimization, service selection | DEAP + PuLP | `RegionalAgent` |
| CoordinatorAgent | Conflict detection, resolution, feedback generation | Python + LLM | `CoordinatorAgent` |
| HierarchicalGA | Service selection + frequency optimization | Custom GA (DEAP) | `HierarchicalGA` |
| ServiceGA | Service subset selection | DEAP | `ServiceGA` |
| FrequencyGA | Sailing frequency optimization | Custom GA | `FrequencyGA` |
| HubMILP | Flow allocation optimization | PuLP | `HubMILP` |
| ServiceGeneratorAgent | Candidate service generation | Heuristics | `ServiceGeneratorAgent` |

## Optimization Pipeline

### Phase 1: Problem Decomposition

1. **Port Clustering**: Geographic clustering into 3 regions (Asia, Europe, Americas)
2. **Regional Splitting**: Assign ports and demands to regional agents
3. **Service Generation**: Create candidate service pool (800-2000 services)

### Phase 2: Regional Optimization

Each RegionalAgent executes:

```
Service Generation → Service Filtering → Hierarchical GA → Hub MILP
```

#### Service Generation Strategies

- **A. Direct Services**: Top-500 high-demand corridors (point-to-point)
- **B. Hub Loops**: Hub + spoke regional loops (21-day cycle)
- **C. Hub-to-Hub Trunks**: Backbone routes between major hubs
- **D. Feeder Services**: Spoke-to-hub connections (7-day cycle)
- **E. Heuristic Pool**: Additional candidates from algorithmic generator

#### Hierarchical GA Process

1. **Level 1 - Service Selection GA**:
   - Population: 80 chromosomes
   - Generations: 120
   - Selection: Binary mask for services
   - Fitness: Weighted profit (50%) + coverage (40%) + cost (10%)

2. **Level 2 - Frequency Optimization GA**:
   - Frequency range: 1-3 sailings/week
   - Fleet constraint: ≤300 vessels total
   - Vessel calculation: ceil(cycle_time * frequency / 7)

#### MILP Flow Optimization

For each hub cluster:
- **Variables**: Direct flow, transfer flow, unserved demand
- **Objective**: Maximize profit - costs - unserved penalty
- **Constraints**: Capacity, demand fulfillment, port handling limits
- **Transfer Pairs**: Up to 2000 hub-mediated transfers

### Phase 3: Global Coordination

1. **Conflict Detection**: Identify services selected in multiple regions
2. **Conflict Resolution**: Keep service in highest-profit region only
3. **Global Metrics**: Aggregate profit, coverage, cost across regions
4. **Feedback Generation**: Gradient signals for next iteration

### Phase 4: Iterative Refinement

Maximum 3 iterations with:
- **Weight Adjustment**: Profit/Coverage/Cost weights tuned based on gaps
- **Exploration Factor**: Increased by 10% each iteration for diversity
- **Convergence Check**: Stop when coverage gap < 1% or max iterations reached

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
Raw Data (CSV) → Problem Instance → Regional Split → GA Optimization → 
MILP Solving → Regional Results → Conflict Resolution → Global Solution
```

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

```
Maximize: α × (Revenue - Operating Costs - Transshipment Costs - Port Costs)
           - β × UnservedDemandPenalty
           + γ × CoverageReward

Where:
- α = profit_weight (default 0.5)
- β = coverage_weight (default 0.4)
- γ = cost_weight (default 0.1)
```

## LLM Integration Points

### Strategic Decision Points

1. **Problem Analysis** (Orchestrator):
   - Network complexity assessment
   - Decomposition strategy validation
   - Size classification (Small/Medium/Large)

2. **Service Strategy** (RegionalAgent):
   - Hub-and-spoke vs direct vs hybrid
   - Hub port selection validation
   - Coverage target setting

3. **Conflict Resolution** (Coordinator):
   - Weight adjustment recommendations
   - Priority action identification
   - Convergence diagnosis

### LLM Prompt Engineering

- **Structured Outputs**: JSON format with required fields
- **Fallback Logic**: Rule-based when LLM fails
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