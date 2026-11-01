# Full 30 seeds summary - C3 pipeline, tests/test_orchestrator.py
Generated 2026-10-21T20:57:34+00:00 from `seed-30/<dataset>/seed_NN.json`. Sample statistics (n-1). Per-run detail: `<dataset>/seed_NN.json`, full artifacts: `<dataset>/runs/seed_NN/`.

## Run status

| dataset | runs | with output | exit 0 | ledger verified | failed/killed | LLM 429 (runs / calls) | distinct profit values |
|---|---|---|---|---|---|---|---|
| baltic | 30 | 30 | 30 | 30 | 0 | 30 / 88 | 10 |
| WAF | 30 | 30 | 30 | 30 | 0 | 30 / 63 | 24 |
| worldsmall | 30 | 30 | 30 | 30 | 0 | 30 / 219 | 30 |
| world500 | 30 | 30 | 29 | 30 | 1 | 30 / 297 | 30 |
| world1000 | 30 | 30 | 30 | 30 | 0 | 30 / 233 | 26 |

## LLM availability during the runs

Seeds run in order; when the provider's daily limit is reached the remaining seeds run on the rule-based fallback (decisions without LLM guidance, ~seconds instead of minutes). Compute time is therefore reported by regime; `optimiser_plan_sec` (the network optimiser alone) does not depend on the LLM.

| dataset | LLM-assisted runs | full-fallback runs | mean profit assisted | mean profit fallback | median pipeline s (assisted / fallback) | median optimiser s (assisted / fallback) |
|---|---|---|---|---|---|---|
| baltic | 8 | 22 | 622,263 | 628,834 | 219.10 / 2.50 | 0.26 / 0.23 |
| WAF | 1 | 29 | 4,962,034 | 5,049,157 | 8.70 / 5.40 | 0.81 / 0.41 |
| worldsmall | 30 | 0 | 46,991,456 | n/a | 402.70 / n/a | 115.08 / n/a |
| world500 | 30 | 0 | 172,044,723 | n/a | 466.00 / n/a | 112.93 / n/a |
| world1000 | 25 | 5 | 246,549,214 | 246,742,378 | 342.30 / 330.90 | 77.70 / 75.90 |

## Original metrics - mean over seeds

| metric | baltic | WAF | worldsmall | world500 | world1000 |
|---|---|---|---|---|---|
| weekly_profit_usd | 627,081 | 5,046,252 | 46,991,456 | 172,044,723 | 246,581,408 |
| weekly_revenue_usd | 2,651,512 | 12,263,387 | 144,658,454 | 428,196,726 | 633,235,181 |
| weekly_total_cost_usd | 2,024,431 | 7,217,134 | 97,666,998 | 256,152,003 | 386,653,774 |
| profit_margin_on_revenue | 0.24 | 0.41 | 0.33 | 0.40 | 0.39 |
| coverage_pct | 60.20 | 79.71 | 48.18 | 15.08 | 12.91 |
| served_teu | 5,904 | 13,616 | 133,211 | 407,470 | 612,750 |
| unserved_teu | 3,904 | 3,466 | 143,283 | 2,294,600 | 4,132,528 |
| services_operated | 2.97 | 8.83 | 30.10 | 76.63 | 121.00 |
| departures_per_week | 2.97 | 8.93 | 31.93 | 148.60 | 203.33 |
| vessels_assigned | 4.50 | 31.10 | 173.97 | 730.70 | 1,166 |
| vessels_idle | 1.50 | 10.90 | 89.03 | 1,839 | 3,348 |
| deployment_ratio (vessel utilisation) | 0.75 | 0.74 | 0.66 | 0.28 | 0.26 |
| productive_load_factor (capacity utilisation) | 0.78 | 0.49 | 0.56 | 0.60 | 0.56 |
| profit_per_assigned_vessel_usd | 142,408 | 162,293 | 271,068 | 235,465 | 211,435 |
| pipeline_runtime_sec | 49.79 | 6.34 | 412.12 | 573.36 | 353.18 |
| driver_wall_sec | 51.16 | 7.61 | 416.03 | 578.48 | 365.20 |
| global_solver_integer_phase_sec | 0.17 | 0.32 | 100.91 | 94.41 | 33.64 |
| gap_to_lp_bound_pct | 12.29 | 7.40 | 23.62 | 17.87 | 34.13 |

