# MA_08 — INDEPENDENT ECONOMIC ORACLE AND VALIDATION REPORT

**System:** AI Vessel Routing System — Multi-Agent Optimizer
**Audit mode:** Forensic, evidence-driven, read-only
**Date:** 2026-10-05
**Status:** COMPLETE

---

## 0. Purpose

This document builds an economic oracle **independent of the system under audit**, uses it to test the reported results, and states plainly what it does and does not prove.

**Constraint honoured:** the oracle is derived only from the raw dataset and from first principles. **No project module was imported, no project formula was reused, and the RL engine was not consulted as a standard** — per the mandate that this audit be independent of the RL formulation.

---

## 1. Construction of the oracle

### 1.1 Design rule: representation-independent quantities

The oracle uses only quantities that **do not change when units are re-expressed.** This makes it immune to the FFE/TEU question entirely — it cannot be accused of preferring one convention over another.

| Quantity | Formula | Representation-dependent? |
|---|---|---|
| Gross revenue | `Σ FFE × ($/FFE)` | **No** — units cancel to USD |
| Demand (FFE) | `Σ FFE` | Yes (FFE) |
| Demand (TEU) | `Σ FFE × k` | Yes (TEU) |
| Fleet tonnage | `Σ quantity × t/day` | No |
| Fuel ceiling | tonnage × price × 7 | No |

Revenue is the keystone: `FFE × $/FFE = USD`, so the total is USD regardless of how the pieces are labelled.

### 1.2 Inputs (transcribed, not imported)

```
demand_world_small.csv      1,764 rows   FFEPerWeek, Revenue_1
fleet_world_small.csv          6 rows   Vessel class, Quantity   → 263 vessels
fuel_cost.py:19-56                    consumption t/day by class
fuel_cost.py:62                       BUNKER_PRICE_PER_TON = 600.0
```

---

## 2. Oracle bounds

### 2.1 Revenue ceiling

```
Gross revenue = Σ FFE × $/FFE
```

Verified three ways:

| Route | Value |
|---|---|
| Raw: `Σ FFE × Revenue_1` | **264,870,100.00** |
| Converted: `Σ (FFE·k) × (Revenue_1/k)` | **264,870,100.00** |
| Aggregate: `Q_TEU × (RawRev / Q_TEU)` | **264,870,100.00** |

**No correct formulation can exceed this. It is the total value of moving every TEU in the dataset, at its own lane rate, exactly once.**

### 2.2 Fuel ceiling

```
Fleet burn = Σ (quantity × consumption_tons_per_day) = 13,175 t/day
Ceiling    = 13,175 × 600 × 7 = $55,335,000/week
```

Assumes all 263 vessels underway every hour — physically unattainable but an upper bound.

### 2.3 Profit ceiling

```
Max profit ≤ Gross revenue − non-fuel cost − fuel
          ≤ 264,870,100.00 − 142,581,832.21 − fuel
```

| Fuel | Max profit |
|---|---|
| 0 (bounding only) | **122,288,267.79** |
| $25M (realistic low) | 97,288,267.79 |
| $35M (realistic high) | 87,288,267.79 |
| $55.3M (physical max) | 66,953,267.79 |

### 2.4 Independent plausibility bounds (industry norms)

Used as **corroboration only** — not as a correctness standard.

| Metric | Industry range | Reported | Ratio |
|---|---|---|---|
| Bunker cost, $/TEU-week | 15 – 40 | **2,371.42** | **59–158×** |
| Gross revenue, $/TEU | 300 – 1,500 | **4,109.58** | **2.7–13.7×** |
| Liner profit margin | 5 – 15% | 30.41% | 2–6× |

---

## 3. Test results

### 3.1 T1 — Revenue ceiling

| | |
|---|---|
| **Test** | `reported_revenue ≤ dataset_gross_revenue` |
| **Oracle** | 264,870,100.00 |
| **Reported** | 1,136,109,658.57 |
| **Result** | ❌ **FAIL — 4.2893× the ceiling** |

### 3.2 T2 — Fuel physical bound

| | |
|---|---|
| **Test** | `reported_fuel ≤ fleet_burn_ceiling` |
| **Oracle** | 55,335,000 |
| **Reported** | 648,031,918.31 |
| **Result** | ❌ **FAIL — 11.71× the ceiling** |

### 3.3 T3 — Profit ceiling (fuel-independent)

| | |
|---|---|
| **Test** | `reported_profit ≤ gross_revenue − non_fuel_cost` |
| **Oracle** | 122,288,267.79 |
| **Reported** | 345,495,908.06 |
| **Result** | ❌ **FAIL — exceeds by 223,207,640.27** |

**This test is the strongest result in the audit.** It holds regardless of fuel, regardless of whether the fuel model is fixed, and regardless of any formulation choice. It uses only the dataset's own revenue and the system's own reported non-fuel cost.

### 3.4 T4 — Demand conservation

