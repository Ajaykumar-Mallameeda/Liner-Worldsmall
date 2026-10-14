| metric (mean over solved runs) | A | B | C_vub | D_ls |
|---|---:|---:|---:|---:|
| runs / solved / invalid-plan / other | 20 / 20 / 0 / 0 | 20 / 20 / 0 / 0 | 20 / 20 / 0 / 0 | 20 / 20 / 0 / 0 |
| revenue M USD/wk | 97.95 | 106.16 | 104.37 | 102.15 |
| vessel cost M | 16.71 | 17.09 | 16.85 | 16.87 |
| fuel cost M | 29.11 | 29.56 | 29.34 | 29.38 |
| port-call fixed incl. canal+capacity charge M | 8.55 | 8.73 | 8.58 | 8.50 |
| handling M | 17.55 | 19.29 | 19.03 | 18.42 |
| transshipment M | 1.33 | 1.38 | 1.43 | 1.29 |
| port variable M | 0.00 | 0.00 | 0.00 | 0.00 |
| total cost M | 73.24 | 76.05 | 75.23 | 74.45 |
| **profit M USD/wk** | 24.71 | 30.12 | 29.15 | 27.70 |
| margin % | 25.0 | 28.4 | 27.9 | 27.1 |
| coverage % | 31.2 | 33.9 | 33.3 | 32.6 |
| served TEU/wk | 86,353 | 93,611 | 91,943 | 90,068 |
| services | 28.1 | 29.4 | 29.3 | 28.6 |
| departures/wk | 30.8 | 31.5 | 31.4 | 30.8 |
| vessels assigned (of owned) | 175.6 | 179.8 | 179.0 | 176.9 |
| owned | 263 | 263 | 263 | 263 |
| fleet vessel utilisation (assigned/owned) | 0.667 | 0.683 | 0.681 | 0.673 |
| service leg load factor (mean of services) | 0.596 | 0.631 | 0.623 | 0.608 |
| leg load factor (mean of legs) | 0.609 | 0.645 | 0.638 | 0.623 |
| network leg load factor (carried/offered TEU-legs) | 0.582 | 0.618 | 0.614 | 0.602 |
| max p90 transit days | 43.9 | 39.2 | 44.2 | 39.2 |
| stage wall s | 124.1 | 116.7 | 121.4 | 120.1 |
| capped-model gap to bound % (incumbent vs LP bound) | 53.0 | -1.6 | 1.6 | 47.4 |
| ledger violations (sum) | 0 | 0 | 0 | 0 |
| transit violations (sum) | 0 | 0 | 0 | 0 |

Vessels assigned / owned by class (mean):

| class | A | B | C_vub | D_ls |
|---|---:|---:|---:|---:|
| Feeder_450 | 22.6 / 24 | 23.8 / 24 | 23.9 / 24 | 22.1 / 24 |
| Feeder_800 | 26.4 / 29 | 27.9 / 29 | 27.8 / 29 | 26.9 / 29 |
| Panamax_1200 | 60.1 / 68 | 59.5 / 68 | 61.5 / 68 | 60.8 / 68 |
| Panamax_2400 | 66.2 / 74 | 68.4 / 74 | 65.8 / 74 | 67.0 / 74 |
| Post_panamax | 0.0 / 58 | 0.0 / 58 | 0.0 / 58 | 0.0 / 58 |
| Super_panamax | 0.2 / 10 | 0.1 / 10 | 0.1 / 10 | 0.1 / 10 |

Unserved demand by reason (mean % of total demand):

| reason | A | B | C_vub | D_ls |
|---|---:|---:|---:|---:|
| capacity_exhausted | 3.79 | 3.80 | 4.69 | 3.53 |
| fleet_inventory_exhausted | 36.88 | 41.76 | 39.24 | 36.87 |
| limit_below_fastest_sailing_time | 3.37 | 3.37 | 3.37 | 3.37 |
| no_time_feasible_service_in_pool | 7.89 | 7.89 | 7.89 | 7.89 |
| not_economic_to_open_service | 17.32 | 8.87 | 11.10 | 15.36 |
| not_profitable_to_carry | 0.39 | 0.46 | 0.47 | 0.41 |
| unclassified_residual | nan | nan | 0.00 | nan |

Paired differences vs `A` (same seed; positive = arm higher):

| arm | n pairs | profit mean M | median | sd | min (seed) | max (seed) | seeds higher | coverage pp mean | coverage higher |
|---|---:|---:|---:|---:|---|---|---:|---:|---:|
| B | 20 | +5.41 | +3.62 | 5.14 | +0.42 (7) | +21.33 (14) | 20/20 | +2.63 | 19/20 |
| C_vub | 20 | +4.44 | +2.34 | 5.27 | -0.03 (7) | +20.91 (14) | 19/20 | +2.02 | 17/20 |
| D_ls | 20 | +3.00 | +1.11 | 3.91 | -0.51 (4) | +13.54 (14) | 18/20 | +1.34 | 15/20 |
