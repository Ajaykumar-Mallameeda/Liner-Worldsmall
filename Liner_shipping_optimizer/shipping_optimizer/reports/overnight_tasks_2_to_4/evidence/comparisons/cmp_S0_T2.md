## Counts
| tree | total | pass | FAIL | skip | xfail |
|---|---|---|---|---|---|
| S0 | 940 | 856 | 56 | 20 | 8 |
| T2 | 963 | 878 | 57 | 20 | 8 |

## S0 -> T2
- failing in both: 56
- newly failing in T2 (pass/skip/xfail/absent in S0): 1
  - `tests.test_economic_metric_documentation::test_service_record_count_disagrees_with_headline`  [S0: pass]
- fixed in T2 (FAIL in S0, pass in T2): 0
- other status changes: 0
- only in S0: 0
- only in T2: 23
  - `tests.test_capacity_units.TestClassIdentity::test_both_fleet_files_name_the_same_classes` [pass]
  - `tests.test_capacity_units.TestClassIdentity::test_classes_missing_from_either_file_are_rejected` [pass]
  - `tests.test_capacity_units.TestClassIdentity::test_model_classes_are_those_names_and_lookup_returns_the_right_spec` [pass]
  - `tests.test_capacity_units.TestFieldInterpretation::test_canonical_capacities` [pass]
  - `tests.test_capacity_units.TestFieldInterpretation::test_every_class_capacity_equals_the_raw_column_value` [pass]
  - `tests.test_capacity_units.TestFieldInterpretation::test_synthetic_value_is_not_scaled` [pass]
  - `tests.test_capacity_units.TestMalformedCapacity::test_invalid_capacity_is_rejected_and_names_the_column[-450]` [pass]
  - `tests.test_capacity_units.TestMalformedCapacity::test_invalid_capacity_is_rejected_and_names_the_column[-inf]` [pass]
  - `tests.test_capacity_units.TestMalformedCapacity::test_invalid_capacity_is_rejected_and_names_the_column[0]` [pass]
  - `tests.test_capacity_units.TestMalformedCapacity::test_invalid_capacity_is_rejected_and_names_the_column[]` [pass]
  - `tests.test_capacity_units.TestMalformedCapacity::test_invalid_capacity_is_rejected_and_names_the_column[abc]` [pass]
  - `tests.test_capacity_units.TestMalformedCapacity::test_invalid_capacity_is_rejected_and_names_the_column[inf]` [pass]
  - `tests.test_capacity_units.TestMalformedCapacity::test_invalid_capacity_is_rejected_and_names_the_column[nan]` [pass]
  - `tests.test_capacity_units.TestMalformedCapacity::test_missing_capacity_column_is_rejected` [pass]
  - `tests.test_capacity_units.TestMalformedCapacity::test_rejected_capacity_never_produces_a_default_class` [pass]
  - `tests.test_capacity_units.TestProvisionalStatus::test_constants_declare_the_provisional_teu_reading` [pass]
  - `tests.test_capacity_units.TestProvisionalStatus::test_evidence_trail_is_recorded_and_states_no_unit_definition_was_found` [pass]
  - `tests.test_capacity_units.TestProvisionalStatus::test_hand_built_fleet_defaults_to_provisional` [pass]
  - `tests.test_capacity_units.TestProvisionalStatus::test_loaded_fleet_carries_the_status` [pass]
  - `tests.test_capacity_units.TestProvisionalStatus::test_problem_built_by_the_loader_exposes_the_status` [pass]
  - `tests.test_capacity_units.TestProvisionalStatus::test_report_copy_cannot_mutate_the_module_constant` [pass]
  - `tests.test_capacity_units.TestProvisionalStatus::test_validation_report_states_the_assumption` [pass]
  - `tests.test_capacity_units.TestProvisionalStatus::test_verified_status_requires_an_authoritative_source` [pass]
