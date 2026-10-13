| Metric | Frozen baseline M0 (1 run) (n=1) | Task 8 (legacy configuration) (3 runs) (n=3) | Task 9 (loops 60) (2 runs) (n=2) | Task 10 final (default) (3 runs) (n=3) |
|---|---:|---:|---:|---:|
| Verified weekly profit (USD) | 2,671,085 | 2,997,948 | 6,117,190 | 9,056,448 |
| Profit margin on revenue (%) | 11.5 | 10.7 | 13.2 | 13.3 |
| Cargo coverage (% of demand) | 6.5 | 8.2 | 13.5 | 21.1 |
| Unique served TEU / week | 17,962 | 22,696 | 37,213 | 58,301 |
| Selected services | 8.0 | 9.3 | 11.5 | 18.0 |
| Vessels deployed | 40 | 37 | 80 | 122 |
| Fuel cost per week (USD) | 9,728,592 | 11,106,175 | 19,293,578 | 28,103,044 |
| Candidate count (modelled pool) | 1,083 | 1,089 | 1,220 | 1,174 |
| Global-stage runtime (s) | 25 | 24 | 28 | 116 |
| Whole pipeline runtime (s) | 159 | 75 | 92 | 336 |
| Ledger violations (sum) | 0 | 0 | 0 | 0 |

Per-run weekly profit (USD) / coverage (%) / assertions:

* **Frozen baseline M0 (1 run)**: `M0_orch` 2,671,085 / 6.5% / 310/310 (verified True, MILP feasible)
* **Task 8 (legacy configuration) (3 runs)**: `LEGACY6_run1` 2,342,117 / 7.7% / 342/342 (verified True, MILP feasible); `LEGACY6_run2` 3,441,048 / 8.7% / 342/342 (verified True, MILP feasible); `LEGACY6_run3` 3,210,678 / 8.2% / 342/342 (verified True, MILP feasible)
* **Task 9 (loops 60) (2 runs)**: `T9ONLY6_run1` 6,439,113 / 14.4% / 342/342 (verified True, MILP feasible); `T9ONLY6_run2` 5,795,266 / 12.6% / 342/342 (verified True, MILP feasible)
* **Task 10 final (default) (3 runs)**: `FINAL7_default_run1` 9,022,634 / 18.8% / 342/342 (verified True, MILP feasible); `FINAL7_default_run2` 9,112,217 / 20.1% / 342/342 (verified True, MILP feasible); `FINAL7_default_run3` 9,034,492 / 24.4% / 342/342 (verified True, MILP feasible)
