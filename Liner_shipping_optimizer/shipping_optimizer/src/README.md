# AI Vessel Routing System - Documentation

## Overview

The AI Vessel Routing System is a sophisticated multi-agent optimization framework designed for global liner shipping networks. It combines Genetic Algorithms (GA), Mixed-Integer Linear Programming (MILP), Large Language Models (LLMs), and multi-agent coordination to optimize vessel deployment, service selection, and cargo flow allocation.

## System Capabilities

- **Scale**: Optimizes networks with 435 ports, ~1,200 services, 9,600 demand lanes
- **Multi-objective**: Balances profit maximization, demand coverage, and cost minimization
- **Hybrid Optimization**: Combines GA for combinatorial selection with MILP for flow optimization
- **Intelligent Coordination**: LLM-driven strategic decisions and conflict resolution
- **Iterative Refinement**: Feedback loop with automatic weight adjustment

## Documentation Structure

### Core Documentation
- **[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)**: Complete system overview, architecture, and design decisions
- **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)**: Developer onboarding, API reference, and code examples
- **[DATA_DICTIONARY.md](DATA_DICTIONARY.md)**: Data structures, file formats, and specifications
- **[RUNBOOK.md](RUNBOOK.md)**: Operational procedures, troubleshooting, and maintenance
- **[FAQ.md](FAQ.md)**: Frequently asked questions and common issues

## Quick Start

### Prerequisites
- Python 3.8+
- 8GB RAM minimum (16GB recommended)
- OpenRouter API key for LLM integration

### Installation
```bash
# Clone and setup
git clone <repository-url>
cd shipping_optimizer
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your OpenRouter API key
```

### Run Basic Optimization
```python
from src.agents.orchestrator_agent import OrchestratorAgent
from src.data.network_loader import NetworkLoader

# Load and optimize
loader = NetworkLoader()
problem = loader.load_world_large()
result = OrchestratorAgent().process({"problem": problem})

# View results
print(f"Annual Profit: ${result['summary_metrics']['annual_profit']:,.0f}")
print(f"Coverage: {result['summary_metrics']['coverage']:.1f}%")
print(f"Services: {result['summary_metrics']['total_services']}")
```

## System Architecture at a Glance

```
┌─────────────────────┐
│  ORCHESTRATOR       │  ← Master controller, problem analysis
└─────────┬───────────┘
          │
┌─────────▼───────────┐
│  REGIONAL SPLITTER  │  ← Decompose by geography
└─────────┬───────────┘
          │
    ┌─────┴─────┐
    │           │
┌───▼───┐   ┌───▼───┐
│ASIA   │   │EUROPE │  ← Parallel regional optimization
└───┬───┘   └───┬───┘
    │           │
    └─────┬─────┘
          │
┌─────────▼───────────┐
│  COORDINATOR        │  ← Conflict resolution, feedback
└─────────────────────┘
```

## Key Features

### 1. Hierarchical Optimization
- **Level 1 - Service Selection GA**: Chooses which services to operate
- **Level 2 - Frequency GA**: Determines sailing frequency (1-3 per week)
- **MILP Flow Optimization**: Allocates cargo flow with transshipment

### 2. Multi-Agent Coordination
- **3 Regional Agents**: Asia, Europe, Americas
- **Global Coordinator**: Resolves cross-regional conflicts
- **Iterative Feedback**: Up to 3 iterations with weight tuning

### 3. Service Generation
- **Direct Services**: Point-to-point for high-demand corridors
- **Hub Loops**: Regional services via hub ports
- **Trunk Routes**: Backbone between major hubs
- **Feeder Services**: Spoke-to-hub connections

### 4. Intelligent Decision Making
- **LLM Analysis**: Network complexity assessment
- **Automatic Weight Tuning**: Profit/Coverage/Cost balance
- **Strategic Explanations**: Human-readable insights

## Performance Characteristics

| Instance Size | Ports | Services | Runtime | Memory |
|--------------|-------|----------|---------|--------|
| Small        | 50    | 200      | <1 min  | 10MB   |
| Medium       | 200   | 800      | 3-5 min | 50MB   |
| Large        | 435   | 1,200    | 5-10 min| 200MB  |

## Output Metrics

The system provides comprehensive metrics including:
- **Financial**: Weekly/annual profit, profit margin, cost breakdown
- **Operational**: Services deployed, vessels required, fleet utilization
- **Service Level**: Demand coverage, satisfied TEU, transshipment rates
- **Quality**: Convergence score, iteration count, conflict resolution

## Configuration

Key tunable parameters:
- **GA**: Population size (80), generations (120), weights
- **MILP**: Time limit (120s), transfer pairs (2000)
- **System**: Fleet size (300), coverage target (70%), max iterations (3)

## Support

- **Documentation**: See docs/ folder for detailed guides
- **Issues**: Report bugs via GitHub issues
- **FAQ**: Check [FAQ.md](FAQ.md) for common questions
- **Runbook**: See [RUNBOOK.md](RUNBOOK.md) for operational procedures

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Update documentation
6. Submit a pull request

See [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) for detailed contribution guidelines.

## License

[Add license information here]

---

**Last Updated**: 2026-04-23
**Version**: 1.0
**Documentation Version**: 1.0