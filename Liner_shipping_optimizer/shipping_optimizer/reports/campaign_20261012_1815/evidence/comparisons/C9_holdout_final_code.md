
### C9_base

| seed | status | profit M | margin % | cov % | served TEU | svc | ves | LF | bound M | gap % | solver s | ledger | viol | reconciled | reopt M | LS M | notes |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---|
| 10 | feasible | 14.51 | 16.8 | 27.7 | 76,484 | 27 | 152 | 0.698 | 41.1 | 64.7 | 120 | True | 0 | True | 2.08 |  |  |
| 11 | feasible | 11.86 | 14.2 | 27.6 | 76,281 | 32 | 167 | 0.705 | 41.5 | 71.4 | 120 | True | 0 | True | 2.17 |  |  |
| 12 | feasible | 10.51 | 13.8 | 23.6 | 65,230 | 29 | 146 | 0.624 | 41.1 | 74.4 | 120 | True | 0 | True | 2.60 |  |  |
| 13 | feasible | 12.69 | 15.7 | 25.6 | 70,802 | 30 | 144 | 0.626 | 42.0 | 69.8 | 120 | True | 0 | True | 3.60 |  |  |
| 14 | feasible | 13.24 | 17.3 | 24.6 | 68,116 | 24 | 133 | 0.715 | 41.8 | 68.3 | 120 | True | 0 | True | 4.33 |  |  |
| 15 | feasible | 11.00 | 16.0 | 21.4 | 59,068 | 22 | 124 | 0.672 | 41.6 | 73.5 | 119 | True | 0 | True | 1.65 |  |  |
| 16 | feasible | 12.78 | 16.8 | 23.8 | 65,874 | 23 | 128 | 0.682 | 41.0 | 68.8 | 119 | True | 0 | True | 1.83 |  |  |
| 17 | feasible | 11.44 | 16.0 | 22.9 | 63,300 | 25 | 136 | 0.681 | 42.3 | 73.0 | 119 | True | 0 | True | 2.68 |  |  |
| 18 | feasible | 12.13 | 18.2 | 20.7 | 57,161 | 19 | 118 | 0.669 | 41.1 | 70.5 | 119 | True | 0 | True | 1.67 |  |  |
| 19 | feasible | 12.55 | 15.3 | 26.1 | 72,098 | 27 | 154 | 0.659 | 41.3 | 69.6 | 120 | True | 0 | True | 2.50 |  |  |

- profit M/wk: mean 12.271 | median 12.338 | min 10.508 | max 14.511 | sd 1.099 (n=10)
- coverage %: mean 24.396 | median 24.234 | min 20.677 | max 27.667 | sd 2.270 (n=10)
- served TEU: mean 67,441.400 | median 66,995.000 | min 57,161.200 | max 76,483.600 | sd 6,273.999 (n=10)
- services: mean 25.800 | median 26.000 | min 19.000 | max 32.000 | sd 3.763 (n=10) | vessels: mean 140.200 | median 140.000 | min 118.000 | max 167.000 | sd 14.386 (n=10)
- margin %: mean 16.012 | median 15.993 | min 13.779 | max 18.154 | sd 1.278 (n=10) | load factor: mean 0.673 | median 0.677 | min 0.624 | max 0.715 | sd 0.029 (n=10)
- statuses: {'feasible': 10} | ledger valid: 10 / 10 | violations total: 0 | reconciled: 10 / 10
- negative-profit plans: 0

### C9_ls

| seed | status | profit M | margin % | cov % | served TEU | svc | ves | LF | bound M | gap % | solver s | ledger | viol | reconciled | reopt M | LS M | notes |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---|
| 10 | feasible | 16.44 | 17.0 | 31.3 | 86,456 | 34 | 168 | 0.701 | 41.1 | 60.0 | 105 | True | 0 | True | 0.00 | 2.37 | LS 8 moves |
| 11 | feasible | 13.92 | 17.1 | 26.5 | 73,221 | 32 | 156 | 0.733 | 41.5 | 66.5 | 105 | True | 0 | True | 0.00 | 2.35 | LS 12 moves |
| 12 | feasible | 12.59 | 14.6 | 26.6 | 73,628 | 33 | 164 | 0.654 | 41.1 | 69.4 | 105 | True | 0 | True | 0.00 | 2.46 | LS 14 moves |
| 13 | feasible | 14.29 | 15.3 | 29.5 | 81,624 | 34 | 171 | 0.640 | 42.0 | 65.9 | 105 | True | 0 | True | 0.00 | 2.37 | LS 6 moves |
| 14 | feasible | 15.29 | 16.8 | 28.4 | 78,450 | 30 | 170 | 0.721 | 41.8 | 63.4 | 105 | True | 0 | True | 0.00 | 2.59 | LS 15 moves |
| 15 | feasible | 13.67 | 14.2 | 30.0 | 83,066 | 33 | 185 | 0.677 | 41.6 | 67.1 | 104 | True | 0 | True | 0.00 | 4.36 | LS 16 moves |
| 16 | feasible | 13.32 | 15.4 | 26.9 | 74,468 | 28 | 163 | 0.687 | 41.0 | 67.5 | 104 | True | 0 | True | 0.00 | 0.81 | LS 6 moves |
| 17 | feasible | 14.66 | 17.3 | 26.5 | 73,392 | 27 | 152 | 0.661 | 42.3 | 65.3 | 104 | True | 0 | True | 0.00 | 1.70 | LS 8 moves |
| 18 | feasible | 14.57 | 17.9 | 26.1 | 72,065 | 29 | 147 | 0.727 | 41.1 | 64.5 | 104 | True | 0 | True | 0.00 | 2.92 | LS 12 moves |
| 19 | feasible | 14.08 | 16.2 | 27.4 | 75,819 | 30 | 154 | 0.651 | 41.3 | 65.9 | 105 | True | 0 | True | 0.00 | 3.24 | LS 13 moves |

