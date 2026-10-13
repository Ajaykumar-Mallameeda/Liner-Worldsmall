# Data Dictionary - AI Vessel Routing System

## Overview

This document defines all data structures, file formats, and data flows used in the AI Vessel Routing System. It includes specifications for input files, intermediate data structures, and output formats.

## Core Data Types

### Port

Represents a port in the maritime network.

```python
@dataclass
class Port:
    id: int              # Unique port identifier
    name: str            # Port name (e.g., "Shanghai")
    latitude: float      # Geographic latitude (-90 to 90)
    longitude: float     # Geographic longitude (-180 to 180)
    handling_cost: float = 0    # Cost per TEU for port handling (USD)
    draft: float = 0            # Maximum vessel draft (meters)
    port_call_cost: float = 0   # Fixed cost per port call (USD)
```

**Constraints:**
- `id` must be unique across all ports
- `latitude` and `longitude` must be valid geographic coordinates
- `handling_cost` ≥ 0 (USD/TEU)
- `draft` ≥ 0 (meters)
- `port_call_cost` ≥ 0 (USD)

### Service

Represents a shipping service route with vessel deployment parameters.

```python
@dataclass
class Service:
    id: int                    # Unique service identifier
    ports: List[int]          # Ordered list of port IDs to visit
    capacity: float           # Vessel capacity (TEU)
    weekly_cost: float        # Weekly operating cost (USD/week)
    cycle_time: int = 7       # Round trip duration (days)
    speed: float = 18         # Vessel speed (knots)
    fuel_cost: float = 0      # Weekly fuel cost (USD/week)
```

**Constraints:**
- `id` must be unique across all services
- `ports` list must have length ≥ 2
- All port IDs in `ports` must exist in the problem
- `capacity` > 0 (TEU)
- `weekly_cost` ≥ 0 (USD/week)
- `cycle_time` ≥ 1 (days)
- `speed` > 0 (knots)

### Demand

Represents cargo demand between two ports.

```python
@dataclass
class Demand:
    origin: int              # Origin port ID
    destination: int         # Destination port ID
    weekly_teu: float        # Weekly demand volume (TEU/week)
    revenue_per_teu: float   # Revenue per TEU (USD/TEU)
```

**Constraints:**
- `origin` ≠ `destination` (no self-loops)
- `origin` and `destination` must exist in the problem
- `weekly_teu` > 0 (TEU/week)
- `revenue_per_teu` > 0 (USD/TEU)

### Problem

Container for the complete optimization problem instance.

```python
class Problem:
    def __init__(
        self,
        ports: List[Port],                    # All ports in network
        services: List[Service],              # Candidate services
        demands: List[Demand],                # All demand corridors
        distance_matrix: Dict = None          # Port-to-port distances
    ):
        self.ports = ports
        self.services = services
        self.demands = demands
        self.distance_matrix = distance_matrix
        
        # Runtime attributes (modified during optimization)
        self.profit_weight: float = 0.5
        self.coverage_weight: float = 0.4
        self.cost_weight: float = 0.1
        self.exploration_factor: float = 1.0
```

**Constraints:**
- `distance_matrix` must be provided
- Matrix must be symmetric: distance[i][j] = distance[j][i]
- Distance entries must be ≥ 0 (nautical miles)

## Input Data Files

### ports.csv

Port definitions for the network.

| Column | Type | Unit | Required | Description |
|--------|------|------|----------|-------------|
| id | integer | - | Yes | Unique port identifier |
| name | string | - | Yes | Human-readable port name |
| latitude | float | degrees | Yes | Geographic latitude |
| longitude | float | degrees | Yes | Geographic longitude |
| handling_cost | float | USD/TEU | No | Default: 0 |
| draft | float | meters | No | Maximum vessel draft |
| port_call_cost | float | USD | No | Fixed cost per call |

**Example:**
```csv
id,name,latitude,longitude,handling_cost,draft,port_call_cost
1001,Shanghai,31.2304,121.4737,15.0,15.5,50000
1002,Ningbo,29.8683,121.5440,14.5,15.0,45000
1003,Singapore,1.3521,103.8198,18.0,16.0,75000
```

