
### G11_base

| run | assertions | status | iter | profit M | margin % | cov % | served | svc | ves | LF | ledger | viol | MILP | bound M | reopt M | LS M | p90 max d | min slack d | s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---:|---:|
| G11_base_run1 | 364/364 | complete | 2 | 13.75 | 17.5 | 25.1 | 69,418 | 28 | 147 | 0.648 | True | 0 | feasible | 42.3 | 3.02 | 0.00 | 40.1 | 0.011 | 381 |
| G11_base_run2 | 364/364 | complete | 1 | 12.80 | 18.3 | 22.5 | 62,155 | 19 | 117 | 0.706 | True | 0 | feasible | 42.6 | 2.47 | 0.00 | 48.8 | 0.028 | 418 |
| G11_base_run3 | 364/364 | complete | 1 | 13.75 | 15.2 | 28.2 | 78,016 | 31 | 165 | 0.679 | True | 0 | feasible | 41.8 | 3.95 | 0.00 | 41.6 | 0.026 | 384 |
  - G11_base_run1: iterations (profit M, cov %, milp) [(11.65, 19.5, 'feasible'), (13.09, 22.9, 'feasible'), (13.75, 25.1, 'feasible')]; vub=False; ls_applied=False; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 29, 'Panamax_1200': 62, 'Panamax_2400': 28, 'Post_panamax': 19, 'Super_panamax': 9}
  - G11_base_run2: iterations (profit M, cov %, milp) [(11.32, 23.3, 'feasible'), (12.8, 22.5, 'feasible'), (11.44, 21.4, 'feasible')]; vub=False; ls_applied=False; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 10, 'Panamax_1200': 56, 'Panamax_2400': 15, 'Post_panamax': 28, 'Super_panamax': 8}
  - G11_base_run3: iterations (profit M, cov %, milp) [(9.26, 19.6, 'feasible'), (13.75, 28.2, 'feasible'), (13.11, 25.2, 'feasible')]; vub=False; ls_applied=False; cv_added=None; vessels {'Feeder_450': 0, 'Feeder_800': 24, 'Panamax_1200': 66, 'Panamax_2400': 32, 'Post_panamax': 34, 'Super_panamax': 9}

- profit M: mean 13.43 (min 12.80, max 13.75); coverage % mean 25.3; assertions ['364/364', '364/364', '364/364']

### G11_fin

| run | assertions | status | iter | profit M | margin % | cov % | served | svc | ves | LF | ledger | viol | MILP | bound M | reopt M | LS M | p90 max d | min slack d | s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---:|---:|---:|---:|
| G11_fin_run1 | 368/368 | complete | 1 | 15.98 | 17.3 | 29.7 | 82,122 | 31 | 170 | 0.745 | True | 0 | feasible | 17.0 | 0.00 | 1.61 | 35.5 | 0.020 | 433 |
| G11_fin_run2 | 368/368 | complete | 2 | 15.56 | 15.8 | 31.4 | 86,732 | 34 | 189 | 0.726 | True | 0 | feasible | 17.9 | 0.00 | 2.12 | 35.3 | 0.033 | 457 |
| G11_fin_run3 | 368/368 | complete | 1 | 16.95 | 19.6 | 28.5 | 78,704 | 30 | 154 | 0.749 | True | 0 | feasible | 16.0 | 0.00 | 1.47 | 35.9 | 0.047 | 444 |
  - G11_fin_run1: iterations (profit M, cov %, milp) [(15.36, 30.5, 'feasible'), (15.98, 29.7, 'feasible'), (15.47, 29.6, 'feasible')]; vub=True; ls_applied=True; cv_added=12; vessels {'Feeder_450': 0, 'Feeder_800': 29, 'Panamax_1200': 66, 'Panamax_2400': 34, 'Post_panamax': 33, 'Super_panamax': 8}
  - G11_fin_run2: iterations (profit M, cov %, milp) [(12.94, 25.3, 'feasible'), (15.57, 30.2, 'feasible'), (15.56, 31.4, 'feasible')]; vub=True; ls_applied=True; cv_added=12; vessels {'Feeder_450': 2, 'Feeder_800': 29, 'Panamax_1200': 56, 'Panamax_2400': 70, 'Post_panamax': 23, 'Super_panamax': 9}
  - G11_fin_run3: iterations (profit M, cov %, milp) [(15.61, 31.6, 'feasible'), (16.95, 28.5, 'feasible'), (15.3, 30.9, 'feasible')]; vub=True; ls_applied=True; cv_added=27; vessels {'Feeder_450': 2, 'Feeder_800': 29, 'Panamax_1200': 48, 'Panamax_2400': 40, 'Post_panamax': 27, 'Super_panamax': 8}

- profit M: mean 16.16 (min 15.56, max 16.95); coverage % mean 29.8; assertions ['368/368', '368/368', '368/368']