## Added metrics - mean over seeds

| metric | baltic | WAF | worldsmall | world500 | world1000 |
|---|---|---|---|---|---|
| contribution_margin_usd | 1,272,194 | 9,386,263 | 114,760,123 | 337,126,703 | 503,648,418 |
| contribution_margin_per_teu_usd | 215.47 | 689.39 | 861.74 | 827.49 | 821.96 |
| contribution_margin_pct_of_revenue | 47.97 | 76.54 | 79.34 | 78.73 | 79.54 |
| teu_vessel_utilisation_average | 0.78 | 0.49 | 0.56 | 0.60 | 0.56 |
| teu_vessel_utilisation_min | 0.62 | 0.33 | 0.24 | 0.29 | 0.21 |
| teu_vessel_utilisation_max | 0.88 | 0.76 | 0.89 | 1.00 | 1.00 |
| transit_time_days_average (TEU-weighted) | 2.65 | 9.55 | 22.98 | 16.28 | 15.56 |
| transit_time_days_min | 1.08 | 4.42 | 0.01 | 0.20 | 0.38 |
| transit_time_days_max | 8.88 | 18.00 | 59.91 | 69.24 | 67.71 |
| teu_through_transshipment | 0.00 | 0.00 | 29,712 | 8,741 | 13,946 |
| teu_through_transshipment_share_pct | 0.00 | 0.00 | 22.28 | 2.14 | 2.28 |
| transshipment_transfer_moves_teu | 0.00 | 0.00 | 30,178 | 9,481 | 14,549 |
| compute_time_pipeline_sec | 49.79 | 6.34 | 412.12 | 573.36 | 353.18 |
| compute_time_driver_wall_sec | 51.16 | 7.61 | 416.03 | 578.48 | 365.20 |
| compute_time_optimiser_plan_sec | 0.24 | 0.47 | 114.42 | 107.71 | 77.80 |
| compute_time_llm_latency_sum_sec | 18.27 | 0.53 | 44.93 | 113.53 | 96.04 |

## Per-dataset statistics (min / mean / median / max / std dev)

### baltic (30 runs with output)

