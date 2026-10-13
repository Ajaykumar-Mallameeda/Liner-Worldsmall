# Developer Guide - AI Vessel Routing System

## Quick Start

### Prerequisites

- Python 3.8+
- 8GB RAM minimum (16GB recommended for large instances)
- OpenRouter API key for LLM integration

### Installation

```bash
# Clone repository
git clone <repository-url>
cd shipping_optimizer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Running a Simple Optimization

```python
from src.agents.orchestrator_agent import OrchestratorAgent
from src.data.network_loader import NetworkLoader

# Load problem instance
loader = NetworkLoader()
problem = loader.load_world_large()

# Run optimization
orchestrator = OrchestratorAgent()
result = orchestrator.process({"problem": problem})

# View results
print(f"Annual Profit: ${result['summary_metrics']['annual_profit']:,.0f}")
print(f"Coverage: {result['summary_metrics']['coverage']:.1f}%")
print(f"Services: {result['summary_metrics']['total_services']}")
```

## Code Architecture

### Module Structure

```
src/
├── agents/                 # Multi-agent framework
│   ├── orchestrator_agent.py    # Master controller
│   ├── regional_agent.py        # Regional optimization
│   ├── coordinator_agent.py     # Conflict resolution
│   └── service_generator_agent.py # Service creation
├── optimization/           # Core algorithms
│   ├── hierarchical_ga.py       # Two-level genetic algorithm
│   ├── service_ga.py            # Service selection GA
│   ├── frequency_ga.py          # Frequency optimization GA
│   └── hub_milp.py              # Flow allocation MILP
├── data/                  # Data handling
│   ├── network_loader.py        # Load problem instances
│   ├── preprocess.py            # Data cleaning
│   └── graph_builder.py         # Network visualization
├── services/              # Service generation
│   ├── hub_detector.py          # Hub identification
│   └── candidate_service_generator.py
├── llm/                   # LLM integration
│   ├── evaluator.py             # LLM client wrapper
│   └── metrics.py               # Response validation
├── decomposition/         # Problem splitting
│   ├── port_clustering.py       # Geographic clustering
│   └── regional_splitter.py     # Demand assignment
└── utils/                 # Utilities
    ├── config.py               # Configuration management
    └── logger.py               # Structured logging
```

### Core Abstractions

#### Base Agent Class

```python
class BaseAgent:
    """Base class for all agents in the system"""
    
    def __init__(self, name: str, role: str, model: str):
        self.name = name
        self.role = role
        self.model = model
        
    def call_llm(self, prompt: str, temperature: float = 0.1) -> str:
        """Call LLM with error handling and retries"""
        
    def get_system_prompt(self) -> str:
        """Override to define agent-specific behavior"""
        
    def process(self, input_data: Dict) -> Dict:
        """Main entry point - override in subclasses"""
```

#### Problem Data Structure

```python
@dataclass
class Problem:
    ports: List[Port]
    services: List[Service]
    demands: List[Demand]
    distance_matrix: Dict[int, Dict[int, float]]
    
    # Runtime attributes
    profit_weight: float = 0.5
    coverage_weight: float = 0.4
    cost_weight: float = 0.1
    exploration_factor: float = 1.0
```

## Customization Guide

### Adding a New Regional Agent

```python
from src.agents.regional_agent import RegionalAgent

class CustomRegionalAgent(RegionalAgent):
    def __init__(self, name: str, region: str, model: str):
        super().__init__(name, region, model)
        
    def custom_optimization_step(self, problem: Problem):
        """Add custom logic before GA"""
        
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        # Custom preprocessing
        problem = input_data["problem"]
        problem = self.custom_optimization_step(problem)
        
        # Run standard pipeline
        result = super().process({"problem": problem})
        
        # Custom postprocessing
        result["custom_metrics"] = self.calculate_custom_metrics(result)
        return result
```

### Modifying GA Parameters

```python
from src.optimization.hierarchical_ga import HierarchicalGA

# Create custom GA configuration
ga = HierarchicalGA(
    problem,
    pop_size=120,           # Default: 80
    generations=200,        # Default: 120
    w_profit=0.6,          # Default: 0.5
    w_coverage=0.3,        # Default: 0.4
    w_cost=0.1,            # Default: 0.1
    max_runtime_sec=120.0, # Default: 60.0
)

result = ga.run()
```

### Custom Cost Functions

```python
from src.optimization.hub_milp import HubMILP