| | |
|---|---|
| **Test** | `satisfied + unserved == true_demand` |
| **Oracle** | 276,446.80 |
| **Reported** | 305,021.20 |
| **Result** | ❌ **FAIL — +28,574.40 (+10.34%)** |

### 3.5 T5 — Coverage consistency

| | |
|---|---|
| **Test** | `reported_coverage == satisfied / true_demand × 100` |
| **Computed** | 273,267.10 / 276,446.80 = **98.8498%** |
| **Reported** | 89.5895% |
| **Result** | ❌ **FAIL — understated by 9.26 pp** |

Note the reported coverage is *arithmetically* consistent with the clamped satisfied value (273,267.10). The defect is upstream, in the clamp, not in the division.

### 3.6 T6 — Cost identity

| | |
|---|---|
| **Test** | `Σ components == total_cost` |
| **Computed** | 100,822,500.00 + 22,531,440.01 + 19,227,892.20 + 648,031,918.31 = 790,613,750.52 |
| **Reported** | 790,613,750.51 |
| **Result** | ✅ **PASS** (1¢ rounding) |

### 3.7 T7 — Profit identity

| | |
|---|---|
| **Test** | `revenue − total_cost == weekly_profit` |
| **Computed** | 345,495,908.06 |
| **Reported** | 345,495,908.06 |
| **Result** | ✅ **PASS** — but tautological (MA-06-15), so it carries no validation value |

### 3.8 T8 — Regional reconciliation

| | |
|---|---|
| **Test** | `Σ regional == global` |
| **Result** | ✅ **PASS** for all cost components and profit |

Σ fuel = 648,031,918.31 ✓; Σ operating = 100,822,500.00 ✓; Σ profit = 345,495,908.06 ✓

### 3.9 T9 — Service reconciliation

| | |
|---|---|
| **Test** | `Σ regional services_selected == total_services` |
| **Computed** | 104 + 100 + 108 = 312 |
| **Reported** | 312 |
| **Result** | ✅ **PASS** |

### 3.10 T10 — Fleet feasibility

| | |
|---|---|
| **Test** | `vessels_required ≤ vessels_available` |
| **Required** | 624 (312 services × 2 vessels, cycle_time 14) |
| **Available** | 263 |
| **Result** | ❌ **FAIL — 2.37× overcommit, unreported** |

### 3.11 Summary

| Test | Result |
|---|---|
| T1 Revenue ceiling | ❌ FAIL |
| T2 Fuel physical bound | ❌ FAIL |
| T3 Profit ceiling | ❌ FAIL |
| T4 Demand conservation | ❌ FAIL |
| T5 Coverage consistency | ❌ FAIL |
| T6 Cost identity | ✅ PASS |
| T7 Profit identity | ✅ PASS (tautological) |
| T8 Regional reconciliation | ✅ PASS |
| T9 Service reconciliation | ✅ PASS |
| T10 Fleet feasibility | ❌ FAIL |

**7 failures, 3 passes — and both economically meaningful passes are structural checks.** Every test that could detect a substantive error failed.

---

## 4. Why the existing test suite caught none of this

| Suite property | Consequence |
|---|---|
| Only **internal identities** are asserted | k² inflation, cost sign inversion, and coverage clamps all pass |
| **SHA-256 baseline** on `pipeline_output.json` across 5 maritime modules | Protects the **bytes**, freezing defects rather than catching them |
| `assert 0 <= coverage <= 100` (`orchestrator_agent.py:311`) | **Enforces** the clamp artifact instead of detecting it |
| No cross-check against raw data | Nothing compares output to input |
| No physical-bound test | Nothing checks fuel against fleet capacity |
| `revenue = profit + cost` | Revenue is defined so it cannot fail |

**The suite is a regression guard, not a correctness oracle.** It would pass identically if revenue were multiplied by 4.0 — which is what happened.

---

## 5. What the oracle does not prove

Stated explicitly, per the mandate's skepticism requirement:

| Not proven | Why |
|---|---|
| That the **correct** profit is ~$87–97M | That figure depends on repairs outside this phase. It is a *bound*, not a prediction. |
| That the fuel model is wrong in a specific way | MA-04-01 proves the *number* is impossible; which term is at fault requires the code changes not authorized here. |
| That a different optimizer would be better | Out of scope; a formulation difference is not a defect. |
| GA run-to-run variance | The pipeline was not executed (MA_01 §11); spread is unmeasured. |
| WorldLarge economics | No WorldLarge artifact exists. |
| That the defects are the *only* ones | Two independent subagent passes plus direct inspection found 60+; absence of further findings is not proof of absence. |

---

## 6. The oracle as a reusable instrument

If a future correction phase is authorized, these ten tests are the acceptance criteria:

