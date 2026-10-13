# Task 4 — fuel from the canonical fleet

Supersedes the "NOT STARTED" provenance note in `reports/overnight_tasks_2_to_4/task4_fuel_provenance_and_calculation.md`.

## Understanding first
`fleet_data.csv` supplies, per class: capacity, `Bunker ton per day at designSpeed`, `Idle Consumption ton/day`, and
`minSpeed / designSpeed / maxSpeed`. It supplies **one** operating point (the design speed). It does not supply a bunker price,
a consumption-vs-speed law, or port time. The previous code instead used a hard-coded table
("Clarksons Research 2024") that contradicted the file:

| class | legacy table cap / t/day / kn | fleet file cap / t/day / design kn | legacy USD per 1000 nm | canonical USD per 1000 nm | ratio |
|---|---|---|---|---|---|
| Feeder_450 | 450 / 15 / 16 | 450 / 18.8 / **12.0** | 26,042 | 39,167 | 1.50 |
| Feeder_800 | 800 / 25 / 17 | 800 / 23.7 / 14.0 | 40,850 | 42,321 | 1.04 |
| Panamax_1200 | 1,200 / 35 / 18 | 1,200 / 52.5 / 18.0 | 54,012 | 72,917 | 1.35 |
| Panamax_2400 | 2,400 / 55 / 19 | 2,400 / 57.4 / 16.0 | 80,409 | 89,688 | 1.12 |
| Post_panamax | **5,000** / 80 / 22 | **4,200** / 82.2 / 16.5 | 101,010 | 124,545 | 1.23 |
| Super_panamax | **8,000** / 100 / 23 | **7,500** / 126.9 / 17.0 | 120,773 | 186,618 | 1.55 |

The legacy table understated fuel by 4–55 % and used speeds above the class maximum for two classes; time (design speed) and
fuel (table speed) were on different bases.

## Model (adapted to what the data supports)
* sea days = nm ÷ (design speed × 24); sea fuel = sea days × `Bunker t/day @ design`;
  port fuel = port days × `Idle t/day`; USD = tonnes × bunker price.
* price **600 USD/t** — not in the canonical files; the LINERLIB documentation value, kept as an explicit overridable
  assumption (`BUNKER_PRICE_SOURCE`), reported in `network_ledger.assumptions`.
* a rotation is closed: `[A,B]` and `[A,B,A]` cost the same, return leg exactly once; weekly fuel = rotation fuel × departures.
* no consumption-vs-speed law is invented; the speed factor (maritime IP-2) scales sailing time only.
* missing distance → `MissingDistanceError`; unknown class, or no fleet registered and the canonical files not loadable →
  `UnknownVesselClassError`; non-finite / negative input → `FuelCostError` — never zero, never a default class
  (`map_capacity_to_vessel_class` now returns the registered class nearest in capacity and raises if none is registered).

## Implementation
`src/utils/fuel_cost.py` — table derived from the loaded fleet (`register_fleet_specification`), lazy bootstrap from the
canonical fleet files; retired table kept only as a comment; legacy module preserved as `fuel_cost_legacy.py`. Every caller
(GA surrogate, FrequencyGA, HubMILP/network model, ledger) takes fuel from `ServiceModel.fuel_cost_per_rotation`, so there is
one calculation.

## Tests
* `tests/test_shared_contracts.py::TestFuelCostContract` — hand-computed value `1000/(16·24)·15·600 = 23,437.50`, linearity,
  closed-rotation identity, weekly scaling, missing-input errors, table == fleet for all six classes, canonical Post_panamax value.
* `tests/test_network_economics.py` — `FUEL_AB = (2200/288·20 + 2·2)·600 = 94,066.67`.
* `tests/maritime/test_phase7_integration.py` (IP-2 weather factor) — 35 passed / 2 skipped.
