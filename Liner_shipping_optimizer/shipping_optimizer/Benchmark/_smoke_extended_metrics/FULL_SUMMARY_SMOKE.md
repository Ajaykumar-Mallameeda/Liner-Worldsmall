# Full smoke summary - C3 pipeline, tests/test_orchestrator.py
Generated 2026-10-21T05:43:38+00:00 from `_smoke_extended_metrics/<dataset>/seed_NN.json`. Sample statistics (n-1). Per-run detail: `<dataset>/seed_NN.json`, full artifacts: `<dataset>/runs/seed_NN/`.

## Run status

| dataset | runs | with output | exit 0 | ledger verified | failed/killed | LLM 429 (runs / calls) | distinct profit values |
|---|---|---|---|---|---|---|---|
| baltic | 1 | 1 | 1 | 1 | 0 | 1 / 5 | 1 |
| WAF | - | - | - | - | - | - | - |
| worldsmall | 1 | 1 | 1 | 1 | 0 | 1 / 6 | 1 |
| world500 | - | - | - | - | - | - | - |
| world1000 | - | - | - | - | - | - | - |

## LLM availability during the runs

Seeds run in order; when the provider's daily limit is reached the remaining seeds run on the rule-based fallback (decisions without LLM guidance, ~seconds instead of minutes). Compute time is therefore reported by regime; `optimiser_plan_sec` (the network optimiser alone) does not depend on the LLM.

| dataset | LLM-assisted runs | full-fallback runs | mean profit assisted | mean profit fallback | median pipeline s (assisted / fallback) | median optimiser s (assisted / fallback) |
|---|---|---|---|---|---|---|
| baltic | 1 | 0 | 597,747 | n/a | 167.70 / n/a | 0.25 / n/a |
| worldsmall | 1 | 0 | 47,334,394 | n/a | 490.70 / n/a | 114.73 / n/a |

## Original metrics - mean over seeds

| metric | baltic | WAF | worldsmall | world500 | world1000 |
|---|---|---|---|---|---|
| weekly_profit_usd | 597,747 | n/a | 47,334,394 | n/a | n/a |
| weekly_revenue_usd | 2,596,440 | n/a | 147,334,220 | n/a | n/a |
| weekly_total_cost_usd | 1,998,693 | n/a | 99,999,826 | n/a | n/a |
| profit_margin_on_revenue | 0.23 | n/a | 0.32 | n/a | n/a |
| coverage_pct | 58.83 | n/a | 48.69 | n/a | n/a |
| served_teu | 5,770 | n/a | 134,622 | n/a | n/a |
| unserved_teu | 4,038 | n/a | 141,872 | n/a | n/a |
| services_operated | 3.00 | n/a | 30.00 | n/a | n/a |
| departures_per_week | 3.00 | n/a | 33.00 | n/a | n/a |
| vessels_assigned | 4.00 | n/a | 176.00 | n/a | n/a |
| vessels_idle | 2.00 | n/a | 87.00 | n/a | n/a |
| deployment_ratio (vessel utilisation) | 0.67 | n/a | 0.67 | n/a | n/a |
| productive_load_factor (capacity utilisation) | 0.67 | n/a | 0.53 | n/a | n/a |
| profit_per_assigned_vessel_usd | 149,437 | n/a | 268,945 | n/a | n/a |
| pipeline_runtime_sec | 167.70 | n/a | 490.70 | n/a | n/a |
| driver_wall_sec | 187.40 | n/a | 492.40 | n/a | n/a |
| global_solver_integer_phase_sec | 0.14 | n/a | 101.12 | n/a | n/a |
| gap_to_lp_bound_pct | 14.77 | n/a | 24.51 | n/a | n/a |

## Added metrics - mean over seeds

