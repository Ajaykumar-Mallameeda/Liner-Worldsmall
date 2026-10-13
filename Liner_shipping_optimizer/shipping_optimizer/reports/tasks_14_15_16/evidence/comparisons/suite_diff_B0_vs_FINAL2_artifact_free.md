## Counts
| tree | total | pass | FAIL | skip | xfail |
|---|---|---|---|---|---|
| B0 | 1240 | 1143 | 51 | 46 | 0 |
| FINAL2 | 1295 | 1198 | 51 | 46 | 0 |

## B0 -> FINAL2
- failing in both: 51
- newly failing in FINAL2 (pass/skip/xfail/absent in B0): 0
- fixed in FINAL2 (FAIL in B0, pass in FINAL2): 0
- other status changes: 0
- only in B0: 0
- only in FINAL2: 55
  - `tests.test_incumbent_vessel_trim.TestIncumbentVesselTrim::test_clean_incumbent_is_unchanged` [pass]
  - `tests.test_incumbent_vessel_trim.TestIncumbentVesselTrim::test_slack_vessels_are_trimmed_and_the_plan_reconciles` [pass]
  - `tests.test_incumbent_vessel_trim.TestIncumbentVesselTrim::test_trim_helper_is_a_noop_without_slack_and_never_adds_vessels` [pass]
  - `tests.test_incumbent_vessel_trim.TestIncumbentVesselTrim::test_trimming_never_touches_revenue_or_the_other_cost_terms` [pass]
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
  - `tests.test_milp_backend.TestBackendSelection::test_default_is_cbc` [pass]
  - `tests.test_milp_backend.TestBackendSelection::test_fixed_frequency_solves_stay_on_cbc` [pass]
  - `tests.test_milp_backend.TestBackendSelection::test_highs_matches_cbc_on_a_problem_both_can_close` [pass]
  - `tests.test_milp_backend.TestBackendSelection::test_unknown_backend_is_an_error_not_a_silent_cbc` [pass]
  - `tests.test_milp_backend.TestHighsStatusMapping::test_exception_is_a_solver_error` [pass]
  - `tests.test_milp_backend.TestHighsStatusMapping::test_infeasible` [pass]
  - `tests.test_milp_backend.TestHighsStatusMapping::test_no_incumbent_is_not_solved_with_the_backend_message` [pass]
  - `tests.test_milp_backend.TestHighsStatusMapping::test_optimal_with_a_loose_gap_is_not_called_optimal` [pass]
  - `tests.test_milp_backend.TestHighsStatusMapping::test_solver_noise_is_not_reported_as_a_flow_on_an_inactive_service` [pass]
  - `tests.test_milp_backend.TestHighsStatusMapping::test_time_limit_incumbent_is_feasible_with_the_dual_bound` [pass]
  - `tests.test_regional_filter.TestAgent::test_economic_filter_end_to_end` [pass]
  - `tests.test_regional_filter.TestAgent::test_economic_report_reconciles` [pass]
  - `tests.test_regional_filter.TestAgent::test_legacy_filter_is_unchanged_when_selected` [pass]
  - `tests.test_regional_filter.TestMode::test_auto_follows_the_task_9_10_generators` [pass]
  - `tests.test_regional_filter.TestMode::test_explicit_values_override_and_garbage_is_an_error` [pass]
  - `tests.test_regional_filter.TestSelectEconomic::test_cap_keeps_the_best_economics_not_the_first_generated` [pass]
  - `tests.test_regional_filter.TestSelectEconomic::test_demand_loops_are_exempt_and_do_not_use_cap_slots` [pass]
  - `tests.test_regional_filter.TestSelectEconomic::test_loss_making_candidates_are_not_dropped_while_the_cap_has_room` [pass]
  - `tests.test_regional_filter.TestSelectEconomic::test_no_class_is_named_or_treated_specially` [pass]
  - `tests.test_regional_filter.TestSelectEconomic::test_no_corridor_is_still_dropped_with_its_reason_counted` [pass]
  - `tests.test_regional_filter.TestSelectEconomic::test_ties_keep_generation_order_and_the_result_is_deterministic` [pass]
  - `tests.test_regional_filter.TestSelectEconomic::test_unavailable_economics_is_ranked_last_and_counted_never_zero` [pass]
