#!/usr/bin/env bash
# Fresh B0 baselines (frozen Tasks 14-16 final tree, no environment variable set): two clean
# end-to-end orchestrator runs.  Run 1 snapshots the live tree (taken before any Tasks 19-21
# edit); run 2 re-uses run 1's snapshot as its source so it cannot see later edits.
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
cd "$PROJ"
T="reports/tasks_19_20_21/evidence/tools/snaprun.py"
ARGS="tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider"
unset LINER_REGIONAL_FILTER NETWORK_MILP_BACKEND LINER_PATH_SELECTION LINER_MAX_TRANSFERS
python -I "$T" T19B0_orch_run1 T19B0_orch_run1 -- $ARGS
SNAP_SOURCE="D:/liner_scratch/snap_T19B0_orch_run1" python -I "$T" T19B0_orch_run2 T19B0_orch_run2 -- $ARGS
echo B0_ORCH_DONE
