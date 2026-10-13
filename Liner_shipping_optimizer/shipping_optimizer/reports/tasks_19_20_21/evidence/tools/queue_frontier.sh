#!/usr/bin/env bash
# Coverage-profit frontier (Task 19 objective hierarchy) - EXPERIMENTAL strategies on the
# candidate path configuration "R" (flow re-optimisation), production CBC 120 s, seeds 0-2:
#   FRprod        profit-first (production)
#   FRcov25/30/35 epsilon constraint: profit-max s.t. served TEU >= 25/30/35 % of demand
#   FRlex0/5/10   lexicographic: profit-max, then max served TEU s.t. profit >= (1-eps) x stage 1
# Waits for the earlier queue to finish.
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
cd "$PROJ"
EV=reports/tasks_19_20_21/evidence
SNAP="D:/liner_scratch/snap_T19_ctl4"
until grep -q QUEUE_DONE $EV/runs/queue_m4_m2.driver.txt 2>/dev/null; do sleep 10; done
for spec in "FRprod:prod" "FRcov25:cov:0.25" "FRcov30:cov:0.30" "FRcov35:cov:0.35" \
            "FRlex0:lex:0.0:0.5" "FRlex5:lex:0.05:0.5" "FRlex10:lex:0.10:0.5"; do
  TAG="${spec%%:*}"; STRAT="${spec#*:}"
  bash $EV/tools/run_jobs.sh "$SNAP" "$TAG" 3 "0 1 2" "R" cbc 120 "$STRAT" > $EV/runs/$TAG.driver.txt 2>&1
done
echo FRONTIER_DONE