| metric | min | mean | median | max | std dev | cv % |
|---|---|---|---|---|---|---|
| weekly_profit_usd | 597,747 | 627,081 | 637,858 | 670,637 | 24,576 | 3.92 |
| weekly_revenue_usd | 2,223,320 | 2,651,512 | 2,695,130 | 3,172,210 | 169,314 | 6.39 |
| weekly_total_cost_usd | 1,596,176 | 2,024,431 | 2,042,791 | 2,567,053 | 164,947 | 8.15 |
| profit_margin_on_revenue | 0.19 | 0.24 | 0.23 | 0.28 | 0.02 | 6.77 |
| coverage_pct | 50.49 | 60.20 | 61.01 | 74.23 | 4.06 | 6.74 |
| served_teu | 4,952 | 5,904 | 5,984 | 7,280 | 397.98 | 6.74 |
| unserved_teu | 2,528 | 3,904 | 3,824 | 4,856 | 397.98 | 10.19 |
| services_operated | 2.00 | 2.97 | 3.00 | 4.00 | 0.32 | 10.78 |
| departures_per_week | 2.00 | 2.97 | 3.00 | 4.00 | 0.32 | 10.78 |
| vessels_assigned | 3.00 | 4.50 | 5.00 | 6.00 | 0.68 | 15.16 |
| vessels_idle | 0.00 | 1.50 | 1.00 | 3.00 | 0.68 | 45.49 |
| deployment_ratio (vessel utilisation) | 0.50 | 0.75 | 0.83 | 1.00 | 0.11 | 15.16 |
| productive_load_factor (capacity utilisation) | 0.67 | 0.78 | 0.80 | 0.90 | 0.09 | 11.59 |
| profit_per_assigned_vessel_usd | 100,859 | 142,408 | 132,391 | 209,048 | 22,271 | 15.64 |
| pipeline_runtime_sec | 2.20 | 49.79 | 2.55 | 240.70 | 86.12 | 172.97 |
| driver_wall_sec | 3.40 | 51.16 | 3.75 | 242.90 | 86.37 | 168.83 |
| global_solver_integer_phase_sec | 0.12 | 0.17 | 0.16 | 0.41 | 0.06 | 35.25 |
| gap_to_lp_bound_pct | 5.45 | 12.29 | 13.85 | 15.80 | 3.49 | 28.43 |
| contribution_margin_usd | 1,051,994 | 1,272,194 | 1,314,241 | 1,471,755 | 87,706 | 6.89 |
| contribution_margin_per_teu_usd | 200.52 | 215.47 | 215.79 | 219.63 | 4.37 | 2.03 |
| contribution_margin_pct_of_revenue | 45.15 | 47.97 | 48.00 | 48.76 | 0.76 | 1.58 |
| teu_vessel_utilisation_average | 0.67 | 0.78 | 0.80 | 0.90 | 0.09 | 11.59 |
| teu_vessel_utilisation_min | 0.51 | 0.62 | 0.56 | 0.77 | 0.10 | 16.65 |
| teu_vessel_utilisation_max | 0.79 | 0.88 | 0.86 | 0.99 | 0.08 | 9.50 |
| transit_time_days_average (TEU-weighted) | 1.88 | 2.65 | 2.63 | 3.14 | 0.36 | 13.61 |
| transit_time_days_min | 1.08 | 1.08 | 1.08 | 1.08 | 0.00 | 0.00 |
| transit_time_days_max | 6.38 | 8.88 | 9.30 | 9.82 | 1.30 | 14.63 |
| teu_through_transshipment | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | n/a |
| teu_through_transshipment_share_pct | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | n/a |
| transshipment_transfer_moves_teu | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | n/a |
| compute_time_pipeline_sec | 2.20 | 49.79 | 2.55 | 240.70 | 86.12 | 172.97 |
| compute_time_driver_wall_sec | 3.40 | 51.16 | 3.75 | 242.90 | 86.37 | 168.83 |
| compute_time_optimiser_plan_sec | 0.17 | 0.24 | 0.23 | 0.52 | 0.08 | 31.92 |
| compute_time_llm_latency_sum_sec | 0.13 | 18.27 | 0.23 | 120.53 | 38.67 | 211.66 |

Seeds 20 shared with the earlier run: 20 identical weekly profit (to 1 cent), max difference 0.00 USD, mean 0.00 USD.

### WAF (30 runs with output)

