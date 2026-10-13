# MA_04 — COMPLETE COST LEDGER AND FORMULATION AUDIT

**System:** AI Vessel Routing System — Multi-Agent Optimizer
**Audit mode:** Forensic, evidence-driven, read-only
**Date:** 2026-10-05
**Status:** COMPLETE

---

## 0. The headline

**Reported fuel cost is 11.7× the physically impossible maximum.**

The entire WorldSmall fleet — all 263 vessels — burning at design consumption, 24 hours a day, 7 days a week, at $600/tonne, costs **$55,335,000/week**. The artifact reports **$648,031,918.31/week**.

This is not a modelling-choice dispute. It is a bound derived from the project's own fleet file and its own consumption table, and it is exceeded by a factor of 11.7.

---

## 1. The reported cost ledger

From `frontend/public/pipeline_output.json` → `summary_metrics`:

| Component | USD/week | % of total cost | % of revenue |
|---|---|---|---|
| Fuel | **648,031,918.31** | **81.97%** | 57.04% |
| Operating | 100,822,500.00 | 12.75% | 8.87% |
| Transshipment | 22,531,440.01 | 2.85% | 1.98% |
| Port | 19,227,892.20 | 2.43% | 1.69% |
| **Total cost** | **790,613,750.51** | 100% | 69.58% |
| Revenue | 1,136,109,658.57 | — | 100% |
| **Weekly profit** | **345,495,908.06** | — | 30.41% |

**The cost identity holds exactly:**

```
100,822,500.00 + 22,531,440.01 + 19,227,892.20 + 648,031,918.31 = 790,613,750.52
```
(matches `total_cost` = 790,613,750.51 to 1¢)

Regional decomposition:

| Region | Services | Operating | Fuel | Transship | Port | Total cost | Profit |
|---|---|---|---|---|---|---|---|
| Asia | 104 | 42,843,750 | 317,028,478.29 | 12,344,146.67 | **913,818.00** | 373,130,192.96 | 309,439,989.61 |
| Europe | 100 | 20,935,000 | 113,427,137.78 | 2,243,176.00 | **14,825,836.20** | 151,431,149.98 | **308,493.42** |
| Americas | 108 | 37,043,750 | 217,576,302.24 | 7,944,117.33 | **3,488,238.00** | 266,052,407.57 | 35,747,425.03 |
| **Σ** | **312** | **100,822,500** | **648,031,918.31** | **22,531,440.00** | **19,227,892.20** | **790,613,750.51** | **345,495,908.06** |

**Every Σ reconciles exactly.** The aggregation layer is arithmetically sound. Every defect below is *upstream* of the ledger.

Two anomalies are immediately visible and both are real:

| Anomaly | Observation |
|---|---|
| **Asia port cost** | **913,818** across 104 services — **16.2× lower per service** than Europe's 14,825,836 across 100 |
| **Profit distribution** | Asia earns **964× more per service** than Europe (2,975,385 vs 3,085 USD/service/week) |

---

## 2. MA-04-01 — Fuel exceeds the physical maximum of the fleet (CRITICAL)

### 2.1 The bound

Computed from `data/raw/fleet_world_small.csv` (263 vessels) and `fuel_cost.py:19-56` (`VESSEL_FUEL_CONSUMPTION`), at `BUNKER_PRICE_PER_TON = 600.0`:

| Class | Vessels | t/day each | t/day total |
|---|---|---|---|
| Feeder_450 | 24 | 15 | 360 |
| Feeder_800 | 29 | 25 | 725 |
| Panamax_1200 | 68 | 35 | 2,380 |
| Panamax_2400 | 74 | 55 | 4,070 |
| Post_panamax | 58 | 80 | 4,640 |
| Super_panamax | 10 | 100 | 1,000 |
| **Total** | **263** | | **13,175 t/day** |

```
13,175 t/day × 600 USD/t   =  7,905,000 USD/day
           × 7 days/week   = 55,335,000 USD/week     ← HARD CEILING
Reported                   = 648,031,918 USD/week
Ratio                      = 11.71×
```

### 2.2 Why the bound is airtight

This ceiling assumes **every vessel in the fleet is underway every hour of every week** at its design daily consumption — no port time, no idle, no weather, no slow steaming. Real liner operation burns roughly **50–65%** of this (the model itself applies a 0.9 speed factor for port time, `fuel_cost.py:144`). So a realistic ceiling is ~$30–36M/week, making the reported figure **~18–21× realistic**.

