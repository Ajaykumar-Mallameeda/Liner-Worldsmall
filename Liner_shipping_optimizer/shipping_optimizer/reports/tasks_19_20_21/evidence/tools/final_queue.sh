#!/usr/bin/env bash
# Final validation queue on the FROZEN final snapshot (D:/liner_scratch/snap_T19_final).
# Every batch waits for an idle machine first (wait_idle.ps1); every batch carries its own reference.
#   S1  whole suite, artifact-free:   baseline B0 tree vs final tree
#   O1  orchestrator x3, accepted default (no switch)
#   O2  orchestrator x1, documented rollback (explicit switches) - must behave as the frozen B0
#   M7  controlled, CBC 120 s, seeds 0-9:  RB (rollback = B0)  vs  D (default)
#   O3  orchestrator x1 HiGHS opt-in (120 s) and x1 HiGHS opt-in 300 s (experimental, not the default)
#   M8  controlled, HiGHS 300 s, seeds 0-4: RB vs D
#   M9  iteration experiment (3 iterations/seed), CBC 120 s, seeds 0-4: D vs DEL (elitism) vs DELOP
#   M10 coverage-floor frontier on D, CBC 120 s, seeds 0-9: prod vs cov25 (LINER_GLOBAL_MIN_COVERAGE)
#   S2  whole suite, artifact-present: baseline vs final
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
cd "$PROJ"
EV=reports/tasks_19_20_21/evidence
SNAPF="D:/liner_scratch/snap_T19_final"
SNAPB="D:/liner_scratch/snap_T19B0_orch_run1"
SR="python -I $EV/tools/snaprun.py"
idle() { powershell -NoProfile -ExecutionPolicy Bypass -File "$EV/tools/wait_idle.ps1" -MaxMinutes 45; }
note() { echo "[$(date +%H:%M:%S)] $*"; }
clean_env() { unset LINER_FLOW_REOPT LINER_PROFIT_FLOOR_REPAIR LINER_MAX_TRANSFERS LINER_PATH_SELECTION \
  LINER_PATH_BUDGET LINER_CLASS_TIME_FEASIBLE LINER_ROUTE_OPERATORS LINER_ELITISM NETWORK_MILP_BACKEND \
  GLOBAL_STAGE_TIME_LIMIT_SEC LINER_GLOBAL_MIN_COVERAGE LINER_REGIONAL_FILTER LINER_DEMAND_LOOP_BUDGET LINER_CLASS_SCREEN; }
SUITE="tests --ignore=tests/test_orchestrator.py -q --tb=line -p no:cacheprovider"
ORCH="tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider"

note S1; idle; clean_env
SNAP_EXCLUDE=pipeline_output.json SNAP_SOURCE="$SNAPB" $SR T19S_B0_free T19S_B0_free -- $SUITE "--junitxml=$EV/runs/T19S_B0_free.junit.xml"
idle; SNAP_EXCLUDE=pipeline_output.json SNAP_SOURCE="$SNAPF" $SR T19S_final_free T19S_final_free -- $SUITE "--junitxml=$EV/runs/T19S_final_free.junit.xml"

note O1
for i in 1 2 3; do
  idle; clean_env
  SNAP_SOURCE="$SNAPF" $SR T19O_default_run$i T19O_default_run$i -- $ORCH
done

note O2
idle; clean_env
export LINER_FLOW_REOPT=0 LINER_PROFIT_FLOOR_REPAIR=0 LINER_MAX_TRANSFERS=1 LINER_PATH_SELECTION=fastest \
       LINER_PATH_BUDGET=fixed LINER_CLASS_TIME_FEASIBLE=0 LINER_ROUTE_OPERATORS=0 LINER_ELITISM=0
SNAP_SOURCE="$SNAPF" $SR T19O_rollback_run1 T19O_rollback_run1 -- $ORCH
clean_env

note M7
idle; bash $EV/tools/run_jobs4.sh "$SNAPF" M7 4 "0 1 2 3 4 5 6 7 8 9" "RB D" cbc 120 > $EV/runs/M7.driver.txt 2>&1

note O3
idle; clean_env; export NETWORK_MILP_BACKEND=highs
SNAP_SOURCE="$SNAPF" $SR T19O_highs120_run1 T19O_highs120_run1 -- $ORCH
idle; clean_env; export NETWORK_MILP_BACKEND=highs GLOBAL_STAGE_TIME_LIMIT_SEC=300
SNAP_SOURCE="$SNAPF" $SR T19O_highs300_run1 T19O_highs300_run1 -- $ORCH
clean_env

note M8
idle; bash $EV/tools/run_jobs4.sh "$SNAPF" M8 4 "0 1 2 3 4" "RB D" highs 300 > $EV/runs/M8.driver.txt 2>&1

note M9
idle; bash $EV/tools/run_iter_jobs4.sh "$SNAPF" M9 4 "0 1 2 3 4" "D DEL DELOP" cbc 120 > $EV/runs/M9.driver.txt 2>&1

note M10
idle; bash $EV/tools/run_jobs4.sh "$SNAPF" M10 4 "0 1 2 3 4 5 6 7 8 9" "DCOV25" cbc 120 > $EV/runs/M10.driver.txt 2>&1

note S2
# artifact-present state: the snapshot of a real orchestrator run (it holds pipeline_output.json at its root)
idle; clean_env
SNAP_SOURCE="$SNAPB" $SR T19S_B0_present T19S_B0_present -- $SUITE "--junitxml=$EV/runs/T19S_B0_present.junit.xml"
idle; SNAP_SOURCE="D:/liner_scratch/snap_T19O_default_run1" $SR T19S_final_present T19S_final_present -- $SUITE "--junitxml=$EV/runs/T19S_final_present.junit.xml"
note QUEUE_FINAL_DONE
