#!/usr/bin/env bash
# Task 15 release gates, second round (after the solver-noise flow fix).  The Task 16 filter
# code is present in the tree, so the legacy filter is selected explicitly: this round gates
# Task 15 only.
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
cd "$PROJ"
T="$PROJ/reports/tasks_14_15_16/evidence/tools/snaprun.py"
ARGS="tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider"
export LINER_REGIONAL_FILTER=legacy
NETWORK_MILP_BACKEND=highs python -I "$T" T15g2_orch_highs_run1 T15g2_orch_highs_run1 -- $ARGS
NETWORK_MILP_BACKEND=highs python -I "$T" T15g2_orch_highs_run2 T15g2_orch_highs_run2 -- $ARGS
NETWORK_MILP_BACKEND=highs python -I "$T" T15g2_orch_highs_run3 T15g2_orch_highs_run3 -- $ARGS
python -I "$T" T15g2_orch_default_run1 T15g2_orch_default_run1 -- $ARGS
echo GATES2_DONE