### services.csv

Candidate service definitions.

| Column | Type | Unit | Required | Description |
|--------|------|------|----------|-------------|
| id | string | - | Yes | Service identifier (e.g., "S001") |
| capacity | float | TEU | Yes | Vessel capacity |
| weekly_cost | float | USD/week | Yes | Weekly operating cost |
| cycle_time | integer | days | No | Round trip duration (default: 7) |
| speed | float | knots | No | Vessel speed (default: 18) |
| fuel_cost | float | USD/week | No | Weekly fuel cost (default: 0) |
| ports | string | - | Yes | Comma-separated port IDs |

**Example:**
```csv
id,capacity,weekly_cost,cycle_time,speed,fuel_cost,ports
S001,10000,150000,14,18,50000,"1001,1003,1005,1007"
S002,8000,120000,10,20,40000,"1002,1004"
S003,12000,200000,21,16,60000,"1008,1009,1010,1011,1012"
```

### demands.csv

Demand matrix between ports.

| Column | Type | Unit | Required | Description |
|--------|------|------|----------|-------------|
| origin | integer | - | Yes | Origin port ID |
| destination | integer | - | Yes | Destination port ID |
| weekly_teu | float | TEU/week | Yes | Weekly demand volume |
| revenue_per_teu | float | USD/TEU | Yes | Revenue per TEU |

**Example:**
```csv
origin,destination,weekly_teu,revenue_per_teu
1001,2001,5000,250.0
1001,2002,3500,275.0
1002,2001,2800,240.0
1002,2003,4200,260.0
```

### dist_dense.csv

Distance matrix between ports (nautical miles).

| Column | Type | Unit | Required | Description |
|--------|------|------|----------|-------------|
| origin | integer | - | Yes | Origin port ID |
| destination | integer | - | Yes | Destination port ID |
| distance_nm | float | NM | Yes | Distance in nautical miles |

**Example:**
```csv
origin,destination,distance_nm
1001,1002,120.5
1001,1003,2450.0
1002,1003,2380.5
```

## Intermediate Data Structures

### Chromosome

GA solution representation.

```python
chromosome = {
    "services": List[int],          # Binary mask: 1 = selected, 0 = not
    "frequencies": List[int],       # Sailings per week (1-3)
    "coverage_estimate": float,     # Expected coverage percentage
    "skip_milp": bool              # True if too weak for MILP
}
```

**Constraints:**
- `len(services) == len(problem.services)`
- `len(frequencies) == len(problem.services)`
- `frequencies[i] ∈ {0, 1, 2, 3}` where 0 = not selected
- `coverage_estimate ∈ [0, 100]`

### Regional Result

Output from a regional agent optimization.

```python
regional_result = {
    "agent": str,                   # Agent name
    "region": str,                  # Region name (Asia/Europe/Americas)
    "status": str,                  # "Optimal", "Feasible", or "Infeasible"
    
    # Service metrics
    "services_generated": int,      # Total candidates generated
    "services_filtered": int,       # After filtering
    "services_selected": int,       # Selected by GA
    
    # Financial metrics
    "weekly_profit": float,         # USD/week
    "annual_profit": float,         # USD/year
    "operating_cost": float,        # USD/week
    "transship_cost": float,        # USD/week
    "port_cost": float,             # USD/week
    "total_cost": float,            # USD/week
    
    # Coverage metrics
    "coverage_percent": float,      # Percentage of demand satisfied
    "satisfied_demand": float,      # TEU/week
    "unserved_demand": float,       # TEU/week
    "total_demand": float,          # TEU/week
    
    # Derived metrics
    "profit_margin_pct": float,     # Profit / (Profit + Cost) * 100
    "profit_per_service": float,    # USD/service/week
    "cost_per_service": float,      # USD/service/week
    "uncovered_teu": float,         # Absolute TEU not covered
    
    # Network information
    "hub_ports": List[int],         # Detected hub port IDs
    "strategy": str,                # LLM-generated strategy text
    "explanation": str,             # LLM explanation
    
    # Performance
    "elapsed_sec": float            # Runtime in seconds
}
```

