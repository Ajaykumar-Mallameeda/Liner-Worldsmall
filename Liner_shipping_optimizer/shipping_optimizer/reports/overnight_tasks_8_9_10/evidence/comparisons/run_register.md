# Run register (every recorded test / benchmark run)

LLM rate limits (HTTP 429) are ignored by design: the deterministic fallback text is used and its
count is recorded per run below. Commands are `python -m pytest ...` from the snapshot tree.

| label | exit | elapsed s | assertions / summary | profit USD/wk | margin % | coverage % | services | vessels | mode | 429 |
|---|---:|---:|---|---:|---:|---:|---:|---:|---|---:|
| FINAL2_default_run1 | 0 | 306 | 342/342 (failed 0) | 8,990,629 | 13.91 | 20.04 | 16 | 107 | legacy_uniform|60|per_rotation_screening | 2 |
| FINAL2_default_run2 | 0 | 234 | 342/342 (failed 0) | 10,927,221 | 16.06 | 21.36 | 19 | 119 | legacy_uniform|60|per_rotation_screening | 3 |
| FINAL2_default_run3 | 0 | 378 | 342/342 (failed 0) | 8,321,834 | 13.96 | 18.11 | 14 | 97 | legacy_uniform|60|per_rotation_screening | 2 |
| FINAL2_suite_artifact_free | 1 | 54 | 54 failed, 1130 passed, 46 skipped, 44 warnings in 50.85s |  |  |  |  |  |  |  |
| FINAL2_suite_artifact_present | 1 | 124 | 56 failed, 1154 passed, 20 skipped, 44 warnings in 120.77s (0:02:00) |  |  |  |  |  |  |  |
| FINAL3_default_run1 | 0 | 322 | 342/342 (failed 0) | 9,144,819 | 15.13 | 19.07 | 18 | 113 | legacy_uniform|60|per_rotation_screening | 3 |
| FINAL3_suite_artifact_free | 1 | 73 | 52 failed, 1132 passed, 46 skipped, 44 warnings in 70.61s (0:01:10) |  |  |  |  |  |  |  |
| FINAL4_default_run1 | 0 | 491 | 342/342 (failed 0) | 8,960,065 | 14.75 | 18.47 | 18 | 121 | legacy_uniform|60|per_rotation_screening | 3 |
| FINAL4_default_run2 | 4294967295 | 319 |  |  |  |  |  |  |  |  |
| FINAL5_default_run1 | 4294967295 | 223 |  |  |  |  |  |  |  |  |
| FINAL6_default_run1 | 0 | 343 | 342/342 (failed 0) | 9,518,241 | 13.91 | 21.15 | 22 | 136 | legacy_uniform|60|per_rotation_screening | 3 |
| FINAL6_default_run2 | 1 | 466 | 1 failed, 1 warning in 463.73s (0:07:43) =================== |  |  |  |  |  |  |  |
| FINAL6_default_run3 | 120 | 466 |  |  |  |  |  |  |  |  |
| FINAL6_suite_artifact_free | 1 | 116 | 51 failed, 1140 passed, 46 skipped, 44 warnings in 111.86s (0:01:51) |  |  |  |  |  |  |  |
| FINAL6_suite_artifact_present | 1 | 122 | 53 failed, 1164 passed, 20 skipped, 44 warnings in 118.24s (0:01:58) |  |  |  |  |  |  |  |
| FINAL7_default_run1 | 0 | 393 | 342/342 (failed 0) | 9,022,634 | 14.17 | 18.85 | 15 | 109 | legacy_uniform|60|per_rotation_screening | 0 |
| FINAL7_default_run2 | 0 | 298 | 342/342 (failed 0) | 9,112,217 | 13.90 | 20.05 | 17 | 113 | legacy_uniform|60|per_rotation_screening | 2 |
| FINAL7_default_run3 | 0 | 332 | 342/342 (failed 0) | 9,034,492 | 11.78 | 24.37 | 22 | 143 | legacy_uniform|60|per_rotation_screening | 2 |
| FINAL7_regional_run1 | 0 | 77 | 349/349 (failed 0) | 4,543,626 | 13.78 | 10.50 | 8 | 52 | regional_snapshot|60|per_rotation_screening | 3 |
| FINAL7_regional_run2 | 0 | 124 | 349/349 (failed 0) | 3,941,472 | 9.83 | 12.88 | 9 | 58 | regional_snapshot|60|per_rotation_screening | 3 |
| FINAL7_regional_run3 | 0 | 100 | 349/349 (failed 0) | 4,258,037 | 12.20 | 11.05 | 7 | 45 | regional_snapshot|60|per_rotation_screening | 3 |
| FINAL7_suite_artifact_free | 1 | 55 | 51 failed, 1143 passed, 46 skipped, 44 warnings in 52.95s |  |  |  |  |  |  |  |
| FINAL7_suite_artifact_present | 1 | 61 | 53 failed, 1167 passed, 20 skipped, 44 warnings in 59.13s |  |  |  |  |  |  |  |
| FINAL_default_run1 | 0 | 259 | 342/342 (failed 0) | 9,273,684 | 14.72 | 19.50 | 17 | 109 | legacy_uniform|60|per_rotation_screening | 3 |
| FINAL_default_run2 | 0 | 360 | 342/342 (failed 0) | 8,908,682 | 14.39 | 19.28 | 19 | 116 | legacy_uniform|60|per_rotation_screening | 2 |
| FINAL_suite_artifact_free | 1 | 48 | 54 failed, 1130 passed, 46 skipped, 44 warnings in 45.53s |  |  |  |  |  |  |  |
| FINAL_suite_artifact_present | 1 | 53 | 56 failed, 1154 passed, 20 skipped, 44 warnings in 49.50s |  |  |  |  |  |  |  |
| HUB_focus1 | 1 | 51 | 3 failed, 102 passed, 1 warning in 49.34s |  |  |  |  |  |  |  |
| LEGACY4_run1 | 0 | 109 | 342/342 (failed 0) | 3,789,962 | 13.18 | 8.13 | 9 | 36 | legacy_uniform|0|legacy_nearest_capacity | 3 |
| LEGACY4_run2 | 0 | 113 | 342/342 (failed 0) | 4,693,627 | 13.86 | 10.01 | 11 | 42 | legacy_uniform|0|legacy_nearest_capacity | 3 |
| LEGACY6_run1 | 0 | 82 | 342/342 (failed 0) | 2,342,117 | 8.68 | 7.68 | 8 | 38 | legacy_uniform|0|legacy_nearest_capacity | 3 |
| LEGACY6_run2 | 0 | 107 | 342/342 (failed 0) | 3,441,048 | 12.03 | 8.74 | 10 | 36 | legacy_uniform|0|legacy_nearest_capacity | 3 |
| LEGACY6_run3 | 0 | 65 | 342/342 (failed 0) | 3,210,678 | 11.48 | 8.21 | 10 | 36 | legacy_uniform|0|legacy_nearest_capacity | 3 |
| LEGACYCFG_run1 | 0 | 152 | 342/342 (failed 0) | 3,192,661 | 11.43 | 8.18 | 10 | 36 | legacy_uniform|0|legacy_nearest_capacity | 3 |
| LEGACYCFG_run2 | 0 | 91 | 342/342 (failed 0) | 1,177,379 | 4.46 | 7.48 | 8 | 39 | legacy_uniform|0|legacy_nearest_capacity | 3 |
| LEGACYCFG_run3 | 0 | 97 | 342/342 (failed 0) | 4,234,465 | 11.66 | 10.70 | 13 | 50 | legacy_uniform|0|legacy_nearest_capacity | 3 |
| M0_orch | 0 | 206 | 310/310 (failed 0) | 2,671,085 | 11.48 | 6.50 | 8 | 40 | None|None|None | 0 |
| M0_suite_artifact_free | 1 | 129 | 52 failed, 979 passed, 43 skipped, 44 warnings in 124.78s (0:02:04) |  |  |  |  |  |  |  |
| M0_suite_artifact_present | 1 | 69 | 53 failed, 1001 passed, 20 skipped, 44 warnings in 64.31s (0:01:04) |  |  |  |  |  |  |  |
| OWN_focus1 | 0 | 8 | 64 passed, 3 skipped, 1 warning in 6.01s |  |  |  |  |  |  |  |
| OWN_focus2 | 1 | 12 | 1 failed, 95 passed, 3 skipped, 1 warning in 10.52s |  |  |  |  |  |  |  |
| OWN_focus3 | 0 | 12 | 96 passed, 3 skipped, 1 warning in 10.15s |  |  |  |  |  |  |  |
| PR_focus2_fin | 1 | 24 | 29 failed, 236 passed, 14 skipped, 1 warning in 22.45s |  |  |  |  |  |  |  |
| PR_focus_fin8 | 1 | 22 | 30 failed, 234 passed, 14 skipped, 1 warning in 22.27s |  |  |  |  |  |  |  |
| T10_focus1 | 1 | 14 | 3 failed, 143 passed, 1 warning in 11.89s |  |  |  |  |  |  |  |
| T10_focus10 | 1 | 24 | 32 failed, 273 passed, 9 skipped, 1 warning in 21.66s |  |  |  |  |  |  |  |
| T10_focus2 | 0 | 4 | 26 passed, 1 warning in 2.71s |  |  |  |  |  |  |  |
| T10_focus3 | 0 | 14 | 126 passed, 1 warning in 12.20s |  |  |  |  |  |  |  |
| T10_focus4 | 1 | 6 | 1 failed, 34 passed, 1 warning in 4.73s |  |  |  |  |  |  |  |
| T10_focus5 | 0 | 7 | 62 passed, 1 warning in 6.07s |  |  |  |  |  |  |  |
| T10_focus6 | 1 | 57 | 5 failed, 199 passed, 1 warning in 52.88s |  |  |  |  |  |  |  |
| T10_focus7 | 1 | 10 | 4 failed, 163 passed, 1 warning in 8.65s |  |  |  |  |  |  |  |
| T10_focus8 | 1 | 6 | 3 failed, 69 passed, 1 warning in 4.49s |  |  |  |  |  |  |  |
| T10_focus9 | 0 | 10 | 62 passed, 1 warning in 8.44s |  |  |  |  |  |  |  |
| T8A_focus1 | 1 | 9 | 33 failed, 66 passed, 14 skipped, 1 warning in 7.25s |  |  |  |  |  |  |  |
| T8A_focus2 | 0 | 5 | 50 passed, 5 skipped, 1 warning in 3.81s |  |  |  |  |  |  |  |
| T8A_orch1 | 0 | 173 | 327/327 (failed 0) | 2,720,552 | 8.67 | 9.26 | 10 | 44 | None|None|None | 0 |
| T8B_focus1 | 0 | 6 | 112 passed, 3 skipped, 1 warning in 4.33s |  |  |  |  |  |  |  |
| T8B_orch1_legacy | 0 | 199 | 332/332 (failed 0) | 2,565,240 | 9.32 | 8.31 | 9 | 35 | legacy_uniform|None|None | 0 |
| T8B_orch2_regional | 1 | 169 | 337/339 (failed 2) | 147,947 | 2.84 | 1.65 | 1 | 7 | regional_snapshot|None|None | 0 |
| T9_focus1 | 0 | 7 | 25 passed, 1 warning in 5.17s |  |  |  |  |  |  |  |
| T9_focus2 | 0 | 10 | 54 passed, 1 warning in 7.62s |  |  |  |  |  |  |  |
| T9_orch1_loops60 | 1 | 113 | 341/342 (failed 1) | 6,436,749 | 13.99 | 13.80 | 12 | 85 | legacy_uniform|60|legacy_nearest_capacity | 2 |
| T9_orch2_loops60_ownership | 0 | 212 | 342/342 (failed 0) | 7,063,480 | 14.76 | 13.45 | 9 | 71 | legacy_uniform|60|legacy_nearest_capacity | 2 |
| T9ONLY4_run1 | 1 | 135 | 341/342 (failed 1) | 6,991,216 | 14.05 | 14.00 | 11 | 79 | legacy_uniform|60|legacy_nearest_capacity | 3 |
| T9ONLY5_run1 | 1 | 92 | 341/342 (failed 1) | 6,129,843 | 13.36 | 13.62 | 14 | 82 | legacy_uniform|60|legacy_nearest_capacity | 3 |
| T9ONLY6_run1 | 0 | 106 | 342/342 (failed 0) | 6,439,113 | 13.18 | 14.37 | 12 | 81 | legacy_uniform|60|legacy_nearest_capacity | 3 |
| T9ONLY6_run2 | 0 | 96 | 342/342 (failed 0) | 5,795,266 | 13.17 | 12.55 | 11 | 79 | legacy_uniform|60|legacy_nearest_capacity | 3 |
| T9ONLY_run2 | 0 | 82 | 342/342 (failed 0) | 6,251,805 | 14.92 | 12.12 | 13 | 71 | legacy_uniform|60|legacy_nearest_capacity | 3 |