**No unit ambiguity can rescue this.** Even if `BUNKER_PRICE_PER_TON` were mis-set by 10×, the tonnage alone is impossible. The fleet cannot burn 11.7× its design consumption.

### 2.3 Root cause — fuel is not tied to the fleet, and is multiplied by frequency

**There is no vessel↔service correspondence anywhere in the cost model.** `hub_milp.py:312-322`:

```python
fuel_cost = sum(
    calculate_weekly_fuel_cost(
        self.problem.services[s].ports,
        self.problem.distance_matrix,
        self.problem.services[s].vessel_class or "Post_panamax",
        self.problem.services[s].cycle_time or 7,
        **_ip2_fc_kwargs,
    ) * max(1, round(frequencies[s]) if s < len(frequencies) else 1)   # ← × frequency
    for s in range(len(self.problem.services))
    if s < len(services_mask) and services_mask[s]
)
```

Three compounding factors:

1. **Frequency multiplication.** Weekly fuel is multiplied by the service's frequency. A service at frequency *f* burns fuel for *f* sailings per week — correct in principle — but nothing constrains `Σ f` against the 263-vessel fleet. The constraint that would do so (`hub_milp.py:389`) is the **verified no-op** from MA-01-03.
2. **`max(1, round(...))` floor.** Frequency is floored at 1, so no service can escape its fuel charge.
3. **312 services × 1 vessel each = 312 vessels demanded against 263 available** — a 19% fleet shortfall that is neither detected nor reported.

**The cost model computes what the *proposed network* would burn, with no check that the fleet could supply it.** The result is an unconstrained, physically impossible number presented as achieved economics.

---

## 3. MA-04-02 — The fleet's own fuel data is loaded and never used

`network_loader.py:191-201` loads, per vessel class:

| Field | Consumer |
|---|---|
| `Bunker ton per day at designSpeed` | **none** |
| `Idle Consumption ton/day` | **none** |
| `TC rate daily (fixed Cost)` | **none** |
| `Capacity FFE` | **none** |
| `panamaFee`, `suezFee` | **none** |
| `designSpeed`, `minSpeed`, `maxSpeed` | **none** |

Fuel comes instead from a **hardcoded table** (`fuel_cost.py:19-56`) whose consumption figures are *nominally* the same industry-standard numbers — but which is disconnected from the fleet file. Charter cost is likewise never computed from `tc_rate_daily`.

**Classification: E — missing model component.** The data exists and is correct; the model ignores it.

### 3.1 Charter cost is entirely absent from the ledger

`operating_cost` traces to `Service.weekly_cost`, a **flat constant** — not to `tc_rate_daily × days`. For `regional_agent.py:266-274` the service default is `weekly_cost = 150,000` regardless of vessel class, size, or speed.

| Vessel cost line | Should be | Actually is |
|---|---|---|
| Charter | `tc_rate_daily × cycle_days` (class-specific) | flat `weekly_cost` constant |
| Canal transit | `panama_fee` / `suez_fee` per transit | **absent entirely** |
| Port call fixed | `port_call_cost` per call | present but misapplied (MA-04-04) |

`distance_dense.csv` carries `IsPanama` and `IsSuez` flags that are **never read** — the routing information needed to charge canal fees is present in the data and unused.

---

## 4. MA-04-03 — FrequencyGA omits fuel from its fitness

```python
# src/optimization/frequency_ga.py:211
return revenue - operating_cost - transship_cost - overcap_penalty - port_cost
```

Fuel is computed at `:161-166` but is **not in the returned expression**. The frequency optimizer therefore selects frequencies that maximize profit-without-fuel.

**Consequence.** The GA drives frequencies as high as the objective allows, because fuel does not oppose it. That directly feeds MA-04-01: with no fuel term and no fleet constraint, frequency is unconstrained upward, and the MILP — which *does* charge fuel per frequency — inherits an inflated frequency vector.

**Classification: A — verified implementation defect.** The variable is computed and discarded.

---

## 5. MA-04-04 — Port cost is computed on the wrong basis

### 5.1 MILP port cost

