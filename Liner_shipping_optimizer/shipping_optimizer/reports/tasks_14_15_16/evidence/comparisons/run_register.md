# Run register (every recorded test / benchmark run)

LLM rate limits (HTTP 429) are ignored by design: the deterministic fallback text is used and its
count is recorded per run below. Commands are `python -m pytest ...` from the snapshot tree.

| label | exit | elapsed s | assertions / summary | profit USD/wk | margin % | coverage % | services | vessels | mode | 429 |
|---|---:|---:|---|---:|---:|---:|---:|---:|---|---:|
| B0_orch1 | 0 | 373 | 342/342 (failed 0) | 8,710,134 | 13.32 | 20.06 | 17 | 120 | legacy_uniform|60|per_rotation_screening | 0 |
| B0_suite_free | 1 | 124 | 51 failed, 1143 passed, 46 skipped, 44 warnings in 119.67s (0:01:59) |  |  |  |  |  |  |  |
| B0_suite_present | 1 | 72 | 53 failed, 1167 passed, 20 skipped, 44 warnings in 69.33s (0:01:09) | 8,710,134 | 13.32 | 20.06 | 17 | 120 | legacy_uniform|60|per_rotation_screening | 0 |
| FINAL2_orch_default_run1 | 0 | 396 | 342/342 (failed 0) | 10,332,387 | 13.30 | 24.48 | 25 | 143 | legacy_uniform|60|per_rotation_screening | 2 |
| FINAL2_orch_default_run2 | 0 | 384 | 342/342 (failed 0) | 11,415,021 | 14.43 | 24.57 | 27 | 157 | legacy_uniform|60|per_rotation_screening | 2 |
| FINAL2_suite_free | 1 | 121 | 51 failed, 1198 passed, 46 skipped, 44 warnings in 118.60s (0:01:58) |  |  |  |  |  |  |  |
| FINAL2_suite_present | 1 | 58 | 53 failed, 1222 passed, 20 skipped, 44 warnings in 56.54s | 10,332,387 | 13.30 | 24.48 | 25 | 143 | legacy_uniform|60|per_rotation_screening | 2 |
| FINAL_suite_free | 1 | 75 | 51 failed, 1198 passed, 46 skipped, 44 warnings in 72.57s (0:01:12) |  |  |  |  |  |  |  |
| FINAL_tree | 0 | 0 |  |  |  |  |  |  |  |  |
| T14_orch1 | 0 | 398 | 342/342 (failed 0) | 9,192,548 | 14.67 | 19.47 | 19 | 121 | legacy_uniform|60|per_rotation_screening | 2 |
| T14_suite_free | 1 | 136 | 51 failed, 1172 passed, 46 skipped, 44 warnings in 131.24s (0:02:11) |  |  |  |  |  |  |  |
| T15_orch_default_run1 | 0 | 395 | 342/342 (failed 0) | 8,479,961 | 13.19 | 19.68 | 16 | 111 | legacy_uniform|60|per_rotation_screening | 2 |
| T15_orch_highs_run1 | 0 | 313 | 342/342 (failed 0) | 9,596,995 | 14.03 | 20.91 | 17 | 124 | legacy_uniform|60|per_rotation_screening | 2 |
| T15_orch_highs_run2 | 0 | 335 | 342/342 (failed 0) | 10,568,425 | 16.18 | 20.07 | 17 | 121 | legacy_uniform|60|per_rotation_screening | 2 |
| T15_orch_highs_run3 | 1 | 318 | 341/342 (failed 1) | 10,037,850 | 16.30 | 18.56 | 16 | 112 | legacy_uniform|60|per_rotation_screening | 2 |
| T15A_tree | 0 | 0 |  |  |  |  |  |  |  |  |
| T15AB2_tree | 0 | 0 |  |  |  |  |  |  |  |  |
| T15AB_tree | 0 | 0 |  |  |  |  |  |  |  |  |
| T15g2_orch_default_run1 | 0 | 445 | 342/342 (failed 0) | 9,055,647 | 15.11 | 17.77 | 14 | 103 | legacy_uniform|60|per_rotation_screening | 1 |
| T15g2_orch_highs_run1 | 0 | 271 | 342/342 (failed 0) | 10,473,832 | 15.99 | 19.71 | 18 | 124 | legacy_uniform|60|per_rotation_screening | 3 |
| T15g2_orch_highs_run2 | 0 | 354 | 342/342 (failed 0) | 9,728,676 | 14.77 | 20.84 | 21 | 123 | legacy_uniform|60|per_rotation_screening | 2 |
| T15g2_orch_highs_run3 | 0 | 330 | 342/342 (failed 0) | 10,309,927 | 15.57 | 20.53 | 15 | 119 | legacy_uniform|60|per_rotation_screening | 2 |
| T16g_orch_econ_highs_run1 | 0 | 403 | 342/342 (failed 0) | 9,819,024 | 17.84 | 17.59 | 16 | 92 | legacy_uniform|60|per_rotation_screening | 2 |
| T16g_orch_econ_run1 | 0 | 444 | 342/342 (failed 0) | 10,849,359 | 14.12 | 23.69 | 25 | 142 | legacy_uniform|60|per_rotation_screening | 2 |
| T16g_orch_econ_run2 | 0 | 484 | 342/342 (failed 0) | 9,978,633 | 13.06 | 23.73 | 27 | 150 | legacy_uniform|60|per_rotation_screening | 1 |
| T16g_orch_econ_run3 | 0 | 410 | 342/342 (failed 0) | 11,816,105 | 15.51 | 24.01 | 25 | 133 | legacy_uniform|60|per_rotation_screening | 2 |
| T16prod_tree | 0 | 0 |  |  |  |  |  |  |  |  |
