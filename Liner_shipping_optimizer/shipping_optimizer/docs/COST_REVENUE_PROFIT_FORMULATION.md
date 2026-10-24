# Cost, Revenue and Profit Formulation - Present Working Configuration

Liner shipping network design (WorldSmall / LINERLIB) - AI Vessel Routing System

| Item | Value |
|---|---|
| Written | 2026-10-17 |
| Code state described | git `HEAD` = `47bbdb9` **plus the uncommitted working tree** (modified: `src/data/network_loader.py`, `src/network/network_milp.py`, `src/network/plan.py`, `src/network/reconcile.py`, `src/network/trunk_candidates.py`; the opt-in experiments `dual_screen`, `targeted_paths`, `trunk_lanes` are archived under `archive/experimental_not_retained_2026-10-15/` and are NOT part of the described configuration). None of the uncommitted edits changes a cost or revenue formula. |
| Dataset | WorldSmall (47 ports, 1,764 OD rows, 6 vessel classes, 263 vessels) |
| Horizon | one operating **week**, steady state; annual figures are `weekly x 52` |
| Currency / units | USD; TEU (1 FFE = 2 TEU, converted once at the loader); nautical miles; knots; days; metric tonnes |
| Method of writing | Every formula below was read from the source file named next to it (file:line refer to the working tree on the date above). The cost and revenue totals of the stored run were then **recomputed by hand from the raw data files**, independently of the optimiser; see Section 14. |

**How to read the status tags.** Each assumption carries the status the code itself assigns in
`src/network/assumption_register.py` (the register that every plan stores in `network_ledger.assumptions.assumption_register`):

