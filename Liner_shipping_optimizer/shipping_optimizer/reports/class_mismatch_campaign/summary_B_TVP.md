| metric (mean over solved runs) | B | T | V | P |
|---|---:|---:|---:|---:|
| runs / solved / invalid-plan / other | 20 / 20 / 0 / 0 | 20 / 20 / 0 / 0 | 20 / 19 / 0 / 1 | 20 / 20 / 0 / 0 |
| revenue M USD/wk | 106.16 | 107.88 | 103.53 | 106.66 |
| vessel cost M | 17.09 | 17.10 | 17.27 | 17.22 |
| fuel cost M | 29.56 | 28.28 | 29.88 | 29.90 |
| port-call fixed incl. canal+capacity charge M | 8.73 | 8.78 | 8.51 | 9.14 |
| handling M | 19.29 | 19.45 | 18.31 | 19.21 |
| transshipment M | 1.38 | 1.13 | 1.33 | 1.43 |
| port variable M | 0.00 | 0.00 | 0.00 | 0.00 |
| total cost M | 76.05 | 74.75 | 75.31 | 76.90 |
| **profit M USD/wk** | 30.12 | 33.14 | 28.22 | 29.76 |
| margin % | 28.4 | 30.7 | 27.2 | 27.9 |
| coverage % | 33.9 | 34.3 | 33.2 | 33.9 |
| served TEU/wk | 93,611 | 94,720 | 91,720 | 93,677 |
| services | 29.4 | 25.1 | 31.8 | 28.7 |
| departures/wk | 31.5 | 25.6 | 32.8 | 30.9 |
| vessels assigned (of owned) | 179.8 | 160.1 | 180.7 | 179.7 |
| owned | 263 | 263 | 263 | 263 |
| fleet vessel utilisation (assigned/owned) | 0.683 | 0.609 | 0.687 | 0.683 |
| service leg load factor (mean of services) | 0.631 | 0.588 | 0.594 | 0.642 |
| leg load factor (mean of legs) | 0.645 | 0.605 | 0.610 | 0.651 |
| network leg load factor (carried/offered TEU-legs) | 0.618 | 0.577 | 0.589 | 0.623 |
| max p90 transit days | 39.2 | 42.0 | 37.9 | 41.5 |
| stage wall s | 116.7 | 120.6 | 120.6 | 119.0 |
| capped-model gap to bound % (incumbent vs LP bound) | -1.6 | -5.5 | 9.3 | 13.0 |
| ledger violations (sum) | 0 | 0 | 0 | 0 |
| transit violations (sum) | 0 | 0 | 0 | 0 |

Vessels assigned / owned by class (mean):

| class | B | T | V | P |
|---|---:|---:|---:|---:|
| Feeder_450 | 23.8 / 24 | 22.4 / 24 | 22.1 / 24 | 22.0 / 24 |
| Feeder_800 | 27.9 / 29 | 26.4 / 29 | 25.2 / 29 | 27.5 / 29 |
| Panamax_1200 | 59.5 / 68 | 55.9 / 68 | 64.7 / 68 | 60.5 / 68 |
| Panamax_2400 | 68.4 / 74 | 45.5 / 74 | 68.7 / 74 | 69.7 / 74 |
| Post_panamax | 0.0 / 58 | 0.0 / 58 | 0.0 / 58 | 0.0 / 58 |
| Super_panamax | 0.1 / 10 | 10.0 / 10 | 0.0 / 10 | 0.1 / 10 |

Unserved demand by reason (mean % of total demand):

| reason | B | T | V | P |
|---|---:|---:|---:|---:|
| capacity_exhausted | 3.80 | 3.19 | 3.13 | 3.85 |
| fleet_inventory_exhausted | 41.76 | 24.33 | 35.57 | 36.53 |
| limit_below_fastest_sailing_time | 3.37 | 3.37 | 3.37 | 3.37 |
| no_time_feasible_service_in_pool | 7.89 | 7.24 | 6.64 | 7.89 |
| not_economic_to_open_service | 8.87 | 27.14 | 17.68 | 14.79 |
| not_profitable_to_carry | 0.46 | 0.47 | 0.43 | 0.43 |

Paired differences vs `B` (same seed; positive = arm higher):

| arm | n pairs | profit mean M | median | sd | min (seed) | max (seed) | seeds higher | coverage pp mean | coverage higher |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|
| T | 20 | +3.02 | +2.92 | 1.46 | +0.23 (10) | +5.88 (13) | 20/20 | +0.40 | 12/20 |
| V | 19 | -1.80 | -1.20 | 3.48 | -8.18 (19) | +4.11 (16) | 7/19 | -0.65 | 10/19 |
| P | 20 | -0.36 | -0.07 | 1.76 | -4.71 (19) | +4.40 (1) | 10/20 | +0.02 | 11/20 |
