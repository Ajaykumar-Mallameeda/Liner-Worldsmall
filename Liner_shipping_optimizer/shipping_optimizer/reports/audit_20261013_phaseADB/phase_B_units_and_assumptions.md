# Phase B — Data, units and modelling assumptions (read-only)

Paper under review: *Liner Shipping Network Design with Reinforcement Learning*, Dutta, Lin, Jin (C3 AI), arXiv:2411.09068v1 (13 Nov 2024), 28 printed pages,
file `C:\Users\WINDOWS\Downloads\copies\linershipping\source.pdf`, SHA-256 `689a408a…5898b`.  It is **not** named `RL_paper.pdf`; identity INFERRED from content.
Page numbers are the printed page numbers.  Text was extracted with `pdftotext`; Table 2 lost its row alignment in extraction (§1.4).

## 1. What the paper defines

### 1.1 Unit evidence (minimal quotes)

| # | Quantity | Evidence (page / item) | Reading | Label |
|---|---|---|---|---|
| P1 | raw demand quantity | p.15 A.1, `dq`: "demand quantity in FFE per week"; p.3 §3: "demands specified in the quantity of Forty-Foot Equivalent units (FFE)" | **FFE per week** | VERIFIED (paper) |
| P2 | flow variable | p.16 Eq. 29–31: `f_ed` "the quantity of commodity demand d that flows through edge e", summed against `dq` (Eq. 30: `Y_d(dq − Σ f)`) | same unit as `dq` ⇒ **FFE** (implied by Eq. 30, never stated separately) | INFERRED |
| P3 | vessel capacity | p.15 A.1, `vcap`: "the maximum number of FFEs the vessel can carry at once"; p.9: "Feeder 800 vessels (with a capacity of 800 FFEs)" and "Feeder 450 … 450 FFEs" | **FFE** | VERIFIED (paper) |
| P4 | revenue rate | p.15, `dR`: "Revenue, generated per unit FFE transported"; Eq. 29 `R = Σ dR · f` | **USD per FFE** | VERIFIED |
| P5 | port / transshipment rates | p.15: `pv` "additional cost in USD per FFE for visiting this port, based on the vessel's capacity"; `pt` "cost in USD per FFE for transferring cargo across different services" | **USD per FFE**; `pf` USD per call | VERIFIED |
| P6 | rejected-demand penalty | p.15, `Yd`: "penalty for rejection of this demand, which is set to $1000"; Eq. 30 multiplies it by unserved `dq − Σf` | **USD 1,000 per unit of demand (FFE)** — per unit vs per demand record is not stated; Eq. 30 reads per unit | INFERRED (per FFE) / AMBIGUOUS |
| P7 | time horizon of profit | p.15: demands "normalized to a weekly frequency" (p.15 A.1, p.3); Tables 1–2 give "Profit ($)" / "Max profit (in million $)" with no horizon | probably per week | **AMBIGUOUS** |
| P8 | output tables | Table 1 (p.9) "Profit ($) breakdown"; Table 2 (p.10) "Max profit (in million $)" | USD; horizon not stated | AMBIGUOUS |
| P9 | vessel use / frequency | p.3: "permit fractional vessel assignments"; p.16–17: `n_{v,s}` is the vessel count per service, "required number of vessels can be calculated as a function of the total distance … and the vessel's designed speed … no expected idle time … except for the required 1 day at each port" (p.17) | **fractional vessels**, no integer frequency, 1 day per port call | VERIFIED |
| P10 | unused / excess vessels | p.9 Table 1 + text: "if a solution utilizes fewer vessels than the available fleet, a profit is gained based on the time charter rate … more … additional costs"; Eq. 34 `C_unused = −Σ (v_n − Σ n_{v,r})·v_TC` | **credited / charged at TC rate** (soft fleet limit) | VERIFIED |
| P11 | capacity & fleet constraints | p.9 §6: "we relax the hard limit on the number of vessels, treating it as a soft constraint with an associated penalty"; p.16: capacity limits derived from vessel capacity of the services (details deferred to Brouer et al. 2014) | per-edge capacity = Σ vessels × `vcap` (FFE) | INFERRED (full constraints not in the paper) |
| P12 | transit time | p.3: "excluding considerations for transit time and vessel speed optimization" | **no end-to-end transit constraint** | VERIFIED |
| P13 | port-call cost basis | Eq. 35 `(p_f + p_v·v_cap)·n_{v,s}` summed over ports of each service (p.17) | variable port cost charged on **vessel capacity per call**, not on cargo | VERIFIED (equation) / equation glyphs partly lost in extraction |
| P14 | handling | Eq. 31 (p.16): onload/offload cost `p_l` on flow at origin/destination + `p_t` on transfers | per FFE of flow | INFERRED (symbol `p_l` garbled; text p.16 states "two components") |
| P15 | “TEU” | the string "TEU" does not occur in the paper (0 matches) | **the paper is FFE-native throughout** | VERIFIED |

