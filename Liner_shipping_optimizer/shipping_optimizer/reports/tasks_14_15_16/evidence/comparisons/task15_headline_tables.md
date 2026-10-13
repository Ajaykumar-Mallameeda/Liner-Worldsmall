# Task 15 - solver strategy comparison (tables generated from recorded runs)

## 1. Proven optimum of each pool vs what the production strategy realises

Optimum = unrestricted integer problem solved by HiGHS to a proven relative gap <= 1e-4 (`T15_highs600`). Production = LP relaxation -> restriction to its support -> CBC, 120 s. All values are independent-ledger operating profit, USD M / week.

| seed | proven optimum | gap to bound at stop | production CBC (B0) | % of optimum | reconciled (B0) | production CBC (patched) | HiGHS backend 120 s | % of optimum |
|---:|---:|---:|---:|---:|---|---:|---:|---:|
| 0 | 9.98 | -0.000 % | 9.66 | 96.8 | True | 9.66 | 9.85 | 98.8 |
| 1 | 9.37 | 0.009 % | 8.32 | 88.8 | False | 8.32 | 9.37 | 100.0 |
| 2 | 8.83 | 0.008 % | 8.28 | 93.7 | True | 8.28 | 8.83 | 100.0 |
| 3 | 9.42 | 0.004 % | 8.41 | 89.3 | True | 8.41 | 9.42 | 100.0 |
| 4 | 9.07 | 0.009 % | 7.77 | 85.7 | True | 7.77 | 9.07 | 100.0 |
| **mean (sd)** | **9.33** (0.43) | | **8.49** (0.70) | 90.9 | | **8.49** (0.70) | **9.31** (0.39) | 99.7 |

## 2. All strategies, 5 paired seeds (same pool per seed), 120 s unless stated

| strategy | tree | solver | n | mean M | sd | min .. max | vs production CBC (paired, mean M) | seeds better | reconciled | solve s | ledger violations |
|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| prod (production) | B0 | CBC LP-guided | 5/5 | 8.49 | 0.70 | 7.77 .. 9.66 | 0.00 | 0/5 | 4/5 | 117 | 0 |
| fullint (unrestricted) | B0 | CBC | 3/5 | -5.00 | 3.76 | -8.99 .. -1.53 | -13.57 | 0/3 | 2/3 | 109 | 0 |
| two:40 | B0 | CBC | 1/5 | 7.97 | 0.00 | 7.97 .. 7.97 | -1.69 | 0/1 | 0/1 | 103 | 0 |
| two:60 | B0 | CBC | 5/5 | 5.75 | 2.99 | 0.69 .. 7.73 | -2.74 | 0/5 | 4/5 | 108 | 0 |
| prod + vessel trim (patch A) | T15A | CBC LP-guided | 5/5 | 8.49 | 0.70 | 7.77 .. 9.66 | 0.00 | 0/5 | 5/5 | 120 | 0 |
| A_sa | T15A | CBC | 5/5 | 7.87 | 1.22 | 6.27 .. 9.40 | -0.62 | 1/5 | 5/5 | 119 | 0 |
| A_pert | T15A | CBC | 5/5 | 8.12 | 0.98 | 6.85 .. 9.43 | -0.37 | 1/5 | 5/5 | 120 | 0 |
| A_top120 | T15A | CBC | 5/5 | 8.17 | 0.41 | 7.60 .. 8.59 | -0.32 | 2/5 | 5/5 | 16 | 0 |
| A_top60 | T15A | CBC | 5/5 | 7.33 | 0.61 | 6.37 .. 7.89 | -1.16 | 0/5 | 5/5 | 6 | 0 |
| prog:100,160,240 | T15A | CBC progressive | 5/5 | 8.56 | 0.25 | 8.28 .. 8.91 | 0.08 | 3/5 | 5/5 | 119 | 0 |
| prog:120,200 | T15A | CBC progressive | 5/5 | 8.67 | 0.40 | 8.28 .. 9.32 | 0.19 | 2/5 | 5/5 | 118 | 0 |
| HiGHS backend (patch B), 120 s | T15AB | HiGHS unrestricted | 5/5 | 9.31 | 0.39 | 8.83 .. 9.85 | 0.82 | 5/5 | 5/5 | 104 | 0 |
| HiGHS 600 s (reference optimum) | B0 pool | HiGHS unrestricted | 5/5 | 9.33 | 0.43 | 8.83 .. 9.98 | 0.85 | 5/5 | 5/5 | 240 | 0 |

## 3. Time to proven optimality and bounds (HiGHS 600 s reference)

| seed | optimum M | dual bound M | gap % | solve s | services | vessels | coverage % | margin % |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 9.98 | 9.98 | -0.000 | 275.0 | 21 | 129 | 22.4 | 14.4 |
| 1 | 9.37 | 9.37 | 0.009 | 296.0 | 15 | 121 | 19.2 | 15.0 |
| 2 | 8.83 | 8.84 | 0.008 | 201.7 | 14 | 113 | 19.7 | 14.1 |
| 3 | 9.42 | 9.42 | 0.004 | 201.3 | 13 | 108 | 17.1 | 16.5 |
| 4 | 9.07 | 9.07 | 0.009 | 223.8 | 18 | 123 | 20.2 | 14.3 |

## 4. Cost components (USD M / week) - production CBC (patched) vs HiGHS backend, same pools

| seed | solver | revenue | vessel hire | fuel | port calls | handling | transshipment | total cost | profit | served TEU | unserved TEU |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | CBC | 67.22 | 17.91 | 26.65 | 0.63 | 11.53 | 0.31 | 57.57 | 9.66 | 59,618 | 216,829 |
| 0 | HiGHS | 62.38 | 16.28 | 24.21 | 0.59 | 10.72 | 0.22 | 52.53 | 9.85 | 55,120 | 221,327 |
| 1 | CBC | 70.44 | 19.31 | 29.81 | 0.69 | 11.62 | 0.14 | 62.11 | 8.32 | 61,619 | 214,828 |
| 1 | HiGHS | 62.48 | 17.03 | 24.60 | 0.56 | 10.43 | 0.03 | 53.11 | 9.37 | 53,172 | 223,275 |
| 2 | CBC | 63.12 | 17.84 | 25.84 | 0.50 | 10.14 | 0.06 | 54.84 | 8.28 | 55,125 | 221,322 |
| 2 | HiGHS | 62.85 | 17.85 | 24.84 | 0.51 | 10.32 | 0.01 | 54.02 | 8.83 | 54,541 | 221,906 |
| 3 | CBC | 63.42 | 17.37 | 26.00 | 0.54 | 10.33 | 0.32 | 55.01 | 8.41 | 53,056 | 223,391 |
| 3 | HiGHS | 57.19 | 15.22 | 22.20 | 0.44 | 9.45 | 0.06 | 47.77 | 9.42 | 47,324 | 229,123 |
| 4 | CBC | 54.70 | 14.13 | 23.20 | 0.56 | 8.55 | 0.10 | 46.93 | 7.77 | 46,214 | 230,233 |
| 4 | HiGHS | 63.43 | 16.84 | 25.89 | 0.58 | 10.41 | 0.11 | 54.36 | 9.07 | 55,733 | 220,714 |
