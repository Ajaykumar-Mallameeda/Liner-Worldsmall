#!/usr/bin/env bash
# Third queue: after queue2 (M5, M2, frontier) - M6 on the tree with the profit-floor repair (ctl5):
#   CBC 120 s, seeds 0-9: F1R F1AR F1ATR F1TR
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
cd "$PROJ"
EV=reports/tasks_19_20_21/evidence
until grep -q QUEUE2_DONE $EV/runs/queue2.driver.txt 2>/dev/null; do sleep 15; done
bash $EV/tools/run_jobs3.sh "D:/liner_scratch/snap_T19_ctl5" M6 4 "0 1 2 3 4 5 6 7 8 9" "F1R F1AR F1ATR F1TR" cbc 120 > $EV/runs/M6.driver.txt 2>&1
echo QUEUE3_DONE