### 1.2 Consequence for "all quantities are FFE"

The paper defines demand, flow, vessel capacity, revenue rate, port / transshipment rates and penalty in the **same** unit (FFE).  It does not state a relationship to TEU.
The statement "vessel classes are labelled in FFE" is therefore **not** what carries the evidence: the paper's own Appendix A.1 defines `vcap` as an FFE count.

### 1.3 What the paper does *not* establish

* The unit of the *original LINERLIB column* `Capacity FFE` in the benchmark's own technical report (Brouer, Pisinger, Sigurd 2014) — the RL paper is a *secondary* source
  (it re-uses the dataset and describes it).  The primary source is not in the project.  → **AMBIGUOUS at the primary source**, defined at the secondary source.
* Whether penalty is per FFE or per demand record (P6).
* Whether profits are weekly (P7).

### 1.4 Table 2 (p.10) values — World Small

The extraction yields four World Small numbers `42.73 42.32 32.28 40.10` for four rows (encoder-only RL, encoder-decoder RL, LINERLIB, ORTools).  The row alignment
could not be established from the text layer (no rendering tool was available).  **Do not use these values as a target** until the table is read from the rendered page.
Baltic (0.28 / 0.29 / 0.26) and WAF (5.60 / 5.60 / 5.20) are stated in the paper; they are outside the scope of this task (Baltic and WAF must not be run).

### 1.5 Differences between the paper's model and ours (comparability)

| Aspect | Paper | Ours (live tree) | Evidence |
|---|---|---|---|
| Demand / flow unit | FFE | TEU (= FFE × k, k ≈ 2) | `network_loader.py:515, 528` |
| Vessel capacity | FFE count | `Capacity FFE` used **as TEU** | `network_loader.py:675` |
| Revenue | USD/FFE × FFE | USD/TEU × TEU, gross invariant | `load_demands` |
| Rejected demand | −1000 USD per unit | 0 in objective and ledger | `network_milp.py` docstring; A9 |
| Unused vessels | credit at TC | none | grep, Phase D §5 |
| Vessels / frequency | fractional | integer `f`, `n = ceil(T f/7)` | `required_vessels` |
| Transit-time | none | hard end-to-end limit + 5.5 d dwell per transfer | `paths.py` |
| Port stay | 1 day | 24 h | `EconomicsAssumptions.port_stay_hours` |
| Variable port cost | `pv × vcap` per call | per TEU of cargo | `paths.py:20–22`, `ledger.py:291–301` |
| Fuel | `dist/speed × vfs` + idle per port day | `designSpeed` operating point; same inputs | `economics.py` |
| Fleet limit | soft | hard per class | MILP |
| MCF | greedy heuristic | exact LP/MILP | App. B vs `network_milp.py` |

Every row but the first three is a **modelling-variant difference**, not a unit difference; none can be changed in this task.

## 2. Our unit trace

