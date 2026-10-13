## Counts
| tree | total | pass | FAIL | skip | xfail |
|---|---|---|---|---|---|
| B0 | 1240 | 1143 | 51 | 46 | 0 |
| T14 | 1269 | 1172 | 51 | 46 | 0 |

## B0 -> T14
- failing in both: 51
- newly failing in T14 (pass/skip/xfail/absent in B0): 0
- fixed in T14 (FAIL in B0, pass in T14): 0
- other status changes: 0
- only in B0: 0
- only in T14: 29
  - `tests.test_margin_verdict.TestClassifier::test_a_loss_reports_the_negative_margin` [pass]
  - `tests.test_margin_verdict.TestClassifier::test_above_target` [pass]
  - `tests.test_margin_verdict.TestClassifier::test_below_target_is_advisory_and_keeps_the_real_margin` [pass]
  - `tests.test_margin_verdict.TestClassifier::test_exactly_at_target_is_at_or_above` [pass]
  - `tests.test_margin_verdict.TestClassifier::test_labels` [pass]
  - `tests.test_margin_verdict.TestClassifier::test_no_revenue_means_no_margin_not_zero` [pass]
  - `tests.test_margin_verdict.TestClassifier::test_the_target_is_defined_once_and_is_15_percent` [pass]
  - `tests.test_margin_verdict.TestClassifier::test_unverified_accounting_exposes_no_margin_even_if_one_is_passed[False]` [pass]
  - `tests.test_margin_verdict.TestClassifier::test_unverified_accounting_exposes_no_margin_even_if_one_is_passed[None]` [pass]
  - `tests.test_margin_verdict.TestCoordinator::test_below_target_network_keeps_feasible_verified_and_positive` [pass]
  - `tests.test_margin_verdict.TestCoordinator::test_loss_is_reported_with_the_real_negative_margin` [pass]
  - `tests.test_margin_verdict.TestCoordinator::test_margin_at_exactly_15_earns_the_point_like_a_higher_margin` [pass]
  - `tests.test_margin_verdict.TestCoordinator::test_margin_does_not_create_a_rerun_or_change_the_feedback` [pass]
  - `tests.test_margin_verdict.TestCoordinator::test_unverified_ledger_exposes_no_margin_or_profitability_claim` [pass]
  - `tests.test_margin_verdict.TestCoordinator::test_without_a_ledger_the_regional_margin_earns_no_point` [pass]
  - `tests.test_margin_verdict.TestCoordinator::test_zero_revenue_has_no_margin_and_no_fabricated_ratio` [pass]
  - `tests.test_margin_verdict.TestIterationSelection::test_a_real_margin_beats_an_undefined_one_on_the_tie_break` [pass]
  - `tests.test_margin_verdict.TestIterationSelection::test_a_single_below_target_iteration_is_selected_not_rejected` [pass]
  - `tests.test_margin_verdict.TestIterationSelection::test_higher_profit_wins_even_with_the_lower_margin` [pass]
  - `tests.test_margin_verdict.TestIterationSelection::test_llm_prompt_is_built_with_an_undefined_margin` [pass]
  - `tests.test_margin_verdict.TestIterationSelection::test_selection_uses_all_in_cost_not_vessel_hire` [pass]
  - `tests.test_margin_verdict.TestIterationSelection::test_undefined_margin_stays_none_on_the_scorecard` [pass]
  - `tests.test_margin_verdict.TestIterationSelection::test_unverified_iteration_exposes_no_verified_margin` [pass]
  - `tests.test_margin_verdict.TestReportWriters::test_at_target_and_above` [pass]
  - `tests.test_margin_verdict.TestReportWriters::test_below_target_is_labelled_poor_and_says_it_is_advisory` [pass]
  - `tests.test_margin_verdict.TestReportWriters::test_loss` [pass]
  - `tests.test_margin_verdict.TestReportWriters::test_regional_explanation_boundaries` [pass]
  - `tests.test_margin_verdict.TestReportWriters::test_unverified_is_not_labelled_good_or_poor` [pass]
  - `tests.test_margin_verdict.TestReportWriters::test_zero_revenue_is_undefined` [pass]
