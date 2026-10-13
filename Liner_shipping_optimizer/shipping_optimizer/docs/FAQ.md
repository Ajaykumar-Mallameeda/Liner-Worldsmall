# Frequently Asked Questions - AI Vessel Routing System

## General Questions

### Q: What problem does this system solve?

A: The AI Vessel Routing System optimizes global liner shipping networks by determining:
- Which shipping services to operate (from thousands of candidates)
- How frequently each service should sail
- How to allocate cargo flow across the network
- Where to use hub transshipment vs direct routing

It balances competing objectives of maximizing profit, maximizing demand coverage, and minimizing costs while respecting real-world constraints like fleet size limits.

### Q: How does it compare to traditional optimization methods?

A: Traditional approaches typically use either:
1. **Pure MILP**: Precise but doesn't scale to large networks
2. **Pure heuristics**: Fast but may miss optimal solutions
3. **Manual planning**: Based on experience but not systematic

Our hybrid approach combines:
- **Genetic Algorithms**: For combinatorial service selection
- **MILP**: For precise flow allocation
- **LLMs**: For strategic decision-making
- **Multi-agent decomposition**: For scalability

This gives us the scalability of heuristics with the precision of mathematical optimization.

### Q: What scale of problems can it handle?

A: The system is designed for:
- **Small**: ~50 ports, 500 services, <1 minute
- **Medium**: ~200 ports, 800 services, 3-5 minutes  
- **Large**: ~435 ports, 1,200 services, 5-10 minutes

The regional decomposition allows it to handle even larger networks by splitting them geographically.

## Technical Questions

### Q: Why use Genetic Algorithms instead of just MILP?

A: Service selection is a combinatorial problem with:
- Binary decisions (use service or not)
- Thousands of candidates
- Complex interactions between services

Pure MILP would have:
- ~1,200 binary variables
- Exponential solution time
- Difficulty finding good initial solutions

GA provides:
- Fast exploration of solution space
- Natural handling of binary encoding
- Ability to escape local optima

### Q: What's the role of LLMs in the system?

A: LLMs (Large Language Models) are used strategically for:
1. **Network Analysis**: Understanding complexity and decomposition strategy
2. **Weight Tuning**: Adjusting optimization weights based on results
3. **Explanations**: Generating human-readable analysis of solutions
4. **Decision Making**: Evaluating trade-offs when metrics conflict

They are NOT used for the core mathematical optimization - that's handled by GA and MILP.

### Q: How does the multi-agent system work?

A: The system uses three types of agents:

1. **Orchestrator Agent**: 
   - Master controller
   - Analyzes the global problem
   - Coordinates regional agents
   - Aggregates results

2. **Regional Agents** (3 of them):
   - Each handles a geographic region (Asia, Europe, Americas)
   - Runs local GA+MILP optimization
   - Returns regional solution

3. **Coordinator Agent**:
   - Detects conflicts between regions
   - Resolves service overlaps
   - Generates feedback for next iteration

### Q: How does the feedback loop work?

A: The system iterates up to 3 times:

1. **Initial Run**: Default weights (profit: 50%, coverage: 40%, cost: 10%)
2. **Analysis**: Coordinator evaluates results
3. **Adjustment**: If needed, weights are tuned based on gaps:
   - Low coverage → increase coverage weight
   - Low profit → increase profit weight
   - Many conflicts → adjust exploration
4. **Re-run**: Regional agents use new weights
5. **Convergence**: Stops when coverage improves <1% or max iterations reached

## Data Questions

### Q: What data inputs are required?

A: Four CSV files are required:

1. **ports.csv**: Port locations and costs
   ```
   id,name,latitude,longitude,handling_cost,draft,port_call_cost
   ```

2. **services.csv**: Candidate shipping routes
   ```
   id,capacity,weekly_cost,cycle_time,speed,fuel_cost,ports
   ```

3. **demands.csv**: Cargo demand between ports
   ```
   origin,destination,weekly_teu,revenue_per_teu
   ```

4. **dist_dense.csv**: Distances between ports
   ```
   origin,destination,distance_nm
   ```

### Q: Where does the service data come from?

A: Services are generated algorithmically based on:
1. **Direct routes**: Top-500 high-demand corridors
2. **Hub loops**: Hub + regional spokes
3. **Hub-to-hub**: Backbone between major hubs
4. **Feeders**: Spoke-to-hub connections
5. **Heuristics**: Algorithmic candidates

This ensures a comprehensive candidate pool covering different service archetypes.

### Q: How are hub ports identified?

A: Hubs are identified by:
1. **Demand Volume**: Total TEU moving through the port
2. **Connectivity**: Number of direct services
3. **Geographic Position**: Centrality in network

