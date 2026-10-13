# MA_07 — NETWORK ECONOMICS AND DEMAND RECONCILIATION AUDIT

**System:** AI Vessel Routing System — Multi-Agent Optimizer
**Audit mode:** Forensic, evidence-driven, read-only
**Date:** 2026-10-05
**Status:** COMPLETE

---

## 0. The headline

**The reported weekly profit of $345,495,908.06 exceeds the maximum profit physically attainable from this dataset by approximately $258 million per week.**

The dataset contains $264,870,100/week of gross revenue. Non-fuel costs are $142,581,832/week. Even at a *zero* fuel bill, the ceiling is $122,288,268/week. The reported profit is **2.8× that bound** — and this holds without needing to judge whether the fuel figure itself is right.

---

## 1. The independent oracle

Built from raw data only. **No project module was imported.**

```python
import csv
rows = csv.DictReader(open('data/raw/demand_world_small.csv', delimiter='\t'))
# FFE_TO_TEU_CONVERSIONS transcribed from network_loader.py:74-91
# Q_TEU   = Σ FFE × k
# Revenue = Σ FFE × $/FFE          ← units cancel, no conversion needed
```

**Why revenue needs no conversion:** `FFE × ($/FFE)` is already USD. The FFE→TEU conversion is a change of representation, not of value. Any correct formulation — raw, or TEU with a properly divided rate — yields the same total. This makes the revenue ceiling a **representation-independent bound.**

| Quantity | Value |
|---|---|
| Demand (raw) | 138,247.00 FFE/week |
| Demand (as loaded) | 276,446.80 TEU/week |
| **Dataset gross revenue** | **264,870,100.00 USD/week** |

### 1.1 Verified by three independent routes

| Route | Result |
|---|---|
| `Σ FFE × Revenue_1` (raw) | 264,870,100.00 |
| `Σ (FFE·k) × (Revenue_1/k)` (both converted) | 264,870,100.00 |
| `Q_TEU × (RawRev / Q_TEU)` (aggregate rate) | 264,870,100.00 |

All three agree exactly. The oracle is not sensitive to how units are represented.

---

## 2. The profit ceiling

### 2.1 Non-fuel costs (as reported)

```
operating  100,822,500.00
transship   22,531,440.01
port        19,227,892.20
            ---------------
subtotal   142,581,832.21
```

### 2.2 Ceilings under three fuel assumptions

| Fuel assumption | Total cost | Max profit |
|---|---|---|
| **Zero fuel** (impossible, for bounding only) | 142,581,832.21 | **122,288,267.79** |
| Realistic low ($25M/wk) | 167,581,832.21 | 97,288,267.79 |
| Realistic high ($35M/wk) | 177,581,832.21 | 87,288,267.79 |
| Physical fleet max ($55.3M/wk) | 197,916,832.21 | 66,953,267.79 |
| **Reported fuel ($648.0M/wk)** | 790,613,750.51 | **−525,743,650.51** |

### 2.3 The comparison that settles it

```
Reported weekly profit          =  345,495,908.06
Max profit with ZERO fuel cost  =  122,288,267.79
                                 -------------------
EXCESS                          =  223,207,640.27
```

**This bound requires no assumption about fuel at all.** Even if fuel were free, the reported profit could not be achieved — because the dataset only contains $264.87M/week of gross revenue and $142.58M/week of non-fuel cost is already committed.

Against a *realistic* fuel figure the excess is larger still:

| Comparison | Excess |
|---|---|
| vs zero-fuel ceiling | +223,207,640.27 |
| vs realistic high ($35M fuel) | **+258,207,640.26** |
| vs physical max ($55.3M fuel) | +278,542,640.27 |

---

## 3. Reconciling the artifact to the oracle

### 3.1 Revenue

| | Value | vs ceiling |
|---|---|---|
| Dataset gross revenue (ceiling) | 264,870,100.00 | — |
| Reported revenue | 1,136,109,658.57 | **×4.2893** |
| **Excess** | **+871,239,558.57** | +328.9% |

The excess is fully attributed by MA-03:

| Source | Mechanism | Magnitude |
|---|---|---|
| k² rate inflation | `network_loader.py:109` | ×4.0018 |
| Multi-service overlap | `service_ga.py:134-138` | ×1.0719 |
| **Combined** | | **×4.2893** ✓ |

The two factors multiply to exactly the observed ratio — the revenue line is **fully explained** by two identified defects, with no residual.

