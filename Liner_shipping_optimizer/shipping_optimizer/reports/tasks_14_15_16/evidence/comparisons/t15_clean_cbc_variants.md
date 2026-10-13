# Task 15 - CBC strategies on the patched tree (trim), clean concurrency cap 4, 5 paired seeds, 120 s

Seeds: [0, 1, 2, 3, 4]. Pool per seed (unique candidates): 0: 1217, 1: 1215, 2: 1215, 3: 1210, 4: 1207. Profit = independent-ledger operating profit, USD M / week.

## 1. Every run (seed x strategy)

| seed | strategy | status | solver | profit M | MILP obj M | reconciled | coverage % | margin % | services | vessels | bound M | gap to bound % | solve s | wall s | viol | regional==ledger |
|---:|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | A_pert | feasible | feasible | 9.43 | 9.43 | True | 21.1 | 14.0 | 22 | 126 | 44.2 | 78.7 | 119.8 | 121.9 | 0 | True |
| 1 | A_pert | feasible | feasible | 6.85 | 6.85 | True | 17.7 | 12.2 | 17 | 111 | 44.6 | 84.6 | 120.2 | 122.7 | 0 | True |
| 2 | A_pert | feasible | feasible | 7.81 | 7.81 | True | 20.2 | 12.0 | 17 | 118 | 44.3 | 82.4 | 120.2 | 121.4 | 0 | True |
| 3 | A_pert | feasible | feasible | 7.78 | 7.78 | True | 17.1 | 14.0 | 17 | 107 | 43.6 | 82.2 | 119.9 | 122.5 | 0 | True |
| 4 | A_pert | feasible | feasible | 8.71 | 8.71 | True | 20.0 | 13.8 | 19 | 115 | 44.5 | 80.4 | 118.4 | 119.5 | 0 | True |
| 0 | A_sa | feasible | feasible | 9.40 | 9.40 | True | 21.5 | 13.9 | 22 | 133 | 44.2 | 78.7 | 118.4 | 120.4 | 0 | True |
| 1 | A_sa | feasible | feasible | 6.27 | 6.27 | True | 17.1 | 10.9 | 20 | 124 | 44.6 | 86.0 | 119.1 | 121.4 | 0 | True |
| 2 | A_sa | feasible | feasible | 7.25 | 7.25 | True | 15.9 | 14.2 | 12 | 76 | 44.3 | 83.6 | 119.1 | 121.3 | 0 | True |
| 3 | A_sa | feasible | feasible | 7.72 | 7.72 | True | 15.8 | 14.8 | 13 | 101 | 43.6 | 82.3 | 122.7 | 124.5 | 0 | True |
| 4 | A_sa | feasible | feasible | 8.69 | 8.69 | True | 18.3 | 15.0 | 17 | 108 | 44.5 | 80.5 | 117.9 | 120.7 | 0 | True |
| 0 | A_top120 | feasible | feasible | 8.48 | 8.48 | True | 13.7 | 18.3 | 10 | 74 | 44.2 | 80.8 | 6.8 | 10.0 | 0 | True |
| 1 | A_top120 | feasible | feasible | 8.59 | 8.59 | True | 18.8 | 14.0 | 14 | 107 | 44.6 | 80.8 | 36.7 | 38.8 | 0 | True |
| 2 | A_top120 | feasible | feasible | 7.60 | 7.60 | True | 18.9 | 12.6 | 13 | 100 | 44.3 | 82.9 | 11.5 | 13.5 | 0 | True |
| 3 | A_top120 | feasible | feasible | 7.92 | 7.92 | True | 16.0 | 14.7 | 11 | 95 | 43.6 | 81.8 | 7.6 | 10.1 | 0 | True |
| 4 | A_top120 | feasible | feasible | 8.24 | 8.24 | True | 17.9 | 14.3 | 13 | 100 | 44.5 | 81.5 | 17.5 | 19.5 | 0 | True |
| 0 | A_top60 | feasible | feasible | 7.50 | 7.50 | True | 12.2 | 17.8 | 7 | 61 | 44.2 | 83.0 | 5.5 | 7.5 | 0 | True |
| 1 | A_top60 | feasible | feasible | 7.89 | 7.89 | True | 18.6 | 13.1 | 12 | 104 | 44.6 | 82.3 | 5.9 | 7.8 | 0 | True |
| 2 | A_top60 | feasible | feasible | 6.37 | 6.37 | True | 14.3 | 13.7 | 9 | 71 | 44.3 | 85.6 | 5.7 | 8.2 | 0 | True |
| 3 | A_top60 | feasible | feasible | 7.76 | 7.76 | True | 16.7 | 14.1 | 11 | 98 | 43.6 | 82.2 | 4.8 | 6.9 | 0 | True |
| 4 | A_top60 | feasible | feasible | 7.13 | 7.13 | True | 15.9 | 13.5 | 10 | 88 | 44.5 | 84.0 | 5.9 | 8.4 | 0 | True |
| 0 | prod | feasible | feasible | 9.66 | 9.66 | True | 21.6 | 14.4 | 21 | 120 | 44.2 | 78.1 | 118.5 | 120.5 | 0 | True |
| 1 | prod | feasible | feasible | 8.32 | 8.32 | True | 22.3 | 11.8 | 21 | 131 | 44.6 | 81.4 | 120.1 | 122.0 | 0 | True |
| 2 | prod | feasible | feasible | 8.28 | 8.28 | True | 19.9 | 13.1 | 15 | 106 | 44.3 | 81.3 | 121.0 | 123.1 | 0 | True |
| 3 | prod | feasible | feasible | 8.41 | 8.41 | True | 19.2 | 13.3 | 19 | 121 | 43.6 | 80.7 | 120.7 | 122.9 | 0 | True |
| 4 | prod | feasible | feasible | 7.77 | 7.77 | True | 16.7 | 14.2 | 17 | 111 | 44.5 | 82.5 | 118.3 | 121.8 | 0 | True |

