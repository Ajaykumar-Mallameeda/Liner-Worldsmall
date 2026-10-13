# Task 16 - candidate-filter experiment (tables generated from recorded runs)

## HiGHS backend, 600 s (proves the optimum of each pool when it can)

| variant | pool (unique cand.) | seed 0 | seed 1 | seed 2 | seed 3 | seed 4 | mean | sd | paired vs legacy (mean) | seeds better | coverage % | services | vessels | margin % | violations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| legacy | 1213 | 9.98 | 9.37 | 8.83 | 9.42 | 9.07 | 9.33 | 0.43 | 0.00 | 0/5 | 19.7 | 16.2 | 119 | 14.8 | 0 |
| exempt_screened | 1213 | 9.98 | 9.37 | 8.83 | 9.42 | 9.07 | 9.33 | 0.43 | 0.00 | 0/5 | 19.7 | 16.2 | 119 | 14.8 | 0 |
| econ_cap | 1161 | 12.45* | 12.19* | 11.63* | 10.27* | 10.87* | 11.48 | 0.91 | 2.15 | 5/5 | 25.5 | 26.8 | 148 | 14.2 | 0 |
| nofilter | 1281 | 10.10 | 9.37 | 8.93 | 9.42 | 9.07 | 9.38 | 0.45 | 0.04 | 4/5 | 19.2 | 16.2 | 115 | 15.3 | 0 |

`*` = incumbent at the 600 s limit, not proven optimal (relative gap to the MIP dual bound: econ_cap s0: 7.8 %, econ_cap s1: 14.0 %, econ_cap s2: 7.4 %, econ_cap s3: 19.9 %, econ_cap s4: 9.3 %).

## production CBC strategy (LP restriction), 120 s

| variant | pool (unique cand.) | seed 0 | seed 1 | seed 2 | seed 3 | seed 4 | mean | sd | paired vs legacy (mean) | seeds better | coverage % | services | vessels | margin % | violations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| legacy | 1213 | 9.66 | 8.32 | 8.28 | 8.42 | 8.54 | 8.64 | 0.58 | 0.00 | 0/5 | 19.9 | 17.4 | 113 | 13.7 | 0 |
| exempt_screened | 1213 | 9.66 | 8.32 | 8.28 | 8.42 | 8.54 | 8.64 | 0.58 | 0.00 | 0/5 | 19.9 | 17.4 | 113 | 13.7 | 0 |
| econ_cap | 1161 | 8.57 | 10.62 | 8.43 | 8.62 | 9.52 | 9.15 | 0.93 | 0.51 | 4/5 | 19.8 | 21.2 | 121 | 14.4 | 0 |
| nofilter | 1281 | 9.56 | 8.66 | 8.28 | 8.56 | 8.71 | 8.75 | 0.48 | 0.11 | 3/5 | 20.2 | 18.0 | 115 | 13.7 | 0 |

## Production code path (`LINER_REGIONAL_FILTER=economic`) vs the harness variant `econ_cap`

| seed | pool hash == harness econ_cap | CBC 120 s: profit M | HiGHS 120 s: profit M | HiGHS status | violations | regional==ledger |
|---:|---|---:|---:|---|---:|---|
| 0 | True | 8.57 | 8.47 | feasible | 0 | True |
| 1 | True | 10.62 | 7.38 | feasible | 0 | True |
| 2 | True | 8.43 | 10.92 | feasible | 0 | True |
| 3 | True | 8.62 | 9.81 | feasible | 0 | True |
| 4 | True | 9.52 | 6.78 | feasible | 0 | True |

## Path-cap sensitivity (`max_paths_per_od` 10 -> 30), HiGHS 600 s

| filter | cap 10 (profit M, per seed) | cap 30 (profit M, per seed) | mean 10 | mean 30 | mean gain |
|---|---|---|---:|---:|---:|
| legacy | 9.98, 9.37, 8.83, 9.42, 9.07 | 3.40, 2.25, 2.45, 12.40, 5.96 | 9.33 | 5.29 | -4.04 |
| economic | 12.45, 12.19, 11.63, 10.27, 10.87 | 9.96, 5.99, 8.02, 2.14, 11.36 | 11.48 | 7.49 | -3.99 |