| Quantity | Source field | Raw unit | Conversion (code) | Internal unit | Downstream | Evidence | Risk | Status |
|---|---|---|---|---|---|---|---|---|
| OD demand | `Demand_WorldSmall_Fixed_Sep.csv · FFEPerWeek` | FFE/week (loader docstring; paper P1) | `weekly_teu = ffe · k`, `k = FFE_TO_TEU_LANE_FACTORS.get(f"{o}-{d}", 2.0)` | TEU/week | MILP demand rows, coverage denominator | `network_loader.py:175–177, 515, 528` | six ODs use unsourced 1.75–2.1 | **Verified (code); provisional (k)** |
| Revenue rate | `Revenue_1` | USD/FFE | `÷ k` | USD/TEU | objective, ledger | `:515–530` | double conversion if later ÷2 again | Verified |
| Port costs | `CostPerFULL`, `CostPerFULLTrnsf`, `PortCallCostPerFFE` | USD/FFE (loader asserts; no upstream sentence — A11) | `÷ TEU_PER_FFE (2.0)` (lane-independent) | USD/TEU | paths, ledger | `:444–455` | direction correct if raw is per FFE | **Provisional** |
| Port-call fixed | `PortCallCostFixed` | USD/call | none | USD/call | `f · Σ` | loader | – | Verified |
| Vessel capacity | `fleet_data.csv · Capacity FFE` | **UNKNOWN** (paper: FFE) | **none** (`capacity_teu = value`) | "TEU" | leg capacity `cap · f`, class screening, load factor | `:675`, `CAPACITY_UNIT_PROVENANCE` | factor 2 relative to demand | **Contradicted relative to the paper; provisional in code** |
| Vessel quantity | `fleet_WorldSmall.csv · Quantity` | vessels | int | vessels | fleet constraint | loader | – | Verified |
| Cargo flow on a leg | MILP `q_p` | TEU/week | – | TEU/week | capacity, ledger | MILP | – | Verified |
| Weekly frequency | `f_s` | departures/week | integer | – | `n = ceil(T f/7)`, cap·f | MILP | A10 | Provisional |
| Round trip | `service_feasibility.evaluate_rotation` | days | distance / (kn·24) + 24 h/port, "declared whole days" | days | `n`, fuel | `economics.py` | – | Verified (source) |
| Distance | `dist_dense.csv · Distance` | nautical miles (paper P-A.1 `edist`) | none | nm | cycle time | loader | – | Verified |
| Transit limit | `TransitTime` | days (reproduces upstream revision rule on 105/105 ODs, REPORTED) | none | days | path feasibility | `:520–522` | semantic scope (A1) | Verified (unit), Unverified (scope) |
| Load factor | ledger / metrics | – | carried TEU / (cap·f) per leg | ratio | KPIs | `metrics.py` | ratio invariant under consistent scaling **only if** capacity is scaled with flow | Verified |
| Coverage | CSV `coverage_pct` | – | `served_teu / demand_teu` | % | verdict | CSV | – | Verified |
| Profit, margin, cost per unit | ledger | USD/week | – | USD/week | KPIs | `ledger.py` | no penalty ⇒ not paper's objective | Verified |

Two facts from this trace that the prior reports state only partly:
1. The loader docstring (module docstring, unit contract block) declares that **quantities are FFE→TEU converted but the vessel column is not**; the asymmetry is the single point where the model's
   capacity-to-demand ratio is determined.  Effect (REPORTED S2): ×1.6–2.5 on profit.
2. Per-lane factors 1.75 / 1.85 / 1.9 / 2.1 are labelled "based on typical cargo mix" with no source; they contradict `TEU_PER_FFE = 2.0` used for costs and are inconsistent
   with the definition (1 FFE = 2 TEU exactly).  Affects six WorldSmall ODs (CNSHA→DEHAM/NLRTM/USLAX, AEJEA→DEHAM/NLRTM, BRSSZ→USLAX), −47.2 TEU of 276,494 (−0.017 %).

## 3. Canonical unit dictionary (proposed; not applied)

| Symbol | Definition | Paper-comparison mode | Operational mode |
|---|---|---|---|
| FFE | forty-foot equivalent = 2 TEU (exactly) | native unit of all quantities | converted at the loader boundary |
| TEU | twenty-foot equivalent | not used | internal cargo unit: demand = 2·FFE, **capacity = 2·`Capacity FFE`** (pending D-01) |
| revenue rate | USD per unit of the mode's cargo unit | USD/FFE | `Revenue_1 / 2` |
| handling / transshipment / port-variable | USD per unit | USD/FFE (paper: `pv·vcap` per call) | `÷ 2` per TEU; basis (cargo vs capacity) per D-02 |
| penalty | USD per unit rejected | 1000 per FFE | 0 in operations (reported separately if used) |
| vessels / frequency | fractional vs integer | fractional | integer weekly |

## 4. FFE / TEU conclusion

