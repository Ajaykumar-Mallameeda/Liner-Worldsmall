# Task 15 - baseline solver strategies, production tree B0, 5 paired seeds, 120 s

Seeds: [0, 1, 2, 3, 4]. Pool per seed (unique candidates): 0: 1217, 1: 1215, 2: 1215, 3: 1210, 4: 1207. Profit = independent-ledger operating profit, USD M / week.

## 1. Every run (seed x strategy)

| seed | strategy | status | solver | profit M | MILP obj M | reconciled | coverage % | margin % | services | vessels | bound M | gap to bound % | solve s | wall s | viol | regional==ledger |
|---:|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | prod | feasible | feasible | 9.66 | 9.66 | True | 21.6 | 14.4 | 21 | 120 | 44.2 | 78.1 | 117.6 | 119.8 | 0 | True |
| 1 | prod | feasible | feasible | 8.32 | 7.26 | False | 22.3 | 11.8 | 21 | 131 | 44.6 | 83.7 | 116.8 | 119.1 | 0 | False |
| 2 | prod | feasible | feasible | 8.28 | 8.28 | True | 19.9 | 13.1 | 15 | 106 | 44.3 | 81.3 | 114.7 | 117.1 | 0 | True |
| 3 | prod | feasible | feasible | 8.41 | 8.41 | True | 19.2 | 13.3 | 19 | 121 | 43.6 | 80.7 | 117.2 | 119.6 | 0 | True |
| 4 | prod | feasible | feasible | 7.77 | 7.77 | True | 16.7 | 14.2 | 17 | 111 | 44.5 | 82.5 | 117.1 | 119.3 | 0 | True |
| 0 | fullint | feasible | feasible | -4.49 | -4.60 | False | 23.5 | -6.0 | 28 | 170 | n/a | nan | 112.1 | 114.1 | 0 | False |
| 1 | fullint | not_solved | not_solved | n/a | 0.00 | None | nan | nan | None | None | n/a | nan | 106.1 | 108.1 | 0 | None |
| 2 | fullint | feasible | feasible | -1.53 | -1.53 | True | 19.7 | -2.4 | 19 | 145 | n/a | nan | 109.3 | 111.2 | 0 | True |
| 3 | fullint | not_solved | not_solved | n/a | 0.00 | None | nan | nan | None | None | n/a | nan | 106.5 | 108.4 | 0 | None |
| 4 | fullint | feasible | feasible | -8.99 | -8.99 | True | 21.2 | -13.4 | 23 | 167 | n/a | nan | 111.3 | 113.3 | 0 | True |
| 0 | two:40 | feasible | feasible | 7.97 | 6.95 | False | 21.2 | 12.2 | 21 | 120 | 44.2 | 84.3 | 104.7 | 107.0 | 0 | False |
| 1 | two:40 | not_solved | not_solved | n/a | 0.00 | None | nan | nan | None | None | 44.6 | 100.0 | 102.6 | 105.1 | 0 | None |
| 2 | two:40 | not_solved | not_solved | n/a | 0.00 | None | nan | nan | None | None | 44.3 | 100.0 | 101.1 | 103.7 | 0 | None |
| 3 | two:40 | not_solved | not_solved | n/a | 0.00 | None | nan | nan | None | None | 43.6 | 100.0 | 106.0 | 108.4 | 0 | None |
| 4 | two:40 | not_solved | not_solved | n/a | 0.00 | None | nan | nan | None | None | 44.5 | 100.0 | 102.4 | 104.8 | 0 | None |
| 0 | two:60 | feasible | feasible | 7.44 | 7.44 | True | 20.5 | 11.4 | 21 | 126 | 44.2 | 83.2 | 109.4 | 111.9 | 0 | True |
| 1 | two:60 | feasible | feasible | 5.36 | -3.24 | False | 13.3 | 12.7 | 14 | 76 | 44.6 | 107.3 | 106.9 | 109.6 | 0 | False |
| 2 | two:60 | feasible | feasible | 7.54 | 7.54 | True | 17.5 | 13.5 | 11 | 87 | 44.3 | 83.0 | 106.4 | 108.8 | 0 | True |
| 3 | two:60 | feasible | feasible | 7.73 | 7.73 | True | 17.4 | 13.4 | 16 | 111 | 43.6 | 82.3 | 111.9 | 114.5 | 0 | True |
| 4 | two:60 | feasible | feasible | 0.69 | 0.69 | True | 19.8 | 1.1 | 21 | 136 | 44.5 | 98.4 | 107.9 | 110.2 | 0 | True |
| 0 | A_sa | not_solved | not_solved | n/a | 9.40 | None | nan | nan | None | None | 44.2 | 78.7 | 117.5 | 119.5 | 0 | None |
| 1 | A_sa | not_solved | not_solved | n/a | 6.03 | None | nan | nan | None | None | 44.6 | 86.5 | 117.0 | 118.9 | 0 | None |
| 2 | A_sa | not_solved | not_solved | n/a | 7.26 | None | nan | nan | None | None | 44.3 | 83.6 | 117.8 | 119.8 | 0 | None |
| 3 | A_sa | not_solved | not_solved | n/a | 8.07 | None | nan | nan | None | None | 43.6 | 81.5 | 117.9 | 120.0 | 0 | None |
| 4 | A_sa | not_solved | not_solved | n/a | 8.69 | None | nan | nan | None | None | 44.5 | 80.5 | 117.0 | 118.7 | 0 | None |
| 0 | A_pert | not_solved | not_solved | n/a | 9.43 | None | nan | nan | None | None | 44.2 | 78.7 | 117.6 | 119.6 | 0 | None |
| 1 | A_pert | not_solved | not_solved | n/a | 4.71 | None | nan | nan | None | None | 44.6 | 89.4 | 119.7 | 121.7 | 0 | None |
| 2 | A_pert | not_solved | not_solved | n/a | 7.86 | None | nan | nan | None | None | 44.3 | 82.3 | 117.6 | 119.7 | 0 | None |
| 3 | A_pert | not_solved | not_solved | n/a | 7.78 | None | nan | nan | None | None | 43.6 | 82.2 | 117.9 | 119.8 | 0 | None |
| 4 | A_pert | not_solved | not_solved | n/a | 8.71 | None | nan | nan | None | None | 44.5 | 80.4 | 117.4 | 119.3 | 0 | None |
| 0 | highs | feasible | feasible | 9.85 | 9.85 | True | 19.9 | 15.8 | 20 | 117 | 10.8 | 8.9 | 120.1 | 122.8 | 0 | True |
| 1 | highs | feasible | feasible | 9.37 | 9.37 | True | 19.2 | 15.0 | 15 | 121 | 10.1 | 7.5 | 120.1 | 122.7 | 0 | True |
| 2 | highs | feasible | feasible | 8.81 | 8.81 | True | 19.4 | 14.4 | 14 | 105 | 9.2 | 4.6 | 120.1 | 122.8 | 0 | True |
| 3 | highs | feasible | feasible | 9.42 | 9.42 | True | 17.1 | 16.5 | 13 | 108 | 9.7 | 2.7 | 120.1 | 122.9 | 0 | True |
| 4 | highs | feasible | feasible | 9.07 | 9.07 | True | 20.2 | 14.3 | 18 | 123 | 9.5 | 4.8 | 120.1 | 122.9 | 0 | True |