| metric | min | mean | median | max | std dev | cv % |
|---|---|---|---|---|---|---|
| weekly_profit_usd | 4,918,355 | 5,046,252 | 5,011,592 | 5,257,474 | 100,414 | 1.99 |
| weekly_revenue_usd | 11,952,200 | 12,263,387 | 12,273,470 | 12,610,850 | 191,144 | 1.56 |
| weekly_total_cost_usd | 6,939,588 | 7,217,134 | 7,221,952 | 7,510,401 | 129,168 | 1.79 |
| profit_margin_on_revenue | 0.40 | 0.41 | 0.41 | 0.42 | 0.005108 | 1.24 |
| coverage_pct | 76.92 | 79.71 | 80.14 | 82.75 | 1.38 | 1.74 |
| served_teu | 13,140 | 13,616 | 13,690 | 14,136 | 236.53 | 1.74 |
| unserved_teu | 2,946 | 3,466 | 3,392 | 3,942 | 236.53 | 6.83 |
| services_operated | 8.00 | 8.83 | 9.00 | 9.00 | 0.38 | 4.29 |
| departures_per_week | 8.00 | 8.93 | 9.00 | 9.00 | 0.25 | 2.84 |
| vessels_assigned | 30.00 | 31.10 | 31.00 | 32.00 | 0.48 | 1.55 |
| vessels_idle | 10.00 | 10.90 | 11.00 | 12.00 | 0.48 | 4.41 |
| deployment_ratio (vessel utilisation) | 0.71 | 0.74 | 0.74 | 0.76 | 0.01 | 1.55 |
| productive_load_factor (capacity utilisation) | 0.46 | 0.49 | 0.49 | 0.52 | 0.02 | 3.23 |
| profit_per_assigned_vessel_usd | 154,347 | 162,293 | 160,884 | 169,596 | 3,961 | 2.44 |
| pipeline_runtime_sec | 4.20 | 6.34 | 5.40 | 26.60 | 3.97 | 62.70 |
| driver_wall_sec | 5.40 | 7.61 | 6.65 | 28.00 | 4.01 | 52.73 |
| global_solver_integer_phase_sec | 0.13 | 0.32 | 0.28 | 0.61 | 0.12 | 37.15 |
| gap_to_lp_bound_pct | 5.44 | 7.40 | 7.18 | 10.20 | 1.35 | 18.23 |
| contribution_margin_usd | 9,165,057 | 9,386,263 | 9,368,985 | 9,613,933 | 141,277 | 1.51 |
| contribution_margin_per_teu_usd | 676.52 | 689.39 | 690.31 | 697.49 | 6.36 | 0.92 |
| contribution_margin_pct_of_revenue | 75.80 | 76.54 | 76.64 | 76.82 | 0.27 | 0.35 |
| teu_vessel_utilisation_average | 0.46 | 0.49 | 0.49 | 0.52 | 0.02 | 3.23 |
| teu_vessel_utilisation_min | 0.33 | 0.33 | 0.33 | 0.37 | 0.00999 | 3.00 |
| teu_vessel_utilisation_max | 0.62 | 0.76 | 0.75 | 0.88 | 0.08 | 10.38 |
| transit_time_days_average (TEU-weighted) | 9.38 | 9.55 | 9.53 | 9.87 | 0.12 | 1.31 |
| transit_time_days_min | 4.42 | 4.42 | 4.42 | 4.42 | 0.00 | 0.00 |
| transit_time_days_max | 18.00 | 18.00 | 18.00 | 18.22 | 0.04 | 0.23 |
| teu_through_transshipment | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | n/a |
| teu_through_transshipment_share_pct | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | n/a |
| transshipment_transfer_moves_teu | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | n/a |
| compute_time_pipeline_sec | 4.20 | 6.34 | 5.40 | 26.60 | 3.97 | 62.70 |
| compute_time_driver_wall_sec | 5.40 | 7.61 | 6.65 | 28.00 | 4.01 | 52.73 |
| compute_time_optimiser_plan_sec | 0.27 | 0.47 | 0.41 | 0.85 | 0.14 | 30.50 |
| compute_time_llm_latency_sum_sec | 0.38 | 0.53 | 0.46 | 1.25 | 0.19 | 36.28 |

Seeds 20 shared with the earlier run: 20 identical weekly profit (to 1 cent), max difference 0.00 USD, mean 0.00 USD.

### worldsmall (30 runs with output)