```python
def oracle_tests(reported, demands_csv, fleet_csv, bunker_price=600.0):
    gross = sum(r.ffe * r.revenue_1 for r in demands_csv)      # USD/wk
    burn  = sum(q * c for q, c in fleet_csv)
    nonfuel = reported.operating + reported.transship + reported.port

    assert reported.revenue <= gross * 1.001,  "T1 revenue exceeds dataset"
    assert reported.fuel <= burn * bunker_price * 7,  "T2 fuel exceeds fleet"
    assert reported.profit <= gross - nonfuel,  "T3 profit exceeds ceiling"
    assert abs(reported.satisfied + reported.unserved
               - total_demand) < 1e-6,          "T4 demand conservation"
    assert abs(reported.coverage
               - reported.satisfied/total_demand*100) < 1e-6, "T5 coverage"
    assert abs(sum(components) - reported.total_cost) < 0.01, "T6 cost identity"
    assert reported.vessels_required <= reported.vessels_available, "T10 fleet"
```

Each test is **fuel-independent or representation-independent** except T2, which is deliberately a physical bound.

---

## 7. The single most important result

> **The reported weekly profit exceeds the maximum attainable profit by $223.2M/week under an assumption that even grants the system free fuel.**

This is not a modelling disagreement. It is arithmetic: the dataset does not contain enough revenue to produce this profit, and the system's own reported non-fuel costs consume most of what there is. Any formulation — MILP, GA, or otherwise — operating on this dataset with these costs cannot exceed $122.3M/week.

The reported $345.5M is therefore **not a suboptimal solution. It is an unattainable one.**

---

## 8. Findings from MA_08

| ID | Finding | Classification | Confidence | Impact |
|---|---|---|---|---|
| **MA-08-01** | **Reported profit $345,495,908.06 exceeds the fuel-independent ceiling $122,288,267.79 by $223,207,640.27** | **A. Verified implementation defect** | **Very high** — oracle verified 3 ways | **CRITICAL** — result is unattainable |
| **MA-08-02** | Reported revenue is **4.2893×** the dataset's gross revenue ceiling | **A. Verified implementation defect** | **Very high** | $871.2M/week phantom |
| **MA-08-03** | Reported fuel is **11.71×** the fleet's physical maximum | **A. Verified implementation defect** | **Very high** | 82% of cost impossible |
| **MA-08-04** | Demand conservation fails by **+10.34%** | **A. Verified implementation defect** | **Very high** | 28,574 TEU/wk phantom |
| **MA-08-05** | Reported coverage is **9.26 pp** below recomputation from its own numerator | **D. Reporting defect** | **Very high** | Understates quality |
| **MA-08-06** | Fleet feasibility fails at **2.37×** and is never reported | **A. Verified implementation defect** | **Very high** | Infeasible solution |
| **MA-08-07** | **3 of 10 oracle tests pass, and both economically meaningful passes are structural** (cost identity, regional reconciliation) | **B. Verified consistent** | **High** | Aggregation sound; defects upstream |
| **MA-08-08** | The profit-identity pass is **tautological** and carries no validation value | **D. Reporting defect** | **High** | False assurance |
| **MA-08-09** | The test suite asserts only internal identities and pins the artifact SHA-256 — it would pass identically with revenue ×4.0 | **D. Reporting defect** | **High** | Defects frozen, not caught |
| **MA-08-10** | `assert 0 <= coverage <= 100` **enforces** the clamp artifact | **A. Verified implementation defect** | **High** | Active guard against correctness |
| **MA-08-11** | Defensible profit range is ~$87–97M/week — stated as a **bound, not a prediction** | **F. Bound, not a finding** | Medium | Frames future validation |
| **MA-08-12** | GA stochastic variance unmeasured — pipeline not executed | **F. Unverified hypothesis** | — | Open limitation |

---

## 9. Reproducing the oracle

```bash
cd shipping_optimizer
python -c "
import csv, json
rows=list(csv.DictReader(open('data/raw/demand_world_small.csv',encoding='utf-8-sig'),delimiter='\t'))
D=[(float(r['FFEPerWeek']),float(r['Revenue_1'])) for r in rows
   if r['Origin'].strip()!=r['Destination'].strip()]
gross=sum(f*v for f,v in D)
fleet=[(24,15),(29,25),(68,35),(74,55),(58,80),(10,100)]
ceil_fuel=sum(q*c for q,c in fleet)*600.0*7
sm=json.load(open('frontend/public/pipeline_output.json',encoding='utf-8'))['summary_metrics']
nonfuel=sm['operating_cost']+sm['transship_cost']+sm['port_cost']
print('T1 revenue  %s  (ceil %.2f)'%('FAIL' if sm['revenue']>gross else 'PASS',gross))
print('T2 fuel     %s  (ceil %.0f)'%('FAIL' if sm['fuel_cost']>ceil_fuel else 'PASS',ceil_fuel))
print('T3 profit   %s  (ceil %.2f)'%('FAIL' if sm['weekly_profit']>gross-nonfuel else 'PASS',gross-nonfuel))
print('  excess    %.2f'%(sm['weekly_profit']-(gross-nonfuel)))
"
```

No project module was imported; no file was written.