## 2. Per-strategy summary over seeds (mean, sd, min .. max)

| strategy | n | profit M mean (sd) | min .. max | coverage % | services | vessels | solve s mean | reconciled | verified (ledger) | usable runs | violations |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| prod | 5 | 8.49 (0.70) | 7.77 .. 9.66 | 19.9 | 18.6 | 118 | 117 | 4/5 | 5/5 | 5/5 | 0 |
| fullint | 5 | -5.00 (3.76) | -8.99 .. -1.53 | 21.5 | 23.3 | 161 | 109 | 2/5 | 3/5 | 3/5 | 0 |
| two:40 | 5 | 7.97 (0.00) | 7.97 .. 7.97 | 21.2 | 21.0 | 120 | 103 | 0/5 | 1/5 | 1/5 | 0 |
| two:60 | 5 | 5.75 (2.99) | 0.69 .. 7.73 | 17.7 | 16.6 | 107 | 108 | 4/5 | 5/5 | 5/5 | 0 |
| A_sa | 5 | n/a (n/a) | n/a .. n/a | nan | nan | nan | 117 | 0/5 | 0/5 | 0/5 | 0 |
| A_pert | 5 | n/a (n/a) | n/a .. n/a | nan | nan | nan | 118 | 0/5 | 0/5 | 0/5 | 0 |
| highs | 5 | 9.30 (0.40) | 8.81 .. 9.85 | 19.2 | 16.0 | 115 | 120 | 5/5 | 5/5 | 5/5 | 0 |