### Conflict

Service overlap between regions.

```python
conflict = {
    "type": "service_overlap",      # Conflict type
    "service_id": int,              # Service identifier
    "regions": List[str]            # Regions that selected it
}
```

### Resolution Log

Conflict resolution audit trail.

```python
resolution = {
    "service_id": int,              # Conflicted service
    "kept_in": str,                 # Region that kept it
    "removed_from": str,            # Region it was removed from
    "keep_profit": float,           # Profit of keeping region
    "drop_profit": float            # Profit of dropping region
}
```

### Feedback Signals

Coordinator feedback for next iteration.

```python
feedback = {
    "needs_rerun": bool,            # Should iterate again?
    "rerun_reason": str,            # Human-readable reason
    "coverage_gap": float,          # How far below target (pp)
    "profit_gap": float,            # How far below floor (USD)
    "conflict_severity": int,       # Number of conflicts
    "weight_adjustments": {         # New GA weights
        "profit_weight": float,
        "coverage_weight": float,
        "cost_weight": float
    },
    "convergence_score": float,     # 0.0 = bad, 1.0 = converged
    "iteration": int,               # Current iteration number
    "at_iteration_cap": bool,       # Hit max iterations?
    
    # Legacy flags
    "conflict_count": int,
    "low_coverage": bool,
    "low_profit": bool
}
```

## Output Data Formats

### Final Solution

Complete optimization result from orchestrator.

```python
solution = {
    # Meta information
    "orchestrator": str,            # Orchestrator name
    "status": str,                  # "complete" or "partial"
    "iterations_run": int,          # Number of iterations executed
    
    # Analysis
    "problem_analysis": str,        # Network complexity analysis
    "executive_summary": str,       # LLM-generated summary
    
    # Regional breakdown
    "regional_results": List[regional_result],
    
    # Global aggregation
    "decision_output": Dict,        # Coordinator decisions
    "summary_metrics": {
        "weekly_profit": float,
        "annual_profit": float,
        "operating_cost": float,
        "transship_cost": float,
        "port_cost": float,
        "total_cost": float,
        "coverage": float,
        "total_services": int,
        "satisfied_demand": float,
        "unserved_demand": float
    },
    
    # Audit trail
    "iteration_audit": List[Dict]   # Per-iteration metrics
}
```

### Service Deployment

Detailed service deployment plan.

```python
deployment = {
    "services": [
        {
            "service_id": int,
            "route": List[int],          # Port sequence
            "frequency": int,            # Sailings/week
            "vessels_required": int,    # Number of vessels
            "allocated_flows": {         # OD pairs served
                (origin, destination): float  # TEU/week
            }
        }
    ],
    "hub_flows": {
        (hub, service1, service2): float  # TEU/week transferred
    },
    "total_vessels": int
}
```

## Data Quality Notes

### Common Issues

1. **Port ID Mismatches**:
   - Issue: Port IDs referenced in services/demands don't exist
   - Impact: Runtime errors, service failures
   - Detection: Validate all IDs against port list
   - Fix: Update or remove invalid references

2. **Asymmetric Distances**:
   - Issue: distance[i][j] ≠ distance[j][i]
   - Impact: Inconsistent routing calculations
   - Detection: Check matrix symmetry
   - Fix: Use max(d_ij, d_ji) or average

3. **Negative Costs**:
   - Issue: Service costs < 0
   - Impact: Unrealistic profit calculations
   - Detection: Cost validation
   - Fix: Verify data source, apply floor

4. **Zero Demand**:
   - Issue: Demand entries with weekly_teu = 0
   - Impact: Wasted computation
   - Detection: Filter pre-processing
   - Fix: Remove or update with real values

### Validation Rules

