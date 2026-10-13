#!/usr/bin/env bash
# After M3 (CBC, seeds 0-4) finishes: M4 = CBC 120 s on seeds 5-9 (B0, R, RFA), then
# M2 = HiGHS 300 s (opt-in, experimental) on seeds 0-4 (B0, R, RFA, RTF).  Same snapshot as M3.
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
cd "$PROJ"
EV=reports/tasks_19_20_21/evidence
until grep -q "BATCH_DONE M3" $EV/runs/M3.driver.txt 2>/dev/null; do sleep 10; done
bash $EV/tools/run_jobs.sh "D:/liner_scratch/snap_T19_ctl3" M4 4 "5 6 7 8 9" "B0 R RFA" cbc 120 > $EV/runs/M4.driver.txt 2>&1
bash $EV/tools/run_jobs.sh "D:/liner_scratch/snap_T19_ctl3" M2 4 "0 1 2 3 4" "B0 R RFA RTF" highs 300 > $EV/runs/M2.driver.txt 2>&1
echo QUEUE_DONE