class CustomHubMILP(HubMILP):
    def _custom_cost_calculation(self, service, frequency):
        """Add custom cost components"""
        base_cost = service.weekly_cost * frequency
        carbon_cost = self.calculate_carbon_cost(service, frequency)
        risk_cost = self.calculate_risk_premium(service)
        return base_cost + carbon_cost + risk_cost
        
    def calculate_carbon_cost(self, service, frequency):
        # Implement carbon pricing
        pass
        
    def calculate_risk_premium(self, service):
        # Implement risk-based costing
        pass
```

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_regional_agent.py

# Run with coverage
pytest --cov=src tests/

# Run performance benchmarks
python benchmark_performance.py
```

### Test Data

Test instances are located in `tests/data/`:
- `small_instance.csv`: 50 ports, quick tests
- `medium_instance.csv`: 200 ports, integration tests
- `large_instance.csv`: 435 ports, performance tests

### Writing Custom Tests

```python
import unittest
from src.optimization.service_ga import ServiceGA
from tests.test_setup import create_test_problem

class TestCustomFeature(unittest.TestCase):
    def setUp(self):
        self.problem = create_test_problem(num_ports=20, num_demands=50)
        
    def test_service_selection(self):
        ga = ServiceGA(self.problem)
        result = ga.run()
        
        # Assertions
        self.assertGreater(result["fitness"], 0)
        self.assertEqual(len(result["services"]), len(self.problem.services))
        
    def test_fleet_constraint(self):
        # Test fleet constraint enforcement
        pass
```

## Performance Optimization

### Profiling

```python
import cProfile
import pstats

from src.agents.orchestrator_agent import OrchestratorAgent

def profile_optimization():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Run optimization
    orchestrator = OrchestratorAgent()
    result = orchestrator.process({"problem": problem})
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)  # Top 20 functions
    
if __name__ == "__main__":
    profile_optimization()
```

### Optimization Tips

1. **Service Filtering**:
   ```python
   # Adjust filtering threshold in RegionalAgent._filter_services
   margin_threshold = 0.3  # Default: 0.5
   ```

2. **MILP Time Limits**:
   ```python
   # Reduce for faster iterations
   milp = HubMILP(problem, chromosome, time_limit=60)
   ```

3. **Parallel Processing**:
   ```python
   # Run regions in parallel (advanced)
   from multiprocessing import Pool
   with Pool(3) as p:
       results = p.map(run_region, regional_problems)
   ```

## Debugging

### Logging Configuration

```python
import logging
from src.utils.logger import setup_logging

# Enable debug logging
setup_logging(level=logging.DEBUG)

# Component-specific logging
logger = logging.getLogger("src.agents.regional_agent")
logger.setLevel(logging.DEBUG)
```

### Common Issues

1. **MILP Infeasibility**:
   ```python
   # Check capacity constraints
   total_demand = sum(d.weekly_teu for d in problem.demands)
   total_capacity = sum(s.capacity for s in problem.services)
   print(f"Demand: {total_demand}, Capacity: {total_capacity}")
   ```

2. **Zero Services Selected**:
   ```python
   # Verify service margins
   for service in problem.services[:5]:
       margin = service.capacity * 0.5 * 150 - service.weekly_cost
       print(f"Service {service.id}: margin = ${margin:,.0f}")
   ```

3. **LLM API Errors**:
   ```python
   # Check API key and model
   from src.utils.config import Config
   print(f"API Key: {Config.OPENROUTER_API_KEY[:10]}...")
   print(f"Model: {Config.ORCHESTRATOR_MODEL}")
   ```

### Debug Mode

```python
# Run with additional diagnostics
orchestrator = OrchestratorAgent()
orchestrator.debug = True  # Enables extra logging
result = orchestrator.process({"problem": problem})

# Access internal state
for entry in orchestrator.iteration_audit:
    print(f"Iteration {entry['iteration']}: coverage={entry['coverage']:.1f}%")
```

## Data Formats

### Input Data Specification

#### Ports CSV
```csv
id,name,latitude,longitude,handling_cost,draft,port_call_cost
1001,Shanghai,31.2304,121.4737,15.0,15.5,50000
1002,Singapore,1.3521,103.8198,18.0,16.0,75000
```

#### Services CSV
```csv
id,capacity,weekly_cost,cycle_time,speed,fuel_cost,ports
S001,10000,150000,14,18,50000,"1001,1003,1005"
S002,8000,120000,10,20,40000,"1002,1004"
```