| metric | baltic | WAF | worldsmall | world500 | world1000 |
|---|---|---|---|---|---|
| contribution_margin_usd | 1,239,905 | n/a | 117,599,724 | n/a | n/a |
| contribution_margin_per_teu_usd | 214.89 | n/a | 873.56 | n/a | n/a |
| contribution_margin_pct_of_revenue | 47.75 | n/a | 79.82 | n/a | n/a |
| teu_vessel_utilisation_average | 0.67 | n/a | 0.53 | n/a | n/a |
| teu_vessel_utilisation_min | 0.52 | n/a | 0.27 | n/a | n/a |
| teu_vessel_utilisation_max | 0.79 | n/a | 0.86 | n/a | n/a |
| transit_time_days_average (TEU-weighted) | 2.33 | n/a | 23.05 | n/a | n/a |
| transit_time_days_min | 1.08 | n/a | 0.01 | n/a | n/a |
| transit_time_days_max | 9.82 | n/a | 63.33 | n/a | n/a |
| teu_through_transshipment | 0.00 | n/a | 29,072 | n/a | n/a |
| teu_through_transshipment_share_pct | 0.00 | n/a | 21.60 | n/a | n/a |
| transshipment_transfer_moves_teu | 0.00 | n/a | 29,072 | n/a | n/a |
| compute_time_pipeline_sec | 167.70 | n/a | 490.70 | n/a | n/a |
| compute_time_driver_wall_sec | 187.40 | n/a | 492.40 | n/a | n/a |
| compute_time_optimiser_plan_sec | 0.25 | n/a | 114.73 | n/a | n/a |
| compute_time_llm_latency_sum_sec | 117.80 | n/a | 36.00 | n/a | n/a |

## Per-dataset statistics (min / mean / median / max / std dev)

### baltic (1 runs with output)

| metric | min | mean | median | max | std dev | cv % |
|---|---|---|---|---|---|---|
| weekly_profit_usd | 597,747 | 597,747 | 597,747 | 597,747 | 0.00 | 0.00 |
| weekly_revenue_usd | 2,596,440 | 2,596,440 | 2,596,440 | 2,596,440 | 0.00 | 0.00 |
| weekly_total_cost_usd | 1,998,693 | 1,998,693 | 1,998,693 | 1,998,693 | 0.00 | 0.00 |
| profit_margin_on_revenue | 0.23 | 0.23 | 0.23 | 0.23 | 0.00 | 0.00 |
| coverage_pct | 58.83 | 58.83 | 58.83 | 58.83 | 0.00 | 0.00 |
| served_teu | 5,770 | 5,770 | 5,770 | 5,770 | 0.00 | 0.00 |
| unserved_teu | 4,038 | 4,038 | 4,038 | 4,038 | 0.00 | 0.00 |
| services_operated | 3.00 | 3.00 | 3.00 | 3.00 | 0.00 | 0.00 |
| departures_per_week | 3.00 | 3.00 | 3.00 | 3.00 | 0.00 | 0.00 |
| vessels_assigned | 4.00 | 4.00 | 4.00 | 4.00 | 0.00 | 0.00 |
| vessels_idle | 2.00 | 2.00 | 2.00 | 2.00 | 0.00 | 0.00 |
| deployment_ratio (vessel utilisation) | 0.67 | 0.67 | 0.67 | 0.67 | 0.00 | 0.00 |
| productive_load_factor (capacity utilisation) | 0.67 | 0.67 | 0.67 | 0.67 | 0.00 | 0.00 |
| profit_per_assigned_vessel_usd | 149,437 | 149,437 | 149,437 | 149,437 | 0.00 | 0.00 |
| pipeline_runtime_sec | 167.70 | 167.70 | 167.70 | 167.70 | 0.00 | 0.00 |
| driver_wall_sec | 187.40 | 187.40 | 187.40 | 187.40 | 0.00 | 0.00 |
| global_solver_integer_phase_sec | 0.14 | 0.14 | 0.14 | 0.14 | 0.00 | 0.00 |
| gap_to_lp_bound_pct | 14.77 | 14.77 | 14.77 | 14.77 | 0.00 | 0.00 |
| contribution_margin_usd | 1,239,905 | 1,239,905 | 1,239,905 | 1,239,905 | 0.00 | 0.00 |
| contribution_margin_per_teu_usd | 214.89 | 214.89 | 214.89 | 214.89 | 0.00 | 0.00 |
| contribution_margin_pct_of_revenue | 47.75 | 47.75 | 47.75 | 47.75 | 0.00 | 0.00 |
| teu_vessel_utilisation_average | 0.67 | 0.67 | 0.67 | 0.67 | 0.00 | 0.00 |
| teu_vessel_utilisation_min | 0.52 | 0.52 | 0.52 | 0.52 | 0.00 | 0.00 |
| teu_vessel_utilisation_max | 0.79 | 0.79 | 0.79 | 0.79 | 0.00 | 0.00 |
| transit_time_days_average (TEU-weighted) | 2.33 | 2.33 | 2.33 | 2.33 | 0.00 | 0.00 |
| transit_time_days_min | 1.08 | 1.08 | 1.08 | 1.08 | 0.00 | 0.00 |
| transit_time_days_max | 9.82 | 9.82 | 9.82 | 9.82 | 0.00 | 0.00 |
| teu_through_transshipment | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | n/a |
| teu_through_transshipment_share_pct | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | n/a |
| transshipment_transfer_moves_teu | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | n/a |
| compute_time_pipeline_sec | 167.70 | 167.70 | 167.70 | 167.70 | 0.00 | 0.00 |
| compute_time_driver_wall_sec | 187.40 | 187.40 | 187.40 | 187.40 | 0.00 | 0.00 |
| compute_time_optimiser_plan_sec | 0.25 | 0.25 | 0.25 | 0.25 | 0.00 | 0.00 |
| compute_time_llm_latency_sum_sec | 117.80 | 117.80 | 117.80 | 117.80 | 0.00 | 0.00 |

