
### O5_base

| run | assertions | status | iter | profit M | margin % | cov % | served | svc | ves | LF | ledger | viol | MILP | bound M | reopt M | LS M | p90 max d | min slack d | s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---:|---:|
| O5_base_run1 | 362/362 | complete | 2 | 13.71 | 16.6 | 25.9 | 71,605 | 26 | 153 | 0.694 | True | 0 | feasible | 41.4 | 3.87 | 0.00 | 39.3 | 0.008 | 417 |
| O5_base_run2 | 362/362 | complete | 2 | 13.37 | 18.4 | 23.0 | 63,506 | 23 | 125 | 0.689 | True | 0 | feasible | 40.6 | 3.44 | 0.00 | 40.6 | 0.010 | 448 |
| O5_base_run3 | 362/362 | complete | 2 | 12.29 | 14.2 | 26.5 | 73,168 | 30 | 171 | 0.639 | True | 0 | feasible | 41.9 | 2.19 | 0.00 | 41.2 | 0.001 | 392 |
  - O5_base_run1: iterations (profit M, cov %, milp) [(12.21, 25.1, 'feasible'), (11.04, 21.7, 'feasible'), (13.71, 25.9, 'feasible')]; vub=False; ls_applied=False; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 21, 'Panamax_1200': 64, 'Panamax_2400': 35, 'Post_panamax': 25, 'Super_panamax': 8}
  - O5_base_run2: iterations (profit M, cov %, milp) [(12.65, 24.0, 'feasible'), (11.48, 20.5, 'feasible'), (13.37, 23.0, 'feasible')]; vub=False; ls_applied=False; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 29, 'Panamax_1200': 31, 'Panamax_2400': 27, 'Post_panamax': 30, 'Super_panamax': 8}
  - O5_base_run3: iterations (profit M, cov %, milp) [(10.04, 27.3, 'feasible'), (10.84, 20.0, 'feasible'), (12.29, 26.5, 'feasible')]; vub=False; ls_applied=False; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 29, 'Panamax_1200': 60, 'Panamax_2400': 54, 'Post_panamax': 19, 'Super_panamax': 9}

- profit M: mean 13.12 (min 12.29, max 13.71); coverage % mean 25.1; assertions ['362/362', '362/362', '362/362']

### O5_ls

| run | assertions | status | iter | profit M | margin % | cov % | served | svc | ves | LF | ledger | viol | MILP | bound M | reopt M | LS M | p90 max d | min slack d | s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---:|---:|
| O5_ls_run1 | 360/360 | complete | 1 | 14.07 | 16.2 | 27.1 | 74,845 | 26 | 165 | 0.663 | True | 0 | feasible | 41.9 | 0.00 | 1.78 | 35.5 | 0.047 | 436 |
| O5_ls_run2 | 360/360 | complete | 0 | 15.44 | 15.5 | 32.0 | 88,596 | 35 | 183 | 0.705 | True | 0 | feasible | 41.2 | 0.00 | 2.76 | 33.9 | 0.025 | 350 |
| O5_ls_run3 | 360/360 | complete | 1 | 15.36 | 16.3 | 30.0 | 82,812 | 34 | 169 | 0.694 | True | 0 | feasible | 38.8 | 0.00 | 4.61 | 34.9 | 0.035 | 433 |
  - O5_ls_run1: iterations (profit M, cov %, milp) [(12.77, 27.5, 'feasible'), (14.07, 27.1, 'feasible'), (13.43, 27.3, 'feasible')]; vub=False; ls_applied=True; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 29, 'Panamax_1200': 58, 'Panamax_2400': 44, 'Post_panamax': 25, 'Super_panamax': 9}
  - O5_ls_run2: iterations (profit M, cov %, milp) [(15.44, 32.0, 'feasible'), (12.36, 23.4, 'feasible'), (14.16, 27.4, 'feasible')]; vub=False; ls_applied=True; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 29, 'Panamax_1200': 63, 'Panamax_2400': 49, 'Post_panamax': 34, 'Super_panamax': 8}
  - O5_ls_run3: iterations (profit M, cov %, milp) [(12.88, 26.4, 'feasible'), (15.36, 30.0, 'feasible'), (14.25, 25.7, 'feasible')]; vub=False; ls_applied=True; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 29, 'Panamax_1200': 51, 'Panamax_2400': 45, 'Post_panamax': 36, 'Super_panamax': 8}

- profit M: mean 14.96 (min 14.07, max 15.44); coverage % mean 29.7; assertions ['360/360', '360/360', '360/360']

### O5_fin

| run | assertions | status | iter | profit M | margin % | cov % | served | svc | ves | LF | ledger | viol | MILP | bound M | reopt M | LS M | p90 max d | min slack d | s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---:|---:|
| O5_fin_run1 | 360/360 | complete | 0 | 15.54 | 17.0 | 28.7 | 79,456 | 30 | 169 | 0.725 | True | 0 | feasible | 16.8 | 0.00 | 2.03 | 34.7 | 0.004 | 515 |
| O5_fin_run2 | 360/360 | complete | 2 | 16.08 | 16.7 | 30.6 | 84,612 | 32 | 176 | 0.757 | True | 0 | feasible | 17.9 | 0.00 | 3.95 | 37.0 | 0.006 | 454 |
| O5_fin_run3 | 360/360 | complete | 0 | 16.85 | 16.3 | 32.9 | 91,073 | 31 | 184 | 0.725 | True | 0 | feasible | 17.6 | 0.00 | 0.84 | 34.5 | 0.047 | 530 |
  - O5_fin_run1: iterations (profit M, cov %, milp) [(15.54, 28.7, 'feasible'), (15.03, 25.9, 'feasible'), (13.2, 29.8, 'feasible')]; vub=True; ls_applied=True; cv_added=13; vessels {'Feeder_450': 2, 'Feeder_800': 29, 'Panamax_1200': 53, 'Panamax_2400': 51, 'Post_panamax': 26, 'Super_panamax': 8}
  - O5_fin_run2: iterations (profit M, cov %, milp) [(15.81, 30.8, 'feasible'), (14.99, 26.4, 'feasible'), (16.08, 30.6, 'feasible')]; vub=True; ls_applied=True; cv_added=13; vessels {'Feeder_450': 2, 'Feeder_800': 29, 'Panamax_1200': 59, 'Panamax_2400': 41, 'Post_panamax': 36, 'Super_panamax': 9}
  - O5_fin_run3: iterations (profit M, cov %, milp) [(16.85, 32.9, 'feasible'), (16.16, 27.0, 'feasible'), (13.42, 29.8, 'feasible')]; vub=True; ls_applied=True; cv_added=33; vessels {'Feeder_450': 2, 'Feeder_800': 29, 'Panamax_1200': 67, 'Panamax_2400': 29, 'Post_panamax': 49, 'Super_panamax': 8}

- profit M: mean 16.16 (min 15.54, max 16.85); coverage % mean 30.8; assertions ['360/360', '360/360', '360/360']
