# Primary-source search and unit confirmation (decision phase)

## What was found
The previous phases treated the LINERLIB *technical report* (Løfstedt/Brouer et al.) as the primary source and recorded it as unavailable.
A **local checkout of the LINERLIB repository** exists (`C:\Users\WINDOWS\Downloads\LINERLIB-master (1)\LINERLIB-master`, not part of the
project tree) and was not used before. It contains the benchmark authors' own artefacts:

| artefact | what it is |
|---|---|
| `include/BM_Graph.hpp`, `bm_data.hpp`, `bm_rotation.h`, `src/bm_reader.cpp`, `bm_rotation.cpp` | the authors' reference parser / rotation cost code, with type and field comments |
| `results/BrouerDesaulniersPisinger2014/WorldSmall_Best_Base.log` (+ high/low/other instances) | the authors' best WorldSmall solutions with per-service and total cost lines |
| `data/transittime_revision/README.txt` | provenance of the revised transit file |
| `README.md` / `readme.txt` | data description, rules for the high/low cases, citation of the technical report |
This is **primary-source material authored by the benchmark creators**, but it is *code and solver output*, not the technical report
itself (cited as DTU Management Engineering report 19.2010; its text is still not available locally). Statuses below say which.

## Unit confirmations (each verified separately)
| quantity | evidence | result | status |
|---|---|---|---|
| vessel capacity (`Capacity FFE`) | `typedef unsigned long long FFE; //Number of Forty Foot Equivalent containers`; `vesselclass(..., FFE capacity, ...)`; `FFE m_capacity; // The maximal load for the vesseltype` (BM_Graph.hpp:21, bm_data.hpp:75-88); the log's `capacity 450 ... # vessels` rows use the same classes | **capacity is an FFE count** (agrees with the RL paper and with the Issue 1 conversion `x2` to TEU) | **PRIMARY (reference code)** - upgrade from `secondary_source` |
| demand quantity | `FFE` typedef used for demand edges (bm_data.cpp prints "FFE:" for demands); README calls demand `FFe` | FFE per week | PRIMARY (reference code) |
| port-call cost | `callCostFixed + callCostPerFFE * vessel capacity` per call (bm_reader.cpp:540; comment "additional per ffe capacity of vessel"); reproduced exactly: **34/34 services, 5,565,837 USD/wk = the log's "Port Call Cost 5.56584e+06"** | per call, per rotation, capacity-based - **the model had charged it per TEU of cargo (fixed in this phase)** | PRIMARY (reference code + solution log) |
| handling (`moveCost`/`CostPerFULL`) and transshipment (`transhipmentCost`/`CostPerFULLTrnsf`) | field comments "cost for a tranship move, i.e. a transhipment requires two moves"; log total "Handling cost 6.19856e+07" for 94.22 % transported; **per-flow detail is not in the log**, so the unit (USD per FFE moved) is *by field naming and the paper's Eq. 31*, not independently reproduced | USD per FFE; our `/2` per TEU conversion is dimensionally consistent | PROVISIONAL (consistent with paper; not independently reproduced) |
| canal fee (`panamaFee`, `suezFee`) | `calculate_canal_cost = num_suez * suez_cost + num_panama * panama_cost` "for one round trip"; **34/34 services of the authors' solution reproduce the traversal counts, costs within the log's 6-digit printing, total 13,935,070 vs 13,935,090 (log: 1.39351e+07)** | USD per traversal per vessel passage, charged once per weekly rotation per flagged leg of the closed rotation | **PRIMARY (reference code + solution log)** |
| blank Panama fee (Post/Super-panamax) | no Post/Super-panamax service in the authors' solution traverses Panama; the Panama edges carry a draft limit of 12.0 m < 13.0 / 12.5 m | the class cannot pass (never zero cost) | PRIMARY (solution log + data), reader code treats blank as 0 but the draft rule excludes the class |
| draft | `rotation::is_draft_feasible` "There must be draft feasibility between vessel_class and port_calls"; ports.csv draft values equal the class drafts; authors' solution: **0 of 34 services violate** | class draft <= port draft and <= leg draft limit; **recorded default plans violated it on 23 % of services (147 of 629)** | PRIMARY; fixed in this phase |
| TC rate | log `Total TC cost` = vessels x TC x 7 (low case TC x1.4) ; sum 35.658 M = "Vessel Class cost" | USD per vessel-day, weekly cost = n x TC x 7 | PRIMARY (solution log) |
| fuel | log `Total bunker cost at 600 USD for one round trip`; sum with idle = 43.86 M = fuel 43.09 + idle 0.765 | tonnes x 600 USD per round trip; **the benchmark scales consumption by (speed/design)^3 (`fuel_burn`)**, our model sails at design speed only | PRIMARY; modelling difference (speed optimisation not modelled) |
| objective horizon | log: "Objective value 5.60083e+07 ... Half year Objective 1.40021e+09" = weekly x 25 | weekly objective; 25-week "half year" label | PRIMARY |

## What the authors' solution shows about our model (for owner information)
* WorldSmall base solution: **94.22 % of demand transported, 98.5 % fleet deployed, weekly objective 56.0 M USD including a 1,000 USD/FFE
  rejection penalty (63.4 M without)**. The benchmark's base model has **no end-to-end transit-time constraint** (the RL paper states the same).
  Our operational model enforces TransitTime limits with a 5.5-day dwell per transfer and reaches 31-34 %. The measured gap is therefore a
  difference of *problem definition* (hard transit limits), not evidence that 70 % coverage is unreachable in the benchmark's own model.
  Whether 70 % is reachable *with* the transit limits is not shown by any run here (limits + fleet inventory + economics bind).
* The per-FFE port charge and canal fee rules above are now implemented; draft feasibility is now a hard rule.

## Still not confirmed from a primary source
* The technical report text (units of `TransitTime` and whether it includes port time; handling cost per move vs per transshipment).
* The reason for the factor 180 in the reference `m_vrc` (vessel running cost = TC x 180 x vessels) versus the weekly cost in the logs.
* Exact data-custodian confirmation of per-FFE handling units. **Request to the data custodian:** the technical report (DTU Management
  Engineering report 19.2010, Løfstedt et al.) or a written column dictionary for `ports.csv` (moveCost, transhipmentCost) and `Demand_*.csv` (TransitTime).
