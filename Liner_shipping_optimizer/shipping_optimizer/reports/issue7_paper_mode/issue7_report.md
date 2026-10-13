# Issue 7 - separate paper-comparison evaluator (2026-10-13)  -  gate: PASS (evaluator separate and partly verified; profit comparison NOT possible)

Code: `src/benchmark/paper_evaluator.py` (new package; **nothing in `src/network` imports it**, enforced by a test), `tests/test_paper_evaluator.py`
(7 tests). Tools and evidence: `tools/`, `paper_table6_design.json`, `table6_evaluation.json`, `paper_mode_plan_evaluation.csv`.
The operational model and its constraints are untouched.

## What the evaluator reproduces (paper arXiv:2411.09068, App. A-B)
FFE-native data read from the raw files (no loader conversion); weekly rotations with fractional vessels
`n = (sum nm / (design speed x 24) + 1 day per port call) / 7`; capacity per service edge; no transit-time constraint; unlimited transfers;
paper Algorithm 1 (greedy MCF, demands by descending revenue, cheapest handling-cost path, Dijkstra on the proxy-node graph);
profit = revenue - 1000 USD x rejected FFE - handling/transshipment - (vessel service + unused-vessel credit at the TC rate + voyage)
(Eq. 28-35). Interpretation switches (voyage basis, port-variable basis, canal basis, capacity basis) are explicit; none is silently chosen.

## Verification actually achieved
| check | result |
|---|---|
| Table 6 design (RL encoder-decoder, World Small, 19 schedules) parsed from the paper PDF; every schedule's closed rotation resolved in `dist_dense.csv` | 19/19, 0 missing legs |
| fractional vessel count of each schedule from the formula vs the paper's number | **19/19 equal to 3 digits** (ratio 1.000; 0.999-1.004) |
| therefore confirmed: `dist_dense.csv` = the paper's distances; class speed = `designSpeed`; 1 day per port call; weekly horizon (/7); class labels = `Capacity FFE` | VERIFIED against the paper |
| paper's reported World Small profit (Table 2) reproduced from its own Table 6 design | **NOT reproduced**: 48 interpretation variants span -1,406 .. +95 M/wk against the reported 32-43 M; no variant is within 40 % |

Why the profit comparison is refused: the printed equations are partly illegible, Table 2's row alignment is lost in the PDF text layer, the
profit horizon is not stated, and the voyage-cost basis (per rotation vs multiplied by the fractional vessel count, Eq. 35) changes the
result by two orders of magnitude (fuel 98.5 kt/wk vs 1,973 kt/wk). With the physical reading (capacity = one weekly departure) the paper's own
design scores -15.8 M/wk (62 % coverage); reading capacity as vessel capacity x vessel count gives +91.3 M (100 % coverage). The reported
42 M lies in between and cannot be attributed to either. **No number from the paper's Table 2 is used as a target.**

## What can be compared like for like (same evaluator, same data, same interpretation)
`paper_mode_plan_evaluation.csv`: the paper's Table 6 design and our recorded plans (default and VUB + LS, seeds 0-2) scored by the paper's
objective. Under both capacity readings the paper's design scores above all of our plans (e.g. physical reading: -15.8 M vs -23 .. -52 M;
vessel-count reading: +91 M vs +58 .. +75 M). This is expected and **not** a defect: the operational model maximises operating profit
without a rejection penalty and with hard transit limits, integer weekly frequencies and fleet inventory, so it leaves 55-70 % of demand
unserved where the paper's objective charges 1,000 USD per rejected FFE. The two evaluators answer different questions and are reported
separately.

## Rules kept
Operational constraints were not relaxed to imitate the paper; WorldSmall only (Baltic/WAF not run); no paper headline is compared with an
operational mean. Both evaluators' definitions are in their module docstrings.

## Open (needs owner / source)
D-02 (decision to adopt a paper mode for benchmarking), the voyage-cost basis of Eq. 35, the profit horizon, the row alignment of Table 2:
all require the primary LINERLIB report or the paper's authors.

## Rollback
`git revert` of this commit (new package, tests, reports); no pipeline file changed.
