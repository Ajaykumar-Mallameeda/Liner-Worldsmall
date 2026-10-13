<div align="center">

# AI Vessel Routing System

### Multi-Agent Liner Shipping Optimizer

[![Version](https://img.shields.io/badge/version-1.0.0--rc1-blue)](https://github.com)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![React](https://img.shields.io/badge/react-18.2-61DAFB)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Build](https://img.shields.io/badge/build-passing-success)](https://github.com)
[![Assertions](https://img.shields.io/badge/assertions-309%2F313-98.7%25-success)](Analysis/V1_BACKEND_FREEZE_CERTIFICATION.md)
[![AI](https://img.shields.io/badge/AI-100%25_Coordinator-violet)](Analysis/AI_INFLUENCE_VERIFICATION_REPORT.md)
[![Contributing](https://img.shields.io/badge/contributing-guide-orange)](CONTRIBUTING.md)
[![Citation](https://img.shields.io/badge/citation-cff-blue)](CITATION.cff)

---

[Architecture](#-architecture) • [Pipeline](#-optimization-pipeline) • [Dashboard](#-dashboard) • [Quick Start](#-quick-start) • [Benchmarks](#-benchmarks) • [Documentation](#-documentation)

---

</div>

## 🚢 Executive Summary

**Demand:** Global liner shipping networks carry over 2 billion tonnes of cargo annually, yet route planning remains a combinatorial optimization problem of extraordinary complexity — planning container vessel routes across **435 ports**, **9,622 origin-destination lanes**, and a fleet of vessels with different capacities, speeds, and operating costs.

**Solution:** The AI Vessel Routing System combines **hierarchical genetic algorithms (GA)**, **mixed-integer linear programming (MILP)**, and **multi-agent LLM coordination** to produce optimized weekly service networks with profit-maximizing route assignments, fleet deployment, and frequency scheduling.

**Result:** A production-grade system that generates on average of **$450.7M/week** in optimized profit across **~400+ services** deployed in **5 global regions**, with **+-52% demand coverage** and **3-iteration convergence**.

```
┌─────────────────────────────────────────────────────────────┐
│          AI VESSEL ROUTING OPTIMIZER — SYSTEM OVERVIEW       │
├───────────────┬───────────────┬───────────────┬──────────────┤
│   435 Ports   │  9,622 Lanes  │  400+ Services│ on avg$450.7M/wk│
│  5 Regions    │  5 Vessel cls │  3 Iterations │ 98.7% Score │
└───────────────┴───────────────┴───────────────┴──────────────┘
```

---

## 👁️ Dashboard

<div align="center">
  <img src="assets/dashboard/overview-dashboard.png" alt="Executive Dashboard" width="90%"/>
  <p><em>Executive Operations Console — 14-tab dashboard with real-time runtime data</em></p>
</div>

The operations dashboard provides **14 interactive tabs** covering fleet management, route exploration, port intelligence, optimization monitoring, and executive reporting. All data originates from a single runtime truth source (`pipeline_output.json`).

> *See the full [Dashboard Gallery](docs/PROJECT_GALLERY.md) and [Screenshots Index](docs/SCREENSHOTS.md) for all 14 views.*

## 🖼 Dashboard Gallery

<div align="center">
  <img src="assets/dashboard/overview-dashboard.png" alt="Overview" width="45%"/>
  <img src="assets/dashboard/fleet-explorer.png" alt="Fleet Explorer" width="45%"/>
  <br/>
  <img src="assets/dashboard/route-explorer.png" alt="Route Explorer" width="45%"/>
  <img src="assets/dashboard/regional-agents.png" alt="Regional Agents" width="45%"/>
  <br/>
  <img src="assets/dashboard/pipeline-visualization.png" alt="Pipeline" width="45%"/>
  <img src="assets/dashboard/ga-milp-analytics.png" alt="GA-MILP Analytics" width="45%"/>
  <br/>
  <img src="assets/dashboard/maritime-map.png" alt="Maritime Map" width="45%"/>
  <img src="assets/dashboard/executive-summary.png" alt="Executive Summary" width="45%"/>
  <p><em>Dashboard gallery — 8 primary views. See <a href="docs/PROJECT_GALLERY.md">full gallery</a> for all 14 tabs.</em></p>
</div>

---

## 🏗 Architecture

<div align="center">
  <img src="assets/architecture/system-architecture.svg" alt="System Architecture" width="95%"/>
  <p><em>Complete system architecture — from data sources to production dashboard. <a href="assets/architecture/system-architecture.svg">Download SVG</a> (open in browser for full resolution)</em></p>
</div>

```
                    ┌─────────────────────────────────────┐
                    │         FastAPI + WebSocket          │
                    │         API Gateway Layer            │
                    └──────────────────┬──────────────────┘
                                       │
                    ┌──────────────────▼──────────────────┐
                    │        Orchestrator Agent            │
                    │   Iteration Loop · Weight Tuning    │
                    │   Convergence Detection · Feedback   │
                    └──────┬────────────────────┬─────────┘
                           │                    │
              ┌────────────▼──────┐    ┌───────▼────────────┐
              │  Coordinator AI   │    │  Consensus Engine   │
              │  LLM Decisions    │    │  Weight Voting      │
              │  Conflict Detect  │    │  Confidence Scoring │
              └────────┬─────────┘    └───────┬────────────┘
                       │                      │
              ┌────────▼──────────────────────▼────────────┐
              │        5 Regional Agents (Parallel)         │
              │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌───┐ │
              │  │ Asia │ │Europe│ │Amer. │ │MEast │ │Afr │ │
              │  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └─┬─┘ │
              │     │         │        │        │        │    │
              │  ┌──▼─────────▼────────▼────────▼────────▼─┐ │
              │  │       Service Generator + Validators    │ │
              │  └────────────────┬────────────────────────┘ │
              └───────────────────┼──────────────────────────┘
                                  │
              ┌───────────────────▼──────────────────────────┐
              │     Hierarchical GA · Frequency GA · MILP   │
              │     Bi-level Optimization Stack              │
              └───────────────────┬──────────────────────────┘
                                  │
              ┌───────────────────▼──────────────────────────┐
              │         Runtime Truth (pipeline_output.json)  │
              │         ←───────────────────→                │
              │         Frontend Dashboard                   │
              │         33 Components · 14 Tabs              │
              └──────────────────────────────────────────────┘
```

---

## 🔄 Optimization Pipeline

<div align="center">
  <img src="assets/architecture/optimization-pipeline.svg" alt="Optimization Pipeline" width="70%"/>
  <p><em>13-stage optimization pipeline — from input data through GA, MILP, and AI coordination to dashboard.</em></p>
</div>

### Stage Details

```
Demand Matrix (9,622 OD lanes)     Fleet Database (6 vessel classes)
         │                                      │
         └──────────────┬───────────────────────┘
                        ▼
            ┌─────────────────────┐
            │  Service Generator  │  → Generates 781-875 candidate services per region
            │  Agent              │
            └──────────┬──────────┘
                       ▼
            ┌─────────────────────┐
            │  Regional Agents     │  → Parallel execution across 5 regions
            │  (ThreadPoolExecutor)│
            └──────────┬──────────┘
                       ▼
            ┌─────────────────────┐
            │  Hierarchical GA     │  → Layer 1: Service selection optimization
            │  (Genetic Algorithm) │  → Layer 2: Frequency optimization
            └──────────┬──────────┘
                       ▼
            ┌─────────────────────┐
            │  Consensus Engine    │  → Weight reconciliation across regions
            │  (Weighted Voting)   │  → Archetype parameter agreement
            └──────────┬──────────┘
                       ▼
            ┌─────────────────────┐
            │  MILP Optimizer      │  → Hub MILP decomposition
            │  (Flow Optimization) │  → Final service selection
            └──────────┬──────────┘
                       ▼
            ┌─────────────────────┐
            │  Coordinator Agent   │  → LLM evaluation: coverage, profit, conflicts
            │  (GPT-OSS-120B)      │  → Adaptive weight adjustment
            └──────────┬──────────┘
                       │
              ┌────────▼────────┐    ┌────────────┐
              │  Converged?     │───→│  No → Rerun │
              │  Score ≥ 0.97   │    │  (max 3 it) │
              └────────┬────────┘    └────────────┘
                       │ Yes
                       ▼
            ┌─────────────────────┐
            │  Runtime Truth       │  → pipeline_output.json
            │  (309/313 Assertions)│  → All KPIs synchronized
            └─────────────────────┘
```

---

## 🤖 Multi-Agent AI Architecture

<div align="center">
  <img src="assets/architecture/multi-agent-architecture.svg" alt="Multi-Agent AI Architecture" width="80%"/>
  <p><em>LLM-coordinated multi-agent system — Coordinator Agent + 5 Regional Agents + Consensus + Validators.</em></p>
</div>

### Agent Interaction

```
                    ┌──────────────────────────────────┐
                    │    Coordinator Agent (LLM)        │
                    │  ┌────────────────────────────┐  │
                    │  │ Problem Analysis            │  │
                    │  │ Weight Adjustment           │  │
                    │  │ Conflict Detection          │  │
                    │  │ Convergence Evaluation       │  │
                    │  └──────────┬─────────────────┘  │
                    └─────────────┼────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
┌──────────────────┐  ┌────────────────────┐  ┌──────────────────┐
│ Weight Validator │  │Archetype Validator │  │Regional Validator│
│ Weights ∈ [0,1]  │  │ Mix ratios sum=1   │  │ Policy schema OK │
└────────┬─────────┘  └─────────┬──────────┘  └────────┬─────────┘
         │                      │                       │
         └──────────────────────┼───────────────────────┘
                                ▼
                    ┌──────────────────────┐
                    │   Consensus Engine    │
                    │  │ Weighted Voting │ │
                    │  │ Conflict Resol. │ │
                    │  │ Confidence Score│ │
                    └──────────────────────┘
```

**AI Integration Metrics:**
- **Coordinator**: 100% AI-generated decisions across all iterations (verified: `coordinator_ai_generated=true`, `coordinator_fallback_count=0`)
- **LLM Calls**: 8 total (3 coordinator + validation)
- **Consensus**: 100% confidence score, all conflicts resolved
- **Service Generator**: Algorithmic fallback (documented — API timeout on free-tier model; production-quality defaults)

---

## 📊 Benchmarks

*Full benchmark details in [docs/BENCHMARKS.md](docs/BENCHMARKS.md)*

### Optimization Performance

| Metric | Value |
|---|---|
| **Ports in Network** | 435 |
| **Origin-Destination Lanes** | 9,622 |
| **Services Deployed** | 400+ |
| **Vessel Classes** | 5 (Feeder 450/800, Panamax, Post-Panamax, Super-Panamax) |
| **Total Fleet Capacity** | 1,655,500 TEU/wk |
| **Fleet Utilization** | 97.7% |
| **Demand Coverage** | 52.5% |
| **Weekly Profit** | **$450.7 million on avg** |
| **Annual Profit (52wk)** | **~$30 billion** |
| **Profit Margin** | 20-35% |
| **Revenue** | $2.84 billion/wk |

### Runtime & Quality

| Metric | Value |
|---|---|
| **Optimization Runtime** | 499.3s (~8 minutes) |
| **Feedback Iterations** | 3 (converged) |
| **Convergence Score** | 0.977 |
| **Consensus Confidence** | 1.0 (100%) |
| **Test Assertions** | 309/313 = **98.7%** |
| **Test Warnings** | 4 |
| **Region Success Rate** | 100% |

### AI Activity

| Metric | Value |
|---|---|
| **Coordinator AI Decisions** | 100% (3/3 iterations) |
| **LLM Calls** | 8 |
| **JSON Parse Success** | 3/3 |
| **Validator Executions** | 3/3 |
| **AI Fallbacks (Coordinator)** | 0 |
| **Service Gen Regions** | 5 (all algorithmic fallback) |

### Frontend

| Metric | Value |
|---|---|
| **Build Time** | 2.3s |
| **Bundle Size (JS)** | 394 KB (118 KB gzipped) |
| **Bundle Size (CSS)** | 17 KB |
| **Components** | 33 |
| **Navigation Tabs** | 14 |
| **Build Warnings** | 0 |
| **Runtime Truth Accuracy** | 100% |

---

## 📂 Repository Structure

```
shipping_optimizer/
├── src/                              # Backend — Python optimization engine
│   ├── agents/                       # Multi-agent AI system
│   │   ├── coordinator_agent.py      # LLM-driven decision agent
│   │   ├── orchestrator_agent.py     # Pipeline iteration controller
│   │   ├── regional_agent.py         # Per-region GA + MILP runner
│   │   └── service_generator_agent.py
│   ├── optimization/                 # OR algorithms
│   │   ├── hierarchical_ga.py        # Bi-level genetic algorithm
│   │   ├── hub_milp.py               # MILP flow optimizer
│   │   ├── frequency_ga.py           # Service frequency GA
│   │   └── service_ga.py             # Service selection GA
│   ├── validation/                   # Runtime validation framework
│   │   ├── consensus_engine.py       # Weighted voting consensus
│   │   ├── weight_validator.py       # Weight normalization
│   │   └── archetype_validator.py    # Archetype parameter validation
│   ├── decomposition/                # Regional decomposition
│   │   ├── regional_splitter.py      # K-means port clustering
│   │   └── port_clustering.py
│   ├── llm/                          # LLM integration
│   │   ├── client.py                 # GPT-OSS-120B client
│   │   └── evaluator.py              # Prompt-based evaluation
│   ├── pipeline/                     # Pipeline orchestration
│   │   └── optimization_pipeline.py  # Main pipeline entry
│   └── config/                       # Configuration
├── frontend/src/                     # Frontend — React dashboard
│   ├── views/                        # App orchestrator
│   ├── components/                   # 33 React components
│   │   ├── common/                   # UI primitives (5)
│   │   ├── layout/                   # Shell components (4)
│   │   ├── overview/                 # Intelligence panels (5)
│   │   ├── regions/                  # Regional views (3)
│   │   ├── optimization/             # Optimization views (12)
│   │   └── map/                      # Maritime map (1)
│   ├── hooks/                        # useOptimizationState
│   ├── runtime/                      # runtimeAdapter
│   ├── services/                     # apiClient + websocketManager
│   └── utils/                        # Formatters + fleetStats
├── pipeline_output.json              # Runtime truth — single source
├── docs/                             # Architecture documentation
├── assets/                           # Screenshots and diagrams
├── *.md                              # 14 certification/report files
├── requirements.txt                  # Python dependencies
└── frontend/package.json             # Node dependencies
```

---

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.11+ for backend
python --version

# Node.js 18+ for frontend
node --version
npm --version
```

### Backend Setup

```bash
cd shipping_optimizer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the optimization pipeline
python -m src.pipeline.optimization_pipeline

# Output: pipeline_output.json (runtime truth)
```

### Frontend Setup

```bash
cd shipping_optimizer/frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Production build
npm run build

# Serve production build
npx serve dist
```

### Mock WebSocket Server (for dashboard)

```bash
cd shipping_optimizer/frontend
node mock-server.cjs

# Dashboard connects to ws://localhost:8000
```

### Access Dashboard

```
Development: http://localhost:5173
Production:  http://localhost:3000
```

---

## 🧪 System Status

| Component | Status | Notes |
|---|---|---|
| Backend | ✅ FROZEN | 42 certified algorithms |
| Frontend | ✅ COMPLETE | 33 components, 14 tabs |
| Runtime Truth | ✅ SYNCHRONIZED | pipeline_output.json → dashboard |
| AI Coordinator | ✅ OPERATIONAL | 100% AI-generated decisions |
| GA + MILP | ✅ CERTIFIED | Bi-level optimization stack |
| Consensus | ✅ ACTIVE | Weighted voting, 100% confidence |
| Validators | ✅ EXECUTING | Weight, archetype, policy |
| Test Suite | ✅ 309/313 = 98.7% | All functional checks pass |
| Build | ✅ CLEAN | 0 errors, 0 warnings |

---

## 🗺 Roadmap

### Version 1 (Current) — Release Candidate
- ✅ Multi-agent AI optimization with LLM coordination
- ✅ GA + MILP bi-level optimization
- ✅ Runtime truth certification (309/313 assertions)
- ✅ Production dashboard with 14 executive tabs
- ✅ Fleet, route, port intelligence explorers
- ✅ Real-time WebSocket data synchronization

### Version 2 — Planned
- [ ] Multi-run comparison and historical trends
- [ ] What-if weight/constraint tuning UI
- [ ] Service generator AI activation
- [ ] PDF export with charts
- [ ] Code splitting for faster initial load
- [ ] Mobile-responsive layout
- [ ] WCAG 2.1 AA accessibility

### Future Research
- Real-time AIS vessel tracking overlay
- Weather routing integration
- Fleet electrification planning
- Carbon emissions optimization
- Reinforcement learning for weight tuning

---

## 📚 Documentation

| Document | Description |
|---|---|
| [V1 Release Validation](Analysis/V1_RELEASE_VALIDATION_REPORT.md) | Comprehensive release readiness assessment |
| [Backend Freeze Certification](Analysis/V1_BACKEND_FREEZE_CERTIFICATION.md) | Algorithm certification and freeze verification |
| [Algorithm Certification](Analysis/ALGORITHM_AND_PROMPT_CORRECTNESS_CERTIFICATION.md) | Algorithmic correctness proofs |
| [Prompt Freeze Report](Analysis/BACKEND_PROMPT_REFINEMENT_AND_FREEZE_REPORT.md) | LLM prompt engineering and freeze |
| [Architecture Consolidation](Analysis/FRONTEND_ARCHITECTURE_CONSOLIDATION_REPORT.md) | Frontend architecture evolution |
| [Component Modularization](Analysis/FRONTEND_COMPONENT_MODULARIZATION_REPORT.md) | Component extraction and clean-up |
| [Production Intelligence](Analysis/FRONTEND_PRODUCTION_INTELLIGENCE_REPORT.md) | Intelligence panel implementation |
| [Executive Operations](Analysis/FRONTEND_EXECUTIVE_OPERATIONS_COMPLETION_REPORT.md) | Final feature completion report |
| [Runtime Synchronization](Analysis/FRONTEND_RUNTIME_TRUTH_SYNCHRONIZATION_REPORT.md) | Runtime truth alignment |
| [Runtime Integration Plan](Analysis/FRONTEND_RUNTIME_INTEGRATION_MASTER_PLAN.md) | Master implementation plan |
| [Product Readiness Audit](Analysis/V1_PRODUCT_READINESS_AND_FRONTEND_MASTER_AUDIT.md) | Pre-release comprehensive audit |
| [System Truth Report](Analysis/SYSTEM_TRUTH_REPORT.md) | System-level truth verification |
| [Architecture](docs/ARCHITECTURE.md) | System architecture documentation |
| [Release Notes](docs/RELEASE_NOTES.md) | V1.0.0-rc1 release notes |
| [Screenshot Guide](docs/IMAGE_GUIDE.md) | Image placement and naming guide |
| [Data Dictionary](docs/DATA_DICTIONARY.md) | Pipeline output field reference |
| [Developer Guide](docs/DEVELOPER_GUIDE.md) | Development environment setup |
| [System Architecture](docs/SYSTEM_ARCHITECTURE.md) | Detailed system design |
| [FAQ](docs/FAQ.md) | Frequently asked questions |
| [Runbook](docs/RUNBOOK.md) | Operations and troubleshooting |

---

## 📖 Citation

```bibtex
@software{ai_vessel_routing_2026,
  title = {AI Vessel Routing System: Multi-Agent Liner Shipping Optimizer},
  version = {1.0.0-rc1},
  year = {2026},
  author = {AI Vessel Routing Team},
  note = {Hybrid AI + OR optimization with GA, MILP, and LLM coordination}
}
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Made with ⚓ for the global shipping industry**

[Back to Top](#-ai-vessel-routing-system)

</div>