Seeds 1 shared with the earlier run: 1 identical weekly profit (to 1 cent), max difference 0.00 USD, mean 0.00 USD.

### worldsmall (1 runs with output)

| metric | min | mean | median | max | std dev | cv % |
|---|---|---|---|---|---|---|
| weekly_profit_usd | 47,334,394 | 47,334,394 | 47,334,394 | 47,334,394 | 0.00 | 0.00 |
| weekly_revenue_usd | 147,334,220 | 147,334,220 | 147,334,220 | 147,334,220 | 0.00 | 0.00 |
| weekly_total_cost_usd | 99,999,826 | 99,999,826 | 99,999,826 | 99,999,826 | 0.00 | 0.00 |
| profit_margin_on_revenue | 0.32 | 0.32 | 0.32 | 0.32 | 0.00 | 0.00 |
| coverage_pct | 48.69 | 48.69 | 48.69 | 48.69 | 0.00 | 0.00 |
| served_teu | 134,622 | 134,622 | 134,622 | 134,622 | 0.00 | 0.00 |
| unserved_teu | 141,872 | 141,872 | 141,872 | 141,872 | 0.00 | 0.00 |
| services_operated | 30.00 | 30.00 | 30.00 | 30.00 | 0.00 | 0.00 |
| departures_per_week | 33.00 | 33.00 | 33.00 | 33.00 | 0.00 | 0.00 |
| vessels_assigned | 176.00 | 176.00 | 176.00 | 176.00 | 0.00 | 0.00 |
| vessels_idle | 87.00 | 87.00 | 87.00 | 87.00 | 0.00 | 0.00 |
| deployment_ratio (vessel utilisation) | 0.67 | 0.67 | 0.67 | 0.67 | 0.00 | 0.00 |
| productive_load_factor (capacity utilisation) | 0.53 | 0.53 | 0.53 | 0.53 | 0.00 | 0.00 |
| profit_per_assigned_vessel_usd | 268,945 | 268,945 | 268,945 | 268,945 | 0.00 | 0.00 |
| pipeline_runtime_sec | 490.70 | 490.70 | 490.70 | 490.70 | 0.00 | 0.00 |
| driver_wall_sec | 492.40 | 492.40 | 492.40 | 492.40 | 0.00 | 0.00 |
| global_solver_integer_phase_sec | 101.12 | 101.12 | 101.12 | 101.12 | 0.00 | 0.00 |
| gap_to_lp_bound_pct | 24.51 | 24.51 | 24.51 | 24.51 | 0.00 | 0.00 |
| contribution_margin_usd | 117,599,724 | 117,599,724 | 117,599,724 | 117,599,724 | 0.00 | 0.00 |
| contribution_margin_per_teu_usd | 873.56 | 873.56 | 873.56 | 873.56 | 0.00 | 0.00 |
| contribution_margin_pct_of_revenue | 79.82 | 79.82 | 79.82 | 79.82 | 0.00 | 0.00 |
| teu_vessel_utilisation_average | 0.53 | 0.53 | 0.53 | 0.53 | 0.00 | 0.00 |
| teu_vessel_utilisation_min | 0.27 | 0.27 | 0.27 | 0.27 | 0.00 | 0.00 |
| teu_vessel_utilisation_max | 0.86 | 0.86 | 0.86 | 0.86 | 0.00 | 0.00 |
| transit_time_days_average (TEU-weighted) | 23.05 | 23.05 | 23.05 | 23.05 | 0.00 | 0.00 |
| transit_time_days_min | 0.01 | 0.01 | 0.01 | 0.01 | 0.00 | 0.00 |
| transit_time_days_max | 63.33 | 63.33 | 63.33 | 63.33 | 0.00 | 0.00 |
| teu_through_transshipment | 29,072 | 29,072 | 29,072 | 29,072 | 0.00 | 0.00 |
| teu_through_transshipment_share_pct | 21.60 | 21.60 | 21.60 | 21.60 | 0.00 | 0.00 |
| transshipment_transfer_moves_teu | 29,072 | 29,072 | 29,072 | 29,072 | 0.00 | 0.00 |
| compute_time_pipeline_sec | 490.70 | 490.70 | 490.70 | 490.70 | 0.00 | 0.00 |
| compute_time_driver_wall_sec | 492.40 | 492.40 | 492.40 | 492.40 | 0.00 | 0.00 |
| compute_time_optimiser_plan_sec | 114.73 | 114.73 | 114.73 | 114.73 | 0.00 | 0.00 |
| compute_time_llm_latency_sum_sec | 36.00 | 36.00 | 36.00 | 36.00 | 0.00 | 0.00 |