- profit M/wk: mean 14.282 | median 14.187 | min 12.587 | max 16.437 | sd 1.011 (n=10)
- coverage %: mean 27.933 | median 27.182 | min 26.068 | max 31.274 | sd 1.697 (n=10)
- served TEU: mean 77,218.920 | median 75,143.600 | min 72,065.200 | max 86,456.000 | sd 4,690.894 (n=10)
- services: mean 31.000 | median 31.000 | min 27.000 | max 34.000 | sd 2.408 (n=10) | vessels: mean 163.000 | median 163.500 | min 147.000 | max 185.000 | sd 10.630 (n=10)
- margin %: mean 16.168 | median 16.515 | min 14.209 | max 17.860 | sd 1.175 (n=10) | load factor: mean 0.685 | median 0.682 | min 0.640 | max 0.733 | sd 0.032 (n=10)
- statuses: {'feasible': 10} | ledger valid: 10 / 10 | violations total: 0 | reconciled: 10 / 10
- negative-profit plans: 0

### C9_fin

| seed | status | profit M | margin % | cov % | served TEU | svc | ves | LF | bound M | gap % | solver s | ledger | viol | reconciled | reopt M | LS M | notes |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---|
| 10 | feasible | 15.49 | 17.5 | 28.7 | 79,242 | 28 | 160 | 0.731 | 16.2 | 4.6 | 106 | True | 0 | True | 0.00 | 1.87 | LS 9 moves |
| 11 | feasible | 15.32 | 17.1 | 29.3 | 81,104 | 37 | 171 | 0.732 | 15.2 | -0.9 | 106 | True | 0 | True | 0.00 | 1.89 | LS 9 moves |
| 12 | feasible | 11.36 | 13.0 | 27.9 | 77,044 | 29 | 173 | 0.679 | 16.3 | 30.4 | 106 | True | 0 | True | 0.00 | 0.17 | LS 2 moves |
| 13 | feasible | 14.59 | 16.4 | 28.5 | 78,912 | 29 | 168 | 0.717 | 16.2 | 10.0 | 106 | True | 0 | True | 0.00 | 1.05 | LS 9 moves |
| 14 | feasible | 14.19 | 15.7 | 29.3 | 80,930 | 33 | 176 | 0.740 | 15.3 | 7.4 | 106 | True | 0 | True | 0.00 | 0.41 | LS 5 moves |
| 15 | feasible | 16.13 | 17.2 | 30.5 | 84,444 | 35 | 168 | 0.702 | 16.3 | 1.1 | 105 | True | 0 | True | 0.00 | 2.58 | LS 12 moves |
| 16 | feasible | 14.92 | 16.6 | 28.6 | 78,932 | 29 | 163 | 0.748 | 15.4 | 3.4 | 106 | True | 0 | True | 0.00 | 1.33 | LS 7 moves |
| 17 | feasible | 15.73 | 20.0 | 25.6 | 70,773 | 25 | 142 | 0.774 | 15.7 | -0.4 | 105 | True | 0 | True | 0.40 | 0.32 | LS 3 moves |
| 18 | feasible | 15.61 | 16.4 | 30.5 | 84,212 | 33 | 179 | 0.721 | 17.5 | 10.6 | 106 | True | 0 | True | 0.00 | 1.70 | LS 8 moves |
| 19 | feasible | 15.56 | 17.6 | 27.9 | 77,148 | 29 | 163 | 0.710 | 17.2 | 9.8 | 106 | True | 0 | True | 0.00 | 0.94 | LS 5 moves |