| Tag | Meaning |
|---|---|
| `SOURCED_PRIMARY_CODE` | defined by the benchmark authors' reference code / their solution logs (the primary technical-report text was **not** read) |
| `SOURCED_SECONDARY` | defined by a secondary source (benchmark web page, RL paper arXiv:2411.09068) |
| `PROVISIONAL` | a modelling convention without a source; results are conditional on it |
| `UNVERIFIED` | an interpretation not confirmed by any available source |
| `NOT_MODELLED` | a real cost/constraint the model does not contain |
| `CODE-ONLY` | (this document's tag) an assumption that is in the code but is **not** in the register; found while reading the code |

---

## 1. The configuration this document describes

"Present working configuration" = the code defaults **plus the C3 flag set**, which is what `tests/test_orchestrator.py` applies (`C3_CONFIGURATION`, lines 3146-3156; `apply_c3_configuration()`) and what the stored `pipeline_output.json` (`dataset_run.c3_flags`) records.

| Layer | Setting | State |
|---|---|---|
| Economics | port stay 24 h; min. transshipment time 48 h; expected transfer wait 3.5 d; bunker 600 USD/t uniform; sailing speed = class design speed; weather speed factor 1.0 | default |
| Objective | profit only; no coverage reward; no penalty for unserved cargo in the global stage (`unserved_penalty_per_teu = 0`) | default |
| Paths | `selection = fastest`, 10 paths per OD, `max_transfers = 2` (two-transfer paths only for ODs with no direct/one-transfer path), transit-time limit enforced when paths are built | default |
| Post-solve | flow re-optimisation LP **ON**; profit-floor repair (floor 0) **ON** | default |
| Candidate pool | demand-coherent loops (budget 60 per region, 3-5 ports); per-rotation class screening (k = 1, time-feasible class); economic regional filter | default |
| Solver | PuLP 2.7.0 + bundled CBC 2.10.3, single thread; global stage budget `GLOBAL_STAGE_TIME_LIMIT_SEC = 120` | default |
| **C3 flag 1** | `LINER_MILP_VUB=1` - adds the valid inequality `q[od,p] <= weekly_teu[od] * f[s]` | **ON** (C3) |
| **C3 flag 2** | `LINER_LOCAL_SEARCH=1` - exact-LP add/drop/frequency moves; takes 15 s of the 120 s budget | **ON** (C3) |
| **C3 flag 3** | `LINER_TRUNK_CANDIDATES=12`, `LINER_TRUNK_DIVERSE=1`, `LINER_TRUNK_MAX_PORTS=10` - 12 class-forced trunk rotations per under-subscribed class, <= 10 ports | **ON** (C3) |
| **C3 flag 4** | `LINER_MILP_SUPPORT_CAP=105` - integer problem keeps at most 105 LP-support services | **ON** (C3) |
| Not in the configuration (OFF) | route operators / elitism, class variants, LP-rounded start, path-include, HiGHS backend, global coverage floor, regional bunker-price snapshot, maritime intelligence | OFF |

None of the C3 flags changes any cost or revenue formula; they change which services and flows the optimiser *finds*. The formulas in Sections 3-8 are identical with and without them.

---

## 2. Notation

| Symbol | Meaning | Unit |
|---|---|---|
| `s` | a candidate **service** = closed rotation of `n_s` distinct ports sailed by one vessel class | - |
| `c(s)` | vessel class of service `s` | - |
| `f_s` | integer **departures per week** of `s` (0 = not operated) | 1/week |
| `N_s` | vessels deployed on `s` | vessels |
| `d` | an OD demand record (origin `o`, destination `t`) | - |
| `Q_d` | weekly demand of `d` | TEU/week |
| `r_d` | revenue rate of `d` | USD/TEU |
| `L_d` | maximum end-to-end transit time of `d` | days |
| `k` | a **path** (1-3 service segments) for an OD | - |
| `q_k` | TEU/week of OD `d(k)` routed on path `k` | TEU/week |
| `u_d` | TEU/week of `d` left unserved | TEU/week |
| `cap_c` | capacity of one vessel of class `c` | TEU |
| `TC_c` | time-charter hire rate | USD/vessel/day |
| `v_c`, `b_c`, `i_c` | design speed; fuel at design speed; fuel while in port | kn; t/day; t/day |
| `N_c` | vessels owned of class `c` (inventory) | vessels |
| `D(a,b)` | directed sailing distance | nm |
| `g_p` | fixed cost per port call (`PortCallCostFixed`) | USD/call |
| `e_p` | port-call capacity charge rate (`PortCallCostPerFFE / 2`) | USD per TEU of vessel capacity per call |
| `h_p` | handling cost (`CostPerFULL / 2`) | USD/TEU |
| `x_p` | transshipment cost (`CostPerFULLTrnsf / 2`) | USD/TEU |
| `fee_c^Pan`, `fee_c^Sue` | canal fee per traversal (blank in data = class cannot pass) | USD/traversal |
| `H` | port stay per call | 24 h = 1 day |
| `W` | expected wait for the connecting weekly departure | 3.5 days |
| `M` | minimum transshipment handling time | 48 h = 2 days |
| `P_s` | bunker price applicable to `s` | USD/t |
| `phi` | weather speed factor | 1.0 by default |

---

## 3. Input data and the unit boundary

All sources are tab-separated files in `data/raw/WorldSmall/` (extension `.csv`). Conversion happens **once**, in `src/data/network_loader.py`; nothing downstream converts again. `1 FFE = 2 TEU` exactly (the earlier lane-specific factors 1.75-2.1 were removed as unsourced; `FFE_TO_TEU_LANE_FACTORS = {}`).

| Raw column (file) | Conversion | Model symbol | Loader line |
|---|---|---|---|
| `FFEPerWeek` (demand) | `x 2` | `Q_d` TEU/wk | network_loader.py:574 |
| `Revenue_1` (demand), USD/FFE | `/ 2` | `r_d` USD/TEU | :575 |
| `TransitTime` (demand) | read as **days** | `L_d` | :565-568 |
| `Capacity FFE` (fleet_data) | `x 2` | `cap_c` TEU | :734 |
| `TC rate daily (fixed Cost)` | none | `TC_c` USD/day | :735 |
| `designSpeed`, `Bunker ton per day at designSpeed`, `Idle Consumption ton/day` | none | `v_c`, `b_c`, `i_c` | :741-748 |
| `panamaFee`, `suezFee` | none; **blank -> `None`** (not 0) | `fee_c` | :757-763 |
| `CostPerFULL` (ports), USD/FFE | `/ 2` | `h_p` | :490-491 |
| `CostPerFULLTrnsf` | `/ 2` | `x_p` | :496-498 |
| `PortCallCostFixed` | none (per call) | `g_p` | :493-495 |
| `PortCallCostPerFFE` | `/ 2` | `e_p` | :499-501 |
| `Distance`, `IsPanama`, `IsSuez`, `Draft` (dist_dense) | none | `D(a,b)`, canal flags, leg draft | :633-658 |
| `Quantity` (fleet_WorldSmall) | none | `N_c` | :704-716 |

Invariant enforced by construction: `weekly_teu x revenue_per_teu == FFEPerWeek x Revenue_1` for every OD, and `converted TEU flow x converted USD/TEU == raw FFE flow x raw USD/FFE` for every per-FFE rate (rates are always divided, never multiplied).

**WorldSmall vessel classes (raw file values, converted)**

| Class | Owned `N_c` | Capacity FFE -> `cap_c` TEU | TC USD/day -> hire per vessel-week (`7 TC`) | Design speed kn | Bunker t/day | Idle t/day | Draft m | Panama fee | Suez fee |
|---|---|---|---|---|---|---|---|---|---|
| Feeder_450 | 24 | 450 -> 900 | 5,000 -> 35,000 | 12 | 18.8 | 2.4 | 8 | 64,800 | 175,769 |
| Feeder_800 | 29 | 800 -> 1,600 | 8,000 -> 56,000 | 14 | 23.7 | 2.5 | 9.5 | 115,200 | 218,445 |
| Panamax_1200 | 68 | 1,200 -> 2,400 | 11,000 -> 77,000 | 18 | 52.5 | 4.0 | 12 | 172,800 | 267,217 |
| Panamax_2400 | 74 | 2,400 -> 4,800 | 21,000 -> 147,000 | 16 | 57.4 | 5.3 | 11 | 345,600 | 413,533 |
| Post_panamax | 58 | 4,200 -> 8,400 | 35,000 -> 245,000 | 16.5 | 82.2 | 7.4 | 13 | **blank = cannot pass** | 633,007 |
| Super_panamax | 10 | 7,500 -> 15,000 | 55,000 -> 385,000 | 17 | 126.9 | 10.0 | 12.5 | **blank = cannot pass** | 1,035,376 |

Totals of the demand file: 1,764 OD rows; **276,494 TEU/week**; gross revenue if every TEU were carried **264,870,100 USD/week** (mean 957.96 USD/TEU).

---

## 4. Service physical model (what the costs are built on)

Implemented once in `src/network/economics.py` (`build_service_model`, lines 215-307) and **re-derived independently** in `src/network/ledger.py` (lines 141-250) from the raw records.

```
legs of s            closed rotation: (p1,p2), (p2,p3), ..., (pn,p1)           n legs for n ports
speed                v = v_c * phi                                              (phi = 1.0 default)
sea_days_s           = sum over legs of  D(a,b) / (v * 24)
port_days_s          = n_s * H/24                                               (one stay per call; 1 day each)
T_exact_s            = sea_days_s + port_days_s
T_s  (declared)      = ceil( round(T_exact_s, 9) )                              whole days
vessels N_s(f)       = ceil( round(T_s * f / 7, 9) )                            0 if f = 0
max departures       f_max = floor( 7 * N_c / T_s )                             bounded by class inventory
capacity             cap_c * f  TEU per week on EVERY leg of the rotation
```

Consequence worth stating in a paper: because `T_s` is rounded **up** to whole days and `N_s` is an **integer**, the model charges whole vessels. A 10-day rotation needs 2 vessels for one weekly departure although 10/7 = 1.43. This is more conservative than the benchmark paper, which uses fractional vessel counts (register item `weekly_frequency`, status `UNVERIFIED`).

---

## 5. Cost components

The operating cost is the sum of **seven reported items** (the ledger carries an eighth field, `port_variable_cost`, that is always 0 - see 5.8). Items 5.1-5.5 are **service-level** (paid whether or not the vessel is full); 5.6-5.7 are **cargo-level** (per TEU carried).

### 5.1 Vessel hire (`vessel_cost`)

| | |
|---|---|
| Definition | Time-charter hire of every vessel deployed, for the whole week, regardless of load. |
| Formula | `C_vessel = sum_s  N_s * TC_c(s) * 7`   with `N_s = ceil(T_s f_s / 7)` |
| Data | `TC rate daily (fixed Cost)`, fleet inventory |
| Implemented | `economics.py:294` (`vessel_week_cost = tc_rate_daily * 7`), `:167-168`; ledger `ledger.py:232,236` |
| Used by | MILP objective (`network_milp.py:385`), fleet constraint (`:413,419`), local search, repair, ledger |
| Status | Rate: benchmark data. Integer-vessel rule and `x7`: modelling convention (`weekly_frequency`, `UNVERIFIED`). **Unused vessels cost nothing and earn nothing** (register `unused_vessels`, `PROVISIONAL`). |
| MILP detail | The MILP carries `n_s` as a variable with `7 n_s >= T_s f_s`. A time-limited incumbent can hold surplus vessels; `_trim_slack_vessels` (`network_milp.py:117-137`) cuts `n_s` to `ceil(T_s f_s/7)` so the objective equals what the ledger charges (amount reported in `vessel_slack_removed`). |

### 5.2 Fuel (`fuel_cost`)

| | |
|---|---|
| Definition | Fuel burnt at sea at the class design speed plus fuel burnt in port (idle consumption) for every port day, per rotation, times departures per week, times the bunker price. |
| Formula | `fuel_t_s = sea_days_s * b_c + port_days_s * i_c`  (tonnes per rotation)<br>`C_fuel = sum_s  f_s * fuel_t_s * P_s` |
| Data | `Bunker ton per day at designSpeed`, `Idle Consumption ton/day`, distances; price from `bunker_prices.py` |
| Implemented | `economics.py:270-271, 295-296`; ledger `ledger.py:229-231, 237` (tonnes **recomputed** in the ledger, only the price is passed in) |
| Price rule | **Default `legacy_uniform` = 600 USD/t for every service** (`bunker_prices.py:69`; stored run: `fuel_pricing.mode = legacy_uniform`, `provenance = assumed`). The alternative `regional_snapshot` mode (pinned file `data/pricing/bunker_snapshot_2026-10-09_vlsfo.json`; cheapest observed bunkering port on the rotation, otherwise a global reference) exists but is **OFF** in this configuration. |
| Used by | MILP (`network_milp.py:386`), all screens, ledger |
| Status | Consumption: benchmark data **at design speed only**; no consumption-vs-speed law is modelled. Price: `SOURCED_SECONDARY` (benchmark page), explicitly *not* a market price. Fuel grade (`fuel_grade`): `UNVERIFIED`. |
| Share of cost | Largest item (33.2 % of cost in the stored run; 34.7 % in the 20-seed C3 mean). |

### 5.3 Port-call fixed cost (part of `port_call_fixed_cost`)

| | |
|---|---|
| Definition | A fixed charge each time a vessel calls at a port, once per call of every weekly rotation. Independent of cargo. |
| Formula | `C_portfix = sum_s  f_s * sum_{p in s} g_p` |
| Data | `PortCallCostFixed` |
| Implemented | `economics.py:278-279`; ledger `ledger.py:239-240` |
| Status | Structure follows the authors' reference code (`bm_reader.cpp`) and solution log (34/34 services reconciled, per `economics.py:272-275`). The per-FFE unit reading of the companion columns is `PROVISIONAL` (register `cost_units`). |

### 5.4 Port-call capacity charge (part of `port_call_fixed_cost`)

| | |
|---|---|
| Definition | The per-FFE port-call charge is applied to the **vessel capacity**, not to the cargo: each call costs `PortCallCostPerFFE x vessel capacity (FFE)`. In TEU terms: `e_p x cap_c`. |
| Formula | `C_cap = sum_s  f_s * cap_c * sum_{p in s} e_p`,  with `e_p = PortCallCostPerFFE / 2` |
| Implemented | `economics.py:276-277`; ledger `ledger.py:178-180, 241` (memo field `port_capacity_charge_cost`) |
| Note | It is **not** a cargo charge. `paths.py:24-26` states this explicitly, and the path charge `pi_k` (5.6/5.7) therefore excludes it. |
| Status | `PROVISIONAL` (`cost_units`): the "per FFE of capacity" reading is taken from the reference code and log; no upstream sentence confirms the unit. |

### 5.5 Canal fees (part of `port_call_fixed_cost`)

| | |
|---|---|
| Definition | Panama and Suez traversal fees, charged **per directed leg of the closed rotation flagged `IsPanama` / `IsSuez`**, once per weekly departure. |
| Formula | `C_canal = sum_s  f_s * ( n_s^Pan * fee_c^Pan + n_s^Sue * fee_c^Sue )`  where `n_s^Pan`, `n_s^Sue` count flagged legs of the closed rotation |
| Rules | A blank fee means the class **cannot pass**: the service is rejected (`canal_not_passable_for_class`), never charged 0. Draft feasibility (hard): class draft <= every port draft on the rotation and <= the draft limit of any leg that lists one. |
| Implemented | `physical_rules.py:50-86`; `economics.py:253-257, 279`; ledger re-derivation `ledger.py:175-215` |
| Status | `SOURCED_PRIMARY_CODE` (reference-code `calculate_canal_cost` and the authors' WorldSmall log: 34/34 traversal counts, costs within the log's rounding). Fees are benchmark data, not a verified real tariff. Owner countersign (decision D-08) is recorded as outstanding in the register. |
| Reported as | included in `port_call_fixed_cost`; separately as memo `canal_fee_cost`. |

**Reported line:** `port_call_fixed_cost = C_portfix + C_cap + C_canal`  (`ledger.py:239-241, 249`).

### 5.6 Handling (`handling_cost`)

| | |
|---|---|
| Definition | Load at the origin port and unload at the destination port, per TEU carried. |
| Formula | `C_handle = sum over flows (od, path k, q_k)  q_k * ( h_o + h_t )`  with `h_p = CostPerFULL / 2` |
| Implemented | `paths.py:448` (`base_cost`); ledger `ledger.py:337`; MILP objective via `port_cost_per_teu` (`network_milp.py:384`) |
| Rule | Only the origin and destination ports are charged. Through-cargo staying on board at an intermediate port is **not** charged. |
| Status | Unit reading `PROVISIONAL` (`cost_units`). |
| Share | 29.5 % of cost in the stored run (second-largest item). |

### 5.7 Transshipment (`transshipment_cost`)

| | |
|---|---|
| Definition | Cost of moving a TEU between two services at a hub. It **replaces** the discharge-plus-reload lifts (no separate handling at the hub). |
| Formula | `C_trans = sum over flows  q_k * sum_{hub in path k} x_hub`,  `x_p = CostPerFULLTrnsf / 2` |
| Implemented | `paths.py:431, 501` (`hcost`); ledger `ledger.py:340-343` |
| Time side-effect | each transfer adds a **dwell** to transit time: `M/24 + W = 2 + 3.5 = 5.5 days` (`economics.py:105-107`). |
| Status | Cost rate: benchmark data (`PROVISIONAL` unit reading). Dwell: 48 h from the benchmark page (`SOURCED_SECONDARY`), the 3.5 d wait is a **model convention** (`transfer_dwell`, `PROVISIONAL`). |

### 5.8 `port_variable_cost` (reserved, always 0)

The ledger dataclass has the field (`ledger.py:62`) and prints it, but nothing increments it: the per-FFE port charge was moved into 5.4. It stays in the output schema (stored run: `0.0`). Do not present it as a cost component in the paper.

### 5.9 Total operating cost

```
C_total = C_vessel + C_fuel + C_portcall(= C_portfix + C_cap + C_canal) + C_handle + C_trans + 0
```
`Ledger.operating_cost` (`ledger.py:73-76`).

### 5.10 Cost deliberately NOT in the profit (status `NOT_MODELLED` / `PROVISIONAL`)

| Not included | Why / where stated |
|---|---|
| Penalty for unserved demand | The benchmark paper uses 1,000 USD per rejected FFE (`paper_ledger.py`); the operating profit **excludes** it by definition (`rejection_penalty`, `PROVISIONAL`). The global MILP's `unserved_penalty` defaults to 0 and is reported separately if ever non-zero. |
| Credit for unused vessels | The paper credits spare vessels at the TC rate; here they cost and earn 0 (`unused_vessels`). |
| Cargo-handling **time**, slack in weekly schedules, weather, congestion | `economics.py:30-31`: no source. Weather speed factor exists only behind the optional maritime-intelligence flag (OFF). |
| Speed optimisation / slow steaming | One operating point per class (design speed). |
| Empty-container repositioning, container leasing, inventory/cargo-delay value, demand elasticity, overheads, capital cost, insurance, port/terminal dues beyond the data columns, carbon cost | not in the data or code. |

---

## 6. Revenue

| | |
|---|---|
| Definition | Revenue is earned **per TEU delivered**, at the rate of the OD, **once per OD TEU** (not per leg, not per service ridden, not reduced for transfers or for transit time). |
| Formula | `R = sum over flows (od d, path k)  q_k * r_d`,  `r_d = Revenue_1 / 2` (USD per TEU) |
| Equivalent per OD | `R_d = served_d * r_d`,  `0 <= served_d = sum_k q_k <= Q_d` |
| Implemented | ledger `ledger.py:336`; MILP `network_milp.py:383` (`revenue = sum r_d * q`); flow re-opt `flow_reopt.py:87-88` |
| Partial service | Allowed: `q` is continuous, so a fraction of an OD's weekly TEU can be carried and the rest left unserved (`sum_k q_k + u_d = Q_d`). |
| Attribution to services | `row["revenue"]` per service (`ledger.py:346-352`) splits an OD's revenue over the services of its path in proportion to **ride days**. This is for reporting only; totals are not affected. |
| Time-feasibility | A path is built only if its end-to-end transit time <= `L_d` (days). Transit = sailing days of ridden legs + one port stay at each *intermediate* port + `5.5 d` at each hub. The ledger re-checks (`transit_time_exceeded`). |
| Status | Rates: benchmark data; per-FFE -> per-TEU reading `SOURCED_SECONDARY` (`ffe_to_teu`). `TransitTime` file choice: `PROVISIONAL`; its scope (does it include port time?): `UNVERIFIED` (`transit_file`, `transit_scope`). |

---

## 7. Profit, margin and coverage (the reported numbers)

```
Operating profit  Pi  = R - C_total                                (USD/week)
Annual profit           = 52 * Pi                                   (assumes 52 identical weeks)
Profit margin           = Pi / R                                     (None when R <= 0 or ledger unverified)
Coverage                = served_TEU / total_demand_TEU
served_TEU              = sum_d min( sum_k q_k , Q_d )
```

Accounting identity (`ledger.py:10-22`, enforced and re-checked by `metrics.py:196-200`):

```
operating_profit = cargo_revenue
                 - vessel_cost - fuel_cost - port_call_fixed_cost
                 - handling_cost - transshipment_cost - port_variable_cost
```

* **Authority.** The ledger (`src/network/ledger.py`) is computed **from the plan alone** - which services run at which frequency and which TEU rode which service segments - using the raw distance matrix, fleet and port records. It does not import the service model or the MILP. It is the only source of reported profit (`metrics.py:20-24`). If the ledger has a violation, the result is not reported as verified.
* **Checks the ledger runs** (`ledger.py`): duplicate/invalid service, unknown class, missing distance or port record, draft infeasibility, canal not passable, missing fuel price, **fleet inventory per class**, path validity (connectivity, no revisited port, no service ridden twice, at most `max_transfers + 1` segments), **leg capacity** (`load <= cap_c f` on every leg), **demand conservation**, **transit-time limit**.
* **MILP/ledger reconciliation** (`plan.py:395-409`): `|MILP profit - ledger profit| <= 1e-6 * scale + 1e-3`; otherwise `reconciled = false` and the verified flag is withdrawn (`reconcile.py:479`).
* **Margin verdict band** (`metrics.py:47, 67-100`): advisory target **15 %** of revenue; bands `at_or_above_target / below_target / loss / undefined / unverified`. It is advisory only: it never blocks acceptance, changes feasibility, drives a rerun or chooses an iteration.

---

## 8. Optimisation objective and constraints (what the solver maximises)

### 8.1 Network MILP (`src/network/network_milp.py`)

Variables: `f_s` integer, `n_s` integer, `q_k >= 0`, `u_d >= 0`.

```
maximise   sum_k ( r_d(k) - pi_k ) q_k
         - sum_s [ 7 TC_c(s) n_s  +  ( F_s + G_s ) f_s ]
         - lambda * sum_d u_d                       lambda = 0 in the global stage (default)

  pi_k = h_o + h_t + sum_{hub in k} x_hub           per-TEU path charge          (paths.py:448,501)
  F_s  = fuel_t_s * P_s                             fuel per rotation            (economics.py:295)
  G_s  = sum_p g_p + cap_c sum_p e_p + canal_s      port + capacity + canal per rotation (economics.py:278)

subject to
  demand        sum_{k of d} q_k + u_d  = Q_d                         each OD once
  leg capacity  sum_{k riding (s,l)} q_k <= cap_c f_s                 EVERY leg l of EVERY service
  vessels       7 n_s >= T_s f_s                                      (i.e. n_s >= ceil(T_s f_s / 7))
  fleet         sum_{s in class c} n_s <= N_c                         per class
  bounds        f_s <= min( floor(7 N_c / T_s), ceil(demand reachable by s / cap_c) )
  [C3]  VUB     q_k <= Q_d * f_s    for every service s on path k     (valid inequality, removes no integer point)
```

Lines: objective `:383-389`; demand `:391-396`; leg capacity `:398-403`; VUB `:404-411`; vessels `:412-413`; fleet `:414-419`; `f` upper bound `:355-361`.

With `lambda = 0` the objective **is** the operating profit; any penalty is reported separately in `objective_components` and never enters the ledger. (In the regional stage `HubMILP` passes `alpha_unserved = 300 USD/TEU` as an optimisation-only penalty with *fixed* frequencies; the figures it reports are still the ledger's, and the regional numbers are replaced by the global stage - Section 9.)

### 8.2 Solution method and what is (not) claimed

1. LP relaxation (`f`, `n` continuous) -> `relaxation_bound`, a valid upper bound **for the capped model only**; services used by the LP (`f > 1e-6`) are the "LP support".
2. [C3] keep at most 105 LP-support services (those carrying most LP cargo).
3. Integer problem on that restriction with CBC, time-limited (120 s stage; 15 s reserved for local search). Status is `optimal` **only** if the restricted MILP closed **and** no service was dropped; otherwise `feasible`.
4. Post-solve improvement, each step keeping the ledger valid:
   * **Local search** [C3] (`local_search.py`): moves `add / drop / freq +-1`, each evaluated by the exact cargo LP; profit of a configuration `F` = `LP_margin(F) - sum_s weekly_fixed_cost_s(f_s)`.
   * **Flow re-optimisation** (`flow_reopt.py:51-168`): with all `f_s`, `n_s` fixed, solve the LP `max sum (r_d - pi_k) q_k` over **all** valid time-feasible paths of the operated services (not just the 10 per OD), subject to OD demand and leg capacity, never serving less than the incumbent. Replaces the flows only if the margin rises by > 1 USD.
   * **Profit-floor repair** (`flow_reopt.py:174-331`): only if profit < 0; switches off the worst loss-making services and re-routes. Untouched when profit >= floor (it was not applied in the stored run: "profit floor met").
5. The independent ledger recomputes everything (Section 7).

Honest status wording used by the code (`solve_semantics.py`): the raw CBC string `"Optimal"` is **not** a proof; the conclusion of the stored run's capped MILP is `feasible_time_limit_gap_unresolved` (incumbent 32.81 M, bound 46.68 M USD/week, gap 29.7 % **of the capped model**), and the final plan (44.98 M after local search and flow re-optimisation) "is not comparable to the capped bound as optimality evidence" (`optimality_claim: none`).

---

## 9. Regional bookkeeping (partition of the verified global result)

The pipeline first solves per region, then re-solves **one global network** over the union of all candidate services (`reconcile.py`), so regional numbers are never summed from independent solves. After the global plan is verified it is partitioned back to regions so that `sum(regions) == global ledger` exactly (`reconcile.py:332-471`):

| Item | Assigned to |
|---|---|
| revenue, served/unserved TEU, handling, transshipment | the region of the OD's **origin** (disjoint) |
| a service's vessel, fuel, port-call (incl. capacity charge and canal) cost | **one** region: a deterministic two-phase rule (every region with cargo gets one service it uses; remaining services go to the region whose cargo uses them most; ties prefer the proposer, then region order) |
| region total cost / profit / margin | `total_cost = vessel + fuel + port_fixed + handling + transship`; `profit = revenue - total_cost`; `margin = profit / revenue` |

Only the *split between regions* depends on this rule; the network totals do not.

---

## 10. Search-time surrogates (guide the search; never reported as profit)

| Where | Formula | Caveats found in the code |
|---|---|---|
| `economics.estimate_best_frequency` (`:310-324`) | `f* = argmax_{1<=f<=min(f_max, ceil(demand/cap))}  min(cap f, demand) * rev_net - weekly_fixed_cost(f)`; `weekly_fixed_cost(f) = N(f) 7 TC + f * fuel/rotation + f * portcall/rotation` | demand and `rev_net` are per-service aggregates of the ODs with both ends on the rotation and a transit-feasible ride |
| ServiceGA (`service_ga.py:245-292`) | `profit = revenue - fixed - port`, with `served_od = min(Q_od, sum_s cap_s*share_{s,od})`; fitness (profit_first) `= 10*profit/1e7 + 0.01*coverage + 0.1*cost/1e7` (`normalization.py`) | **(i)** per-TEU port charge `_od_port` adds `h + e` at both ends (`:144-147`), i.e. it charges `PortCallCostPerFFE` as a cargo charge **and** (inside `weekly_fixed_cost`) as a capacity charge - a double count that exists only in this surrogate; **(ii)** no transshipment cost and direct-only cargo sharing; **(iii)** the `cost` weight is +0.1, so fixed cost enters with coefficient -9.9 instead of -10 (immaterial); **(iv)** in `profit_first` mode the coordinator's weight adjustments (`profit_weight`, ...) are not used by the fitness (they act only in `legacy` mode) |
| FrequencyGA (`frequency_ga.py:146-151`) | `margin_i(f) = min(cap f, route_demand_i) * net_rev_i - weekly_fixed_cost(f)`, repaired to the class inventory | same double count of `e_p` in `net_rev` |
| Stand-alone profit screens (`demand_coherent._Evaluator`, `class_screening`, `trunk_candidates`, `regional_filter`) | `standalone = sum_od served_od * net_rate_od - weekly_fixed_cost(f)`, `net_rate = r - (h_a + e_a + h_b + e_b)` | used to *rank/select candidates*, "a screen, not a verdict"; the same `e_p` double count makes the screens slightly pessimistic; stand-alone profits are not additive across overlapping services |
| Cost-aware path slot cost (`paths.py:275-301`, OFF by default) | `F_s(1) * tau / (T_s * cap_c)` per TEU, full-load lower bound | informational |

Because the final network is chosen by the global MILP and priced by the ledger, these surrogate effects can change *which candidates are explored*, not the reported profit of a given plan.

---

## 11. Decision-layer quantities (control flow, not economics)

| Quantity | Definition | Source |
|---|---|---|
| Rerun triggers | coverage < **70 %**, or profit < **0**, or any service-overlap conflict; capped at 3 iterations | `coordinator_agent.py:20-27, 612-657` |
| Convergence score | `( min(1, cov/70) + [profit>0] + conflict_score ) / 3` | `coordinator_agent.py:657` |
| Iterations | `MIN_ITERATIONS = MAX_ITERATIONS = 3` (convergence is suppressed until three candidates exist) | `orchestrator_agent.py:33-34, 1028-1039` |
| Iteration selection | Pareto dominance over `{profit, global coverage, total_cost, unserved, negative-profit regions, violations, conflicts}`, then deterministic weighted score `0.60 profit + 0.25 coverage + 0.15 total_cost` (normalised); an LLM may propose, but is validated and falls back to the deterministic rule | `iteration_selection.py:40-104` |
| `total_cost` used by the decision layer | the **all-in** cost (hire + fuel + port + handling + transshipment) from the verified ledger; `operating_cost` is only the hire component and is kept for display | `metrics.py:11-18` (finding F-15) |

The 70 % coverage target and the 15 % margin band are *targets/advisories*, not constraints of the optimisation; the stored run ends at 44.6 % coverage because the objective is profit, not coverage.

---

## 12. Paper-comparison ledger (separate from the operational model)

`src/benchmark/paper_ledger.py` / `paper_evaluator.py` re-evaluate a network with the cost equations of Dutta, Lin, Jin (arXiv:2411.09068, App. A, Eq. 28-35) so results can be compared like for like. **It is not the operational profit.**

```
profit_paper = R_total - C_reject - C_handle - C_NDP,            C_NDP = C_service + C_unused + C_voyage
C_reject  = 1000 USD x FFE rejected                              (Eq. 30)
C_handle  = sum q ( p_l[origin] + p_l[destination] + sum p_t[transfer ports] )     (Eq. 31)
C_service = sum_s n_s TC_c 7                                      (Eq. 33; fractional n_s)
C_unused  = -(N_c - sum n_s) TC_c 7   (a credit when vessels are spare)           (Eq. 34)
C_voyage  = port calls (p_f + p_v x vessel capacity) + fuel (sailing + 1 idle day per call) + canal   (Eq. 35)
```
Differences from the operational model: fractional vessels, rejection penalty, unused-vessel credit, no transit-time limit, unlimited transfers, greedy routing. Whether voyage terms are charged per rotation or per vessel is an explicit switch; the authors' log supports `per_rotation`. The paper gives **no fuel price** (the code takes it as an argument and leaves fuel cost unavailable if none is given).

---

## 13. Complete assumption list

### 13.1 Registered assumptions (verbatim from `assumption_register.py`)

| Id | Assumption | Value | Status | Affects |
|---|---|---|---|---|
| capacity_unit | Vessel capacity unit | `Capacity FFE x 2 -> TEU` once at the loader | `SOURCED_PRIMARY_CODE` (reference code types capacity as FFE; RL paper agrees; technical-report text not read) | capacity, coverage, profit levels (**x1.6-2.5 against the TEU reading**) |
| ffe_to_teu | FFE -> TEU | 1 FFE = 2 TEU exactly | `SOURCED_SECONDARY` | demand, revenue rates, per-FFE costs |
| transit_file | Transit-time limits | `Demand_WorldSmall_Fixed_Sep.csv` (original `TransitTime`, days) | `PROVISIONAL` (authors recommend the revised file; 13.0 % of demand differs; 105 ODs) | coverage |
| transit_scope | `TransitTime` scope | end-to-end days incl. port stays and transfer dwell | `UNVERIFIED` | coverage |
| port_stay | Port stay per call | 24 h | `SOURCED_SECONDARY` (benchmark page; paper: 1 day) | cycle time, vessels, transit |
| transfer_dwell | Transfer dwell | 48 h minimum + 3.5 d expected wait | `PROVISIONAL` (48 h sourced; 3.5 d is a convention = half a week) | multi-service paths, coverage |
| bunker_price | Bunker price | 600 USD/t uniform | `SOURCED_SECONDARY` (not a market price) | fuel cost (largest item) |
| fuel_grade | Fuel grade / vessel fuel systems | VLSFO-equivalent for every vessel | `UNVERIFIED` | fuel cost |
| weekly_frequency | Frequency granularity | integer departures/week; vessels = `ceil(T f / 7)` | `UNVERIFIED` (paper uses fractional vessels) | thin long routes, coverage |
| cost_units | Port cost units | per-FFE columns `/2`; port call = fixed + per-FFE x vessel capacity | `PROVISIONAL` | handling, transshipment, port-call cost |
| canal_fees | Suez / Panama fees | traversals of the closed rotation x class fee, once per weekly departure; blank = cannot pass | `SOURCED_PRIMARY_CODE` (owner countersign D-08 outstanding) | canal routes, class eligibility |
| rejection_penalty | Rejected-demand penalty | none in operating profit | `PROVISIONAL` | comparability with the paper |
| unused_vessels | Unused vessels | no credit, no cost | `PROVISIONAL` | comparability with the paper |

### 13.2 Additional assumptions found in the code (not in the register) - `CODE-ONLY`

| # | Assumption | Where | Effect |
|---|---|---|---|
| A1 | Every vessel sails at its class **design speed** on every leg; fuel is the single design-point rate (no speed-consumption law, no slow steaming) | `economics.py:19-23, 266` | fuel cost, cycle time |
| A2 | Port fuel = idle t/day x **24 h x number of calls**, whatever the cargo and whatever the real stay | `economics.py:269-271` | fuel cost |
| A3 | One bunker price for sea and port fuel of a service | `economics.py:295` | fuel cost |
| A4 | Rotation time is rounded **up** to whole days before vessels are computed | `economics.py:292` | vessel cost (conservative) |
| A5 | A weekly schedule with `f` departures is feasible whenever `N >= ceil(T f/7)`; no schedule slack, no departure-time structure | `economics.py:151-153` | vessel cost, feasibility |
| A6 | Cargo flows are continuous (fractional TEU); partial OD service allowed | `network_milp.py:378` | revenue, coverage |
| A7 | Revenue is independent of path, number of transfers, transit time and service quality | `ledger.py:336` | revenue |
| A8 | Transit time of a ride excludes the stay at origin and destination, includes one stay at each intermediate port | `economics.py:189-204` | time-feasible paths |
| A9 | Demand is constant over the 52 weeks; annual = weekly x 52 | orchestrator/regional `annual_profit` | annual figures |
| A10 | Paths: at most 10 per OD enter the MILP (`fastest` order = direct first, then fastest transfers), at most 2 transfers; the full valid set is used only by the post-solve LP | `paths.py:57, 61` | solution quality (stored run: 929 of 1,764 ODs at the cap; 66,575 valid paths not in the MILP) |
| A11 | Services are enumerated as **candidates** (generator sections A-G, <= 10 ports for trunks); the optimum is over the candidate pool, not over all possible rotations | `service_generator_agent.py` | solution quality |
| A12 | Regional stage uses `alpha_unserved = 300 USD/TEU` as an optimisation-only penalty; `TRANSSHIP_COST_PER_TEU = 80` and `PORT_COST_PER_TEU = 0` are still passed to the GA/HubMILP constructors but are **ignored** by the current formulation (data costs are used) | `regional_agent.py:32-36`, `hub_milp.py` docstring | none on reported profit |
| A13 | A bunkering port assumption exists only in the OFF `regional_snapshot` mode (cheapest observed port on the rotation; an optimistic bound) | `bunker_prices.py:17-27` | not active |
| A14 | Weather speed factor clamped to [0.5, 1.5]; active only if maritime intelligence is enabled (OFF) | `economics.py:345-351` | not active |
| A15 | Dataset distance record: one record per directed pair (the first listed, which is also the shortest in WorldSmall) | `docs/MULTI_DATASET.md` | route length |

---

## 14. Worked example and verification (so a reader can check the formulas)

### 14.1 One service, by hand (from the stored run)

Service `americas_svc_241`: ports ITGIT - TRAMB, class **Feeder_450**, `f = 1`.

```
distance      D(ITGIT,TRAMB)+D(TRAMB,ITGIT)         = 2,024 nm
sea_days      2,024 / (12 kn x 24)                  = 7.0278 d
port_days     2 calls x 1 d                         = 2.0 d
T             ceil(9.0278)                          = 10 d
vessels       ceil(10 x 1 / 7)                      = 2
vessel cost   2 x 5,000 USD/d x 7                   = 70,000
fuel_t        7.0278 x 18.8 + 2 x 2.4               = 136.92 t
fuel cost     1 x 136.92 x 600                      = 82,153.33
port fixed    9,242 + 9,517                         = 18,759
capacity chg  (6/2 + 19/2) x 900 TEU                = 11,250      (cap = 450 FFE x 2)
canal         no flagged leg                        = 0
-----------------------------------------------------------------
service-level cost per week                         = 70,000 + 82,153.33 + 30,009 = 182,162.33
```
(`port_call_fixed_cost` of this service = 18,759 + 11,250 = **30,009**.)

### 14.2 Whole network, stored run (`pipeline_output.json`, `network_ledger.weekly_usd`)

> **Caveat.** This is **one unseeded run** (`LINER_SEED = null`) of the C3 configuration, 3 iterations, selected iteration 2, wall time 818.8 s, status `feasible`. It illustrates the formulas; it is not a benchmark result. The 20-seed C3 reference (`reports/continuation_20261015/ws1_provenance/C3_baseline_freeze.json`) gives mean profit **42.47 M** USD/week (sd 3.94 M, min 31.79 M, max 47.07 M), mean coverage 44.0 %, 28 services on average; all 20 runs `feasible`, 0 ledger violations.

| Item | Stored run, USD/week | % of revenue | % of cost | 20-seed C3 mean cost |
|---|---:|---:|---:|---:|
| Revenue `R` | 132,816,260 | 100.0 | - | (mean revenue 132.40 M) |
| Vessel hire | 21,154,000 | 15.9 | 24.1 | 21,369,250 |
| Fuel | 29,185,549 | 22.0 | 33.2 | 31,190,996 |
| Port-call fixed (incl. capacity charge and canal) | 10,276,954 | 7.7 | 11.7 | 10,194,055 |
| Handling | 25,949,208 | 19.5 | 29.5 | 26,028,562 |
| Transshipment | 1,271,700 | 1.0 | 1.4 | 1,147,733 |
| `port_variable_cost` | 0 | - | - | 0 |
| **Total operating cost** | **87,837,411** | 66.1 | 100 | 89,930,596 |
| **Operating profit** | **44,978,849** | **33.9** | - | mean 42,471,976 |

Network facts of that run: 30 services operated (16 two-port); 152 vessels deployed (of 263 owned); served 123,416 of 276,494 TEU = **44.6 %** coverage (94,114 TEU direct, 27,444 one-transfer, 1,858 two-transfer); capped-MILP gap 29.7 % of its own bound.

### 14.3 Independent recomputation performed for this document

Using only the raw files in `data/raw/WorldSmall/` and the service list and routed flows stored in the output (not the optimiser):

| Quantity | Hand recomputation | Ledger | Difference |
|---|---:|---:|---:|
| Vessel cost (30 services) | 21,154,000.00 | 21,154,000.00 | 0.0000 |
| Fuel cost | 29,185,548.92 | 29,185,548.92 | 0.0000 |
| Port-call fixed (incl. capacity charge, canal) | 10,276,954.00 | 10,276,954.00 | 0.0000 |
| Revenue (123,416 TEU over the stored flows) | 132,816,260.00 | 132,816,260.00 | 0.0 |
| Handling | 25,949,208.00 | 25,949,208.00 | 0.0 |
| Transshipment | 1,271,700.00 | 1,271,700.00 | 0.0 |
| `revenue - total_operating_cost - operating_profit` | - | - | 0.0 |

This confirms that the formulas in Sections 4-7 are the ones the code applies, to the cent. It does **not** validate the *inputs* (price, units, port-cost interpretation) - those are the assumptions of Section 13.

Minimal reproduction (run from the project root; reads only the raw files and the stored output):

```python
import csv, json, math
RAW = "data/raw/WorldSmall/"
rd = lambda n: list(csv.DictReader(open(RAW + n, encoding="utf-8-sig", newline=""), delimiter="\t"))
ports = {r["UNLocode"]: r for r in rd("ports.csv")}
fleet = {r["Vessel class"]: r for r in rd("fleet_data.csv")}
dist, flag = {}, {}
for r in rd("dist_dense.csv"):
    k = (r["fromUNLOCODe"], r["ToUNLOCODE"]); dist[k] = float(r["Distance"])
    flag[k] = (int(float(r["IsPanama"] or 0)), int(float(r["IsSuez"] or 0)))
nl = json.load(open("pipeline_output.json", encoding="utf-8"))["network_ledger"]
price, tot = 600.0, dict(vessel=0.0, fuel=0.0, port=0.0)
for s in nl["plan"]["services"]:
    c, P, f = fleet[s["vessel_class"]], s["ports"], s["frequency_per_week"]
    legs = [(P[i], P[(i + 1) % len(P)]) for i in range(len(P))]
    sea = sum(dist[l] for l in legs) / (float(c["designSpeed"]) * 24); pd_ = len(P) * 1.0
    T = math.ceil(round(sea + pd_, 9)); N = math.ceil(round(T * f / 7, 9))
    cap = 2 * float(c["Capacity FFE"])
    canal = sum(flag[l][0] * float(c["panamaFee"] or 0) + flag[l][1] * float(c["suezFee"] or 0) for l in legs)
    tot["vessel"] += N * float(c["TC rate daily (fixed Cost)"]) * 7
    tot["fuel"]   += f * (sea * float(c["Bunker ton per day at designSpeed"]) + pd_ * float(c["Idle Consumption ton/day"])) * price
    tot["port"]   += f * (sum(float(ports[p]["PortCallCostFixed"]) for p in P)
                          + cap * sum(float(ports[p]["PortCallCostPerFFE"]) / 2 for p in P) + canal)
print(tot, nl["weekly_usd"])
```
(The snippet does not re-check class-pass rules for blank canal fees; the optimiser never emits such a service, and the full check is `ledger.py:204-215`.)

---

## 15. Limitations to state when citing these results

1. **Not a proven optimum.** CBC is time-limited; the stored capped MILP has a 29.7 % gap to its own LP bound, and the final plan (after local search and flow re-optimisation) lies outside that model. Report profit as "ledger-verified feasible plan", not "optimal".
2. **Inputs are assumptions, not observations**: 600 USD/t uniform bunker price (not a market price); 24 h port stay; 3.5-day expected transfer wait; FFE reading of capacity (profit levels move by a factor 1.6-2.5 under the TEU reading); per-FFE port-cost reading; `TransitTime` unit (days) and scope.
3. **Profit-only objective.** Coverage is an outcome (44.6 % in the stored run; 30.1-47.9 % across 20 seeds), not a target; in the 20 frozen C3 seeds the maximum coverage was 47.9 %, so the 70 % rerun target was never met (the iteration cap of 3 ends the loop instead).
4. **Run-to-run variance.** C3 profit spans 31.8-47.1 M USD/week across 20 seeds (sd 3.9 M). Quote distributions, not a single run.
5. **Integer, whole-day vessel counting** is more conservative than the paper's fractional vessels; comparisons to the paper use the separate paper ledger (Section 12).
6. **No penalty/credit terms**: unserved cargo is free, unused vessels are free; the operating profit is therefore an upper-style measure relative to a rejection-penalised objective.
7. **Surrogate quirks** (Section 10) affect search guidance only.
8. **Open owner decisions recorded elsewhere**: canal-fee countersign (D-08), advisory 15 % margin target, Tier-0 sign-off.

---

## 16. Source index

| Topic | File (working tree) | Lines |
|---|---|---|
| Unit conversion, loader | `src/data/network_loader.py` | 86-104, 484-503, 570-577, 734-763 |
| Defaults of assumptions | `src/network/economics.py` | 51-110 |
| Service model: time, vessels, fuel, port cost | `src/network/economics.py` | 215-307 |
| Per-service weekly cost | `src/network/economics.py` | 167-180 |
| Canal fee, draft rules | `src/network/physical_rules.py` | 50-86 |
| Bunker price modes | `src/network/bunker_prices.py` | 69-77, 299-396 |
| Path time and per-TEU charges | `src/network/paths.py` | 1-45, 424-505 |
| MILP objective, constraints | `src/network/network_milp.py` | 15-22, 355-448 |
| Slack-vessel trim | `src/network/network_milp.py` | 117-137 |
| Orchestrating plan + ledger | `src/network/plan.py` | 145-422 |
| Independent ledger | `src/network/ledger.py` | 10-22, 107-399 |
| Flow re-optimisation, repair | `src/network/flow_reopt.py` | 51-331 |
| Local search | `src/network/local_search.py` | 1-48 (docstring) |
| Global stage + regional partition | `src/network/reconcile.py` | 231-612 |
| Canonical economics for decisions | `src/network/metrics.py` | 11-100, 118-220 |
| Assumption register | `src/network/assumption_register.py` | 20-62 |
| GA surrogates | `src/optimization/service_ga.py`, `frequency_ga.py`, `normalization.py` | 245-292; 146-151; PROFIT_FIRST_WEIGHTS |
| Regional HubMILP | `src/optimization/hub_milp.py` | 56-265 |
| C3 flags | `tests/test_orchestrator.py` | 3141-3156 |
| Paper-comparison ledger | `src/benchmark/paper_ledger.py`, `paper_evaluator.py` | 1-27; 160-220 |