The system uses a scoring algorithm that weights these factors to identify the top 20 hubs.

### Q: What if my data is incomplete?

A: The system has fallbacks:
- **Missing distances**: Use great circle calculation
- **Missing costs**: Apply defaults (handling: $15/TEU, port call: $50K)
- **Missing ports**: Can't run - all ports must be defined
- **Missing services**: Generate automatically using heuristics

## Configuration Questions

### Q: How do I tune the GA parameters?

A: Key parameters and their effects:

| Parameter | Default | Effect of Increasing | Effect of Decreasing |
|-----------|---------|---------------------|---------------------|
| pop_size | 80 | Better solutions, slower | Faster, lower quality |
| generations | 120 | More optimization, slower | Faster, less refined |
| w_profit | 0.5 | Prioritize profit | Prioritize coverage/cost |
| w_coverage | 0.4 | Higher demand coverage | May miss profitable routes |
| w_cost | 0.1 | Lower operating costs | Higher operating costs |

For quick tests: reduce pop_size to 40, generations to 60
For quality: increase pop_size to 120, generations to 180

### Q: How do I adjust the fleet size constraint?

A: The fleet size is hardcoded at 300 vessels. To change it:

1. **Temporary change**:
   ```python
   # In hub_milp.py
   HubMILP.fleet_size = 250  # New limit
   ```

2. **Permanent change**:
   ```python
   # Add to config.py
   FLEET_SIZE = int(os.getenv("FLEET_SIZE", "300"))
   ```

3. **Runtime adjustment**:
   ```python
   problem.fleet_size = 350  # For specific problem
   ```

### Q: Can I add more regions?

A: Yes, but requires code changes:

1. **Update orchestrator**:
   ```python
   self.regional_agents: List[RegionalAgent] = [
       RegionalAgent("regional_asia", "Asia", Config.REGIONAL_MODEL),
       RegionalAgent("regional_europe", "Europe", Config.REGIONAL_MODEL),
       RegionalAgent("regional_americas", "Americas", Config.REGIONAL_MODEL),
       RegionalAgent("regional_africa", "Africa", Config.REGIONAL_MODEL),  # New
   ]
   ```

2. **Update clustering**:
   ```python
   clustering = PortClustering(n_clusters=len(self.regional_agents))
   ```

3. **Consider performance**: More regions = more parallelism but smaller problems per region

## Performance Questions

### Q: Why is my optimization running slowly?

A: Common causes and fixes:

1. **Too many services** (>2000):
   - Increase service filtering threshold
   - Remove low-margin services
   
2. **Too many transfer pairs**:
   - Reduce MAX_TRANSFER_PAIRS from 2000
   - Filter low-demand hubs
   
3. **MILP struggling**:
   - Reduce time limit per cluster
   - Skip MILP for low-coverage chromosomes
   
4. **Memory pressure**:
   - Use sparse matrices for distances
   - Process regions sequentially

### Q: Can I run optimizations in parallel?

A: Yes, at two levels:

1. **Regional Parallelism** (built-in):
   - Each region runs independently
   - Limited by 3 regions in current design
   
2. **Instance Parallelism** (external):
   ```python
   from multiprocessing import Pool
   
   def run_optimization(instance_data):
       return orchestrator.process(instance_data)
   
   with Pool(4) as p:
       results = p.map(run_optimization, instances)
   ```

### Q: How can I speed up the MILP solver?

A: Strategies for faster MILP:

1. **Reduce variables**:
   - Fewer transfer pairs
   - Aggregate small demands
   
2. **Better bounds**:
   - Provide warm starts from previous runs
   - Use heuristic initial solution
   
3. **Solver settings**:
   ```python
   # In hub_milp.py
   solver = pulp.PULP_CBC_CMD(
       msg=0,
       timeLimit=60,        # Shorter time
       maxSeconds=60,
       threads=4           # Use more threads
   )
   ```

## Troubleshooting Questions

### Q: Why am I getting negative profit?

A: Common causes:

1. **Costs too high**:
   - Check service.weekly_cost values
   - Verify revenue_per_teu > costs
   
2. **Penalties too high**:
   - Reduce ALPHA_UNSERVED from 300
   - Check transship_cost_per_teu
   
3. **Poor service selection**:
   - Services don't match demand patterns
   - Generate more relevant candidates

Debug with:
```python
for service in problem.services[:5]:
    margin = service.capacity * 0.5 * 150 - service.weekly_cost
    print(f"Service {service.id}: margin=${margin:,.0f}")
```

### Q: Why is coverage so low?

A: Possible reasons:

1. **Insufficient services**:
   - Not enough candidates to cover all demand
   - Services don't connect the right ports
   
2. **Capacity constraints**:
   - Fleet too small for demand volume
   - Individual services too small
   