| metric | min | mean | median | max | std dev | cv % |
|---|---|---|---|---|---|---|
| weekly_profit_usd | 42,818,062 | 46,991,456 | 47,138,515 | 49,596,554 | 1,587,328 | 3.38 |
| weekly_revenue_usd | 134,298,890 | 144,658,454 | 145,769,110 | 151,557,890 | 4,755,981 | 3.29 |
| weekly_total_cost_usd | 89,849,984 | 97,666,998 | 98,594,300 | 105,986,568 | 4,295,114 | 4.40 |
| profit_margin_on_revenue | 0.30 | 0.33 | 0.33 | 0.35 | 0.01 | 3.50 |
| coverage_pct | 44.73 | 48.18 | 48.41 | 50.64 | 1.78 | 3.69 |
| served_teu | 123,674 | 133,211 | 133,846 | 140,026 | 4,921 | 3.69 |
| unserved_teu | 136,468 | 143,283 | 142,648 | 152,820 | 4,921 | 3.43 |
| services_operated | 25.00 | 30.10 | 30.00 | 34.00 | 2.01 | 6.66 |
| departures_per_week | 25.00 | 31.93 | 32.00 | 37.00 | 2.38 | 7.44 |
| vessels_assigned | 159.00 | 173.97 | 173.00 | 193.00 | 10.05 | 5.78 |
| vessels_idle | 70.00 | 89.03 | 90.00 | 104.00 | 10.05 | 11.29 |
| deployment_ratio (vessel utilisation) | 0.60 | 0.66 | 0.66 | 0.73 | 0.04 | 5.78 |
| productive_load_factor (capacity utilisation) | 0.53 | 0.56 | 0.55 | 0.60 | 0.02 | 3.76 |
| profit_per_assigned_vessel_usd | 234,858 | 271,068 | 271,213 | 308,788 | 19,207 | 7.09 |
| pipeline_runtime_sec | 375.00 | 412.12 | 399.75 | 516.80 | 35.99 | 8.73 |
| driver_wall_sec | 376.40 | 416.03 | 407.60 | 519.70 | 36.79 | 8.84 |
| global_solver_integer_phase_sec | 95.52 | 100.91 | 101.89 | 103.90 | 2.20 | 2.18 |
| gap_to_lp_bound_pct | 15.85 | 23.62 | 23.87 | 28.83 | 3.58 | 15.15 |
| contribution_margin_usd | 106,348,794 | 114,760,123 | 115,460,360 | 119,986,129 | 3,587,082 | 3.13 |
| contribution_margin_per_teu_usd | 842.35 | 861.74 | 860.37 | 889.62 | 12.34 | 1.43 |
| contribution_margin_pct_of_revenue | 78.72 | 79.34 | 79.26 | 79.96 | 0.36 | 0.46 |
| teu_vessel_utilisation_average | 0.53 | 0.56 | 0.55 | 0.60 | 0.02 | 3.76 |
| teu_vessel_utilisation_min | 0.07 | 0.24 | 0.24 | 0.43 | 0.11 | 44.23 |
| teu_vessel_utilisation_max | 0.76 | 0.89 | 0.88 | 1.00 | 0.07 | 8.06 |
| transit_time_days_average (TEU-weighted) | 22.53 | 22.98 | 22.94 | 23.59 | 0.25 | 1.09 |
| transit_time_days_min | 0.01 | 0.01 | 0.01 | 0.02 | 0.00225 | 15.79 |
| transit_time_days_max | 53.11 | 59.91 | 61.33 | 63.33 | 3.05 | 5.09 |
| teu_through_transshipment | 21,672 | 29,712 | 29,270 | 34,854 | 2,993 | 10.07 |
| teu_through_transshipment_share_pct | 17.13 | 22.28 | 22.28 | 26.05 | 1.84 | 8.26 |
| transshipment_transfer_moves_teu | 21,672 | 30,178 | 30,559 | 34,854 | 3,129 | 10.37 |
| compute_time_pipeline_sec | 375.00 | 412.12 | 399.75 | 516.80 | 35.99 | 8.73 |
| compute_time_driver_wall_sec | 376.40 | 416.03 | 407.60 | 519.70 | 36.79 | 8.84 |
| compute_time_optimiser_plan_sec | 108.75 | 114.42 | 114.64 | 117.25 | 2.44 | 2.13 |
| compute_time_llm_latency_sum_sec | 14.41 | 44.93 | 38.21 | 143.53 | 30.19 | 67.18 |

Seeds 20 shared with the earlier run: 7 identical weekly profit (to 1 cent), max difference 3,498,819 USD, mean 671,352 USD.

### world500 (30 runs with output)

