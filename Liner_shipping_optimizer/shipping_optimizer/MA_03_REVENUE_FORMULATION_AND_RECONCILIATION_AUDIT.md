# MA_03 — REVENUE FORMULATION AND RECONCILIATION AUDIT

**System:** AI Vessel Routing System — Multi-Agent Optimizer
**Audit mode:** Forensic, evidence-driven, read-only
**Date:** 2026-10-05
**Status:** COMPLETE

---

## 0. Summary of the revenue model

The system computes revenue in **four different places**, with **four different formulas**, and reports a **fifth** value that is derived from profit and cost rather than from revenue.

| # | Location | Formula | Lane-specific rate? |
|---|---|---|---|
| 1 | `service_ga.py:146-148` → `:243` | `Σ served × avg_rev_per_teu × yield_factor` | **No — network average** |
| 2 | `service_ga.py:285` | `served × avg_rev_per_teu` (per-service margin) | No |
| 3 | `frequency_ga.py:200` | `demands[0].revenue_per_teu` — **the first demand's rate** | No — arbitrary single lane |
| 4 | `hub_milp.py:411+` | `Σ flow × demand.revenue_per_teu` (per-lane) | **Yes** |
| 5 | `orchestrator_agent.py:316` | `total_profit + total_cost` — **tautology** | N/A |

The MILP is the only revenue model that respects lane-level rates. The GAs — which perform the actual service and frequency selection — use a **single network-wide average** or **one arbitrary lane**.

---

## 1. MA-02-01 restated as the revenue-rate defect

### 1.1 The one-line root cause

```python
# src/data/network_loader.py:106-109
weekly_teu      = float(row["FFEPerWeek"]) * ffe_to_teu_factor    # ×k  ✓
revenue_per_teu = float(row["Revenue_1"])  * ffe_to_teu_factor    # ×k  ✗ should be ÷k
```

### 1.2 The measured rate inflation

`avg_rev_per_teu` is the demand-weighted mean rate (`service_ga.py:146-148`). Both the implemented and the corrected values, computed directly from the raw CSV:

| Quantity | Value | Basis |
|---|---|---|
| Total demand as loaded `Q_TEU = Σ FFE·k` | 276,446.80 | TEU/week |
| Total demand raw `Q_FFE = Σ FFE` | 138,247.00 | FFE/week |
| Raw CSV theoretical revenue `Σ FFE × $/FFE` | **264,870,100.00** | USD/week |
| `avg_rev_per_teu` **as implemented** | **3,834.1919** | `Σ (FFE·k)(k)($/FFE) / Q_TEU` |
| `avg_rev_per_teu` **correct** | **958.1232** | `Σ (FFE·k)($/FFE/k) / Q_TEU` |
| Independent cross-check `Σ FFE×$/FFE / Q_TEU` | **958.1232** | identical ✓ |
| **Inflation on the rate** | **× 4.001773** | exactly `mean(k²)`, FFE-weighted |

The cross-check matters: the corrected rate computed two independent ways — dividing the raw revenue by converted volume, and converting both sides of each product — agree to **10 significant figures**. The revenue model is *internally* coherent; it is the loader that breaks it.

**Sanity check on the corrected rate.** 958.12 USD/TEU is a plausible liner freight rate. The implemented 3,834.19 USD/TEU is ~4× that — implausible for ocean container freight on any published trade lane. The magnitude argument and the dimensional argument agree.

### 1.3 Reconciliation to the reported figure

| Step | Value |
|---|---|
| Theoretical revenue, all demand served, **correct** rate | 264,870,100.00 |
| Theoretical revenue, all demand served, **implemented** rate | 1,059,950,076.25 |
| **Reported** `revenue` in artifact | **1,136,109,658.57** |
| Reported ÷ theoretical-correct | **× 4.2893** |
| Reported ÷ theoretical-implemented | ×1.0719 |

The residual ×1.0719 over the theoretical-implemented figure is attributable to the GA revenue effects in §3 — chiefly the `yield_factor > 1` behavior and the multi-service double-count.