```python
# hub_milp.py:599-601
share = port_service_loads[p][s_idx] / port_load[p]
port_alloc += share * (load * handling + load * variable)   # per-TEU rate × service TOTAL load
port_alloc += share * fixed                                  # per-CALL fixed cost × a load ratio
```

Two distinct errors:

| Defect | Detail |
|---|---|
| **Per-TEU rate applied to service total load** | `handling` and `variable` are **USD per TEU** rates. They are multiplied by `load`, the **service's total load across all ports** — not the load at this port. A 5000-TEU service calling at 10 ports is charged the per-TEU handling rate ten times over on 5000 TEU instead of once on 500 TEU. |
| **Fixed per-call cost multiplied by a load ratio** | `port_call_cost` is USD **per call**. Multiplying it by `share` (a load fraction) produces a meaningless intermediate. A fixed cost per call must be multiplied by the **number of calls**, not a tonnage ratio. |

### 5.2 ServiceGA port cost — stale variable leak

```python
# service_ga.py:262-281  (inside the per-port loop)
for p_id in svc.ports:
    port = next(...)
    if port:
        port_hc = getattr(port, "handling_cost", 0.0)     # ← set inside the loop
        ...
        port_cost += served * handling_cost + fixed_cost + served * variable_cost
```

`port_hc` is assigned inside the `for p_id` loop and **persists after the loop exits**. Then:

```python
# service_ga.py:295
service_cost = svc.weekly_cost + service_fuel_cost + (served * port_hc if 'port_hc' in locals() else 0)
```

The service-level cost for the **negative-margin penalty** uses the handling cost of whichever port happened to be **last in the service's port list** — not a sum over ports, not a port-specific cost.

| Defect | Detail |
|---|---|
| **Stale-variable leak** | `port_hc` is loop-scoped in practice but function-scoped in fact; `'port_hc' in locals()` is true whenever *any* prior iteration defined it |
| **Last-port-only** | Negative-margin penalties use one arbitrary port's handling rate for the entire service |
| **`fixed_cost` zeroed when dataset value is 0** | `fixed_cost = port_fixed if port_fixed > 0 else 0` silently discards a legitimately-zero-but-meaningful rate and treats "missing" as "free" |

**This explains the Asia port-cost anomaly.** Asia's `port_cost` is 913,818 across 104 services (8,786/service); Europe's is 14,825,836 across 100 (148,258/service) — **16.9× difference** for comparable service counts and the same cost code. The regional divergence is a symptom of the basis error interacting with different port mixes and port-load distributions.

---

## 6. MA-04-05 — Transshipment cost double-counts load

```python
# hub_milp.py:548-551
transfer_flow[(d, s1, s2)] ...
# revenue split /2.0 applied while transshipment load is counted in full
```

A transferred unit is charged transshipment cost while its revenue is halved. Whether this is a defect or a formulation choice depends on intent — but it is **not documented**, and it is applied at `/2.0` as a hardcoded constant rather than derived.

**Classification: C — specification ambiguity** (pending the intent question in §9).

---

## 7. MA-04-06 — The unserved-demand penalty is a penalty, not a cost

`alpha_unserved = 300.0` (`regional_agent.py:314`) enters the MILP objective as an **objective penalty**:

```
profit_expr − 300 × unserved_expr
```

It is **not** a line in the reported cost ledger. The comment at `orchestrator_agent.py:314-315` claims:

> *"the unserved penalty is treated as a cost captured in the operating cost component"*

This is **factually wrong**. Inspecting `operating_cost` at `hub_milp.py:304-309`:

```python
operating_cost = sum(
    self.problem.services[s].weekly_cost * max(1, round(frequencies[s]) ...)
    for s in range(...) if s < len(services_mask) and services_mask[s]
)
```

It is a sum of `weekly_cost × frequency` — nothing else. The unserved penalty is absent from every reported cost line and is instead absorbed into the reported `profit`.

**Classification: D — reporting defect.** The cost ledger is incomplete relative to the stated objective, and the comment misdescribes where the penalty lands.

---

## 8. Independent fuel oracle

Because the reported fuel figure is physically impossible, an independent bound is derived from first principles — no project code involved.

### 8.1 Upper bound (physical ceiling)

```
Ceiling = Σ_classes (quantity × consumption_tons_per_day) × bunker_price × 7
        = 13,175 t/day × 600 USD/t × 7 days
        = $55,335,000 / week
```

