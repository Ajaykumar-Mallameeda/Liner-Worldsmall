| configuration | seeds | pool (unique) | 2-port / 3 / 4 / 5 / 6+ | standalone-profitable | profit USD/wk mean (sd) | min .. max | margin % | coverage % | services | vessels | LP bound M | MILP s | ledger violations |
|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| old | 5 | 1140 | 912 / 108 / 0 / 0 / 120 | 10.6 | 3.24 M (1.88) | 0.43 .. 5.62 M | 10.8 | 8.5 | 9.8 | 42 | 48.5 | 23 | 0 |
| loops15 | 5 | 1151 | 897 / 111 / 9 / 14 / 120 | 30.4 | 3.40 M (0.53) | 2.45 .. 3.96 M | 8.4 | 12.5 | 10.4 | 72 | 49.8 | 26 | 0 |
| loops30 | 5 | 1157 | 880 / 119 / 16 / 23 / 120 | 46.0 | 4.06 M (0.30) | 3.67 .. 4.41 M | 9.6 | 12.9 | 11.0 | 78 | 50.3 | 26 | 0 |

Per-seed weekly profit (USD M) and coverage (%):

| seed | old | loops15 | loops30 |
|---|---:|---:|---:|
| 0 | 5.62 / 11.8% | 3.71 / 12.8% | 4.37 / 11.2% |
| 1 | 5.01 / 11.7% | 3.96 / 9.3% | 3.67 / 13.6% |
| 2 | 2.33 / 4.9% | 3.66 / 13.0% | 4.09 / 14.1% |
| 3 | 0.43 / 7.9% | 3.21 / 15.5% | 4.41 / 13.4% |
| 4 | 2.82 / 6.3% | 2.45 / 11.9% | 3.77 / 12.1% |

Paired difference in weekly profit vs `old` (same seed; USD M; positive = better):

| configuration | seed 0 | seed 1 | seed 2 | seed 3 | seed 4 | mean | seeds better |
|---|---:|---:|---:|---:|---:|---:|---:|
| loops15 | -1.91 | -1.06 | +1.33 | +2.78 | -0.37 | +0.15 | 2/5 |
| loops30 | -1.24 | -1.35 | +1.76 | +3.98 | +0.95 | +0.82 | 3/5 |

Vessel classes in the operated plan (mean vessels deployed) and classes present in the pool (mean candidates):

| configuration | Feeder_800 (deployed / pool) | Panamax_1200 (deployed / pool) | Panamax_2400 (deployed / pool) | Post_panamax (deployed / pool) | Super_panamax (deployed / pool) |
|---|---:|---:|---:|---:|---:|
| old | 3.2 / 498 | 0.0 / 0 | 11.0 / 18 | 22.0 / 496 | 6.0 / 128 |
| loops15 | 2.2 / 481 | 12.8 / 10 | 33.6 / 28 | 15.4 / 501 | 8.0 / 131 |
| loops30 | 2.8 / 464 | 19.2 / 22 | 33.8 / 35 | 16.6 / 505 | 6.0 / 131 |

Operated services by generator section (mean count):

| configuration | demand_loop | direct | heuristic | trunk | unknown |
|---|---:|---:|---:|---:|---:|
| old | 0.0 | 2.0 | 2.0 | 1.2 | 4.6 |
| loops15 | 0.2 | 1.8 | 1.0 | 0.0 | 7.4 |
| loops30 | 1.6 | 1.8 | 1.0 | 0.0 | 6.6 |