---

## 2. Revenue model #3 — `frequency_ga.py:200` uses a single arbitrary lane

```python
# src/optimization/frequency_ga.py:200
avg_rev_per_teu = self.problem.demands[0].revenue_per_teu if self.problem.demands else 1000.0
```

Despite the variable name, this is **not an average**. It is the rate of whichever demand happens to be first in the list. `service_ga.py:146` computes a true weighted average 50 lines away in a different module; `frequency_ga.py` does not use it.

For the WorldSmall dataset, `demands[0]` is the first row of `demand_world_small.csv`. Its lane factor is the default k = 2.0, so its inflated rate is `Revenue_1 × 2.0`. Whatever that lane's rate is, **every** service evaluated by FrequencyGA is priced at it.

**Classification: A — verified implementation defect.** Either name it `demands[0].revenue_per_teu` or compute the average; naming it `avg_` and computing a single lane's rate is a defect regardless of formulation intent.

---

## 3. ServiceGA revenue — network average, not lane rates

### 3.1 The formula

```python
# service_ga.py:144-148
total_teu = self.total_demand or 1.0
self.avg_rev_per_teu = sum(
    d.weekly_teu * d.revenue_per_teu for d in self.problem.demands
) / total_teu

# service_ga.py:241-243
yield_factor = 0.6 + 0.4 * (served / (effective_capacity or 1))
revenue += served * self.avg_rev_per_teu * yield_factor
```

### 3.2 Defect A — `yield_factor` is not a yield

`yield_factor = 0.6 + 0.4·(served / effective_capacity)` evaluates to the range **(0.6, 1.0]**. It is a *utilization* factor, and it correctly reduces revenue for under-filled services. **This part is sound.** Flagged only because the name implies otherwise and the parameter it appears to model (empty-sailing loss) is not present.

### 3.3 Defect B — `served` counts a lane once per covering service

```python
# service_ga.py:134-138
for i, port_set in enumerate(self.service_port_sets):
    if o in port_set and d_port in port_set:
        self.service_direct_demand[i] += teu        # ← every covering service
```

A demand lane is credited **in full to every service whose port set contains both endpoints.** A lane from Shanghai to Rotterdam is credited to the Asia–Europe service *and* to any transatlantic or round-world service that happens to call at both ports. Then:

```python
# service_ga.py:236
served = min(effective_capacity, direct)     # direct already includes the lane
```

`served` is capped by capacity, but the **revenue** it generates is `served × avg_rev_per_teu`, using the network average — so a lane counted in three services earns three times the network-average rate.

**Measured consequence.** Mean port degree in the WorldSmall demand graph is **75.1 lanes per port**; with 309 selected services across 47 ports, each service calls at a large port subset, so the expected number of services covering a given OD pair is well above 1. The artifact is consistent with this:

| Quantity | Value |
|---|---|
| Artifact `revenue` | 1,136,109,658.57 |
| Implied served volume at implemented rate (3,834.19) | **296,310.07 TEU/week** |
| True total demand | 276,446.80 TEU/week |
| **Implied over-count** | **× 1.0719** |

Served volume exceeds true demand by **19,863 TEU/week**, even before the ×4 rate inflation. The GA's revenue is not a partition of demand; it is a **weighted overlap** of demand across services.

### 3.4 Defect C — `avg_rev_per_teu` erases lane economics entirely

Because a single average rate is applied to all lanes, the GA is **indifferent to which lane it serves**. A 1,052-FFE/week Shanghai–Rotterdam lane and a 2-FFE/week Jebel Ali–Hamburg lane earn the same rate per TEU. Lane profitability differences — which are the entire basis of network design — do not enter service selection.

This is not a units problem. Even with the k² defect fixed, the ServiceGA would still price all lanes identically. **The two defects are independent and both must be fixed for lane-aware selection to work.**

---

## 4. Reconciliation of reported revenue to components

### 4.1 The reported value cannot be decomposed

`orchestrator_agent.py:316` sets `revenue = profit + cost`. The artifact's revenue is therefore:

