
### P3_base

| seed | status | profit M | margin % | cov % | served TEU | svc | ves | LF | bound M | gap % | solver s | ledger | viol | reconciled | reopt M | LS M | notes |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---|
| 0 | feasible | 13.20 | 16.3 | 26.6 | 73,570 | 30 | 143 | 0.647 | 41.3 | 68.0 | 120 | True | 0 | True | 2.54 |  |  |
| 1 | feasible | 11.57 | 15.9 | 23.4 | 64,636 | 26 | 140 | 0.678 | 41.9 | 72.4 | 119 | True | 0 | True | 3.12 |  |  |
| 2 | feasible | 12.10 | 17.0 | 22.8 | 62,960 | 21 | 112 | 0.601 | 41.4 | 70.8 | 119 | True | 0 | True | 1.46 |  |  |
| 3 | feasible | 9.37 | 12.8 | 22.1 | 60,975 | 28 | 138 | 0.566 | 39.5 | 76.3 | 120 | True | 0 | True | 2.44 |  |  |
| 4 | feasible | 10.57 | 15.0 | 22.0 | 60,806 | 27 | 133 | 0.648 | 41.9 | 74.8 | 119 | True | 0 | True | 2.80 |  |  |
| 5 | feasible | 11.33 | 14.5 | 23.7 | 65,608 | 24 | 145 | 0.651 | 41.3 | 72.5 | 119 | True | 0 | True | 1.81 |  |  |
| 6 | feasible | 10.58 | 11.8 | 28.4 | 78,614 | 32 | 173 | 0.609 | 41.6 | 74.6 | 118 | True | 0 | True | 6.10 |  |  |
| 7 | feasible | 13.70 | 14.8 | 28.6 | 78,984 | 28 | 167 | 0.654 | 40.5 | 66.1 | 119 | True | 0 | True | 4.25 |  |  |
| 8 | feasible | 11.19 | 12.2 | 29.3 | 80,946 | 31 | 167 | 0.620 | 40.4 | 72.3 | 120 | True | 0 | True | 5.52 |  |  |
| 9 | feasible | 11.58 | 14.0 | 25.9 | 71,688 | 31 | 158 | 0.643 | 40.3 | 71.3 | 120 | True | 0 | True | 2.15 |  |  |

- profit M/wk: mean 11.519 | median 11.450 | min 9.374 | max 13.699 | sd 1.201 (n=10)
- coverage %: mean 25.277 | median 24.832 | min 21.996 | max 29.281 | sd 2.692 (n=10)
- served TEU: mean 69,878.720 | median 68,648.000 | min 60,806.000 | max 80,946.000 | sd 7,441.611 (n=10)
- services: mean 27.800 | median 28.000 | min 21.000 | max 32.000 | sd 3.280 (n=10) | vessels: mean 147.600 | median 144.000 | min 112.000 | max 173.000 | sd 17.789 (n=10)
- margin %: mean 14.432 | median 14.667 | min 11.788 | max 17.049 | sd 1.666 (n=10) | load factor: mean 0.632 | median 0.645 | min 0.566 | max 0.678 | sd 0.031 (n=10)
- statuses: {'feasible': 10} | ledger valid: 10 / 10 | violations total: 0 | reconciled: 10 / 10
- negative-profit plans: 0

### P3_ls

| seed | status | profit M | margin % | cov % | served TEU | svc | ves | LF | bound M | gap % | solver s | ledger | viol | reconciled | reopt M | LS M | notes |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---|
| 0 | feasible | 15.68 | 15.8 | 31.9 | 88,052 | 33 | 167 | 0.670 | 41.3 | 62.0 | 105 | True | 0 | True | 0.00 | 3.52 | LS 13 moves |
| 1 | feasible | 15.55 | 15.9 | 30.4 | 84,076 | 31 | 181 | 0.712 | 41.9 | 62.9 | 104 | True | 0 | True | 0.00 | 4.47 | LS 14 moves |
| 2 | feasible | 14.51 | 18.9 | 24.6 | 68,017 | 24 | 127 | 0.691 | 41.4 | 65.0 | 104 | True | 0 | True | 0.00 | 2.88 | LS 8 moves |
| 3 | feasible | 13.40 | 17.2 | 24.0 | 66,478 | 30 | 137 | 0.615 | 39.5 | 66.0 | 105 | True | 0 | True | 0.00 | 4.44 | LS 22 moves |
| 4 | feasible | 11.74 | 14.5 | 25.9 | 71,666 | 31 | 156 | 0.688 | 41.9 | 72.0 | 104 | True | 0 | True | 0.00 | 2.20 | LS 11 moves |
| 5 | feasible | 14.53 | 14.7 | 30.9 | 85,296 | 33 | 181 | 0.687 | 41.3 | 64.8 | 104 | True | 0 | True | 0.00 | 2.94 | LS 11 moves |
| 6 | feasible | 13.46 | 14.4 | 29.5 | 81,600 | 35 | 182 | 0.692 | 41.6 | 67.6 | 103 | True | 0 | True | 0.00 | 3.49 | LS 12 moves |
| 7 | feasible | 14.94 | 15.7 | 30.2 | 83,534 | 34 | 169 | 0.662 | 40.5 | 63.1 | 105 | True | 0 | True | 0.00 | 1.61 | LS 12 moves |
| 8 | feasible | 13.88 | 15.8 | 28.0 | 77,540 | 31 | 158 | 0.639 | 40.4 | 65.7 | 105 | True | 0 | True | 0.00 | 3.62 | LS 12 moves |
| 9 | feasible | 13.85 | 17.1 | 24.9 | 68,886 | 32 | 147 | 0.679 | 40.3 | 65.6 | 105 | True | 0 | True | 0.00 | 4.67 | LS 21 moves |