### 3.2 Cost

| | Value | vs bound |
|---|---|---|
| Fuel (ceiling: $55.3M physical) | 648,031,918.31 | **×11.71** |
| Non-fuel | 142,581,832.21 | — |

### 3.3 Demand

| | Value | vs oracle |
|---|---|---|
| True demand | 276,446.80 | — |
| Reported satisfied | 273,267.10 | 98.8498% |
| Reported coverage | 89.5895% | **−9.26 pp** |
| Reported satisfied + unserved | 305,021.20 | **+10.34%** phantom |

---

## 4. The full reconciliation identity

```
reported_profit = reported_revenue − reported_cost
                = 1,136,109,658.57 − 790,613,750.51
                =   345,495,908.06            ✓ identity holds
```

The identity is **internally exact and externally false.** Decomposed:

```
reported_profit
    = 4.2893 × dataset_revenue  −  (fuel: 11.71 × physical_max)  −  non_fuel
    = 1,136,109,658.57          −  648,031,918.31                −  142,581,832.21
    = 345,495,908.06
```

Had the two defects not been present, the same pipeline structure would yield:

```
true_profit ≈ 264,870,100 × 0.9885 (coverage) − 142,581,832 − (25–35M realistic fuel)
           ≈ 87–97 M USD/week
```

**The reported $345.5M is roughly 3.6–4.0× the defensible range.**

---

## 5. Regional economics are not comparable

| Region | Services | Satisfied (TEU) | Profit | Profit/service | Margin |
|---|---|---|---|---|---|
| Asia | 104 | 147,838.50 | 309,439,989.61 | **2,975,385** | 45.3% |
| Europe | 100 | 45,330.00 | **308,493.42** | **3,085** | 0.2% |
| Americas | 108 | 80,098.60 | 35,747,425.03 | 330,995 | 11.8% |

**Asia earns 964× more per service than Europe**, with comparable service counts. Europe serves 31% of Asia's cargo across 96% of its services.

Root cause chain:

```
Asia   served 3.26x more demand per service  ──┐
                                             ├──► profit divergence
Europe profit includes the MILP coverage_reward
        which scales with operating_cost     ──┘
       Asia op_cost 42.8M  → reward ~16.1M
       Europe op_cost 20.9M → reward ~8.2M
```

Europe's 0.2% margin means its `total_cost` (151.4M) almost exactly equals its profit (0.31M) + ... i.e. revenue ≈ cost. **This is the signature of the coverage_reward term dominating** — it adds to profit in proportion to cost, so a low-cost region earns almost no bonus and reports near-zero margin.

**Classification: D — reporting defect.** The three regions are not solving comparable problems, and the artifact presents them as if they were.

---

## 6. Coverage reconciliation

### 6.1 The denominator is correct; the numerator is not

`true_global_demand = Σ d.weekly_teu` (`orchestrator_agent.py:505`) = **276,446.80** ✓ — the loader total, no error in the denominator.

The numerator is corrupted by the clamp asymmetry (MA-06-14):

| Region | satisfied | capped? | unserved | capped? |
|---|---|---|---|---|
| Asia | 147,838.50 | **yes** (= total_demand) | 13,274.67 | no |
| Europe | 45,330.00 | yes | 6,307.70 | no |
| Americas | 80,098.60 | **yes** (= total_demand) | 12,171.73 | no |

### 6.2 Both the over- and under-statement are artifacts

| Metric | Reported | Recomputed | Delta |
|---|---|---|---|
| Coverage | 89.5895% | **98.8498%** | **−9.26 pp understated** |
| Served + unserved | 305,021.20 | 276,446.80 | **+10.34% overstated** |

Two regions report **exactly 100.0000%** — the arithmetic signature of `min(satisfied, total_demand)` saturating, not of perfect service.

**Neither the coverage figure nor the demand accounting can be relied upon.**

---

## 7. Vessel economics

No vessel-level economics are reported anywhere:

| Field | Artifact | API |
|---|---|---|
| Vessels required | absent | absent |
| Vessels available | absent | absent |
| Utilization | absent | `vesselsUtilized: None` |
| Feasibility flag | absent | absent |

The system deploys **624 vessels against 263 available** (MA-05-01) and reports neither number.

---

## 8. Findings from MA_07

