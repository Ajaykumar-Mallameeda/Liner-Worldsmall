
### C9b_base

| seed | status | profit M | margin % | cov % | served TEU | svc | ves | LF | bound M | gap % | solver s | ledger | viol | reconciled | reopt M | LS M | notes |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---|
| 10 | feasible | 14.98 | 16.9 | 28.3 | 78,192 | 31 | 159 | 0.693 | 41.1 | 63.5 | 119 | True | 0 | True | 2.58 |  |  |
| 11 | feasible | 11.86 | 14.2 | 27.6 | 76,281 | 32 | 167 | 0.705 | 41.5 | 71.4 | 120 | True | 0 | True | 2.17 |  |  |
| 12 | feasible | 10.51 | 13.8 | 23.6 | 65,230 | 29 | 146 | 0.624 | 41.1 | 74.4 | 120 | True | 0 | True | 2.60 |  |  |
| 13 | feasible | 12.69 | 15.7 | 25.6 | 70,802 | 30 | 144 | 0.626 | 42.0 | 69.8 | 119 | True | 0 | True | 3.60 |  |  |
| 14 | feasible | 13.24 | 17.3 | 24.6 | 68,116 | 24 | 133 | 0.715 | 41.8 | 68.3 | 119 | True | 0 | True | 4.33 |  |  |
| 15 | feasible | 11.11 | 16.2 | 21.2 | 58,694 | 22 | 122 | 0.668 | 41.6 | 73.3 | 120 | True | 0 | True | 1.66 |  |  |
| 16 | feasible | 12.75 | 16.9 | 23.7 | 65,636 | 22 | 127 | 0.686 | 41.0 | 68.9 | 119 | True | 0 | True | 1.78 |  |  |
| 17 | feasible | 11.44 | 16.0 | 22.9 | 63,300 | 25 | 136 | 0.681 | 42.3 | 73.0 | 119 | True | 0 | True | 2.68 |  |  |
| 18 | feasible | 12.51 | 18.2 | 21.7 | 59,863 | 22 | 126 | 0.681 | 41.1 | 69.6 | 118 | True | 0 | True | 1.85 |  |  |
| 19 | feasible | 12.55 | 15.3 | 26.1 | 72,098 | 27 | 154 | 0.659 | 41.3 | 69.6 | 120 | True | 0 | True | 2.50 |  |  |

- profit M/wk: mean 12.364 | median 12.529 | min 10.508 | max 14.981 | sd 1.185 (n=10)
- coverage %: mean 24.533 | median 24.191 | min 21.232 | max 28.285 | sd 2.244 (n=10)
- served TEU: mean 67,821.200 | median 66,876.000 | min 58,694.000 | max 78,191.600 | sd 6,204.402 (n=10)
- services: mean 26.400 | median 26.000 | min 22.000 | max 32.000 | sd 3.720 (n=10) | vessels: mean 141.400 | median 140.000 | min 122.000 | max 167.000 | sd 14.396 (n=10)
- margin %: mean 16.058 | median 16.125 | min 13.779 | max 18.165 | sd 1.293 (n=10) | load factor: mean 0.674 | median 0.681 | min 0.624 | max 0.715 | sd 0.029 (n=10)
- statuses: {'feasible': 10} | ledger valid: 10 / 10 | violations total: 0 | reconciled: 10 / 10
- negative-profit plans: 0

### C9b_ls

| seed | status | profit M | margin % | cov % | served TEU | svc | ves | LF | bound M | gap % | solver s | ledger | viol | reconciled | reopt M | LS M | notes |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---|
| 10 | feasible | 16.44 | 17.0 | 31.3 | 86,456 | 34 | 168 | 0.701 | 41.1 | 60.0 | 104 | True | 0 | True | 0.00 | 2.37 | LS 8 moves |
| 11 | feasible | 13.92 | 17.1 | 26.5 | 73,221 | 32 | 156 | 0.733 | 41.5 | 66.5 | 105 | True | 0 | True | 0.00 | 2.35 | LS 12 moves |
| 12 | feasible | 12.59 | 14.6 | 26.6 | 73,628 | 33 | 164 | 0.654 | 41.1 | 69.4 | 105 | True | 0 | True | 0.00 | 2.46 | LS 14 moves |
| 13 | feasible | 14.29 | 15.3 | 29.5 | 81,624 | 34 | 171 | 0.640 | 42.0 | 65.9 | 104 | True | 0 | True | 0.00 | 2.37 | LS 6 moves |
| 14 | feasible | 15.29 | 16.8 | 28.4 | 78,450 | 30 | 170 | 0.721 | 41.8 | 63.4 | 104 | True | 0 | True | 0.00 | 2.59 | LS 15 moves |
| 15 | feasible | 13.67 | 14.2 | 30.0 | 83,066 | 33 | 185 | 0.677 | 41.6 | 67.1 | 105 | True | 0 | True | 0.00 | 4.36 | LS 16 moves |
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

