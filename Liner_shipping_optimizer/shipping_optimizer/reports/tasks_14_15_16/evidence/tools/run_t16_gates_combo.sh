#!/usr/bin/env bash
# One end-to-end run of the combination the data says needs a longer budget: HiGHS + economic
# filter at the production 120 s global-stage limit (waits for the Task 16 gate chain).
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
cd "$PROJ"
until grep -q T16GATES_DONE "$PROJ/reports/tasks_14_15_16/evidence/runs/T16_gates.driver.txt" 2>/dev/null; do sleep 5; done
T="$PROJ/reports/tasks_14_15_16/evidence/tools/snaprun.py"
ARGS="tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider"
LINER_REGIONAL_FILTER=economic NETWORK_MILP_BACKEND=highs python -I "$T" T16g_orch_econ_highs_run1 T16g_orch_econ_highs_run1 -- $ARGS
echo COMBO_DONE