- profit M/wk: mean 14.154 | median 14.194 | min 11.739 | max 15.679 | sd 1.104 (n=10)
- coverage %: mean 28.040 | median 28.783 | min 24.047 | max 31.851 | sd 2.774 (n=10)
- served TEU: mean 77,514.520 | median 79,570.000 | min 66,478.000 | max 88,052.000 | sd 7,669.611 (n=10)
- services: mean 31.400 | median 31.500 | min 24.000 | max 35.000 | sd 2.871 (n=10) | vessels: mean 160.500 | median 162.500 | min 127.000 | max 182.000 | sd 18.167 (n=10)
- margin %: mean 16.014 | median 15.829 | min 14.371 | max 18.909 | sd 1.338 (n=10) | load factor: mean 0.673 | median 0.683 | min 0.615 | max 0.712 | sd 0.027 (n=10)
- statuses: {'feasible': 10} | ledger valid: 10 / 10 | violations total: 0 | reconciled: 10 / 10
- negative-profit plans: 0

### P3_c1

| seed | status | profit M | margin % | cov % | served TEU | svc | ves | LF | bound M | gap % | solver s | ledger | viol | reconciled | reopt M | LS M | notes |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---|
| 0 | feasible | 13.46 | 17.8 | 24.2 | 66,936 | 24 | 129 | 0.644 | 16.3 | 17.5 | 121 | True | 0 | True | 1.63 |  |  |
| 1 | feasible | 15.50 | 18.1 | 27.1 | 74,998 | 26 | 148 | 0.693 | 16.6 | 6.5 | 121 | True | 0 | True | 4.48 |  |  |
| 2 | feasible | 12.63 | 18.0 | 21.7 | 60,086 | 22 | 121 | 0.649 | 16.7 | 24.5 | 121 | True | 0 | True | 1.69 |  |  |
| 3 | feasible | 12.40 | 16.0 | 24.6 | 68,068 | 29 | 155 | 0.681 | 15.9 | 22.1 | 121 | True | 0 | True | 2.62 |  |  |
| 4 | feasible | 12.62 | 15.8 | 25.5 | 70,598 | 26 | 143 | 0.703 | 15.9 | 20.6 | 121 | True | 0 | True | 3.65 |  |  |
| 5 | feasible | 13.56 | 17.5 | 24.6 | 68,036 | 31 | 147 | 0.680 | 16.4 | 17.2 | 121 | True | 0 | True | 3.06 |  |  |
| 6 | feasible | 14.33 | 17.8 | 24.7 | 68,185 | 25 | 149 | 0.683 | 16.0 | 10.3 | 119 | True | 0 | True | 3.53 |  |  |
| 7 | feasible | 13.33 | 16.3 | 26.1 | 72,260 | 28 | 156 | 0.691 | 15.9 | 16.4 | 120 | True | 0 | True | 3.21 |  |  |
| 8 | feasible | 14.37 | 17.3 | 26.5 | 73,328 | 26 | 149 | 0.641 | 17.2 | 16.6 | 121 | True | 0 | True | 3.09 |  |  |
| 9 | feasible | 12.27 | 17.5 | 22.0 | 60,780 | 20 | 123 | 0.648 | 15.6 | 21.1 | 120 | True | 0 | True | 1.70 |  |  |