### C9b_c1ls

| seed | status | profit M | margin % | cov % | served TEU | svc | ves | LF | bound M | gap % | solver s | ledger | viol | reconciled | reopt M | LS M | notes |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---|
| 10 | feasible | 15.96 | 16.6 | 31.2 | 86,302 | 35 | 167 | 0.675 | 17.4 | 8.5 | 106 | True | 0 | True | 0.00 | 1.73 | LS 6 moves |
| 11 | feasible | 14.17 | 15.5 | 28.8 | 79,678 | 33 | 166 | 0.708 | 15.4 | 8.1 | 106 | True | 0 | True | 0.00 | 3.67 | LS 16 moves |
| 12 | feasible | 14.60 | 17.5 | 26.8 | 74,086 | 33 | 149 | 0.719 | 16.0 | 8.9 | 106 | True | 0 | True | 0.00 | 2.32 | LS 8 moves |
| 13 | feasible | 15.40 | 16.6 | 29.0 | 80,239 | 30 | 169 | 0.696 | 15.5 | 0.7 | 106 | True | 0 | True | 0.00 | 1.57 | LS 9 moves |
| 14 | feasible | 13.70 | 18.1 | 23.6 | 65,362 | 22 | 134 | 0.705 | 15.2 | 10.1 | 106 | True | 0 | True | 0.00 | 1.59 | LS 6 moves |
| 15 | feasible | 14.29 | 15.4 | 28.7 | 79,321 | 30 | 172 | 0.622 | 17.1 | 16.5 | 106 | True | 0 | True | 0.00 | 1.02 | LS 3 moves |
| 16 | feasible | 15.23 | 15.7 | 30.5 | 84,272 | 33 | 177 | 0.693 | 15.7 | 3.1 | 106 | True | 0 | True | 0.00 | 1.20 | LS 6 moves |
| 17 | feasible | 14.92 | 18.0 | 26.1 | 72,218 | 27 | 143 | 0.699 | 15.5 | 3.6 | 106 | True | 0 | True | 0.00 | 1.34 | LS 6 moves |
| 18 | feasible | 14.29 | 16.1 | 27.8 | 76,875 | 29 | 170 | 0.664 | 16.8 | 14.9 | 106 | True | 0 | True | 0.00 | 0.62 | LS 3 moves |
| 19 | feasible | 14.19 | 14.9 | 30.2 | 83,619 | 33 | 180 | 0.691 | 16.4 | 13.7 | 106 | True | 0 | True | 0.00 | 1.20 | LS 6 moves |

- profit M/wk: mean 14.675 | median 14.448 | min 13.695 | max 15.964 | sd 0.657 (n=10)
- coverage %: mean 28.287 | median 28.758 | min 23.644 | max 31.218 | sd 2.167 (n=10)
- served TEU: mean 78,197.240 | median 79,499.600 | min 65,362.000 | max 86,302.000 | sd 5,989.626 (n=10)
- services: mean 30.500 | median 31.500 | min 22.000 | max 35.000 | sd 3.640 (n=10) | vessels: mean 162.700 | median 168.000 | min 134.000 | max 180.000 | sd 14.533 (n=10)
- margin %: mean 16.438 | median 16.337 | min 14.933 | max 18.097 | sd 1.065 (n=10) | load factor: mean 0.687 | median 0.694 | min 0.622 | max 0.719 | sd 0.026 (n=10)
- statuses: {'feasible': 10} | ledger valid: 10 / 10 | violations total: 0 | reconciled: 10 / 10
- negative-profit plans: 0

### C9b_fin