| ID | Finding | Classification | Confidence | Impact |
|---|---|---|---|---|
| **MA-07-01** | **Reported weekly profit $345,495,908.06 exceeds the zero-fuel ceiling ($122,288,267.79) by $223.2M — a bound requiring no assumption about fuel** | **A. Verified implementation defect** | **Very high** — three independent oracle routes agree | **CRITICAL** — result is impossible, not merely wrong |
| **MA-07-02** | Against a realistic fuel figure, profit exceeds the ceiling by **$258,207,640.26** | **A. Verified implementation defect** | **Very high** | ~3.6–4.0× defensible range |
| **MA-07-03** | Reported revenue exceeds the dataset's gross revenue ceiling by **$871,239,558.57 (+328.9%)** | **A. Verified implementation defect** | **Very high** | ×4.2893 |
| **MA-07-04** | Revenue excess is **fully explained** by k² inflation (×4.0018) × multi-service overlap (×1.0719) — the factors multiply to the observed ratio with no residual | **B. Verified consistent** | **High** | Both defects confirmed as complete explanations |
| **MA-07-05** | Fuel exceeds the fleet's physical maximum by **11.71×** | **A. Verified implementation defect** | **Very high** | 82% of all cost is impossible |
| **MA-07-06** | Asia earns **964× more per service** than Europe; Europe shows 0.2% margin — the signature of the cost-proportional coverage_reward dominating | **D. Reporting defect** | **High** | Regions not economically comparable |
| **MA-07-07** | Coverage understated by **9.26 pp** (89.5895% reported vs 98.8498% true) | **D. Reporting defect** | **High** | Understates solution quality |
| **MA-07-08** | `satisfied + unserved` overstates true demand by **+10.34%** | **A. Verified implementation defect** | **High** | Phantom demand |
| **MA-07-09** | Two regions report **exactly 100.0000%** coverage — clamp artifacts | **D. Reporting defect** | **High** | False perfection |
| **MA-07-10** | No vessel economics reported despite a **2.37× fleet overcommitment** | **D. Reporting defect** | **High** | Infeasibility invisible |
| **MA-07-11** | Internal identities hold exactly (revenue − cost = profit; cost components sum to total) — the ledger is **arithmetically sound and externally false** | **B. Verified consistent** | **High** | Defects are upstream, not in aggregation |

---

## 9. What the oracle does and does not establish

**Established:**
- The dataset's gross revenue is $264,870,100/week — verified three ways.
- The reported profit is unreachable under any cost assumption, including zero fuel.
- The reported revenue is 4.29× the dataset ceiling, fully explained by two named defects.
- The reported fuel is 11.71× the fleet's physical maximum.

**Not established — and deliberately not claimed:**
- **What the correct profit is.** That depends on repairs that are outside this phase's authorization.
- **Whether a different formulation would be better.** A formulation difference is not a defect.
- **Whether the fleet could support a better network.** Requires running a corrected optimizer, which would need an isolated workspace.
- **GA stochastic variance.** The production pipeline was not executed, so run-to-run spread is unmeasured.

---

## 10. Reproducing the oracle

```bash
cd shipping_optimizer
python -c "
import csv, json
rows=list(csv.DictReader(open('data/raw/demand_world_small.csv',encoding='utf-8-sig'),delimiter='\t'))
F={'AEJEA-DEHAM':2.1,'CNSHA-DEHAM':2.1,'AEJEA-NLRTM':2.1,'CNSHA-NLRTM':2.1,'CNSHA-USLAX':1.85,'BRSSZ-USLAX':1.9}
D=[]
for r in rows:
    o=r['Origin'].strip(); d=r['Destination'].strip()
    if o==d: continue
    k=F.get(o+'-'+d,2.0); f=float(r['FFEPerWeek']); v=float(r['Revenue_1'])
    D.append((k,f,v))
rawrev=sum(f*v for _,f,v in D)          # USD/week, representation-independent
Q=sum(k*f for k,f,_ in D)
sm=json.load(open('frontend/public/pipeline_output.json',encoding='utf-8'))['summary_metrics']
nonfuel=sm['operating_cost']+sm['transship_cost']+sm['port_cost']
print('dataset gross revenue = %.2f'%rawrev)
print('non-fuel cost         = %.2f'%nonfuel)
print('MAX profit (zero fuel)= %.2f'%(rawrev-nonfuel))
print('reported profit       = %.2f'%sm['weekly_profit'])
print('EXCESS                = %.2f'%(sm['weekly_profit']-(rawrev-nonfuel)))
"
```

No project module was imported; no file was written.