* **The convention 1 FFE = 2 TEU is correct and is what the loader uses for demand and port rates.**
* **The vessel capacity is the inconsistent quantity.**  By the only document in the project that defines the column's role (the RL paper p.15 / p.9), `Capacity FFE`
  counts FFEs.  The code reads it as TEU.  Under the paper's definition the capacity in TEU is **2 × the loaded value**, so the model's capacity is half of what its
  own demand conversion implies.
* The primary source (LINERLIB technical report) is not available; the LINERLIB README and OR-tools page state no unit (REPORTED, `CAPACITY_UNIT_PROVENANCE`).
  Therefore the status is: **CONTRADICTED relative to the secondary source; UNVERIFIED at the primary source; owner decision D-01 required.**
* **Do not** double capacity "because the field is called FFE", and do not leave it "because the code treats it as TEU": both are exactly the guesses the policy
  forbids.  The evidence now available (paper p.15, p.9, P15) supports FFE, which is a sufficient reason for the owner to decide, not for the audit to change code.
* The FFE/TEU gate **does not pass** (§8).

## 5. Dimensional-consistency test plan (specifications only; nothing implemented)

| # | Invariant | Production functions exercised | Expected |
|---|---|---|---|
| T1 | `to_teu(1 FFE) = 2`; `to_ffe(to_teu(x)) = x` | new boundary helper (or `network_loader.TEU_PER_FFE` use sites) | exact round trip |
| T2 | Demand given in FFE vs the same physical demand given in TEU produces identical served physical cargo | `load_demands` → `solve_network` (fixed pool, fixed frequencies) | `served_teu` equal to 1e-9 relative |
| T3 | Capacity in FFE vs TEU (same physical capacity) gives identical feasibility and flows | `load_fleet` → `build_models` → MILP | identical `f`, `n`, flows |
| T4 | `weekly_teu · revenue_per_teu` invariant under the inverse scaling of quantity and rate | `load_demands` | equal for all 1,764 rows; includes the six lane-factor ODs |
| T5 | handling / transshipment / port-variable cost invariant under unit change | `load_ports` + `ledger.compute_ledger` | equal total cost |
| T6 | load factor invariant when numerator and denominator scale together | `metrics` | equal |
| T7 | coverage invariant | `metrics` / CSV columns | equal |
| T8 | profit, margin and ledger reconciliation invariant | `compute_ledger`, `reconcile` | equal to 1e-6 relative |
| T9 | capacity-vs-demand unit mismatch is detected | loader contract check (e.g. `Capacity FFE` unit flag ≠ demand unit) | `DataValidationError` / model invalid, never silent |
| T10 | missing / ambiguous unit (status `provisional` without source) is surfaced in the result and in `capacity_unit_status` | `strategy_report`, `reconcile` (existing `capacity_unit_status`) | explicit `provisional` / `invalid` |
| T11 | independent-unit oracle: recompute served cargo and profit in FFE-native arithmetic from raw files and compare with the TEU pipeline | new test using only `pandas` + raw CSV | equal — this closes B-03's common-mode gap |

## 6. Transit, frequency, vessel and cost assumption register

