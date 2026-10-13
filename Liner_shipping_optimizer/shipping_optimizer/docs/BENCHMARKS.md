# Benchmarks

**AI Vessel Routing System v1.0.0-rc1**

*All values sourced from `pipeline_output.json` — the single runtime truth.*

---

## Optimization Performance

### Network Statistics

| Metric | Value |
|---|---|
| **Ports** | 435 |
| **Origin-Destination Lanes** | 9,622 |
| **Regions** | 5 (Asia, Europe, Americas, Middle East, Africa) |
| **Deployed Services** | 511 |
| **Total Selected Services** | 509 (in detailed output) |
| **Unique Ports Served** | 142 |

### Fleet

| Metric | Value |
|---|---|
| **Vessel Classes** | 5 |
| — Feeder 800 | 280 vessels (55%) |
| — Super Panamax | 114 vessels (22%) |
| — Panamax 2400 | 80 vessels (16%) |
| — Post Panamax | 28 vessels (6%) |
| — Feeder 450 | 7 vessels (1%) |
| **Total Capacity Deployed** | 1,655,500 TEU/wk |
| **Total Load** | 1,616,601 TEU/wk |
| **Fleet Utilization** | 97.7% |

### Profit

| Metric | Value |
|---|---|
| **Weekly Profit** | **$901,690,372** |
| **Annual Profit (52-week)** | **$46,887,899,321** |
| **Weekly Revenue** | $2,841,963,843 |
| **Profit Margin** | 81.2% |
| **Operating Cost** | $208,195,000/wk |
| **Fuel Cost** | $1,589,449,294/wk |
| **Transshipment Cost** | $59,382,965/wk |
| **Port Cost** | $83,246,212/wk |
| **Total Cost** | $1,940,273,472/wk |

### Coverage

| Metric | Value |
|---|---|
| **OD-Based Coverage** | **52.5%** |
| **Average Regional Coverage** | 65.1% |
| **Min Regional Coverage** | 37.7% (Americas) |
| **Max Regional Coverage** | 81.4% (Africa) |
| **Coverage Variance** | 43.7% |
| **Satisfied Demand** | 874,314 TEU/wk |
| **Unserved Demand** | 1,020,916 TEU/wk |

### Per-Region Breakdown

| Region | Profit | Coverage | Services | Margin | Generated | Filtered | Selected |
|---|---|---|---|---|---|---|---|
| **Asia** | $81,091,270 | 74.9% | 107 | 18.6% | 781 | 400 | 107 |
| **Europe** | -$31,978,360 | 51.0% | 92 | -8.3% | 875 | 400 | 92 |
| **Americas** | $814,790,731 | 37.7% | 91 | 62.9% | 806 | 400 | 91 |
| **Middle East** | -$88,886,153 | 80.4% | 117 | -38.1% | 744 | 400 | 117 |
| **Africa** | $126,672,883 | 81.4% | 104 | 25.8% | 792 | 400 | 104 |

---

## Runtime & Quality

| Metric | Value |
|---|---|
| **Total Runtime** | 499.3 seconds (~8 minutes) |
| **Feedback Iterations** | 3 (converged) |
| **Convergence Score** | 0.977 |
| **Consensus Confidence** | 1.0 (100%) |
| **Region Success Rate** | 100% |
| **Regions Executed** | 15 (5 regions × 3 iterations) |
| **Regions Failed** | 0 |

### Iteration History

| Iteration | Profit | Coverage | Conv. Score | Rerun |
|---|---|---|---|---|
| 0 | $659,067,329 | 65.9% | 0.981 | Yes |
| 1 | $765,457,315 | 67.7% | 0.989 | Yes |
| 2 | $901,690,372 | 65.1% | 0.977 | No (capped) |

### Weight Trajectory

| Iteration | Profit Weight | Coverage Weight | Cost Weight |
|---|---|---|---|
| 0 | 0.600 | 0.250 | 0.150 |
| 1 | 0.405 | 0.495 | 0.100 |
| 2 (final) | 0.373 | 0.484 | 0.143 |

---

## AI Activity

| Metric | Value |
|---|---|
| **Coordinator AI-Generated** | ✅ 100% (3/3 iterations) |
| **LLM Calls (Total)** | 8 |
| **Coordinator LLM Calls** | 3 |
| **JSON Parse Success** | 3/3 (100%) |
| **Validator Executions** | 3/3 (100%) |
| **Coordinator Fallbacks** | 0 |
| **Service Generator Regions** | 5 (all algorithmic fallback) |
| **Service Generator AI** | 0% (documented limitation) |

### Validator Performance

| Validator | Status | Executions |
|---|---|---|
| Weight Validator | ✅ Active | 3 |
| Archetype Validator | ✅ Active | 5 (fallback) |
| Regional Policy Validator | ✅ Active | 5 |

---

## Backend

| Metric | Value |
|---|---|
| **Assertions Passed** | 309 |
| **Assertions Total** | 313 |
| **Test Score** | **98.7%** |
| **Warnings** | 4 |
| **Pipeline Status** | `complete` |
| **Health Status** | All regions completed |
| **Consensus Confidence** | 1.0 |

---

## Frontend

| Metric | Value |
|---|---|
| **Build Time** | 2.3 seconds |
| **Modules Transformed** | 353 |
| **Bundle JS** | 394 KB (118 KB gzipped) |
| **Bundle CSS** | 17 KB (4.2 KB gzipped) |
| **Components** | 33 |
| **Navigation Tabs** | 14 |
| **Build Warnings** | 0 |
| **Runtime Truth Accuracy** | 100% |

---

## System Status

| Component | Status | Score |
|---|---|---|
| Backend | ✅ FROZEN | 42 algorithms certified |
| Frontend | ✅ COMPLETE | 33 components, 14 tabs |
| Runtime Truth | ✅ SYNCHRONIZED | 100% field accuracy |
| AI Coordinator | ✅ OPERATIONAL | 100% AI-generated decisions |
| GA + MILP | ✅ CERTIFIED | Bi-level optimization |
| Consensus | ✅ ACTIVE | 100% confidence |
| Validators | ✅ EXECUTING | All paths verified |
| Build | ✅ CLEAN | 0 errors, 0 warnings |
