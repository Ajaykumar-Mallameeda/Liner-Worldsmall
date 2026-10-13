# Task 4 — Canonical fleet-backed fuel calculation

> **STATUS UPDATE 2026-10-11:** superseded. The Task 3 blockers were resolved, Task 4 implemented and Tasks 5-7 / Phase D completed and verified - see `../network_economics_redesign/FINAL_REPORT.md`. The text below is the historical record of the overnight run and is left unchanged.

**Status: NOT STARTED.** The plan authorizes Task 4 only after Task 3 passes its gate; Task 3 is blocked (see
`task3_service_feasibility.md`). Nothing below was implemented or executed — it is read-only provenance gathered while
tracing Task 3, recorded so the work can start without re-discovery.

## 1. Fuel inputs the canonical files actually supply
| Field (`fleet_data.csv`) | Unit | Use |
|---|---|---|
| `Bunker ton per day at designSpeed` | metric t/day **at design speed** | sea consumption (one operating point only) |
| `Idle Consumption ton/day` | metric t/day | in-port / idle consumption — currently unmodelled |
| `minSpeed`, `maxSpeed`, `designSpeed` | knots | valid speed range; consumption at other speeds is **not** given |

Not in the canonical files: a bunker **price**, a consumption-vs-speed law, a port-time column. So a full physical fuel
model cannot be claimed from the source alone; price and (if used) a speed law must be explicit, documented assumptions.
The LINERLIB benchmark documentation states a bunker cost of 600 USD per metric ton (via the Google OR-tools LINERLIB
page); the repository has `BUNKER_PRICE_PER_TON = 600.0` hard-coded ("Bunker Index 2024 Average").

## 2. The conflicting hard-coded table (`src/utils/fuel_cost.py::VESSEL_FUEL_CONSUMPTION`)
| Class | table cap / t/day / kn | fleet cap / t/day @ design kn (min–max kn) |
|---|---|---|
| Feeder_450 | 450 / 15 / 16 | 450 / 18.8 / 12 (10–14) — table speed above max |
| Feeder_800 | 800 / 25 / 17 | 800 / 23.7 / 14 (10–17) |
| Panamax_1200 | 1,200 / 35 / 18 | 1,200 / 52.5 / 18 (12–19) |
| Panamax_2400 | 2,400 / 55 / 19 | 2,400 / 57.4 / 16 (12–22) |
| Post_panamax | **5,000** / 80 / 22 | **4,200** / 82.2 / 16.5 (12–23) |
| Super_panamax | **8,000** / 100 / 23 | **7,500** / 126.9 / 17 (12–22) — table speed above max |

Consequence now: Task 3 times a rotation at the fleet `designSpeed`, but fuel is still computed at the table speed and
consumption, so time and fuel are on different bases until this task is done (strict xfail `D-FUEL-TABLE` is its acceptance test).

## 3. Callers that must share one calculation
`calculate_weekly_fuel_cost(svc.ports, …, svc.cycle_time)` is called from `service_ga.py:259,289`, `frequency_ga.py:162`
and `hub_milp.py:315,499,559`. They pass the service's route as listed (open `[a, b]` → the return leg is **not** costed;
the function deliberately does not close the loop) and then multiply by `7 / cycle_time`. Task 4 must route all of them
through one function that closes the rotation exactly once and uses the fleet class's own parameters.

## 4. Other facts recorded
* `calculate_voyage_fuel_cost` applies a 0.9 "sailing fraction" and an optional weather speed factor (IP-2); both are
  undocumented in the source data.
* Unknown classes / missing distances already raise (`UnknownVesselClassError`, `MissingDistanceError`, Task 2 of the earlier
  audit); several error handlers downstream still swallow them (`hub_milp.py:_service_fuel` returns 0.0 on any exception).
* Fuel cost reported at baseline: $510–529 M/week against a corrected gross revenue pool of $264.9 M/week.