| Assumption | Code value / formula | Evidence | Status | Known impact | Consequence if wrong | Clarification needed |
|---|---|---|---|---|---|---|
| `TransitTime` unit | days, max end-to-end | upstream revision rule reproduced on 105/105 ODs (REPORTED) | Verified (unit) / Unverified (includes port + dwell?) | 41 ODs / 3.37 % demand unservable | coverage ceiling misstated | LINERLIB report |
| Dataset match with paper | `Demand_WorldSmall_Fixed_Sep.csv` = unrevised transit file; paper says nothing about transit | benchmark page recommends revised file | Contradicted (authors' recommendation) | 13.0 % demand; ±0.5 M (n = 3) | – | owner D-04 |
| Sailing time | `distance / (designSpeed·24)`, whole days | `economics.py` | Verified (source) | – | – | – |
| Speeds / class eligibility | `designSpeed` only; min/max read, not used | `fleet_data.csv`; `economics.py` | Provisional (no consumption-vs-speed law) | – | – | data |
| Port stay | 24 h | benchmark page (secondary); paper: 1 day (p.17) | Verified (secondary) | S3a/b ±2–5 M | – | primary source |
| Transfer min / dwell | 48 h + 3.5 d wait per transfer | benchmark page (48 h); 3.5 d unsourced | Provisional | ±2.3 M, coverage ±5 pp (S4) | – | owner convention D-06 |
| Cycle-time rounding | "declared whole days", `ceil(round(T f/7, 9))` | `required_vessels` | Verified (source) | – | vessel count ±1 per service | – |
| Integer weekly frequency | `f ∈ {0,1,2,…}` | paper permits fractional vessels (p.3) | Unverified | not run | structure | owner D-07 |
| Capacity per leg / departure | `cap · f` | MILP | Verified (source) | – | – | D-01 |
| Fleet semantics | `Quantity` = available vessels per class, hard | paper: soft + TC credit | Provisional | not run | – | D-02 |
| Fuel units | t/day × days × USD/t | ledger agrees < 1e-6 | Verified (internal) | – | – | – |
| Fuel price / grade | 600 USD/t uniform, VLSFO-equivalent | benchmark page; dated snapshot covers 5 of 47 ports, no licence | Verified (benchmark value); Unverified (grade) | B400 +5.6 M; B1000 collapses to 2–4 services | – | procurement |
| Port-call / handling units | `/2` per FFE→TEU | loader contract only | Provisional | not run | cost ×2 error | D-01 / A11 |
| Revenue horizon | per week | paper ambiguous (P7); demand per week | Provisional | – | – | – |
| Rejection penalty | none | paper: 1000 | Provisional | ranks plans by coverage if applied | non-comparable objective | D-02 |
| Unused vessels | no term | paper: TC credit | Unverified | not run | – | D-02 |
| Canal fees | blank = unknown | fleet file | Provisional | not run | – | D-08 |

## 7. Required owner decisions (Phase B)

| ID | Question | Options | Evidence | Recommendation | Blocks next phase |
|---|---|---|---|---|---|
| D-01 | Unit of `Capacity FFE` | (a) FFE ⇒ `capacity_teu = 2×`; (b) TEU as is; (c) leave provisional and report both | paper p.15/p.9; code provenance; S2 | (a), after the owner checks the LINERLIB report; otherwise (c) with both reported | **Yes** |
| D-02 | Paper mode: penalty, unused-vessel credit, fractional vessels, per-capacity port cost | adopt as a separate flag / not | paper Eq. 28–35 | adopt only as a separate mode; operational objective unchanged | Yes for comparison, no for operations |
| D-03 | Lane-specific FFE→TEU factors | remove (k = 2) / source / keep | unsourced | remove or source them | No (tiny), but needed for T4 |
| D-04 | Revised transit file | adopt / keep and record reason | benchmark authors' recommendation; no measurable change at n = 3 | adopt for benchmark comparisons | No |
| D-06 | Transfer-dwell convention | keep 3.5 d / change | no source | keep; do not relax to buy coverage | No |
| D-07 | Sub-weekly frequency in scope | yes / no | A10 | clarify before any model work | No |
| D-08 | Canal fees (A12), fuel grade (A7) | supply data | fleet file blanks | supply | No |

## 8. Phase B gate

| Gate | Result |
|---|---|
| Unit convention evidence-based and internally consistent | **FAIL** — the capacity unit is contradicted by the paper and unresolved at the primary source; every quantity downstream of capacity is conditional |
| Every unresolved unit isolated with a blocking decision | **PASS** (D-01, D-03; lane factors and per-FFE cost units listed) |
| Paper unit evidence extracted with page citations | **PASS** (P1–P15); Table 2 values **NOT VERIFIED** (§1.4) |
| Dimensional-consistency plan written | **PASS** (T1–T11), not implemented |

## 9. Proposed minimal correction sequence (no implementation)

1. Owner resolves D-01 (and D-03).
2. Write T1–T11 first.  Under option (a), T3, T9 and T11 are expected to fail on the current tree (that is their purpose); T1 and T4–T8 are expected to pass already.
3. Change **one** place — the loader's `capacity_teu` — and update `CAPACITY_UNIT_PROVENANCE`, `tests/test_capacity_units.py`, `strategy_report.capacity_unit`, docs.
4. Re-freeze the baseline (new hashes), then evaluate the accepted candidates on the corrected units; do not carry over absolute profit figures from the old units.