## 2. Per-strategy summary over seeds (mean, sd, min .. max)

| strategy | n | profit M mean (sd) | min .. max | coverage % | services | vessels | solve s mean | reconciled | verified (ledger) | usable runs | violations |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A_pert | 5 | 8.12 (0.98) | 6.85 .. 9.43 | 19.2 | 18.4 | 115 | 120 | 5/5 | 5/5 | 5/5 | 0 |
| A_sa | 5 | 7.87 (1.22) | 6.27 .. 9.40 | 17.7 | 16.8 | 108 | 119 | 5/5 | 5/5 | 5/5 | 0 |
| A_top120 | 5 | 8.17 (0.41) | 7.60 .. 8.59 | 17.1 | 12.2 | 95 | 16 | 5/5 | 5/5 | 5/5 | 0 |
| A_top60 | 5 | 7.33 (0.61) | 6.37 .. 7.89 | 15.5 | 9.8 | 84 | 6 | 5/5 | 5/5 | 5/5 | 0 |
| prod | 5 | 8.49 (0.70) | 7.77 .. 9.66 | 19.9 | 18.6 | 118 | 120 | 5/5 | 5/5 | 5/5 | 0 |

## 3. Paired difference in ledger profit vs `prod` (same seed, same pool; USD M; + = better)

| strategy | seed 0 | seed 1 | seed 2 | seed 3 | seed 4 | mean | seeds better |
|---|---:|---:|---:|---:|---:|---:|---:|
| A_pert | -0.23 | -1.47 | -0.48 | -0.63 | +0.95 | -0.37 | 1/5 |
| A_sa | -0.25 | -2.05 | -1.03 | -0.69 | +0.92 | -0.62 | 1/5 |
| A_top120 | -1.18 | +0.27 | -0.68 | -0.49 | +0.48 | -0.32 | 2/5 |
| A_top60 | -2.16 | -0.44 | -1.92 | -0.65 | -0.64 | -1.16 | 0/5 |

## 4. Solver diagnostics

