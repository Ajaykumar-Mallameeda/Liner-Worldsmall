# Legacy (600 USD/t) versus market-price scenarios on identical captured inputs

Same demand, fleet, captured candidate pool and solver for every row; only the bunker price changes. USD per week. `regional` = cheapest observed bunkering port on the rotation, else the 895.5 USD/t reference; `regional_strict` = rotations without an observed port are rejected; ×0.8 / ×1.2 scale every snapshot price. Violations are the independent ledger's; every scenario reconciles MILP = ledger.

## A. Legacy candidate pool (U4 capture, the pool before Tasks 9 and 10)

Production strategy (LP-guided restriction), 3 captured global-stage call(s), candidates 1096, 1086, 1082.

| scenario | call 0: profit / coverage / services / vessels / status | call 1: profit / coverage / services / vessels / status | call 2: profit / coverage / services / vessels / status | mean profit | ledger violations |
|---|---|---|---|---|---|
| legacy_600 | 1,992,474 / 11.0 % / 13 svc / 53 ves / feasible | 2,623,164 / 9.0 % / 10 svc / 50 ves / feasible | 4,212,367 / 10.1 % / 11 svc / 42 ves / feasible | 2,942,668 | 0 |
| reference_uniform | 0 / 0.0 % / 0 svc / 0 ves / feasible | 0 / 0.0 % / 0 svc / 0 ves / feasible | 0 / 0.0 % / 0 svc / 0 ves / feasible | 0 | 0 |
| regional | 122,893 / 1.6 % / 1 svc / 9 ves / feasible | 411,961 / 1.9 % / 2 svc / 8 ves / feasible | 149,019 / 1.6 % / 1 svc / 8 ves / feasible | 227,958 | 0 |
| regional_x0.8 | 930,917 / 3.7 % / 3 svc / 26 ves / feasible | 2,705,486 / 9.6 % / 11 svc / 51 ves / feasible | 2,157,062 / 6.1 % / 5 svc / 32 ves / feasible | 1,931,155 | 0 |
| regional_x1.2 | 0 / 0.0 % / 0 svc / 0 ves / feasible | 0 / 0.0 % / 0 svc / 0 ves / feasible | 0 / 0.0 % / 0 svc / 0 ves / feasible | 0 | 0 |
| regional_strict | 122,893 / 1.6 % / 1 svc / 9 ves / feasible | 487,006 / 3.5 % / 2 svc / 16 ves / feasible | 496,045 / 3.5 % / 2 svc / 17 ves / feasible | 368,648 | 0 |

Unrestricted integer solve (no LP-guided restriction; time limit 300 s; `optimal` = proven):

| scenario | call 1 |
|---|---|
| regional@full_int | 846,959 / 4.1 % / 4 svc / 19 ves / optimal |
| reference_uniform@full_int | 95,938 / 0.4 % / 1 svc / 2 ves / optimal |
| regional_x1.2@full_int | 67,124 / 0.4 % / 1 svc / 2 ves / optimal |

## B. Final default candidate pool (demand loops 60 and class screening k 1; capture FINAL_global_inputs.pkl)

Production strategy (LP-guided restriction), 3 captured global-stage call(s), candidates 1177, 1183, 1178.

| scenario | call 0: profit / coverage / services / vessels / status | call 1: profit / coverage / services / vessels / status | call 2: profit / coverage / services / vessels / status | mean profit | ledger violations |
|---|---|---|---|---|---|
| legacy_600 | 8,516,897 / 18.7 % / 16 svc / 104 ves / feasible | 9,063,130 / 19.7 % / 17 svc / 109 ves / feasible | 8,869,601 / 19.8 % / 17 svc / 117 ves / feasible | 8,816,543 | 0 |
| reference_uniform | 1,098,902 / 5.3 % / 5 svc / 30 ves / feasible | 2,071,722 / 8.2 % / 6 svc / 37 ves / feasible | 1,718,031 / 7.3 % / 5 svc / 36 ves / feasible | 1,629,552 | 0 |
| regional | 2,704,080 / 10.3 % / 8 svc / 44 ves / feasible | 3,451,478 / 13.4 % / 10 svc / 62 ves / feasible | 2,994,681 / 12.7 % / 9 svc / 63 ves / feasible | 3,050,080 | 0 |
| regional_x0.8 | 6,417,850 / 17.4 % / 12 svc / 95 ves / feasible | 7,307,944 / 15.6 % / 12 svc / 79 ves / feasible | 6,991,522 / 17.6 % / 13 svc / 100 ves / feasible | 6,905,772 | 0 |
| regional_x1.2 | 409,362 / 4.2 % / 3 svc / 13 ves / feasible | 1,284,042 / 4.0 % / 3 svc / 12 ves / feasible | 897,336 / 3.1 % / 2 svc / 11 ves / feasible | 863,580 | 0 |
| regional_strict | 3,192,320 / 10.4 % / 7 svc / 47 ves / feasible | 4,154,054 / 9.1 % / 6 svc / 39 ves / feasible | 3,207,386 / 13.0 % / 9 svc / 65 ves / feasible | 3,517,920 | 0 |

Unrestricted integer solve (no LP-guided restriction; time limit 300 s; `optimal` = proven):

| scenario | call 0 | call 1 | call 2 |
|---|---|---|---|
| regional@full_int | 2,740,142 / 11.0 % / 9 svc / 54 ves / optimal | 3,451,478 / 13.4 % / 10 svc / 62 ves / optimal | 2,994,681 / 12.7 % / 9 svc / 63 ves / optimal |
| reference_uniform@full_int | 1,098,902 / 5.3 % / 5 svc / 30 ves / optimal | 2,071,722 / 8.2 % / 6 svc / 37 ves / optimal | 1,718,031 / 7.3 % / 5 svc / 36 ves / optimal |
| legacy_600@full_int | 8,938,522 / 18.3 % / 16 svc / 104 ves / feasible | 9,275,781 / 19.2 % / 15 svc / 111 ves / feasible | 8,275,061 / 20.0 % / 17 svc / 131 ves / feasible |
