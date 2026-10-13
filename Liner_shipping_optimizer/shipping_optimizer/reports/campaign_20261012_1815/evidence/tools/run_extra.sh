#!/usr/bin/env bash
# Chained AFTER run_remaining.sh (waits for its ALL_DONE): hold-out arm that isolates the class variants' increment
# over C1 + LS (the hold-out of Phase 5 had no C1 + LS arm).  Seeds 10-19, final tree, four arms concurrent.
PROJ="C:/Users/WINDOWS/Liner-Worldsmall/Liner_shipping_optimizer/shipping_optimizer"
CAMP="$PROJ/reports/campaign_20261012_1815/evidence"
until grep -q ALL_DONE "$CAMP/runs/P5_steps2_8.driver.txt" 2>/dev/null; do sleep 30; done
FIN="LINER_MILP_VUB=1,LINER_LOCAL_SEARCH=1,LINER_CLASS_VARIANTS=0.10"
echo "=== EXTRA $(date +%H:%M:%S)"
bash "$CAMP/tools/run_arms.sh" D:/liner_scratch/snap_T9_final "10 11 12 13 14 15 16 17 18 19" 120 \
  "C9b_base=-;C9b_ls=LINER_LOCAL_SEARCH=1;C9b_c1ls=LINER_MILP_VUB=1,LINER_LOCAL_SEARCH=1;C9b_fin=${FIN}" > "$CAMP/runs/C9b.driver.txt" 2>&1
echo "EXTRA_DONE $(date +%H:%M:%S)"