| seed | strategy | services considered | in integer problem | variables | constraints | paths | notes |
|---:|---|---:|---:|---:|---:|---:|---|
| 0 | A_pert | 1201 | 336 | 8751 | 3317 | 13121 | {"restriction": {"lp_support": 327, "chosen": 336, "referenced": 1201, "lp_active": 1201, "selection_sec": 9.1, "perturbed_lps": 2}} |
| 1 | A_pert | 1198 | 359 | 9314 | 3414 | 13200 | {"restriction": {"lp_support": 341, "chosen": 359, "referenced": 1198, "lp_active": 1198, "selection_sec": 7.1, "perturbed_lps": 2}} |
| 2 | A_pert | 1200 | 359 | 9215 | 3407 | 13098 | {"restriction": {"lp_support": 344, "chosen": 359, "referenced": 1200, "lp_active": 1200, "selection_sec": 7.8, "perturbed_lps": 2}} |
| 3 | A_pert | 1193 | 365 | 9587 | 3437 | 13192 | {"restriction": {"lp_support": 348, "chosen": 365, "referenced": 1193, "lp_active": 1193, "selection_sec": 6.8, "perturbed_lps": 2}} |
| 4 | A_pert | 1192 | 353 | 9218 | 3383 | 13021 | {"restriction": {"lp_support": 333, "chosen": 353, "referenced": 1192, "lp_active": 1192, "selection_sec": 8.0, "perturbed_lps": 2}} |
| 0 | A_sa | 1201 | 409 | 9665 | 3613 | 13121 | {"restriction": {"lp_support": 327, "chosen": 409, "referenced": 1201, "lp_active": 1201, "selection_sec": 2.6, "standalone_profitable": 145}} |
| 1 | A_sa | 1198 | 422 | 10065 | 3672 | 13200 | {"restriction": {"lp_support": 341, "chosen": 422, "referenced": 1198, "lp_active": 1198, "selection_sec": 2.8, "standalone_profitable": 147}} |
| 2 | A_sa | 1200 | 426 | 10014 | 3683 | 13098 | {"restriction": {"lp_support": 344, "chosen": 426, "referenced": 1200, "lp_active": 1200, "selection_sec": 1.7, "standalone_profitable": 140}} |
| 3 | A_sa | 1193 | 424 | 10249 | 3679 | 13192 | {"restriction": {"lp_support": 348, "chosen": 424, "referenced": 1193, "lp_active": 1193, "selection_sec": 3.0, "standalone_profitable": 129}} |
| 4 | A_sa | 1192 | 407 | 9750 | 3606 | 13021 | {"restriction": {"lp_support": 333, "chosen": 407, "referenced": 1192, "lp_active": 1192, "selection_sec": 2.5, "standalone_profitable": 134}} |
| 0 | A_top120 | 1201 | 120 | 3840 | 2417 | 13121 | {"restriction": {"lp_support": 327, "chosen": 120, "referenced": 1201, "lp_active": 1201, "selection_sec": 0.0, "top_k": 120}} |
| 1 | A_top120 | 1198 | 120 | 3906 | 2416 | 13200 | {"restriction": {"lp_support": 341, "chosen": 120, "referenced": 1198, "lp_active": 1198, "selection_sec": 0.0, "top_k": 120}} |
| 2 | A_top120 | 1200 | 120 | 3750 | 2402 | 13098 | {"restriction": {"lp_support": 344, "chosen": 120, "referenced": 1200, "lp_active": 1200, "selection_sec": 0.0, "top_k": 120}} |
| 3 | A_top120 | 1193 | 120 | 3788 | 2404 | 13192 | {"restriction": {"lp_support": 348, "chosen": 120, "referenced": 1193, "lp_active": 1193, "selection_sec": 0.0, "top_k": 120}} |
| 4 | A_top120 | 1192 | 120 | 3792 | 2391 | 13021 | {"restriction": {"lp_support": 333, "chosen": 120, "referenced": 1192, "lp_active": 1192, "selection_sec": 0.0, "top_k": 120}} |
| 0 | A_top60 | 1201 | 60 | 2521 | 2082 | 13121 | {"restriction": {"lp_support": 327, "chosen": 60, "referenced": 1201, "lp_active": 1201, "selection_sec": 0.0, "top_k": 60}} |
| 1 | A_top60 | 1198 | 60 | 2574 | 2084 | 13200 | {"restriction": {"lp_support": 341, "chosen": 60, "referenced": 1198, "lp_active": 1198, "selection_sec": 0.0, "top_k": 60}} |
| 2 | A_top60 | 1200 | 60 | 2507 | 2076 | 13098 | {"restriction": {"lp_support": 344, "chosen": 60, "referenced": 1200, "lp_active": 1200, "selection_sec": 0.0, "top_k": 60}} |
| 3 | A_top60 | 1193 | 60 | 2562 | 2084 | 13192 | {"restriction": {"lp_support": 348, "chosen": 60, "referenced": 1193, "lp_active": 1193, "selection_sec": 0.0, "top_k": 60}} |
| 4 | A_top60 | 1192 | 60 | 2529 | 2075 | 13021 | {"restriction": {"lp_support": 333, "chosen": 60, "referenced": 1192, "lp_active": 1192, "selection_sec": 0.0, "top_k": 60}} |
| 0 | prod | 1201 | 327 | 8604 | 3280 | 13121 | {} |
| 1 | prod | 1198 | 341 | 9010 | 3347 | 13200 | {} |
| 2 | prod | 1200 | 344 | 8962 | 3350 | 13098 | {} |
| 3 | prod | 1193 | 348 | 9250 | 3371 | 13192 | {} |
| 4 | prod | 1192 | 333 | 8773 | 3307 | 13021 | {} |