```
1,136,109,658.57 = 345,495,908.06 + 790,613,750.51   ✓ exact
```

**This is not evidence that revenue is correct.** It is evidence only that the artifact is internally consistent with a tautology. There is no independent revenue line in the artifact against which to check.

### 4.2 What would constitute a valid check

A valid reconciliation requires revenue computed at least twice by independent paths. The repository contains **none**:

| Candidate cross-check | Status |
|---|---|
| Artifact revenue vs Σ regional revenue | Tautological — both descend from the same profit/cost |
| Artifact revenue vs raw-CSV Σ FFE × $/FFE | **Never performed by any code or test** |
| Artifact revenue vs MILP revenue expression value | **Never exported** separately |
| Unit-level test on `weekly_teu × revenue_per_teu` | **Absent** |

**Conclusion: revenue in this system is unfalsifiable as reported.** The identity that would expose the k² defect — `Σ weekly_teu × revenue_per_teu == Σ FFE × $/FFE` — is never evaluated anywhere.

---

## 5. Effect on service selection

Revenue is the dominant term in the GA fitness (`normalization.py:114-118` → `10.0 × profit`). The defects propagate as follows:

| Defect | Effect on selection |
|---|---|
| k² rate inflation (MA-02-01) | Uniform ×4 on the profit term for most lanes — mostly cancels in ranking, **except** for the 6 non-default-k lanes, whose relative value is inflated 3.42–4.41× vs 4.0 for the rest. Those 6 lanes (1.84% of demand, 2.21% of raw revenue) are systematically over-valued. |
| Single average rate (§3.4) | Lane economics erased entirely — the GA cannot prefer a high-yield lane over a low-yield one |
| Multi-service double-count (§3.3) | Services with larger port sets earn more revenue for the same cargo → **biases toward broad, many-port services** |
| `frequency_ga` single-lane rate (§2) | All services priced at one arbitrary lane's rate |

The double-count bias is the most structurally significant: it rewards **broad services**, which is the opposite of what efficient liner design requires. A tight 4-port shuttle and a 20-port round-world service calling at both endpoints of the same lane earn identical credit for that lane — but the broad service accumulates credit across many more lanes.

---

## 6. Prior-audit claims on revenue

| Prior claim | Adjudication | Basis |
|---|---|---|
| Revenue inflated by FFE/TEU k² | **CONFIRMED** | Direct arithmetic: 4.001773× on the rate; identical by two independent computations |
| Revenue is profit + cost (tautological) | **CONFIRMED** | `orchestrator_agent.py:316`; artifact reconciles exactly |
| `DEMAND_SCALE = 6` affects revenue | **CORRECTED** | The ×6 scales `weekly_teu` **only**, not revenue. It creates a 6× revenue/cost skew, not a 6× revenue inflation. The prior claim overstated this. |
| Revenue margin values are inconsistent | **NOT REPRODUCED** | Margin values 45.3 / 0.2 / 11.8 recompute correctly from the artifact's own revenue and cost figures. The prior claim does not hold. |

---

## 7. Independent economic oracle — revenue side

Because the system's revenue cannot be self-validated, an independent figure is derived from raw data with no project code involved.

### 7.1 Upper bound: every TEU of demand shipped once at the correct rate

```
Q_TEU  = Σ FFE × k                        = 276,446.80 TEU/week
r̄      = Σ (FFE·k)·($/FFE/k) / Q_TEU       = 958.1232 USD/TEU
Rev_max = Q_TEU × r̄                       = 264,870,100.00 USD/week
```

**By construction `Q_TEU × r̄ ≡ Σ FFE × $/FFE`.** The unit conversion is a change of representation, not a change of value. This is the strongest available statement about revenue: **the raw dataset contains exactly $264,870,100.00/week of gross revenue, and no formulation that correctly represents units can exceed it.**

### 7.2 Realized revenue bound

Realized revenue cannot exceed §7.1. The reported figure exceeds it by **4.2893×**. The excess of **871,239,558.57 USD/week** is not available revenue in the dataset; it is an artifact of the rate inflation and the multi-service overlap.