### 8.2 Realistic bound

Real liner services spend a fraction of calendar time underway. The project's own model uses `speed × 24 × 0.9` (`fuel_cost.py:144`), implying 90% time-at-sea. Adding port-time idle consumption and typical 85–90% schedule utilization:

| Basis | Weekly fuel |
|---|---|
| Absolute ceiling (263 vessels, 100% underway) | **$55,335,000** |
| 90% underway (project's own factor) | $49,801,500 |
| 75% schedule utilization | $41,501,250 |
| Typical liner actual | **$25,000,000 – $35,000,000** |
| **Reported** | **$648,031,918** |
| **Overstatement vs ceiling** | **11.71×** |
| **Overstatement vs realistic** | **~19–26×** |

### 8.3 Per-TEU cross-check

```
Reported fuel / served demand = 648,031,918.31 / 273,267.10 TEU = 2,371.42 USD/TEU
```

Ocean liner bunker cost is conventionally ~**15–40 USD/TEU-week**. The reported figure is **~59–158×** the industry range.

| Cross-check | Value | Ratio to reported |
|---|---|---|
| Industry fuel, $/TEU-week (15–40) | 4,099,007 – 10,930,684 | reported is **59–158×** higher |
| Absolute fleet ceiling, $/TEU-week | 202.49 | reported is **11.7×** higher |
| **Reported, $/TEU-week** | **2,371.42** | — |

All three independent methods — fleet tonnage ceiling, schedule utilization, and per-TEU industry norm — converge on the same conclusion. **The reported fuel cost is wrong by at least an order of magnitude.**

---

## 9. What is *not* claimed

Per the audit mandate, this document does **not** assert which of these should be corrected how. Specifically:

| Question | Status |
|---|---|
| Should fuel use `fleet.bunker_consumption_tons_per_day`? | **Not decided here.** The hardcoded table is nominally equivalent; the defect is the *absence of any fleet constraint*, not the table. |
| Should `weekly_cost` be derived from `tc_rate_daily`? | **Not decided.** It may be a deliberate flat-rate abstraction. Flagged as a modelling gap. |
| Should canal fees be added? | **Not decided.** They are data the model ignores, not costs it was specified to include. |
| Is the `/2.0` revenue split on transfer correct? | **Intent undocumented.** Recorded as ambiguity. |
| Is 0.9 the right at-sea factor? | **Not decided.** Plausible as published. |

The one unambiguous finding is MA-04-01, because it requires no modelling judgement at all: **a number that exceeds a physical bound derived from the project's own fleet file is wrong under every formulation.**

---

## 10. Complete cost ledger — what should exist vs what does

| Real-world cost element | In dataset? | In model? | In reported ledger? |
|---|---|---|---|
| Bunker fuel | ✅ (fleet t/day) | ⚠ hardcoded table, unconstrained | ✅ 648.0M (impossible) |
| Vessel charter | ✅ (`tc_rate_daily`) | ❌ flat `weekly_cost` | ⚠ as "operating" |
| Canal transit (Panama/Suez) | ✅ (`IsPanama`, `IsSuez`, fees) | ❌ | ❌ |
| Port handling | ✅ | ⚠ wrong basis | ⚠ 19.2M |
| Port fixed call | ✅ | ⚠ × load ratio | ⚠ (in above) |
| Transshipment | ✅ | ⚠ double-count | ⚠ 22.5M |
| **Vessel count constraint** | ✅ 263 vessels | ❌ **no-op** | ❌ never reported |
| Idle / in-port consumption | ✅ | ❌ | ❌ |
| Canal transit time | ✅ (`Draft`, canal) | ❌ | ❌ |
| Bunker price volatility | — | ❌ single constant 600 | — |
| **Unserved demand penalty** | — | ✅ objective term | ❌ **absent from ledger** |
| **Overcapacity penalty** | — | ✅ GA only | ❌ |

**Of 12 real-world cost elements present in the dataset, 3 are modelled correctly, 3 are modelled on a wrong basis, and 6 are absent entirely.**

---

## 11. Findings from MA_04

| ID | Finding | Classification | Confidence | Impact |
|---|---|---|---|---|
| **MA-04-01** | **Reported fuel cost $648.0M/wk is 11.71× the entire 263-vessel fleet's physical maximum ($55.3M/wk)** — computed from the project's own fleet file and consumption table | **A. Verified implementation defect** | **Very high** — three independent methods agree | **CRITICAL** — invalidates the entire economic result |
| **MA-04-02** | No vessel↔service correspondence; fuel is `Σ per-service × frequency` with the fleet constraint a **verified no-op** (MA-01-03), so frequency is unconstrained upward | **A. Verified implementation defect** | **High** | Mechanism for MA-04-01 |
| **MA-04-03** | `frequency_ga.py:211` computes fuel at `:161-166` then **omits it from the returned fitness** | **A. Verified implementation defect** | **High** | GA selects frequencies unopposed by fuel |
| **MA-04-04** | MILP port cost applies **per-TEU rates to service-total load** and multiplies a **per-call fixed cost by a load ratio** (`hub_milp.py:599-601`) | **A. Verified implementation defect** | **High** | Port cost wrong basis |
| **MA-04-05** | ServiceGA `port_hc` is a **stale loop variable** used post-loop for the negative-margin penalty (`service_ga.py:295`) — effectively last-port-only | **A. Verified implementation defect** | **High** | Margin penalties use one arbitrary port's rate |
| **MA-04-06** | `fixed_cost = port_fixed if port_fixed > 0 else 0` treats a legitimate 0 as "missing" | **A. Verified implementation defect** | High | Zero rates silently become free |
| **MA-04-07** | `unserved penalty` enters the objective but is **absent from every reported cost line**; the comment claiming it is "captured in the operating cost component" is factually wrong | **D. Reporting defect** | **High** — `operating_cost` is `Σ weekly_cost × freq` only | Ledger incomplete vs stated objective |
| **MA-04-08** | Entire fleet economic vocabulary loaded and unused: `bunker_consumption_tons_per_day`, `idle_consumption_tons_per_day`, `tc_rate_daily`, `capacity_teu`, `panama_fee`, `suez_fee` | **E. Missing model component** | **High** | Charter, canal, real fuel all unmodelled |
| **MA-04-09** | `IsPanama` / `IsSuez` distance-matrix flags never read — canal transit cost and time entirely absent | **E. Missing model component** | **High** | Panama/Suez transits unpriced |
| **MA-04-10** | `Service.weekly_cost` is a flat constant (default 150,000), not `tc_rate_daily × days` | **B. Formulation choice** (possibly deliberate) | Medium | Charter cost not class-differentiated |
| **MA-04-11** | Asia `port_cost` 913,818 (104 svc) vs Europe 14,825,836 (100 svc) — **16.9× per-service divergence** from the same code path | **D. Reporting defect** (symptom of MA-04-04/05) | **High** | Regional cost figures not comparable |
| **MA-04-12** | Asia earns **2,975,385 USD/service/week**; Europe **3,085** — **964× divergence** with comparable service counts and satisfied demand within 3.3× | **D. Reporting defect** | **High** | Regional results are not economically comparable |
| **MA-04-13** | Transshipment revenue split hardcoded `/2.0` with transfer load charged in full; intent undocumented | **C. Specification ambiguity** | Medium | Affects transfer economics |
| **MA-04-14** | Cost ledger **identity holds exactly** at both global and regional levels | **B. Verified correct** | **High** | Aggregation layer is sound; defects are upstream |

---

## 12. Reproducing the fuel bound

```bash
cd shipping_optimizer
python -c "
fleet={'Feeder_450':(24,15),'Feeder_800':(29,25),'Panamax_1200':(68,35),
       'Panamax_2400':(74,55),'Post_panamax':(58,80),'Super_panamax':(10,100)}
tpd=sum(q*c for q,c in fleet.values())
v=sum(q for q,_ in fleet.values())
ceil_wk=tpd*600.0*7
print('vessels            =',v)
print('fleet burn         = %.0f t/day'%tpd)
print('physical ceiling   = \$%.0f/week'%ceil_wk)
print('reported           = \$648031918/week')
print('ratio              = %.2fx'%(648031918/ceil_wk))
print('reported per TEU   = \$%.2f  (industry 15-40)'%(648031918.31/273267.10))
"
```

No project module was imported; no file was written. The figure comes from `data/raw/fleet_world_small.csv` and `src/utils/fuel_cost.py:19-56,62` only.