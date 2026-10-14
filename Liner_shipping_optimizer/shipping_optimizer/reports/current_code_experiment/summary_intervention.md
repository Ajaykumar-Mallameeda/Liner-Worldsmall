| metric (mean over solved runs) | B | BCA |
|---|---:|---:|
| runs / solved / invalid-plan / other | 20 / 20 / 0 / 0 | 20 / 20 / 0 / 0 |
| revenue M USD/wk | 106.16 | 105.04 |
| vessel cost M | 17.09 | 16.94 |
| fuel cost M | 29.56 | 28.85 |
| port-call fixed incl. canal+capacity charge M | 8.73 | 8.52 |
| handling M | 19.29 | 18.68 |
| transshipment M | 1.38 | 1.41 |
| port variable M | 0.00 | 0.00 |
| total cost M | 76.05 | 74.40 |
| **profit M USD/wk** | 30.12 | 30.64 |
| margin % | 28.4 | 29.2 |
| coverage % | 33.9 | 33.2 |
| served TEU/wk | 93,611 | 91,660 |
| services | 29.4 | 29.7 |
| departures/wk | 31.5 | 32.0 |
| vessels assigned (of owned) | 179.8 | 175.6 |
| owned | 263 | 263 |
| fleet vessel utilisation (assigned/owned) | 0.683 | 0.667 |
| service leg load factor (mean of services) | 0.631 | 0.624 |
| leg load factor (mean of legs) | 0.645 | 0.638 |
| network leg load factor (carried/offered TEU-legs) | 0.618 | 0.620 |
| max p90 transit days | 39.2 | 40.2 |
| stage wall s | 116.7 | 118.5 |
| capped-model gap to bound % (incumbent vs LP bound) | -1.6 | 3.6 |
| ledger violations (sum) | 0 | 0 |
| transit violations (sum) | 0 | 0 |

Vessels assigned / owned by class (mean):

| class | B | BCA |
|---|---:|---:|
| Feeder_450 | 23.8 / 24 | 23.1 / 24 |
| Feeder_800 | 27.9 / 29 | 27.9 / 29 |
| Panamax_1200 | 59.5 / 68 | 53.6 / 68 |
| Panamax_2400 | 68.4 / 74 | 70.8 / 74 |
| Post_panamax | 0.0 / 58 | 0.0 / 58 |
| Super_panamax | 0.1 / 10 | 0.1 / 10 |

Unserved demand by reason (mean % of total demand):

| reason | B | BCA |
|---|---:|---:|
| capacity_exhausted | 3.80 | 3.71 |
| fleet_inventory_exhausted | 41.76 | 41.81 |
| limit_below_fastest_sailing_time | 3.37 | 3.37 |
| no_time_feasible_service_in_pool | 7.89 | 7.89 |
| not_economic_to_open_service | 8.87 | 9.62 |
| not_profitable_to_carry | 0.46 | 0.45 |

Paired differences vs `B` (same seed; positive = arm higher):

| arm | n pairs | profit mean M | median | sd | min (seed) | max (seed) | seeds higher | coverage pp mean | coverage higher |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|
| BCA | 20 | +0.52 | +0.82 | 1.07 | -1.06 (5) | +2.40 (1) | 12/20 | -0.71 | 6/20 |
