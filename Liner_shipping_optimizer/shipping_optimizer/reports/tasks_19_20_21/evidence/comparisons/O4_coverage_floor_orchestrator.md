# O4 — end-to-end runs with the opt-in coverage floor (`LINER_GLOBAL_MIN_COVERAGE=0.25`)

Source: `runs/T19O_cov25_run{1,2}.{log,meta.txt,pipeline_output.json}` (tree `snap_T19O_cov25_run{1,2}` =
`snap_T19_final`, manifest sha256 `6baabfa6…5de5`, command `pytest tests/test_orchestrator.py`, only the one variable set).
Table produced by `tools/orch_summary.py` and a read of `optimality` / `iteration_audit` of each output file.

| run | exit | assertions | status | profit M/wk | margin % | coverage % | services / vessels | global-stage status per iteration (0 / 1 / 2) | selected | re-routing gain M | repair |
|---|---:|---|---|---:|---:|---:|---|---|---:|---:|---|
| `T19O_cov25_run1` | 1 | 355 / 361 (6 failed) | complete, ledger verified, 0 violations | **−8.69** | −9.8 | 28.43 | 35 / 215 | not_solved / not_solved / feasible | 2 | 8.93 | not run (floor active) |
| `T19O_cov25_run2` | 0 | 362 / 362 | complete, ledger verified, 0 violations | **+11.65** | 13.8 | 26.10 | 26 / 161 | not_solved / feasible / feasible (iteration profit 0.52 / 11.65 / 9.71 M; iteration 0 is the regional fallback, global coverage 7.5 %) | 1 | 3.36 | not run (floor active) |

Reference, same tree, **floor off** (default): `T19O_default_run1..3` = 12.59 / 12.17 / 13.88 M, coverage 23.0 / 23.6 / 25.5 %, 362/362 each.

## The six failed assertions of run 1

All six are the profit-positivity assertions (`Global weekly profit > 0`, `Network is profitable`, `Weekly profit > 0` ×2,
`Annual profit > 0`, `Profit margin > 0`) applied to a plan that **is** loss-making (−8.69 M/wk).  The assertions did their
job; nothing in the integrity block failed (ledger verified, 0 violations, reconciled, status honest).

## Mechanism (read from the code and the logs, not assumed)

* `src/network/plan.py:212` — `if self.path_config.repair_profit_floor and not min_served_fraction:` — the profit-floor
  repair is **deliberately not run while a coverage floor is active** (dropping services could break the floor).  The repair
  therefore did not act on the −8.69 M incumbent, and `flow_reoptimisation.repair` is null in both runs.
* Global stage `not_solved` on iteration 0 in **both** runs and on iteration 1 in run 1 (counted in the output files as
  three `Unverified (not_solved)` regional results per such iteration; two `global_reconciliation_failed | status=not_solved`
  log lines in the failed run's captured log — the passing run's log is not printed by pytest).  With a 25 % floor the
  time-limited CBC returned no incumbent on those pools and the orchestrator fell back to the regional plans (coverage
  5.7 – 5.8 %, profit +0.52 / −10.06 / −2.99 M, honestly labelled unverified / not solved).  Run 1's iteration 2 found a
  feasible incumbent with 35 services and 215 vessels that meets the floor (28.4 %) at a loss; run 2's iterations 1 and 2
  found profitable incumbents (11.65 / 9.71 M).
* Run 1 also had Groq 429 errors (LLM providers unavailable, ignored as instructed, rule-based fallbacks used); the
  candidate pools of the two runs differ (unseeded).

## What this does and does not show

* In the controlled batch M10 (fixed pools, floor 25 %, 10 seeds) every run was `feasible` with profit 5.45 – 12.62 M and
  coverage 26.2 – 28.7 %: mean −1.55 M for +2.1 pp against the same pools without the floor.
* End to end, one run of two reproduces that trade (11.65 M, 26.1 %) and one does not (loss-making incumbent).
  n = 2: no rate is estimated.  The result is evidence that the floor, combined with a time-limited solver and no repair,
  can return a plan that violates the profit floor of 0 — which is the reason it stays **opt-in / experimental** and is not
  proposed for approval in this mission.
* Follow-up (recorded in `remaining_tasks.md`, not implemented here to keep the accepted patch series unchanged): let the
  repair run under the floor by passing `floor_teu` into `repair_profit_floor` and rejecting trials whose served TEU falls
  below it; then re-run ≥ 10 seeds end to end.