| metric | min | mean | median | max | std dev | cv % |
|---|---|---|---|---|---|---|
| weekly_profit_usd | 169,602,830 | 172,044,723 | 172,377,666 | 173,913,068 | 1,206,735 | 0.70 |
| weekly_revenue_usd | 419,024,130 | 428,196,726 | 427,801,530 | 434,439,780 | 3,992,764 | 0.93 |
| weekly_total_cost_usd | 247,372,015 | 256,152,003 | 256,688,886 | 261,645,877 | 3,968,716 | 1.55 |
| profit_margin_on_revenue | 0.39 | 0.40 | 0.40 | 0.41 | 0.004303 | 1.07 |
| coverage_pct | 14.57 | 15.08 | 15.18 | 15.38 | 0.24 | 1.62 |
| served_teu | 393,804 | 407,470 | 410,306 | 415,470 | 6,588 | 1.62 |
| unserved_teu | 2,286,600 | 2,294,600 | 2,291,764 | 2,308,266 | 6,588 | 0.29 |
| services_operated | 72.00 | 76.63 | 76.00 | 81.00 | 1.96 | 2.55 |
| departures_per_week | 141.00 | 148.60 | 148.50 | 157.00 | 3.85 | 2.59 |
| vessels_assigned | 716.00 | 730.70 | 732.50 | 741.00 | 5.81 | 0.80 |
| vessels_idle | 1,829 | 1,839 | 1,838 | 1,854 | 5.81 | 0.32 |
| deployment_ratio (vessel utilisation) | 0.28 | 0.28 | 0.29 | 0.29 | 0.002262 | 0.80 |
| productive_load_factor (capacity utilisation) | 0.58 | 0.60 | 0.60 | 0.62 | 0.01 | 1.72 |
| profit_per_assigned_vessel_usd | 230,499 | 235,465 | 235,299 | 241,199 | 2,317 | 0.98 |
| pipeline_runtime_sec | 321.80 | 573.36 | 464.80 | 4,119 | 673.50 | 117.47 |
| driver_wall_sec | 325.60 | 578.48 | 469.95 | 4,123 | 673.43 | 116.41 |
| global_solver_integer_phase_sec | 67.88 | 94.41 | 98.50 | 102.87 | 9.91 | 10.49 |
| gap_to_lp_bound_pct | 16.67 | 17.87 | 17.70 | 20.42 | 0.79 | 4.40 |
| contribution_margin_usd | 329,968,158 | 337,126,703 | 336,713,917 | 343,268,698 | 3,137,190 | 0.93 |
| contribution_margin_per_teu_usd | 812.74 | 827.49 | 826.48 | 844.28 | 9.60 | 1.16 |
| contribution_margin_pct_of_revenue | 78.27 | 78.73 | 78.78 | 79.13 | 0.22 | 0.28 |
| teu_vessel_utilisation_average | 0.58 | 0.60 | 0.60 | 0.62 | 0.01 | 1.72 |
| teu_vessel_utilisation_min | 0.05 | 0.29 | 0.37 | 0.42 | 0.14 | 47.42 |
| teu_vessel_utilisation_max | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |
| transit_time_days_average (TEU-weighted) | 15.89 | 16.28 | 16.36 | 16.66 | 0.25 | 1.54 |
| transit_time_days_min | 0.17 | 0.20 | 0.20 | 0.20 | 0.007173 | 3.66 |
| transit_time_days_max | 67.88 | 69.24 | 69.27 | 69.65 | 0.27 | 0.39 |
| teu_through_transshipment | 3,588 | 8,741 | 9,694 | 18,032 | 3,919 | 44.83 |
| teu_through_transshipment_share_pct | 0.89 | 2.14 | 2.34 | 4.39 | 0.94 | 44.06 |
| transshipment_transfer_moves_teu | 3,676 | 9,481 | 9,920 | 19,778 | 4,160 | 43.87 |
| compute_time_pipeline_sec | 321.80 | 573.36 | 464.80 | 4,119 | 673.50 | 117.47 |
| compute_time_driver_wall_sec | 325.60 | 578.48 | 469.95 | 4,123 | 673.43 | 116.41 |
| compute_time_optimiser_plan_sec | 77.58 | 107.71 | 112.54 | 116.47 | 10.91 | 10.13 |
| compute_time_llm_latency_sum_sec | 46.86 | 113.53 | 118.45 | 275.49 | 59.41 | 52.33 |

Seeds 20 shared with the earlier run: 5 identical weekly profit (to 1 cent), max difference 4,245,632 USD, mean 1,044,599 USD.

Failed or killed runs: [{'seed': 1, 'exit_code': 1, 'killed_by_wall_cap': False, 'assertions_failed': 1}]

### world1000 (30 runs with output)

