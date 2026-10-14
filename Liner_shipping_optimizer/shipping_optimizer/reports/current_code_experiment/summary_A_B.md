| metric (mean over solved runs) | A | B |
|---|---:|---:|
| runs / solved / invalid-plan / other | 20 / 20 / 0 / 0 | 20 / 20 / 0 / 0 |
| revenue M USD/wk | 97.95 | 106.16 |
| vessel cost M | 16.71 | 17.09 |
| fuel cost M | 29.11 | 29.56 |
| port-call fixed incl. canal+capacity charge M | 8.55 | 8.73 |
| handling M | 17.55 | 19.29 |
| transshipment M | 1.33 | 1.38 |
| port variable M | 0.00 | 0.00 |
| total cost M | 73.24 | 76.05 |
| **profit M USD/wk** | 24.71 | 30.12 |
| margin % | 25.0 | 28.4 |
| coverage % | 31.2 | 33.9 |
| served TEU/wk | 86,353 | 93,611 |
| services | 28.1 | 29.4 |
| departures/wk | 30.8 | 31.5 |
| vessels assigned (of owned) | 175.6 | 179.8 |
| owned | 263 | 263 |
| fleet vessel utilisation (assigned/owned) | 0.667 | 0.683 |
| service leg load factor (mean of services) | 0.596 | 0.631 |
| leg load factor (mean of legs) | 0.609 | 0.645 |
| network leg load factor (carried/offered TEU-legs) | 0.582 | 0.618 |
| max p90 transit days | 43.9 | 39.2 |
| stage wall s | 124.1 | 116.7 |
| capped-model gap to bound % (incumbent vs LP bound) | 53.0 | -1.6 |
| ledger violations (sum) | 0 | 0 |
| transit violations (sum) | 0 | 0 |

Vessels assigned / owned by class (mean):

| class | A | B |
|---|---:|---:|
| Feeder_450 | 22.6 / 24 | 23.8 / 24 |
| Feeder_800 | 26.4 / 29 | 27.9 / 29 |
| Panamax_1200 | 60.1 / 68 | 59.5 / 68 |
| Panamax_2400 | 66.2 / 74 | 68.4 / 74 |
| Post_panamax | 0.0 / 58 | 0.0 / 58 |
| Super_panamax | 0.2 / 10 | 0.1 / 10 |

Unserved demand by reason (mean % of total demand):

| reason | A | B |
|---|---:|---:|
| capacity_exhausted | 3.79 | 3.80 |
| fleet_inventory_exhausted | 36.88 | 41.76 |
| limit_below_fastest_sailing_time | 3.37 | 3.37 |
| no_time_feasible_service_in_pool | 7.89 | 7.89 |
| not_economic_to_open_service | 17.32 | 8.87 |
| not_profitable_to_carry | 0.39 | 0.46 |

Paired differences vs `A` (same seed; positive = arm higher):

| arm | n pairs | profit mean M | median | sd | min (seed) | max (seed) | seeds higher | coverage pp mean | coverage higher |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|
| B | 20 | +5.41 | +3.62 | 5.14 | +0.42 (7) | +21.33 (14) | 20/20 | +2.63 | 19/20 |