#### Demands CSV
```csv
origin,destination,weekly_teu,revenue_per_teu
1001,2001,5000,250
1002,2002,3000,275
```

### Output Data Format

```json
{
  "orchestrator": "orchestrator",
  "status": "complete",
  "summary_metrics": {
    "weekly_profit": 15000000,
    "annual_profit": 780000000,
    "coverage": 75.3,
    "total_services": 156
  },
  "regional_results": [
    {
      "region": "Asia",
      "weekly_profit": 8000000,
      "coverage_percent": 78.5,
      "services_selected": 85
    }
  ],
  "iteration_audit": [
    {
      "iteration": 0,
      "coverage": 65.2,
      "convergence_score": 0.45
    }
  ]
}
```

## API Reference

### Core Classes

#### OrchestratorAgent

```python
class OrchestratorAgent(BaseAgent):
    """Master controller for the optimization system"""
    
    def analyze_problem(self, problem: Problem) -> str:
        """Analyze network characteristics and complexity"""
        
    def aggregate_results(self, regional_results: List[Dict], 
                        true_global_demand: float) -> Dict:
        """Aggregate regional results into global metrics"""
        
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run complete optimization pipeline"""
```

#### RegionalAgent

```python
class RegionalAgent(BaseAgent):
    """Regional optimization agent"""
    
    def split_by_hubs(self, problem: Problem, 
                     num_hubs: int = 5) -> Dict:
        """Decompose region by hub clusters"""
        
    def _filter_services(self, problem: Problem) -> Problem:
        """Filter services by margin and coverage"""
        
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run regional optimization (GA + MILP)"""
```

#### HierarchicalGA

```python
class HierarchicalGA:
    """Two-level genetic algorithm for service selection"""
    
    def __init__(self, problem: Problem, **kwargs):
        """Initialize with configurable parameters"""
        
    def _filter_services(self) -> None:
        """Pre-filter services by profitability"""
        
    def run(self, seed_chromosome: dict = None) -> Dict[str, Any]:
        """Run hierarchical optimization"""
```

### Utility Functions

#### Network Loader

```python
class NetworkLoader:
    """Load problem instances from data files"""
    
    def load_world_large(self) -> Problem:
        """Load WorldLarge instance (435 ports)"""
        
    def load_custom(self, ports_file: str, services_file: str, 
                   demands_file: str) -> Problem:
        """Load custom instance"""
```

#### Hub Detector

```python
class HubDetector:
    """Identify hub ports based on demand patterns"""
    
    def detect_hubs(self, top_k: int = 10) -> List[int]:
        """Return top-k hub port IDs"""
```

## Best Practices

### Code Style

1. **Type Hints**: Use for all public APIs
2. **Docstrings**: Follow Google style with examples
3. **Logging**: Use structured logging with context
4. **Error Handling**: Graceful degradation with fallbacks

### Performance

1. **Lazy Loading**: Load data only when needed
2. **Memory Management**: Clear large objects after use
3. **Caching**: Cache expensive computations
4. **Profiling**: Profile before optimizing

### Testing

1. **Unit Tests**: Test individual components
2. **Integration Tests**: Test agent interactions
3. **Performance Tests**: Benchmark large instances
4. **Property Tests**: Verify invariants

### LLM Integration

1. **Structured Prompts**: Use templates for consistency
2. **Fallback Logic**: Rule-based when LLM fails
3. **Validation**: Check numeric citations in outputs
4. **Rate Limiting**: Respect API limits

## Troubleshooting

### Performance Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| Runtime > 10 minutes | Too many services | Increase service filtering |
| Memory error | Large distance matrix | Use sparse representation |
| MILP timeout | Too many transfer pairs | Reduce MAX_TRANSFER_PAIRS |

### Quality Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| Coverage < 50% | Insufficient service pool | Generate more candidate services |
| Negative profit | High costs vs revenue | Adjust cost parameters |
| Many conflicts | Regional overlap | Improve clustering |

### Integration Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| LLM API errors | Invalid API key | Check .env configuration |
| Missing ports | ID mismatch | Verify port IDs across files |
| Zero services | All filtered out | Lower margin threshold |

## Contributing

### Development Workflow

1. Fork repository
2. Create feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Update documentation
6. Submit pull request

### Code Review Checklist

- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Performance impact assessed
- [ ] Error handling implemented
- [ ] Logging added
- [ ] Type hints included