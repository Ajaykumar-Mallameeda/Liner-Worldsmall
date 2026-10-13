
### P2_orch_base

| run | assertions | status | iter | profit M | margin % | cov % | served | svc | ves | LF | ledger | viol | MILP | bound M | reopt M | LS M | p90 max d | min slack d | s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---:|---:|
| P2_orch_base_run1 | 362/362 | complete | 0 | 14.11 | 15.8 | 28.3 | 78,328 | 31 | 163 | 0.687 | True | 0 | feasible | 40.0 | 3.42 | 0.00 | 44.4 | 0.048 | 379 |
| P2_orch_base_run2 | 362/362 | complete | 1 | 12.31 | 16.3 | 24.0 | 66,322 | 27 | 136 | 0.677 | True | 0 | feasible | 42.3 | 2.16 | 0.00 | 40.6 | 0.038 | 378 |
| P2_orch_base_run3 | 362/362 | complete | 0 | 13.91 | 17.3 | 24.9 | 68,756 | 29 | 139 | 0.631 | True | 0 | feasible | 41.3 | 1.83 | 0.00 | 40.2 | 0.022 | 380 |
  - P2_orch_base_run1: iterations (profit M, cov %, milp) [(14.11, 28.3, 'feasible'), (12.22, 29.6, 'feasible'), (11.33, 21.5, 'feasible')]; vub=False; ls_applied=False; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 29, 'Panamax_1200': 50, 'Panamax_2400': 41, 'Post_panamax': 33, 'Super_panamax': 10}
  - P2_orch_base_run2: iterations (profit M, cov %, milp) [(11.61, 24.1, 'feasible'), (12.31, 24.0, 'feasible'), (11.79, 24.4, 'feasible')]; vub=False; ls_applied=False; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 29, 'Panamax_1200': 44, 'Panamax_2400': 26, 'Post_panamax': 27, 'Super_panamax': 10}
  - P2_orch_base_run3: iterations (profit M, cov %, milp) [(13.91, 24.9, 'feasible'), (11.94, 21.4, 'feasible'), (13.26, 23.8, 'feasible')]; vub=False; ls_applied=False; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 26, 'Panamax_1200': 26, 'Panamax_2400': 46, 'Post_panamax': 31, 'Super_panamax': 10}

- profit M: mean 13.44 (min 12.31, max 14.11); coverage % mean 25.7; assertions ['362/362', '362/362', '362/362']

### P2_orch_c1

| run | assertions | status | iter | profit M | margin % | cov % | served | svc | ves | LF | ledger | viol | MILP | bound M | reopt M | LS M | p90 max d | min slack d | s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---:|---:|
| P2_orch_c1_run1 | 362/362 | complete | 1 | 14.39 | 16.2 | 28.1 | 77,758 | 28 | 161 | 0.685 | True | 0 | feasible | 16.8 | 2.44 | 0.00 | 45.2 | 0.044 | 508 |
| P2_orch_c1_run2 | 362/362 | complete | 1 | 14.71 | 16.7 | 27.8 | 76,772 | 28 | 160 | 0.652 | True | 0 | feasible | 17.0 | 2.94 | 0.00 | 42.8 | 0.022 | 496 |
| P2_orch_c1_run3 | 362/362 | complete | 2 | 14.43 | 16.0 | 29.0 | 80,050 | 31 | 163 | 0.688 | True | 0 | feasible | 16.0 | 4.23 | 0.00 | 40.6 | 0.028 | 508 |
  - P2_orch_c1_run1: iterations (profit M, cov %, milp) [(13.4, 26.9, 'feasible'), (14.39, 28.1, 'feasible'), (13.53, 25.0, 'feasible')]; vub=True; ls_applied=False; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 28, 'Panamax_1200': 68, 'Panamax_2400': 22, 'Post_panamax': 34, 'Super_panamax': 9}
  - P2_orch_c1_run2: iterations (profit M, cov %, milp) [(13.02, 22.5, 'feasible'), (14.71, 27.8, 'feasible'), (13.29, 24.4, 'feasible')]; vub=True; ls_applied=False; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 28, 'Panamax_1200': 65, 'Panamax_2400': 23, 'Post_panamax': 34, 'Super_panamax': 10}
  - P2_orch_c1_run3: iterations (profit M, cov %, milp) [(10.75, 22.5, 'feasible'), (13.01, 26.2, 'feasible'), (14.43, 29.0, 'feasible')]; vub=True; ls_applied=False; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 28, 'Panamax_1200': 56, 'Panamax_2400': 34, 'Post_panamax': 37, 'Super_panamax': 8}

- profit M: mean 14.51 (min 14.39, max 14.71); coverage % mean 28.3; assertions ['362/362', '362/362', '362/362']