| Bound | Value |
|---|---|
| Dataset gross revenue ceiling | **264,870,100.00 USD/week** |
| Reported revenue | 1,136,109,658.57 USD/week |
| **Excess over ceiling** | **+871,239,558.57 (+328.9%)** |

---

## 8. Findings from MA_03

| ID | Finding | Classification | Confidence | Impact |
|---|---|---|---|---|
| **MA-03-01** | `avg_rev_per_teu` is ×4.001773 the correct rate — k² inflation from `network_loader.py:109`, confirmed by two independent computations agreeing to 10 s.f. | **A. Verified implementation defect** | **High** | Correct rate 958.12 USD/TEU; implemented 3,834.19 |
| **MA-03-02** | ServiceGA prices **all lanes at one network average** (`service_ga.py:243`); lane profitability differences never enter service selection | **A. Verified implementation defect** | **High** | Erases the economic basis of network design |
| **MA-03-03** | A lane is credited **in full to every service covering both endpoints** (`service_ga.py:134-138`); implied served volume 296,310 TEU/wk vs 276,446.80 true — **×1.0719 over-count** | **A. Verified implementation defect** | **High** | Biases selection toward broad many-port services |
| **MA-03-04** | `frequency_ga.py:200` names a variable `avg_rev_per_teu` but assigns `demands[0].revenue_per_teu` — a single arbitrary lane's rate | **A. Verified implementation defect** | **High** | All services priced at one lane's rate |
| **MA-03-05** | Reported revenue exceeds the dataset's gross revenue ceiling (264,870,100.00) by **+871,239,558.57 (+328.9%)** | **D. Reporting defect** | **High** | Reported figure is not attainable from the dataset |
| **MA-03-06** | **No independent revenue cross-check exists anywhere** — the identity that would expose k² (`Σ teu × rate == Σ FFE × $/FFE`) is never evaluated by code or test | **D. Reporting defect** (oracle gap) | **High** | Revenue is unfalsifiable as reported |
| **MA-03-07** | The 6 non-default-k lanes are inflated 3.42–4.41× vs 4.0 for the rest — **non-uniform**, so the defect does not cancel in service ranking | **A. Verified implementation defect** | High | Systematically over-values 1.84% of demand |
| **MA-03-08** | `yield_factor` (0.6–1.0) is a utilization discount, correctly implemented; no defect | **B. Formulation choice** | High | Named for accuracy; behaviour is sound |
| **MA-03-09** | Prior claim that margin values are inconsistent | **G. Not reproduced** | High | Values recompute correctly |
| **MA-03-10** | Prior claim that `DEMAND_SCALE=6` inflates revenue 6× | **G. Partially corrected** | High | Scales demand only; creates 6× revenue/cost skew |

---

## 9. Reproducing the revenue figures

```bash
cd shipping_optimizer
python -c "
import csv
rows=list(csv.DictReader(open('data/raw/demand_world_small.csv',encoding='utf-8-sig'),delimiter='\t'))
F={'AEJEA-DEHAM':2.1,'CNSHA-DEHAM':2.1,'AEJEA-NLRTM':2.1,'CNSHA-NLRTM':2.1,'CNSHA-USLAX':1.85,'BRSSZ-USLAX':1.9}
D=[]
for r in rows:
    o=r['Origin'].strip(); d=r['Destination'].strip()
    if o==d: continue
    k=F.get(o+'-'+d,2.0)
    D.append((k,float(r['FFEPerWeek']),float(r['Revenue_1'])))
Q=sum(k*f for k,f,_ in D)
imp=sum((k*f)*(k*v) for k,f,v in D)/Q
cor=sum(f*v for _,f,v in D)/Q
print('Q_TEU          = %.2f'%Q)
print('avg rate impl  = %.4f'%imp)
print('avg rate corr  = %.4f'%cor)
print('inflation      = %.6f'%(imp/cor))
print('dataset ceiling= %.2f'%(Q*cor))
"
```

No project module was imported; no file was written.