- profit M/wk: mean 14.890 | median 15.405 | min 11.359 | max 16.132 | sd 1.296 (n=10)
- coverage %: mean 28.676 | median 28.608 | min 25.601 | max 30.546 | sd 1.350 (n=10)
- served TEU: mean 79,274.080 | median 79,087.000 | min 70,772.800 | max 84,444.000 | sd 3,731.169 (n=10)
- services: mean 30.700 | median 29.000 | min 25.000 | max 37.000 | sd 3.466 (n=10) | vessels: mean 166.300 | median 168.000 | min 142.000 | max 179.000 | sd 9.900 (n=10)
- margin %: mean 16.726 | median 16.807 | min 12.952 | max 19.973 | sd 1.663 (n=10) | load factor: mean 0.725 | median 0.726 | min 0.679 | max 0.774 | sd 0.025 (n=10)
- statuses: {'feasible': 10} | ledger valid: 10 / 10 | violations total: 0 | reconciled: 10 / 10
- negative-profit plans: 0

### C9_lv

| seed | status | profit M | margin % | cov % | served TEU | svc | ves | LF | bound M | gap % | solver s | ledger | viol | reconciled | reopt M | LS M | notes |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---|
| 10 | feasible | 15.35 | 17.2 | 28.7 | 79,472 | 29 | 165 | 0.729 | 16.2 | 5.5 | 105 | True | 0 | True | 0.00 | 1.74 | LS 7 moves |
| 11 | feasible | 15.57 | 16.6 | 31.0 | 85,832 | 41 | 187 | 0.745 | 15.2 | -2.6 | 106 | True | 0 | True | 0.00 | 2.14 | LS 11 moves |
| 12 | feasible | 12.84 | 13.6 | 30.0 | 82,950 | 37 | 187 | 0.668 | 16.3 | 21.4 | 106 | True | 0 | True | 0.00 | 1.65 | LS 13 moves |
| 13 | feasible | 14.65 | 17.0 | 28.2 | 77,888 | 31 | 166 | 0.718 | 16.2 | 9.6 | 106 | True | 0 | True | 0.00 | 1.11 | LS 12 moves |
| 14 | feasible | 14.18 | 15.9 | 28.7 | 79,472 | 32 | 173 | 0.739 | 15.3 | 7.5 | 106 | True | 0 | True | 0.00 | 0.40 | LS 4 moves |
| 15 | feasible | 16.18 | 17.0 | 31.2 | 86,256 | 36 | 174 | 0.703 | 16.3 | 0.8 | 105 | True | 0 | True | 0.00 | 2.63 | LS 12 moves |
| 16 | feasible | 15.41 | 16.5 | 30.2 | 83,406 | 33 | 173 | 0.757 | 15.4 | 0.2 | 106 | True | 0 | True | 0.00 | 1.82 | LS 14 moves |
| 17 | feasible | 15.73 | 19.9 | 25.7 | 71,131 | 25 | 142 | 0.775 | 15.7 | -0.3 | 105 | True | 0 | True | 0.31 | 0.33 | LS 4 moves |
| 18 | feasible | 15.79 | 16.4 | 31.2 | 86,338 | 36 | 188 | 0.724 | 17.5 | 9.5 | 106 | True | 0 | True | 0.00 | 1.88 | LS 12 moves |
| 19 | feasible | 16.20 | 16.5 | 31.5 | 87,028 | 35 | 187 | 0.716 | 17.2 | 6.1 | 106 | True | 0 | True | 0.00 | 1.58 | LS 11 moves |

- profit M/wk: mean 15.188 | median 15.488 | min 12.838 | max 16.197 | sd 0.985 (n=10)
- coverage %: mean 29.654 | median 30.088 | min 25.730 | max 31.481 | sd 1.726 (n=10)
- served TEU: mean 81,977.280 | median 83,178.000 | min 71,130.800 | max 87,028.000 | sd 4,770.750 (n=10)
- services: mean 33.500 | median 34.000 | min 25.000 | max 41.000 | sd 4.295 (n=10) | vessels: mean 174.200 | median 173.500 | min 142.000 | max 188.000 | sd 13.688 (n=10)
- margin %: mean 16.669 | median 16.540 | min 13.637 | max 19.947 | sd 1.450 (n=10) | load factor: mean 0.728 | median 0.727 | min 0.668 | max 0.775 | sd 0.028 (n=10)
- statuses: {'feasible': 10} | ledger valid: 10 / 10 | violations total: 0 | reconciled: 10 / 10
- negative-profit plans: 0

### paired: C9_ls - C9_base

