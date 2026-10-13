| configuration | seeds | pool (unique) | 2-port / 3 / 4 / 5 / 6+ | standalone-profitable | profit USD/wk mean (sd) | min .. max | margin % | coverage % | services | vessels | LP bound M | MILP s | ledger violations |
|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| loops60 | 5 | 1272 | 912 / 162 / 33 / 44 / 120 | 75.8 | 5.95 M (0.56) | 4.99 .. 6.59 M | 13.5 | 12.9 | 11.4 | 80 | 50.7 | 32 | 0 |
| loops60+screen1 | 5 | 1229 | 871 / 162 / 33 / 43 / 120 | 91.6 | 8.42 M (0.32) | 8.02 .. 8.99 M | 13.0 | 20.3 | 18.4 | 122 | 44.2 | 114 | 0 |
| loops60+screen2 | 5 | 1280 | 877 / 177 / 47 / 60 / 120 | 143.2 | 7.33 M (0.61) | 6.32 .. 8.11 M | 12.8 | 17.3 | 15.2 | 105 | 44.3 | 103 | 0 |
| loops60+screen3 | 5 | 1304 | 879 / 183 / 53 / 69 / 120 | 166.6 | 6.58 M (0.37) | 6.05 .. 7.16 M | 11.9 | 16.7 | 15.2 | 101 | 44.3 | 115 | 0 |
| old+screen1 | 5 | 1098 | 871 / 108 / 0 / 0 / 120 | 17.4 | 2.89 M (1.57) | -0.13 .. 4.27 M | 7.7 | 12.4 | 18.2 | 89 | 40.8 | 70 | 0 |
| old+screen2 | 5 | 1108 | 877 / 111 / 0 / 0 / 120 | 26.8 | 3.58 M (0.55) | 3.18 .. 4.66 M | 9.0 | 12.3 | 17.2 | 86 | 40.9 | 77 | 0 |
| loops60+screenall | 5 | 1805 | 934 / 417 / 189 / 244 / 22 | 194.2 | 3.31 M (0.71) | 2.46 .. 4.42 M | 11.5 | 9.4 | 10.0 | 67 | 39.9 | 29 | 0 |

Per-seed weekly profit (USD M) and coverage (%):

| seed | loops60 | loops60+screen1 | loops60+screen2 | loops60+screen3 | old+screen1 | old+screen2 | loops60+screenall |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 6.59 / 14.9% | 8.99 / 22.5% | 6.32 / 17.6% | 6.65 / 16.5% | 3.00 / 10.8% | 3.25 / 11.3% | 2.90 / 10.7% |
| 1 | 6.00 / 11.3% | 8.40 / 24.2% | 8.11 / 17.8% | 6.33 / 17.5% | -0.13 / 16.9% | 3.18 / 10.5% | 2.46 / 7.9% |
| 2 | 5.76 / 12.0% | 8.28 / 19.9% | 7.71 / 15.6% | 6.05 / 15.6% | 3.34 / 9.6% | 3.56 / 10.1% | 2.93 / 8.9% |
| 3 | 6.40 / 11.5% | 8.02 / 17.9% | 7.45 / 18.4% | 7.16 / 16.6% | 4.27 / 13.8% | 3.27 / 17.4% | 4.42 / 10.8% |
| 4 | 4.99 / 14.8% | 8.40 / 17.2% | 7.05 / 17.3% | 6.70 / 17.3% | 3.96 / 11.0% | 4.66 / 12.3% | 3.86 / 8.7% |

Paired difference in weekly profit vs `loops60` (same seed; USD M; positive = better):

| configuration | seed 0 | seed 1 | seed 2 | seed 3 | seed 4 | mean | seeds better |
|---|---:|---:|---:|---:|---:|---:|---:|
| loops60+screen1 | +2.40 | +2.40 | +2.52 | +1.62 | +3.41 | +2.47 | 5/5 |
| loops60+screen2 | -0.26 | +2.10 | +1.95 | +1.05 | +2.06 | +1.38 | 4/5 |
| loops60+screen3 | +0.07 | +0.33 | +0.29 | +0.76 | +1.71 | +0.63 | 5/5 |
| old+screen1 | -3.59 | -6.13 | -2.41 | -2.13 | -1.03 | -3.06 | 0/5 |
| old+screen2 | -3.34 | -2.82 | -2.20 | -3.13 | -0.34 | -2.37 | 0/5 |
| loops60+screenall | -3.68 | -3.54 | -2.83 | -1.98 | -1.14 | -2.63 | 0/5 |

Vessel classes in the operated plan (mean vessels deployed) and classes present in the pool (mean candidates):

| configuration | Feeder_450 (deployed / pool) | Feeder_800 (deployed / pool) | Panamax_1200 (deployed / pool) | Panamax_2400 (deployed / pool) | Post_panamax (deployed / pool) | Super_panamax (deployed / pool) |
|---|---:|---:|---:|---:|---:|---:|
| loops60 | 0.0 / 26 | 5.0 / 529 | 19.0 / 23 | 39.4 / 42 | 7.6 / 515 | 9.2 / 137 |
| loops60+screen1 | 0.0 / 25 | 13.6 / 891 | 40.8 / 21 | 41.0 / 43 | 17.8 / 223 | 9.0 / 26 |
| loops60+screen2 | 0.0 / 27 | 8.4 / 901 | 26.4 / 36 | 48.4 / 59 | 14.4 / 230 | 7.8 / 28 |
| loops60+screen3 | 0.0 / 29 | 2.8 / 906 | 41.4 / 39 | 37.0 / 69 | 10.4 / 231 | 9.8 / 30 |
| old+screen1 | 0.0 / 0 | 14.6 / 845 | 15.0 / 5 | 36.2 / 20 | 21.4 / 206 | 1.8 / 22 |
| old+screen2 | 0.8 / 1 | 10.6 / 848 | 22.2 / 7 | 31.6 / 22 | 19.2 / 208 | 2.0 / 22 |
| loops60+screenall | 0.0 / 133 | 0.8 / 139 | 55.0 / 139 | 1.8 / 139 | 9.4 / 145 | 0.0 / 1111 |

Operated services by generator section (mean count):

| configuration | demand_loop | direct | heuristic | hub_loop | trunk |
|---|---:|---:|---:|---:|---:|
| loops60 | 8.0 | 2.8 | 0.4 | 0.0 | 0.2 |
| loops60+screen1 | 11.4 | 5.6 | 0.8 | 0.4 | 0.2 |
| loops60+screen2 | 9.2 | 4.0 | 1.4 | 0.2 | 0.4 |
| loops60+screen3 | 9.4 | 4.2 | 1.2 | 0.0 | 0.4 |
| old+screen1 | 0.0 | 12.6 | 5.4 | 0.0 | 0.2 |
| old+screen2 | 0.0 | 11.2 | 5.6 | 0.0 | 0.4 |
| loops60+screenall | 7.6 | 1.6 | 0.8 | 0.0 | 0.0 |
