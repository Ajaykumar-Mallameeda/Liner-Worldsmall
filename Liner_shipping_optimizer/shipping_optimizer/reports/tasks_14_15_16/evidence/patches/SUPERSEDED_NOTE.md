# Superseded patch

`task16_economic_regional_filter_opt_in.patch` (and its `.sha256`) is the **first** version of the Task 16 change, in
which the economic filter was opt-in (`LINER_REGIONAL_FILTER` default `legacy`). It was superseded after the end-to-end
gates (`T16g_orch_econ_run1..3`: 10.85 / 9.98 / 11.82 M against 8.48 - 9.19 M for seven legacy runs) by
`task16_economic_regional_filter_default.patch` (default `auto`: economic while the Task 9/10 generators are on, legacy when
both are off; `tests/test_class_screening.py` pins the legacy filter in the one Task 10 test that encodes it).

Apply `task16_economic_regional_filter_default.patch`, not the opt-in one. The old file is kept only because files in this
project are never deleted.