| seed | d profit M | d coverage pp | d served TEU | d services | d vessels | profit A M | profit B M |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | +1.93 | +3.6 | +9,972 | +7 | +16 | 14.51 | 16.44 |
| 11 | +2.06 | -1.1 | -3,060 | +0 | -11 | 11.86 | 13.92 |
| 12 | +2.08 | +3.0 | +8,398 | +4 | +18 | 10.51 | 12.59 |
| 13 | +1.60 | +3.9 | +10,822 | +4 | +27 | 12.69 | 14.29 |
| 14 | +2.05 | +3.7 | +10,334 | +6 | +37 | 13.24 | 15.29 |
| 15 | +2.67 | +8.7 | +23,998 | +11 | +61 | 11.00 | 13.67 |
| 16 | +0.54 | +3.1 | +8,594 | +5 | +35 | 12.78 | 13.32 |
| 17 | +3.22 | +3.7 | +10,092 | +2 | +16 | 11.44 | 14.66 |
| 18 | +2.45 | +5.4 | +14,904 | +10 | +29 | 12.13 | 14.57 |
| 19 | +1.54 | +1.3 | +3,721 | +3 | +0 | 12.55 | 14.08 |

- d profit M: mean 2.012 | median 2.052 | min 0.537 | max 3.218 | sd 0.683 (n=10); positive in 10/10 seeds, negative in 0
- d coverage pp: mean 3.537 | median 3.629 | min -1.107 | max 8.681 | sd 2.385 (n=10); improved in 9/10, regressed in 1
- d served TEU: mean 9,777.520 | median 10,032.200 | min -3,060.400 | max 23,998.000 | sd 6,594.204 (n=10)
- paired t = 8.84 (n=10, se 0.23 M)

### paired: C9_fin - C9_base

| seed | d profit M | d coverage pp | d served TEU | d services | d vessels | profit A M | profit B M |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | +0.98 | +1.0 | +2,758 | +1 | +8 | 14.51 | 15.49 |
| 11 | +3.46 | +1.7 | +4,823 | +5 | +4 | 11.86 | 15.32 |
| 12 | +0.85 | +4.3 | +11,814 | +0 | +27 | 10.51 | 11.36 |
| 13 | +1.90 | +2.9 | +8,110 | -1 | +24 | 12.69 | 14.59 |
| 14 | +0.95 | +4.6 | +12,814 | +9 | +43 | 13.24 | 14.19 |
| 15 | +5.13 | +9.2 | +25,376 | +13 | +44 | 11.00 | 16.13 |
| 16 | +2.14 | +4.7 | +13,058 | +6 | +35 | 12.78 | 14.92 |
| 17 | +4.29 | +2.7 | +7,473 | +0 | +6 | 11.44 | 15.73 |
| 18 | +3.48 | +9.8 | +27,051 | +14 | +61 | 12.13 | 15.61 |
| 19 | +3.01 | +1.8 | +5,050 | +2 | +9 | 12.55 | 15.56 |

- d profit M: mean 2.619 | median 2.573 | min 0.851 | max 5.134 | sd 1.416 (n=10); positive in 10/10 seeds, negative in 0
- d coverage pp: mean 4.280 | median 3.604 | min 0.998 | max 9.785 | sd 2.866 (n=10); improved in 10/10, regressed in 0
- d served TEU: mean 11,832.680 | median 9,962.000 | min 2,758.400 | max 27,050.800 | sd 7,923.573 (n=10)
- paired t = 5.55 (n=10, se 0.47 M)

### paired: C9_lv - C9_base

| seed | d profit M | d coverage pp | d served TEU | d services | d vessels | profit A M | profit B M |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | +0.84 | +1.1 | +2,988 | +2 | +13 | 14.51 | 15.35 |
| 11 | +3.71 | +3.5 | +9,551 | +9 | +20 | 11.86 | 15.57 |
| 12 | +2.33 | +6.4 | +17,720 | +8 | +41 | 10.51 | 12.84 |
| 13 | +1.96 | +2.6 | +7,086 | +1 | +22 | 12.69 | 14.65 |
| 14 | +0.94 | +4.1 | +11,356 | +8 | +40 | 13.24 | 14.18 |
| 15 | +5.18 | +9.8 | +27,188 | +14 | +50 | 11.00 | 16.18 |
| 16 | +2.63 | +6.3 | +17,532 | +10 | +45 | 12.78 | 15.41 |
| 17 | +4.28 | +2.8 | +7,831 | +0 | +6 | 11.44 | 15.73 |
| 18 | +3.66 | +10.6 | +29,177 | +17 | +70 | 12.13 | 15.79 |
| 19 | +3.65 | +5.4 | +14,930 | +8 | +33 | 12.55 | 16.20 |

- d profit M: mean 2.918 | median 3.137 | min 0.841 | max 5.180 | sd 1.352 (n=10); positive in 10/10 seeds, negative in 0
- d coverage pp: mean 5.258 | median 4.754 | min 1.081 | max 10.554 | sd 2.944 (n=10); improved in 10/10, regressed in 0
- d served TEU: mean 14,535.880 | median 13,143.000 | min 2,988.400 | max 29,176.800 | sd 8,139.221 (n=10)
- paired t = 6.47 (n=10, se 0.45 M)