Seeds 1 shared with the earlier run: 0 identical weekly profit (to 1 cent), max difference 441,958 USD, mean 441,958 USD.

## Added schema fields

| path in seed_NN.json | unit | definition |
|---|---|---|
| `contribution_margin.contribution_margin_usd` | USD/week | revenue - cargo-variable costs (handling + transshipment + per-TEU port variable); profit = contribution margin - fixed service cost (vessel + fuel + port calls) |
| `contribution_margin.contribution_margin_per_teu_usd` | USD/TEU | contribution margin / served TEU |
| `contribution_margin.contribution_margin_pct_of_revenue` | % | 100 x contribution margin / revenue |
| `vessel_utilisation_teu.average` | 0-1 | network carried TEU-legs / offered TEU-legs (capacity-weighted); also *_service_unweighted and *_vessel_weighted |
| `vessel_utilisation_teu.min / .max` | 0-1 | lowest / highest service load factor (each vessel inherits its service's value); leg_min / leg_max over single legs |
| `transit_time_days.mean` | days | TEU-weighted mean transit time of the routed flows (sailing + port stays + transfer dwell); mean_per_flow is unweighted |
| `transit_time_days.min / .max` | days | shortest / longest transit time over the routed flows; p50, p90, mean_direct, mean_transshipped also stored |
| `transshipment.teu` | TEU/week | TEU of flows that change service at least once |
| `transshipment.share_of_served_teu_pct` | % | 100 x transshipped TEU / served TEU |
| `transshipment.transfer_moves_teu` | TEU-moves/week | TEU x number of transfers (a two-transfer container counts twice) |
| `compute_time_sec.pipeline_total` | s | the pipeline call end to end (includes LLM calls and every stage) |
| `compute_time_sec.driver_wall` | s | the driver's wall time around the whole test process (adds start-up and report writing) |
| `compute_time_sec.optimiser_plan_total` | s | network plan stage only (paths, MILP, local search, flow re-optimisation, ledger) |
| `compute_time_sec.llm_call_latency_sum` | s | summed latency of the LLM calls; components may overlap, so it can exceed the wall time |
| `llm_runtime.http_429 / fallback_uses` | count | rate-limited LLM calls and rule-based fallbacks; the run continues on the fallback |