## 3. Paired difference in ledger profit vs `prod` (same seed, same pool; USD M; + = better)

| strategy | seed 0 | seed 1 | seed 2 | seed 3 | seed 4 | mean | seeds better |
|---|---:|---:|---:|---:|---:|---:|---:|
| fullint | -14.15 | n/a | -9.81 | n/a | -16.75 | -13.57 | 0/3 |
| two:40 | -1.69 | n/a | n/a | n/a | n/a | -1.69 | 0/1 |
| two:60 | -2.22 | -2.96 | -0.75 | -0.68 | -7.07 | -2.74 | 0/5 |
| A_sa | n/a | n/a | n/a | n/a | n/a | n/a | 0/0 |
| A_pert | n/a | n/a | n/a | n/a | n/a | n/a | 0/0 |
| highs | +0.20 | +1.05 | +0.52 | +1.01 | +1.30 | 0.82 | 5/5 |

## 4. Solver diagnostics

| seed | strategy | services considered | in integer problem | variables | constraints | paths | notes |
|---:|---|---:|---:|---:|---:|---:|---|
| 0 | prod | 1201 | 327 | 8604 | 3280 | 13121 | {} |
| 1 | prod | 1198 | 341 | 9010 | 3347 | 13200 | {} |
| 2 | prod | 1200 | 344 | 8962 | 3350 | 13098 | {} |
| 3 | prod | 1193 | 348 | 9250 | 3371 | 13192 | {} |
| 4 | prod | 1192 | 333 | 8773 | 3307 | 13021 | {} |
| 0 | fullint | 1201 | 1201 | 17287 | 6108 | 13121 | {} |
| 1 | fullint | 1198 | 1198 | 17360 | 6103 | 13200 | {} |
| 2 | fullint | 1200 | 1200 | 17262 | 6103 | 13098 | {} |
| 3 | fullint | 1193 | 1193 | 17342 | 6088 | 13192 | {} |
| 4 | fullint | 1192 | 1192 | 17169 | 6073 | 13021 | {} |
| 0 | two:40 | 1201 | 327 | 8604 | 3280 | 13121 | {"stage1": {"status": "feasible", "objective": 6952279.162821505, "bound": 44172440.36123621, "runtime": 37.18527840002207, "restricted_to": 327, "polished_obje |
| 1 | two:40 | 1198 | 341 | 9010 | 3347 | 13200 | {"stage1": {"status": "not_solved", "objective": 0.0, "bound": 44649255.836547635, "runtime": 36.18228869995801, "restricted_to": 341, "polished_objective": -In |
| 2 | two:40 | 1200 | 344 | 8962 | 3350 | 13098 | {"stage1": {"status": "not_solved", "objective": 0.0, "bound": 44322409.327285275, "runtime": 36.931826500047464, "restricted_to": 344, "polished_objective": -I |
| 3 | two:40 | 1193 | 348 | 9250 | 3371 | 13192 | {"stage1": {"status": "not_solved", "objective": 0.0, "bound": 43616829.42674695, "runtime": 35.866219000017736, "restricted_to": 348, "polished_objective": -In |
| 4 | two:40 | 1192 | 333 | 8773 | 3307 | 13021 | {"stage1": {"status": "not_solved", "objective": 0.0, "bound": 44491940.03125499, "runtime": 36.31485809996957, "restricted_to": 333, "polished_objective": -Inf |
| 0 | two:60 | 1201 | 327 | 8604 | 3280 | 13121 | {"stage1": {"status": "feasible", "objective": 7435161.782929085, "bound": 44172440.36123621, "runtime": 56.806283799989615, "restricted_to": 327, "polished_obj |
| 1 | two:60 | 1198 | 341 | 9010 | 3347 | 13200 | {"stage1": {"status": "feasible", "objective": -3237607.6195632815, "bound": 44649255.836547635, "runtime": 56.98612109996611, "restricted_to": 341, "polished_o |
| 2 | two:60 | 1200 | 344 | 8962 | 3350 | 13098 | {"stage1": {"status": "feasible", "objective": 7536365.3963999245, "bound": 44322409.327285275, "runtime": 57.13540670002112, "restricted_to": 344, "polished_ob |
| 3 | two:60 | 1193 | 348 | 9250 | 3371 | 13192 | {"stage1": {"status": "feasible", "objective": 7729298.948799972, "bound": 43616829.42674695, "runtime": 55.82882190000964, "restricted_to": 348, "polished_obje |
| 4 | two:60 | 1192 | 333 | 8773 | 3307 | 13021 | {"stage1": {"status": "feasible", "objective": 691741.2854437251, "bound": 44491940.03125499, "runtime": 57.28382279997459, "restricted_to": 333, "polished_obje |
| 0 | A_sa | 1201 | 409 | 9665 | 3613 | 13121 | {"restriction": {"lp_support": 327, "chosen": 409, "referenced": 1201, "lp_active": 1201, "selection_sec": 1.2, "standalone_profitable": 145}} |
| 1 | A_sa | 1198 | 422 | 10065 | 3672 | 13200 | {"restriction": {"lp_support": 341, "chosen": 422, "referenced": 1198, "lp_active": 1198, "selection_sec": 1.2, "standalone_profitable": 147}} |
| 2 | A_sa | 1200 | 426 | 10014 | 3683 | 13098 | {"restriction": {"lp_support": 344, "chosen": 426, "referenced": 1200, "lp_active": 1200, "selection_sec": 1.2, "standalone_profitable": 140}} |
| 3 | A_sa | 1193 | 424 | 10249 | 3679 | 13192 | {"restriction": {"lp_support": 348, "chosen": 424, "referenced": 1193, "lp_active": 1193, "selection_sec": 1.2, "standalone_profitable": 129}} |
| 4 | A_sa | 1192 | 407 | 9750 | 3606 | 13021 | {"restriction": {"lp_support": 333, "chosen": 407, "referenced": 1192, "lp_active": 1192, "selection_sec": 1.3, "standalone_profitable": 134}} |
| 0 | A_pert | 1201 | 336 | 8751 | 3317 | 13121 | {"restriction": {"lp_support": 327, "chosen": 336, "referenced": 1201, "lp_active": 1201, "selection_sec": 8.3, "perturbed_lps": 2}} |
| 1 | A_pert | 1198 | 359 | 9314 | 3414 | 13200 | {"restriction": {"lp_support": 341, "chosen": 359, "referenced": 1198, "lp_active": 1198, "selection_sec": 7.0, "perturbed_lps": 2}} |
| 2 | A_pert | 1200 | 359 | 9215 | 3407 | 13098 | {"restriction": {"lp_support": 344, "chosen": 359, "referenced": 1200, "lp_active": 1200, "selection_sec": 8.2, "perturbed_lps": 2}} |
| 3 | A_pert | 1193 | 365 | 9587 | 3437 | 13192 | {"restriction": {"lp_support": 348, "chosen": 365, "referenced": 1193, "lp_active": 1193, "selection_sec": 8.0, "perturbed_lps": 2}} |
| 4 | A_pert | 1192 | 353 | 9218 | 3383 | 13021 | {"restriction": {"lp_support": 333, "chosen": 353, "referenced": 1192, "lp_active": 1192, "selection_sec": 7.4, "perturbed_lps": 2}} |
| 0 | highs | 1201 | 1201 | 17287 | 6108 | 13121 | {"highs": {"status": 1, "message": "Time limit reached. (HiGHS Status 13: Time limit reached)", "mip_gap": 0.09822090729508805, "mip_dual_bound": 10821893.36070 |
| 1 | highs | 1198 | 1198 | 17360 | 6103 | 13200 | {"highs": {"status": 1, "message": "Time limit reached. (HiGHS Status 13: Time limit reached)", "mip_gap": 0.08081494079329148, "mip_dual_bound": 10128809.78139 |
| 2 | highs | 1200 | 1200 | 17262 | 6103 | 13098 | {"highs": {"status": 1, "message": "Time limit reached. (HiGHS Status 13: Time limit reached)", "mip_gap": 0.04860662230713027, "mip_dual_bound": 9234317.512601 |
| 3 | highs | 1193 | 1193 | 17342 | 6088 | 13192 | {"highs": {"status": 1, "message": "Time limit reached. (HiGHS Status 13: Time limit reached)", "mip_gap": 0.027446875603148534, "mip_dual_bound": 9676352.22977 |
| 4 | highs | 1192 | 1192 | 17169 | 6073 | 13021 | {"highs": {"status": 1, "message": "Time limit reached. (HiGHS Status 13: Time limit reached)", "mip_gap": 0.050520216950419014, "mip_dual_bound": 9523832.13263 |