| metric | min | mean | median | max | std dev | cv % |
|---|---|---|---|---|---|---|
| weekly_profit_usd | 244,892,592 | 246,581,408 | 246,334,368 | 248,248,838 | 995,536 | 0.40 |
| weekly_revenue_usd | 629,435,740 | 633,235,181 | 633,241,050 | 638,479,830 | 2,281,640 | 0.36 |
| weekly_total_cost_usd | 384,114,184 | 386,653,774 | 386,152,539 | 390,527,931 | 1,791,370 | 0.46 |
| profit_margin_on_revenue | 0.39 | 0.39 | 0.39 | 0.39 | 0.001239 | 0.32 |
| coverage_pct | 12.80 | 12.91 | 12.92 | 13.04 | 0.07 | 0.54 |
| served_teu | 607,590 | 612,750 | 613,130 | 618,598 | 3,302 | 0.54 |
| unserved_teu | 4,126,680 | 4,132,528 | 4,132,148 | 4,137,688 | 3,302 | 0.08 |
| services_operated | 117.00 | 121.00 | 121.00 | 124.00 | 1.53 | 1.27 |
| departures_per_week | 198.00 | 203.33 | 204.00 | 208.00 | 2.44 | 1.20 |
| vessels_assigned | 1,163 | 1,166 | 1,166 | 1,174 | 2.80 | 0.24 |
| vessels_idle | 3,340 | 3,348 | 3,348 | 3,351 | 2.80 | 0.08 |
| deployment_ratio (vessel utilisation) | 0.26 | 0.26 | 0.26 | 0.26 | 0.0006203 | 0.24 |
| productive_load_factor (capacity utilisation) | 0.55 | 0.56 | 0.56 | 0.57 | 0.002938 | 0.52 |
| profit_per_assigned_vessel_usd | 210,075 | 211,435 | 211,262 | 213,096 | 851.44 | 0.40 |
| pipeline_runtime_sec | 326.20 | 353.18 | 339.35 | 457.10 | 30.06 | 8.51 |
| driver_wall_sec | 336.80 | 365.20 | 350.50 | 468.30 | 31.13 | 8.52 |
| global_solver_integer_phase_sec | 28.76 | 33.64 | 32.95 | 40.07 | 3.25 | 9.67 |
| gap_to_lp_bound_pct | 33.15 | 34.13 | 33.96 | 36.93 | 0.73 | 2.13 |
| contribution_margin_usd | 500,026,737 | 503,648,418 | 504,012,897 | 507,000,363 | 1,761,625 | 0.35 |
| contribution_margin_per_teu_usd | 815.42 | 821.96 | 822.62 | 826.31 | 3.89 | 0.47 |
| contribution_margin_pct_of_revenue | 79.29 | 79.54 | 79.54 | 79.69 | 0.11 | 0.13 |
| teu_vessel_utilisation_average | 0.55 | 0.56 | 0.56 | 0.57 | 0.002938 | 0.52 |
| teu_vessel_utilisation_min | 0.08 | 0.21 | 0.19 | 0.26 | 0.06 | 28.35 |
| teu_vessel_utilisation_max | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |
| transit_time_days_average (TEU-weighted) | 15.43 | 15.56 | 15.54 | 15.84 | 0.09 | 0.57 |
| transit_time_days_min | 0.28 | 0.38 | 0.38 | 0.38 | 0.02 | 4.74 |
| transit_time_days_max | 67.60 | 67.71 | 67.60 | 69.25 | 0.42 | 0.62 |
| teu_through_transshipment | 12,544 | 13,946 | 13,852 | 17,982 | 1,275 | 9.14 |
| teu_through_transshipment_share_pct | 2.06 | 2.28 | 2.25 | 2.94 | 0.21 | 9.03 |
| transshipment_transfer_moves_teu | 12,698 | 14,549 | 14,340 | 19,720 | 1,596 | 10.97 |
| compute_time_pipeline_sec | 326.20 | 353.18 | 339.35 | 457.10 | 30.06 | 8.51 |
| compute_time_driver_wall_sec | 336.80 | 365.20 | 350.50 | 468.30 | 31.13 | 8.52 |
| compute_time_optimiser_plan_sec | 70.21 | 77.80 | 77.62 | 84.86 | 3.48 | 4.48 |
| compute_time_llm_latency_sum_sec | 81.50 | 96.04 | 86.23 | 163.60 | 20.81 | 21.67 |

Seeds 20 shared with the earlier run: 12 identical weekly profit (to 1 cent), max difference 60,267,240 USD, mean 8,733,989 USD.

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
