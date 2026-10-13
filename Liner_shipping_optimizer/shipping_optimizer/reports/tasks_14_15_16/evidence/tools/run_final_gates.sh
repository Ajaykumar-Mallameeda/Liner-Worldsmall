#!/usr/bin/env bash
# Final gates on the final tree (defaults: LINER_REGIONAL_FILTER unset -> auto -> economic while the
# Task 9/10 generators are on).  Waits for the HiGHS + economic combination run, then:
#   2 x orchestrator (default configuration), then the whole suite in the artifact-present state.
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
cd "$PROJ"
R="reports/tasks_14_15_16/evidence/runs"
until grep -q COMBO_DONE "$R/T16_gates_combo.driver.txt" 2>/dev/null; do sleep 5; done
T="reports/tasks_14_15_16/evidence/tools/snaprun.py"
ARGS="tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider"
unset LINER_REGIONAL_FILTER NETWORK_MILP_BACKEND
python -I "$T" FINAL2_orch_default_run1 FINAL2_orch_default_run1 -- $ARGS
python -I "$T" FINAL2_orch_default_run2 FINAL2_orch_default_run2 -- $ARGS
SNAP_SOURCE="D:/liner_scratch/snap_FINAL2_orch_default_run1" python -I "$T" FINAL2_suite_present FINAL2_suite_present -- tests --ignore=tests/test_orchestrator.py -q --tb=line -p no:cacheprovider "--junitxml=$R/FINAL2_suite_present.junit.xml"
echo FINAL_GATES_DONE
