#!/usr/bin/env bash
# Task 15 release gates: orchestrator test on the patched tree, sequential (one at a time).
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
cd "$PROJ"
T="$PROJ/reports/tasks_14_15_16/evidence/tools/snaprun.py"
ARGS="tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider"
NETWORK_MILP_BACKEND=highs python -I "$T" T15_orch_highs_run1 T15_orch_highs_run1 -- $ARGS
python -I "$T" T15_orch_default_run1 T15_orch_default_run1 -- $ARGS
NETWORK_MILP_BACKEND=highs python -I "$T" T15_orch_highs_run2 T15_orch_highs_run2 -- $ARGS
NETWORK_MILP_BACKEND=highs python -I "$T" T15_orch_highs_run3 T15_orch_highs_run3 -- $ARGS
echo GATES_DONE
