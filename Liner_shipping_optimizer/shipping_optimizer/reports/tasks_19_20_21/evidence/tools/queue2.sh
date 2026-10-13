#!/usr/bin/env bash
# Second queue (replaces queue_m4_m2.sh / queue_frontier.sh): after M4 (CBC 120 s, seeds 5-9 with
# the ctl3 tree):
#   M5   ctl4 tree (final no-regression re-routing), CBC 120 s, seeds 0-9:
#        B0 F1 F2 F1A F1T F1AT         (F1 = re-routing + <=2 transfers; F2 = + multi-hop for all ODs;
#                                        A = adaptive path budget, T = time-feasible class)
#   M2   ctl3 tree, HiGHS 300 s (opt-in, experimental), seeds 0-4: B0 R RFA RTF
#   FR*  coverage-profit frontier on "R" (ctl4), CBC 120 s, seeds 0-2
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
cd "$PROJ"
EV=reports/tasks_19_20_21/evidence
until grep -q "BATCH_DONE M4" $EV/runs/M4.driver.txt 2>/dev/null; do sleep 10; done
bash $EV/tools/run_jobs2.sh "D:/liner_scratch/snap_T19_ctl4" M5 4 "0 1 2 3 4 5 6 7 8 9" "B0 F1 F2 F1A F1T F1AT" cbc 120 > $EV/runs/M5.driver.txt 2>&1
bash $EV/tools/run_jobs2.sh "D:/liner_scratch/snap_T19_ctl3" M2 4 "0 1 2 3 4" "B0 R RFA RTF" highs 300 > $EV/runs/M2.driver.txt 2>&1
for spec in "FRprod:prod" "FRcov25:cov:0.25" "FRcov30:cov:0.30" "FRcov35:cov:0.35" \
            "FRlex0:lex:0.0:0.5" "FRlex5:lex:0.05:0.5" "FRlex10:lex:0.10:0.5"; do
  TAG="${spec%%:*}"; STRAT="${spec#*:}"
  bash $EV/tools/run_jobs2.sh "D:/liner_scratch/snap_T19_ctl4" "$TAG" 3 "0 1 2" "R" cbc 120 "$STRAT" > $EV/runs/$TAG.driver.txt 2>&1
done
echo QUEUE2_DONE
