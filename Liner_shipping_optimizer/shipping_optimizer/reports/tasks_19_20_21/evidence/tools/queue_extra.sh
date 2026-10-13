#!/usr/bin/env bash
# After the final queue:
#   M11  controlled, HiGHS 600 s (long-budget REFERENCE, experimental, not the default), seeds 0-4: RB vs D
#   O4   orchestrator x2 with the opt-in coverage floor LINER_GLOBAL_MIN_COVERAGE=0.25 (everything else default)
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
cd "$PROJ"
EV=reports/tasks_19_20_21/evidence
SNAPF="D:/liner_scratch/snap_T19_final"
SR="python -I $EV/tools/snaprun.py"
idle() { powershell -NoProfile -ExecutionPolicy Bypass -File "$EV/tools/wait_idle.ps1" -MaxMinutes 45; }
note() { echo "[$(date +%H:%M:%S)] $*"; }
clean_env() { unset LINER_FLOW_REOPT LINER_PROFIT_FLOOR_REPAIR LINER_MAX_TRANSFERS LINER_PATH_SELECTION \
  LINER_PATH_BUDGET LINER_CLASS_TIME_FEASIBLE LINER_ROUTE_OPERATORS LINER_ELITISM NETWORK_MILP_BACKEND \
  GLOBAL_STAGE_TIME_LIMIT_SEC LINER_GLOBAL_MIN_COVERAGE LINER_REGIONAL_FILTER LINER_DEMAND_LOOP_BUDGET LINER_CLASS_SCREEN; }
ORCH="tests/test_orchestrator.py -v -s --tb=short -p no:cacheprovider"
until grep -q QUEUE_FINAL_DONE $EV/runs/final_queue.driver.txt 2>/dev/null; do sleep 20; done
note M11
idle; bash $EV/tools/run_jobs4.sh "$SNAPF" M11 4 "0 1 2 3 4" "RB D" highs 600 > $EV/runs/M11.driver.txt 2>&1
note O4
for i in 1 2; do
  idle; clean_env; export LINER_GLOBAL_MIN_COVERAGE=0.25
  SNAP_SOURCE="$SNAPF" $SR T19O_cov25_run$i T19O_cov25_run$i -- $ORCH
  clean_env
done
note QUEUE_EXTRA_DONE