| seed | status | profit M | margin % | cov % | served TEU | svc | ves | LF | bound M | gap % | solver s | ledger | viol | reconciled | reopt M | LS M | notes |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---|
| 10 | feasible | 16.17 | 17.6 | 29.6 | 81,949 | 30 | 169 | 0.722 | 16.2 | 0.4 | 105 | True | 0 | True | 0.00 | 2.80 | LS 7 moves |
| 11 | feasible | 15.50 | 16.4 | 31.1 | 85,906 | 38 | 182 | 0.757 | 15.2 | -2.1 | 106 | True | 0 | True | 0.00 | 2.25 | LS 11 moves |
| 12 | feasible | 13.95 | 14.0 | 31.2 | 86,361 | 36 | 189 | 0.663 | 16.3 | 14.6 | 106 | True | 0 | True | 0.00 | 1.76 | LS 11 moves |
| 13 | feasible | 14.59 | 16.4 | 28.5 | 78,912 | 29 | 168 | 0.717 | 16.2 | 10.0 | 107 | True | 0 | True | 0.00 | 1.05 | LS 9 moves |
| 14 | feasible | 14.19 | 15.7 | 29.3 | 80,930 | 33 | 176 | 0.740 | 15.3 | 7.4 | 106 | True | 0 | True | 0.00 | 0.41 | LS 5 moves |
| 15 | feasible | 16.13 | 17.2 | 30.5 | 84,444 | 35 | 168 | 0.702 | 16.3 | 1.1 | 105 | True | 0 | True | 0.00 | 2.58 | LS 12 moves |
| 16 | feasible | 14.92 | 16.6 | 28.6 | 78,932 | 29 | 163 | 0.748 | 15.4 | 3.4 | 106 | True | 0 | True | 0.00 | 1.33 | LS 7 moves |
| 17 | feasible | 15.73 | 20.0 | 25.6 | 70,773 | 25 | 142 | 0.774 | 15.7 | -0.4 | 106 | True | 0 | True | 0.40 | 0.32 | LS 3 moves |
| 18 | feasible | 15.61 | 16.4 | 30.5 | 84,212 | 33 | 179 | 0.721 | 17.5 | 10.6 | 106 | True | 0 | True | 0.00 | 1.70 | LS 8 moves |
| 19 | feasible | 15.56 | 17.6 | 27.9 | 77,148 | 29 | 163 | 0.710 | 17.2 | 9.8 | 106 | True | 0 | True | 0.00 | 0.94 | LS 5 moves |

- profit M/wk: mean 15.234 | median 15.528 | min 13.945 | max 16.171 | sd 0.742 (n=10)
- coverage %: mean 29.285 | median 29.459 | min 25.601 | max 31.240 | sd 1.634 (n=10)
- served TEU: mean 80,956.720 | median 81,439.600 | min 70,772.800 | max 86,361.200 | sd 4,516.043 (n=10)
- services: mean 31.700 | median 31.500 | min 25.000 | max 38.000 | sd 3.770 (n=10) | vessels: mean 169.900 | median 168.500 | min 142.000 | max 189.000 | sd 12.300 (n=10)
- margin %: mean 16.781 | median 16.492 | min 14.028 | max 19.973 | sd 1.442 (n=10) | load factor: mean 0.725 | median 0.722 | min 0.663 | max 0.774 | sd 0.030 (n=10)
- statuses: {'feasible': 10} | ledger valid: 10 / 10 | violations total: 0 | reconciled: 10 / 10
- negative-profit plans: 0

### paired: C9b_ls - C9b_base

| seed | d profit M | d coverage pp | d served TEU | d services | d vessels | profit A M | profit B M |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | +1.46 | +3.0 | +8,264 | +3 | +9 | 14.98 | 16.44 |
| 11 | +2.06 | -1.1 | -3,060 | +0 | -11 | 11.86 | 13.92 |
| 12 | +2.08 | +3.0 | +8,398 | +4 | +18 | 10.51 | 12.59 |
| 13 | +1.60 | +3.9 | +10,822 | +4 | +27 | 12.69 | 14.29 |
| 14 | +2.05 | +3.7 | +10,334 | +6 | +37 | 13.24 | 15.29 |
| 15 | +2.56 | +8.8 | +24,372 | +11 | +63 | 11.11 | 13.67 |
| 16 | +0.56 | +3.2 | +8,832 | +6 | +36 | 12.75 | 13.32 |
| 17 | +3.22 | +3.7 | +10,092 | +2 | +16 | 11.44 | 14.66 |
| 18 | +2.06 | +4.4 | +12,202 | +7 | +21 | 12.51 | 14.57 |
| 19 | +1.54 | +1.3 | +3,721 | +3 | +0 | 12.55 | 14.08 |