3. **Geographic gaps**:
   - Some ports not connected to network
   - Hub and spoke not reaching remote ports

Check:
```python
# Verify port connectivity
connected_ports = set()
for service in problem.services:
    connected_ports.update(service.ports)
    
unconnected = set(p.id for p in problem.ports) - connected_ports
print(f"Unconnected ports: {unconnected}")
```

### Q: What does "MILP infeasible" mean?

A: The MILP found no feasible solution when:
1. Demand exceeds total capacity
2. Fleet size too small for selected services
3. Conflicting constraints

Fixes:
- Increase fleet size
- Select more services
- Reduce demand (or use penalty)
- Relax capacity constraints

## Integration Questions

### Q: Can I integrate with my existing system?

A: Yes, through these interfaces:

1. **CSV Files**: Direct data exchange
2. **Python API**: Programmatic control
3. **JSON Output**: Standardized results
4. **REST API**: Can be wrapped (not provided)

Example integration:
```python
# Your system -> Optimizer
problem = create_problem_from_your_data()
result = orchestrator.process({"problem": problem})

# Optimizer -> Your system
deploy_plan = extract_deployment_plan(result)
your_system.deploy(deploy_plan)
```

### Q: How do I use custom cost models?

A: Extend the cost calculation:

```python
class CustomHubMILP(HubMILP):
    def _calculate_operating_cost(self, service, frequency):
        base_cost = service.weekly_cost * frequency
        # Add your custom costs
        carbon_cost = self.carbon_pricing * service.fuel_cost
        crew_cost = self.crew_cost_model(service, frequency)
        return base_cost + carbon_cost + crew_cost
```

### Q: Can I add custom constraints?

A: Yes, in several ways:

1. **Service filtering** (pre-optimization):
   ```python
   def filter_by_custom_rule(services):
       return [s for s in services if meets_custom_criteria(s)]
   ```

2. **MILP constraints** (during optimization):
   ```python
   # In HubMILP.solve()
   # Add your constraint
   prob += custom_constraint_expr <= limit
   ```

3. **Post-processing** (after optimization):
   ```python
   def apply_business_rules(solution):
       # Adjust solution to meet rules
       return adjusted_solution
   ```

## Advanced Questions

### Q: How does the system handle uncertainty?

A: Current implementation is deterministic. For uncertainty:

1. **Scenario analysis**:
   ```python
   scenarios = [
       {"demand_multiplier": 0.8, "name": "low_demand"},
       {"demand_multiplier": 1.0, "name": "base"},
       {"demand_multiplier": 1.2, "name": "high_demand"}
   ]
   ```

2. **Robust optimization**:
   - Minimize worst-case performance
   - Use safety margins in capacity

3. **Stochastic programming**:
   - Would require major redesign
   - Multiple demand scenarios with probabilities

### Q: Can it optimize for carbon emissions?

A: Yes, add carbon cost:

```python
# Add carbon pricing to costs
CARBON_PRICE_PER_TON = 50  # $/ton CO2

def calculate_emission_cost(service):
    # Simplified: fuel proportional to distance
    fuel_tons = service.fuel_cost / 700  # $700/ton fuel
    co2_tons = fuel_tons * 3.1  # Emission factor
    return co2_tons * CARBON_PRICE_PER_TON
```

Then include in objective function.

### Q: How is the system validated?

A: Validation happens at multiple levels:

1. **Unit Tests**: Individual components
2. **Integration Tests**: Agent interactions
3. **Performance Tests**: Runtime benchmarks
4. **Quality Checks**: Result thresholds
5. **Historical Validation**: Compare to actual deployments

Run validation with:
```bash
pytest tests/
python benchmark_performance.py
python validate_data.py
```

## Support Questions

### Q: Where can I get help?

A: Support resources:
1. **Documentation**: Check docs/ folder first
2. **Issues**: GitHub issues for bugs
3. **Email**: optimizer-support@company.com
4. **Community**: Internal chat channel

### Q: How do I report a bug?

A: Include in your report:
1. System info (OS, Python version)
2. Input data size (ports, services, demands)
3. Error message and stack trace
4. Steps to reproduce
5. Expected vs actual behavior

Template:
```
Bug: [Brief description]
System: [Windows/Linux/Mac], Python [X.Y]
Input: [N] ports, [M] services
Error: [Paste error here]
Repro: [Steps to cause bug]
Expected: [What should happen]
```

### Q: How can I contribute?

A: Ways to contribute:
1. **Code improvements**: Fork, branch, PR
2. **Bug fixes**: Follow bug report template
3. **Documentation**: Improve docs and examples
4. **Test cases**: Add coverage for edge cases
5. **Performance**: Profile and optimize

See DEVELOPER_GUIDE.md for details.