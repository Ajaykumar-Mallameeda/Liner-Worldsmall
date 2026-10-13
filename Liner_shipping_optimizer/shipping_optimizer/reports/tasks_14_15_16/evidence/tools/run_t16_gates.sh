#!/usr/bin/env bash
# Task 16 release gates: orchestrator with the economic filter (opt-in), default CBC solver,
# sequential; then the whole-suite comparison on the final tree.  Waits for the Task 15
# gate round to finish first (one orchestrator at a time).
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
cd "$PROJ"
until grep -q GATES2_DONE "$PROJ/reports/tasks_14_15_16/evidence/runs/T15_gates2.driver.txt" 2>/dev/null; do sleep 5; done
T="$PROJ/reports/tasks_14_15_16/evidence/tools/snaprun.py"
ARGS="tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider"
R="$PROJ/reports/tasks_14_15_16/evidence/runs"
for i in 1 2 3; do
  LINER_REGIONAL_FILTER=economic python -I "$T" T16g_orch_econ_run$i T16g_orch_econ_run$i -- $ARGS
done
# whole suite (without the orchestrator), final tree, defaults: artifact-free
python -I "$T" FINAL_suite_free FINAL_suite_free -- tests --ignore=tests/test_orchestrator.py -q --tb=line -p no:cacheprovider "--junitxml=$R/FINAL_suite_free.junit.xml"
echo T16GATES_DONE