- d profit M: mean 1.918 | median 2.052 | min 0.564 | max 3.218 | sd 0.669 (n=10); positive in 10/10 seeds, negative in 0
- d coverage pp: mean 3.399 | median 3.423 | min -1.107 | max 8.816 | sd 2.360 (n=10); improved in 9/10, regressed in 1
- d served TEU: mean 9,397.720 | median 9,462.000 | min -3,060.400 | max 24,372.000 | sd 6,523.126 (n=10)
- paired t = 8.60 (n=10, se 0.22 M)

### paired: C9b_c1ls - C9b_base

| seed | d profit M | d coverage pp | d served TEU | d services | d vessels | profit A M | profit B M |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | +0.98 | +2.9 | +8,110 | +4 | +8 | 14.98 | 15.96 |
| 11 | +2.31 | +1.2 | +3,397 | +1 | -1 | 11.86 | 14.17 |
| 12 | +4.10 | +3.2 | +8,856 | +4 | +3 | 10.51 | 14.60 |
| 13 | +2.71 | +3.4 | +9,437 | +0 | +25 | 12.69 | 15.40 |
| 14 | +0.46 | -1.0 | -2,754 | -2 | +1 | 13.24 | 13.70 |
| 15 | +3.18 | +7.5 | +20,627 | +8 | +50 | 11.11 | 14.29 |
| 16 | +2.48 | +6.7 | +18,636 | +11 | +50 | 12.75 | 15.23 |
| 17 | +3.47 | +3.2 | +8,918 | +2 | +7 | 11.44 | 14.92 |
| 18 | +1.78 | +6.2 | +17,012 | +7 | +44 | 12.51 | 14.29 |
| 19 | +1.64 | +4.2 | +11,521 | +6 | +26 | 12.55 | 14.19 |

- d profit M: mean 2.311 | median 2.395 | min 0.456 | max 4.097 | sd 1.069 (n=10); positive in 10/10 seeds, negative in 0
- d coverage pp: mean 3.753 | median 3.320 | min -0.996 | max 7.462 | sd 2.427 (n=10); improved in 9/10, regressed in 1
- d served TEU: mean 10,376.040 | median 9,177.400 | min -2,754.000 | max 20,627.200 | sd 6,709.844 (n=10)
- paired t = 6.49 (n=10, se 0.36 M)

### paired: C9b_fin - C9b_base

| seed | d profit M | d coverage pp | d served TEU | d services | d vessels | profit A M | profit B M |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | +1.19 | +1.4 | +3,758 | -1 | +10 | 14.98 | 16.17 |
| 11 | +3.64 | +3.5 | +9,625 | +6 | +15 | 11.86 | 15.50 |
| 12 | +3.44 | +7.6 | +21,131 | +7 | +43 | 10.51 | 13.95 |
| 13 | +1.90 | +2.9 | +8,110 | -1 | +24 | 12.69 | 14.59 |
| 14 | +0.95 | +4.6 | +12,814 | +9 | +43 | 13.24 | 14.19 |
| 15 | +5.02 | +9.3 | +25,750 | +13 | +46 | 11.11 | 16.13 |
| 16 | +2.17 | +4.8 | +13,296 | +7 | +36 | 12.75 | 14.92 |
| 17 | +4.29 | +2.7 | +7,473 | +0 | +6 | 11.44 | 15.73 |
| 18 | +3.10 | +8.8 | +24,349 | +11 | +53 | 12.51 | 15.61 |
| 19 | +3.01 | +1.8 | +5,050 | +2 | +9 | 12.55 | 15.56 |

- d profit M: mean 2.870 | median 3.052 | min 0.954 | max 5.023 | sd 1.248 (n=10); positive in 10/10 seeds, negative in 0
- d coverage pp: mean 4.752 | median 4.058 | min 1.359 | max 9.315 | sd 2.736 (n=10); improved in 10/10, regressed in 0
- d served TEU: mean 13,135.520 | median 11,219.400 | min 3,757.600 | max 25,750.000 | sd 7,562.349 (n=10)
- paired t = 6.90 (n=10, se 0.42 M)