```python
def validate_problem(problem: Problem) -> List[str]:
    """Validate problem instance and return issues"""
    issues = []
    
    # Check port IDs
    port_ids = {p.id for p in problem.ports}
    
    # Validate services
    for service in problem.services:
        if not service.ports:
            issues.append(f"Service {service.id} has no ports")
        for port_id in service.ports:
            if port_id not in port_ids:
                issues.append(f"Service {service.id} references unknown port {port_id}")
    
    # Validate demands
    for demand in problem.demands:
        if demand.origin not in port_ids:
            issues.append(f"Demand from unknown port {demand.origin}")
        if demand.destination not in port_ids:
            issues.append(f"Demand to unknown port {demand.destination}")
        if demand.weekly_teu <= 0:
            issues.append(f"Non-positive demand {demand.weekly_teu}")
    
    return issues
```

## Data Transformations

### Unit Conversions

| From | To | Formula |
|------|----|---------|
| Days → Weeks | days / 7 | `weeks = days / 7` |
| Knots → NM/day | knots × 24 | `nm_day = knots × 24` |
| TEU → FFE | TEU / 2 | `ffe = teu / 2` |
| USD/week → USD/year | USD/week × 52 | `annual = weekly × 52` |

### Derived Calculations

1. **Vessels Required**:
   ```
   vessels = ceil(service.cycle_time × frequency / 7)
   ```

2. **Service Revenue Potential**:
   ```
   max_revenue = service.capacity × utilization × revenue_per_teu × frequency
   where utilization = 0.5 (default assumption)
   ```

3. **Profit Margin**:
   ```
   margin_pct = profit / (profit + cost) × 100
   ```

4. **Coverage Percentage**:
   ```
   coverage = satisfied_demand / total_demand × 100
   ```

## Data Persistence

### Checkpoint Format

```python
checkpoint = {
    "problem": problem.__dict__,      # Serialized problem
    "iteration": int,                 # Current iteration
    "chromosomes": {                  # Current solutions
        region_id: chromosome
    },
    "weights": {                      # Current GA weights
        "profit_weight": float,
        "coverage_weight": float,
        "cost_weight": float
    },
    "timestamp": str,                 # ISO format timestamp
    "version": str                    # System version
}
```

### Export Formats

1. **CSV Export**:
   - Service selections
   - Flow allocations
   - Regional summaries

2. **JSON Export**:
   - Complete solution
   - Configuration
   - Audit trail

3. **Parquet Export**:
   - Large demand matrices
   - Distance matrices
   - Performance logs

## Data Privacy

### Sensitive Fields

The following fields may contain sensitive business information:
- `revenue_per_teu`: Customer pricing
- `weekly_cost`: Operational costs
- `handling_cost`: Port fees
- Demand volumes between specific ports

### Anonymization Options

1. **Port ID Mapping**:
   ```python
   port_map = {original_id: f"P{idx}" for idx, original_id in enumerate(port_ids)}
   ```

2. **Demand Scaling**:
   ```python
   scale_factor = total_demand / 1000000  # Scale to 1M TEU
   ```

3. **Cost Normalization**:
   ```python
   cost_benchmark = median(costs)
   normalized_costs = [c / cost_benchmark for c in costs]
   ```

## Performance Metrics

### Data Size Characteristics

| Instance | Ports | Services | Demands | Distance Matrix | Memory (MB) |
|----------|-------|----------|---------|-----------------|-------------|
| Small | 50 | 200 | 500 | 2,500 entries | ~10 |
| Medium | 200 | 800 | 2,000 | 40,000 entries | ~50 |
| Large | 435 | 1,200 | 9,600 | 189,225 entries | ~200 |

### Load Times

| Operation | Small | Medium | Large |
|-----------|-------|--------|-------|
| Load CSVs | 0.5s | 2s | 8s |
| Build graph | 0.2s | 1s | 3s |
| Validate | 0.1s | 0.5s | 2s |
| Total | 0.8s | 3.5s | 13s |

### Optimization

1. **Lazy Loading**: Load services only for active regions
2. **Sparse Matrices**: Use scipy.sparse for distance matrix
3. **Indexing**: Pre-compute port-to-service mappings
4. **Caching**: Cache expensive calculations