- profit M/wk: mean 13.448 | median 13.398 | min 12.274 | max 15.500 | sd 0.984 (n=10)
- coverage %: mean 24.716 | median 24.644 | min 21.735 | max 27.129 | sd 1.686 (n=10)
- served TEU: mean 68,327.480 | median 68,126.400 | min 60,086.000 | max 74,998.000 | sd 4,659.574 (n=10)
- services: mean 25.700 | median 26.000 | min 20.000 | max 31.000 | sd 3.068 (n=10) | vessels: mean 142.000 | median 147.500 | min 121.000 | max 156.000 | sd 12.231 (n=10)
- margin %: mean 17.210 | median 17.487 | min 15.787 | max 18.144 | sd 0.827 (n=10) | load factor: mean 0.671 | median 0.680 | min 0.641 | max 0.703 | sd 0.022 (n=10)
- statuses: {'feasible': 10} | ledger valid: 10 / 10 | violations total: 0 | reconciled: 10 / 10
- negative-profit plans: 0

### P3_c1ls

| seed | status | profit M | margin % | cov % | served TEU | svc | ves | LF | bound M | gap % | solver s | ledger | viol | reconciled | reopt M | LS M | notes |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|---|
| 0 | feasible | 15.35 | 15.6 | 31.2 | 86,352 | 32 | 180 | 0.668 | 16.3 | 5.9 | 106 | True | 0 | True | 0.00 | 2.23 | LS 10 moves |
| 1 | feasible | 15.78 | 16.9 | 29.3 | 80,986 | 29 | 168 | 0.675 | 16.6 | 4.8 | 106 | True | 0 | True | 0.00 | 0.51 | LS 3 moves |
| 2 | feasible | 13.44 | 16.3 | 25.9 | 71,504 | 25 | 142 | 0.672 | 16.7 | 19.7 | 106 | True | 0 | True | 0.00 | 1.01 | LS 3 moves |
| 3 | feasible | 12.73 | 16.3 | 24.6 | 67,874 | 29 | 155 | 0.705 | 15.9 | 20.0 | 106 | True | 0 | True | -0.77 | 0.62 | LS 4 moves |
| 4 | feasible | 13.57 | 15.0 | 28.3 | 78,298 | 33 | 170 | 0.689 | 15.9 | 14.6 | 106 | True | 0 | True | 0.00 | 2.13 | LS 8 moves |
| 5 | feasible | 14.29 | 16.1 | 27.3 | 75,570 | 31 | 162 | 0.672 | 16.4 | 12.7 | 106 | True | 0 | True | 0.00 | 0.76 | LS 5 moves |
| 6 | feasible | 14.56 | 17.3 | 26.3 | 72,837 | 27 | 155 | 0.685 | 16.0 | 8.8 | 105 | True | 0 | True | 0.18 | 0.04 | LS 1 moves |
| 7 | feasible | 13.48 | 16.0 | 26.0 | 71,908 | 27 | 154 | 0.668 | 15.9 | 15.5 | 106 | True | 0 | True | 0.00 | 0.46 | LS 3 moves |
| 8 | feasible | 14.33 | 15.9 | 28.4 | 78,626 | 27 | 165 | 0.634 | 17.2 | 16.9 | 106 | True | 0 | True | 0.00 | 0.80 | LS 4 moves |
| 9 | feasible | 12.81 | 16.3 | 24.9 | 68,938 | 28 | 137 | 0.669 | 15.6 | 17.6 | 106 | True | 0 | True | 0.00 | 0.78 | LS 3 moves |

- profit M/wk: mean 14.034 | median 13.929 | min 12.733 | max 15.778 | sd 0.964 (n=10)
- coverage %: mean 27.235 | median 26.842 | min 24.552 | max 31.236 | sd 1.989 (n=10)
- served TEU: mean 75,289.320 | median 74,203.600 | min 67,874.000 | max 86,352.000 | sd 5,497.277 (n=10)
- services: mean 28.800 | median 28.500 | min 25.000 | max 33.000 | sd 2.400 (n=10) | vessels: mean 158.800 | median 158.500 | min 137.000 | max 180.000 | sd 12.319 (n=10)
- margin %: mean 16.177 | median 16.200 | min 14.998 | max 17.314 | sd 0.619 (n=10) | load factor: mean 0.674 | median 0.672 | min 0.634 | max 0.705 | sd 0.017 (n=10)
- statuses: {'feasible': 10} | ledger valid: 10 / 10 | violations total: 0 | reconciled: 10 / 10
- negative-profit plans: 0

### paired: P3_ls - P3_base

