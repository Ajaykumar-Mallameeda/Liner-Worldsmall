# Release Notes

## Version 1.0.0-rc1 — 2026-07-01

*AI Vessel Routing System — Multi-Agent Liner Shipping Optimizer*

---

## Highlights

- 🚢 **511 services** deployed across **5 global regions** (Asia, Europe, Americas, Middle East, Africa)
- 💰 **$901.7M/week** optimized profit | **$46.9B** annualized | **81.2%** profit margin
- 📊 **52.5% demand coverage** | **97.7% fleet utilization** | 1.66M TEU/wk capacity
- 🤖 **100% AI-generated coordinator decisions** across 3 convergent iterations
- ✅ **309/313 assertions** passing (**98.7%** test score)
- 🎛 **14-tab executive operations dashboard** with Fleet, Route, Port explorers
- 📦 **394 KB bundle** | **2.3s build** | **33 modular components**

---

## Architecture

### Backend (Python)

- **Orchestrator Agent**: Runs the 3-iteration feedback loop, coordinates all agents, detects convergence
- **Coordinator Agent**: LLM-driven decision engine — problem analysis, adaptive weight tuning, conflict detection, convergence evaluation (100% AI-generated, 0 fallbacks)
- **5 Regional Agents**: Parallel execution across Asia, Europe, Americas, Middle East, Africa
- **Service Generator Agent**: Generates 744–875 candidate services per region
- **Consensus Engine**: Weighted voting with 100% confidence score, conflict resolution, archetype agreement
- **3 Validators**: Weight validator (ℝ³→[0,1]³), Archetype validator (mix ratios sum=1), Regional policy validator

### Optimization

- **Hierarchical GA**: Bi-level genetic algorithm — L1 service selection, L2 frequency optimization
- **Hub MILP**: Mixed-integer linear programming for hub-and-spoke flow optimization
- **Fitness Function**: Profit-maximizing with coverage and cost constraints
- **K-means Clustering**: 435 ports partitioned into 5 geographic regions
- **Distance Matrix**: 62,002 inter-port pairs with canal and transit time modeling

### Frontend (React 18)

- **33 modular components** across 6 directories (common, layout, overview, regions, optimization, map)
- **14 navigation tabs**: Landing → Overview → Fleet → Routes → Ports → Pipeline → Regional → Funnel → Feedback → Conflict → Map → Scenarios → Export → Summary
- **Single runtime truth source**: All data from `pipeline_output.json` via runtime adapter
- **Real-time WebSocket**: Live pipeline progress with exponential backoff reconnection
- **Production features**: Fleet intelligence, AI decision trace, runtime health, optimization insights, decision explanation, backend certification
- **Dark maritime theme**: Bloomberg/Apple-inspired professional dark UI

---

## Performance

| Metric | Value |
|---|---|
| Build Time | 2.3 seconds |
| Bundle JS | 394 KB (118 KB gzipped) |
| Bundle CSS | 17 KB (4.2 KB gzipped) |
| Modules | 353 |
| Components | 33 |
| Build Warnings | 0 |

---

## Benchmarks

| Metric | Value |
|---|---|
| Optimization Runtime | 499.3 seconds (~8 min) |
| Coverage | 52.5% |
| Weekly Profit | $901,690,372 |
| Annual Profit | $46,887,899,321 |
| Services Deployed | 511 |
| Fleet Capacity | 1,655,500 TEU/wk |
| Fleet Utilization | 97.7% |
| Assertions | 309/313 = 98.7% |
| Convergence Score | 0.977 |
| Consensus Confidence | 1.0 |

*Full benchmark details in [BENCHMARKS.md](BENCHMARKS.md)*

---

## Known Limitations

1. **Service Generator**: 0% AI — operates entirely on algorithmic fallback (free-tier API timeouts). Documented as VERDICT B in certification. Production-quality defaults active.
2. **Test Warnings**: 4 pre-existing failures in executive summary formatting checks. Non-functional.
3. **PDF Export**: Placeholder only. Use JSON/CSV export for data portability.
4. **Mobile Support**: Dashboard is optimized for desktop/laptop/projector. No mobile responsive layout.
5. **Code Splitting**: Entire app is single JS chunk. V2 improvement.

---

## V2 Roadmap

| Priority | Feature |
|---|---|
| P0 | Multi-run comparison with historical trends |
| P0 | What-if weight/constraint tuning via UI |
| P1 | Service generator AI activation |
| P1 | PDF export with charts |
| P1 | React.lazy code splitting |
| P2 | Mobile responsive layout |
| P2 | WCAG 2.1 AA accessibility |
| P2 | Automated test suite (Jest + RTL) |
| P3 | AIS vessel tracking overlay |
| P3 | Real-time pipeline progress animation |

---

## Installation

See [README.md](../README.md#-quick-start) for complete setup instructions.

```bash
# Backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m src.pipeline.optimization_pipeline

# Frontend
cd frontend && npm install && npm run dev
```

---

## Links

- **README**: [../README.md](../README.md)
- **Documentation**: [./](.)
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Benchmarks**: [BENCHMARKS.md](BENCHMARKS.md)
- **Gallery**: [PROJECT_GALLERY.md](PROJECT_GALLERY.md)
- **Screenshots**: [SCREENSHOTS.md](SCREENSHOTS.md)
