| configuration | seeds | pool (unique) | 2-port / 3 / 4 / 5 / 6+ | standalone-profitable | profit USD/wk mean (sd) | min .. max | margin % | coverage % | services | vessels | LP bound M | MILP s | ledger violations |
|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| old+fullint | 2 | 1141 | 912 / 108 / 0 / 0 / 120 | 10.0 | 3.60 M (2.19) | 1.40 .. 5.79 M | 8.8 | 11.9 | 15.0 | 67 | 0.0 | 276 | 0 |
| loops60+fullint | 2 | 1272 | 912 / 162 / 34 / 44 / 120 | 75.0 | 7.87 M (0.33) | 7.54 .. 8.20 M | 13.8 | 16.9 | 16.0 | 103 | 0.0 | 220 | 0 |

Per-seed weekly profit (USD M) and coverage (%):

| seed | old+fullint | loops60+fullint |
|---|---:|---:|
| 0 | 5.79 / 13.7% | 7.54 / 18.2% |
| 3 | 1.40 / 10.1% | 8.20 / 15.7% |

Paired difference in weekly profit vs `old+fullint` (same seed; USD M; positive = better):

| configuration | seed 0 | seed 3 | mean | seeds better |
|---|---:|---:|---:|---:|
| loops60+fullint | +1.76 | +6.80 | +4.28 | 2/2 |

Vessel classes in the operated plan (mean vessels deployed) and classes present in the pool (mean candidates):

| configuration | Feeder_450 (deployed / pool) | Feeder_800 (deployed / pool) | Panamax_1200 (deployed / pool) | Panamax_2400 (deployed / pool) | Post_panamax (deployed / pool) | Super_panamax (deployed / pool) |
|---|---:|---:|---:|---:|---:|---:|
| old+fullint | 0.0 / 0 | 21.0 / 497 | 0.0 / 0 | 12.5 / 18 | 26.5 / 497 | 7.0 / 129 |
| loops60+fullint | 0.0 / 25 | 18.0 / 528 | 16.0 / 24 | 41.0 / 44 | 18.0 / 514 | 10.0 / 137 |

Operated services by generator section (mean count):

| configuration | demand_loop | direct | heuristic | trunk |
|---|---:|---:|---:|---:|
| old+fullint | 0.0 | 8.0 | 4.5 | 2.5 |
| loops60+fullint | 10.0 | 4.5 | 0.5 | 1.0 |
