# Repository Restructuring Plan

## Recommended Target Structure

```
shipping_optimizer/
│
├── backend/                              # FastAPI + WebSocket layer
│   ├── main.py                           # Application entry point
│   ├── routes/
│   │   ├── optimization.py               # POST /api/optimize
│   │   ├── results.py                    # GET /api/results/{id}
│   │   └── health.py                     # GET /api/health
│   ├── websocket/
│   │   ├── manager.py                    # Connection registry
│   │   ├── events.py                     # EventValidator + schema
│   │   └── streamer.py                   # Broadcast logic
│   └── integration/
│       └── orchestrator_bridge.py        # Async bridge to optimization engine
│
├── optimization/                         # Core solver (was src/)
│   ├── agents/
│   │   ├── base.py
│   │   ├── orchestrator.py               # OrchestratorAgent
│   │   ├── regional.py                   # RegionalAgent
│   │   ├── coordinator.py                # CoordinatorAgent
│   │   └── service_generator.py
│   ├── solvers/
│   │   ├── hierarchical_ga.py
│   │   ├── service_ga.py
│   │   ├── frequency_ga.py
│   │   └── hub_milp.py
│   ├── decomposition/
│   │   ├── port_clustering.py
│   │   └── regional_splitter.py
│   ├── data/
│   │   ├── schema.py                     # Port, Service, Demand, Problem
│   │   ├── loader.py                     # NetworkLoader
│   │   └── preprocess.py
│   ├── services/
│   │   ├── hub_detector.py
│   │   └── candidate_generator.py
│   └── llm/
│       ├── client.py
│       ├── evaluator.py
│       └── metrics.py
│
├── datasets/                             # Benchmark data (git-ignored except samples)
│   ├── README.md                         # Data sourcing instructions
│   ├── raw/                              # WorldLarge CSVs (not tracked)
│   │   ├── ports.csv
│   │   ├── Demand_WorldLarge.csv
│   │   ├── fleet_WorldLarge.csv
│   │   └── dist_dense.csv
│   └── samples/                          # Small synthetic instances (tracked)
│       ├── small_10port.json
│       └── medium_50port.json
│
├── benchmarks/                           # Performance measurement
│   ├── README.md
│   ├── run_benchmarks.py                 # Benchmark runner
│   ├── results/                          # Stored benchmark outputs (git-tracked)
│   │   └── worldlarge_20250420.json
│   └── plots/                            # Convergence and performance charts
│       ├── convergence_curve.py
│       └── scalability_analysis.py
│
├── experiments/                          # Research experiments
│   ├── README.md
│   ├── weight_sensitivity/               # How GA weights affect coverage
│   ├── cluster_count_ablation/           # n_clusters = 3,4,5 comparison
│   └── milp_transfer_pair_scaling/       # MAX_TRANSFER_PAIRS sensitivity
│
├── deployment/                           # Infrastructure
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── k8s/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── configmap.yaml
│   └── scripts/
│       ├── health_check.sh
│       └── weekly_maintenance.sh
│
├── docs/                                 # All documentation
│   ├── SYSTEM_ARCHITECTURE.md
│   ├── DEVELOPER_GUIDE.md
│   ├── DATA_DICTIONARY.md
│   ├── RUNBOOK.md
│   ├── FAQ.md
│   └── diagrams/                         # Architecture diagram sources
│       └── system_overview.mermaid
│
├── tests/                                # Test suite
│   ├── unit/
│   │   ├── test_clustering.py
│   │   ├── test_ga.py
│   │   ├── test_milp.py
│   │   └── test_service_generation.py
│   ├── integration/
│   │   ├── test_regional_agent.py
│   │   └── test_orchestrator.py          # Full pipeline (slow)
│   └── conftest.py                       # Shared fixtures
│
├── scripts/                              # Operational scripts
│   ├── generate_sample_dataset.py        # Was src/utils/sample.py
│   ├── validate_data.py
│   └── profile_optimization.py
│
├── config/                               # Configuration
│   ├── default.env                       # Default values
│   └── production.env.example
│
├── frontend/                             # Dashboard (unchanged)
│
├── README.md
├── CONTRIBUTING.md
├── LICENSE
├── .gitignore
├── .env.example
├── requirements.txt
└── requirements-dev.txt
```

## Key Changes from Current Structure

| Current | Target | Reason |
|---------|--------|--------|
| `src/` | `optimization/` | Clearer top-level identity |
| `src/optimization/data.py` | `optimization/data/schema.py` | Separates schema from loader |
| `src/utils/sample.py` | `scripts/generate_sample_dataset.py` | Not a utility — it's a CLI script |
| `src/pipeline/*.py` (empty) | deleted | Dead code |
| `SYSTEM_ARCHITECTURE_ANALYSIS.md` (root) | `docs/` | Belongs in documentation |
| `ARCHITECTURE_AUDIT_REPORT.md` (root) | `docs/` | Belongs in documentation |
| `data/` flat | `datasets/raw/` + `datasets/samples/` | Clear distinction between tracked and untracked |
| no `benchmarks/` | `benchmarks/` | Adds research credibility signal |
| no `experiments/` | `experiments/` | Adds research credibility signal |

## Files to Delete

- `src/pipeline/optimization_pipeline.py` (empty)
- `src/pipeline/orchestration.py` (empty)

## Files to Add

- `datasets/samples/small_10port.json` — synthetic 10-port instance for fast testing
- `benchmarks/run_benchmarks.py` — performance measurement runner
- `scripts/generate_sample_dataset.py` — moved from src/utils/sample.py
- `requirements-dev.txt` — separate dev dependencies (pytest, black, mypy, ruff)
- `LICENSE` — MIT
- `CONTRIBUTING.md` — contribution guide

## .gitignore Improvements

Add to `.gitignore`:
```
# Data (too large for git)
datasets/raw/
data/raw/
*.csv
*.parquet

# Results and logs
logs/
results/
pipeline_output.json

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/
dist/
*.egg-info/

# Environment
.env
!.env.example

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```