| seed | d profit M | d coverage pp | d served TEU | d services | d vessels | profit A M | profit B M |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | +2.48 | +5.2 | +14,482 | +3 | +24 | 13.20 | 15.68 |
| 1 | +3.98 | +7.0 | +19,440 | +5 | +41 | 11.57 | 15.55 |
| 2 | +2.41 | +1.8 | +5,057 | +3 | +15 | 12.10 | 14.51 |
| 3 | +4.03 | +2.0 | +5,503 | +2 | -1 | 9.37 | 13.40 |
| 4 | +1.17 | +3.9 | +10,860 | +4 | +23 | 10.57 | 11.74 |
| 5 | +3.20 | +7.1 | +19,688 | +9 | +36 | 11.33 | 14.53 |
| 6 | +2.88 | +1.1 | +2,986 | +3 | +9 | 10.58 | 13.46 |
| 7 | +1.24 | +1.6 | +4,550 | +6 | +2 | 13.70 | 14.94 |
| 8 | +2.69 | -1.2 | -3,406 | +0 | -9 | 11.19 | 13.88 |
| 9 | +2.27 | -1.0 | -2,802 | +1 | -11 | 11.58 | 13.85 |

- d profit M: mean 2.635 | median 2.585 | min 1.170 | max 4.028 | sd 0.918 (n=10); positive in 10/10 seeds, negative in 0
- d coverage pp: mean 2.762 | median 1.910 | min -1.232 | max 7.122 | sd 2.837 (n=10); improved in 8/10, regressed in 2
- d served TEU: mean 7,635.800 | median 5,280.000 | min -3,406.000 | max 19,688.000 | sd 7,842.648 (n=10)
- paired t = 8.61 (n=10, se 0.31 M)

### paired: P3_c1 - P3_base

| seed | d profit M | d coverage pp | d served TEU | d services | d vessels | profit A M | profit B M |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | +0.27 | -2.4 | -6,634 | -6 | -14 | 13.20 | 13.46 |
| 1 | +3.93 | +3.7 | +10,362 | +0 | +8 | 11.57 | 15.50 |
| 2 | +0.53 | -1.0 | -2,874 | +1 | +9 | 12.10 | 12.63 |
| 3 | +3.03 | +2.6 | +7,093 | +1 | +17 | 9.37 | 12.40 |
| 4 | +2.05 | +3.5 | +9,792 | -1 | +10 | 10.57 | 12.62 |
| 5 | +2.22 | +0.9 | +2,428 | +7 | +2 | 11.33 | 13.56 |
| 6 | +3.74 | -3.8 | -10,429 | -7 | -24 | 10.58 | 14.33 |
| 7 | -0.37 | -2.4 | -6,724 | +0 | -11 | 13.70 | 13.33 |
| 8 | +3.18 | -2.8 | -7,618 | -5 | -18 | 11.19 | 14.37 |
| 9 | +0.70 | -3.9 | -10,908 | -11 | -35 | 11.58 | 12.27 |

- d profit M: mean 1.929 | median 2.136 | min -0.366 | max 3.933 | sd 1.473 (n=10); positive in 9/10 seeds, negative in 1
- d coverage pp: mean -0.561 | median -1.720 | min -3.946 | max 3.748 | sd 2.845 (n=10); improved in 4/10, regressed in 6
- d served TEU: mean -1,551.240 | median -4,754.000 | min -10,908.000 | max 10,362.000 | sd 7,865.510 (n=10)
- paired t = 3.93 (n=10, se 0.49 M)

### paired: P3_c1ls - P3_base

| seed | d profit M | d coverage pp | d served TEU | d services | d vessels | profit A M | profit B M |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | +2.16 | +4.6 | +12,782 | +2 | +37 | 13.20 | 15.35 |
| 1 | +4.21 | +5.9 | +16,350 | +3 | +28 | 11.57 | 15.78 |
| 2 | +1.34 | +3.1 | +8,544 | +4 | +30 | 12.10 | 13.44 |
| 3 | +3.36 | +2.5 | +6,899 | +1 | +17 | 9.37 | 12.73 |
| 4 | +3.00 | +6.3 | +17,492 | +6 | +37 | 10.57 | 13.57 |
| 5 | +2.96 | +3.6 | +9,962 | +7 | +17 | 11.33 | 14.29 |
| 6 | +3.98 | -2.1 | -5,777 | -5 | -18 | 10.58 | 14.56 |
| 7 | -0.22 | -2.6 | -7,076 | -1 | -13 | 13.70 | 13.48 |
| 8 | +3.15 | -0.8 | -2,320 | -4 | -2 | 11.19 | 14.33 |
| 9 | +1.23 | -1.0 | -2,750 | -3 | -21 | 11.58 | 12.81 |

- d profit M: mean 2.516 | median 2.977 | min -0.222 | max 4.211 | sd 1.312 (n=10); positive in 9/10 seeds, negative in 1
- d coverage pp: mean 1.957 | median 2.793 | min -2.560 | max 6.327 | sd 3.154 (n=10); improved in 6/10, regressed in 4
- d served TEU: mean 5,410.600 | median 7,721.400 | min -7,076.000 | max 17,492.000 | sd 8,718.641 (n=10)
- paired t = 5.75 (n=10, se 0.44 M)
